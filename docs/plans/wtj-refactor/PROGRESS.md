# warm_tdm_jupyter refactor — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: Tasks 1–4 done + `pre-release` merged into `wtj-refactor`. Task 5 (Group graduations) deprioritized; analog bench deferred to integrated branch.

See also: [MERGE-cleanup.md](MERGE-cleanup.md) — analysis + plan for adopting the
`cleanup` branch's software refactor (do NOT straight-merge; cherry-pick the
software side, gated on hardware validation).

Review of PR #61 complete. Branch `wtj-refactor` created off `wtj`. Plan set
scaffolded. No source code changed yet.

| Task | Description | Status | Commit |
|---|---|---|---|
| 0 | Review PR #61 + scaffold plan/branch | ✅ | — |
| 1 | Correctness fixes (README, scipy, take_raw timeout, dead import, num_generators) | ✅ | 0a8f16f, 5d097db, 78a1946, 2f079de, fd5d97a |
| 2 | Adopt `cleanup` software refactor (Group split, launcher, maxRows) — [MERGE-cleanup.md](MERGE-cleanup.md) | ✅ merged (cosim-validated; analog bench deferred) | 28bdcaf, da07664, 6f41239, acdcf59, 0491e7b |
| 3 | Rename/rehome → `warm_tdm_api.operations` | ✅ | 7b5946f, f5e22f6 |
| 4 | Analysis + `operations` structural cleanup (config-derived fs/sq1fb_to_pA + CurrentPerLsb tree var, shared ASD helpers, bounded registry) | ✅ | 2026-08-11 |
| 5 | Group graduations (G-items, as they mature — deprioritized) | ⬜ | — |
| 6 | Verification | ⬜ | — |

**Blocked on user decisions:** constants home (PLAN open decision 3) and the
bench board for the Task 2 HW gate. Package name resolved (`operations`); cadence
resolved (rehome-first, graduate-later).

## Log

- 2026-08-11: **Task 4 DONE — implemented + validated in `warm-tdm-r615`.**
  - **Firmware:** added `CurrentPerLsb` RO LinkVariable to `FastDacAmplifierSE`
    (`_Amplifiers.py`; inherited by `Diff` + every FastDacAmplifier), units
    `µA/LSB`, = `dacToOutCurrent(1)-dacToOutCurrent(0)`. Generic name (not SQ1) +
    µA convention per user direction. Flows into the config channel per amp.
  - **`streamreader.py`:** defensive channel-255 config read (`_desep_commas` +
    `pyrogue.yamlToData`, returns `{}` on failure) → `StreamData.config`.
  - **`operations/calibration.py`** (new): `derive_fs` (reads
    `TimingTx.DaqReadoutRate`), `derive_sq1fb_to_pA` (`CurrentPerLsb`×1e6,
    per-column) + `resolve_*` fallbacks; exported from `operations`.
  - **`analysis.py`:** extracted pure `compute_asd`/`channel_timeseries`;
    `plot_stream_data`/`analyze_pair` default fs/sq1fb_to_pA to `None` → derive
    from the file config (per-column sq1fb), explicit override honored, documented
    literal fallback (`DEFAULT_FS`/`DEFAULT_SQ1FB_TO_PA`) + note when absent.
  - **`data.py`:** bounded `StreamData._instances` → `deque(maxlen=128)`
    (`set_max_instances` to resize); `.index` now a stable monotonic id,
    `get_by_index` searches by it, new `get_by_position` keeps the
    `stream_data_id` `-1`=most-recent contract.
  - **Validated (warm-tdm-r615):** base import doesn't auto-load `operations`;
    emulate lifecycle + `CurrentPerLsb`>0 + `TesBiasWaveformProcess` present;
    derived `sq1fb_to_pA` (18566.0) matches live tree; config-less fallback works;
    full `plot_stream_data`/`analyze_pair` run; bounded-registry eviction/ids
    correct. Key provenance fact: streamed value IS the flux-unwrapped SQ1FB DAC
    code (verified through AdcDsp→Biquad Int2Fp unity-gain path), so the per-LSB
    slope is the right conversion; the 1224.23-vs-18566 gap is a front-end diff.
- 2026-08-11: **Task 4 constants — resolved open decision 3 + config-channel
  investigation.** Decided (user) to derive `fs`/`sq1fb_to_pA` from each data
  file's Rogue **config channel (255)** rather than a `constants.py` of literals.
  Verified in emulate mode that `GroupRoot.DataWriter` already dumps the full
  tree YAML to channel 255 (auto on Open/Close), carrying every
  `ColumnBoard[i].AnalogFrontEnd.Channel[c].SQ1FbAmp.{ShuntR,FbR,InputR,IOUTFS}`
  and `...WaveformCapture.Decimation` — enough to reproduce both constants
  offline (AFE-model slope for sq1fb_to_pA; fadc/decimation/row-mux for fs).
  Read-path gaps found: (1) `streamreader.py:36` calls `FileReader` without
  `configChan=255`, silently skipping config; (2) **two rogue version bugs block
  a clean native decode** —
    - rogue **6.6.2** (`warm-tdm-env`): `_FileReader` calls bare `yaml.load()`
      → `TypeError` under PyYAML 6 (no Loader). **Fixed upstream in rogue
      `v6.9.0`**, commit `582133155` (authored by us), switching to
      `pr.yamlToData()`.
    - rogue **6.12.0** (`warm-tdm-env2`/`3`): past that, but the real config dump
      contains a surf `AxiStreamMonAxiL.Bandwidth` value serialized as
      `!!float '3,545,197.211'` (comma thousands-separators) which PyYAML can't
      parse back → one bad leaf aborts the whole decode.
  Env rogue inventory: `warm-tdm-env`=6.6.2, `warm-tdm-env2`/`3`=6.12.0 (env3
  lacks scipy), `rogue-latest`=6.15.0 (lacks scipy/full deps). **Decision (user):
  build a fresh complete env from the canonical repo-root `conda.yml`** (rogue
  unpinned → pulls latest 6.15.0 from tidair-tag; the post-merge conda.yml now
  includes scipy+sympy), env name `warm-tdm-conda`, and validate our code there —
  rather than mutate a shared env or ship a workaround. Env build in progress.
  Full findings + design in PLAN.md Task 4.
- 2026-08-10: **Merged `origin/pre-release` into `wtj-refactor`** (merge commit
  `98abf67`, `--no-ff`) — issue #68 task 1. **Deviation from the roadmap plan:**
  the plan called for a *rebase* dropping the four duplicated Task-2 commits;
  since `pre-release` has moved well past PR #67 (now also #71/#75/#35 + the
  firmware `maxRows`/`rowAddrBits` threading and `NumRows`→`MaxRows` rename), a
  single merge was cleaner than replaying conflicts commit-by-commit. `wtj-refactor`
  is local-only (never pushed), so either was safe. Conflicts (8 files) all
  resolved **to the pre-release side**, since it is the further-evolved version
  of the same Task-2 work wtj had content-ported:
  - `_Group.py`, `_GroupConfig.py`, `_GroupRoot.py`, `_ArgParser.py`: took
    pre-release's `rowAddrBits`/`rowAddrDepth` split, the `maxRows`-via-GroupConfig
    threading (dropped wtj's standalone `maxRows` kwarg/`ret['maxRows']`), the
    `MaxRows`/`RowMap` renames, and the hidden `Activate/DeactivateRowIndex`.
    wtj's `TesBiasWaveformProcess` registration sat in a non-conflicted region and
    is preserved.
  - `_Tuning.py`: took pre-release (%-style logging + `NumRows`→`MaxRows`).
  - Scripts: adopted pre-release's `_setupLibPaths` + `_server.runServer`
    architecture (thin `warmTdmServer.py` headless / `warmTdmGui.py` GUI-default),
    superseding wtj's inline-in-`warmTdmServer.py` approach. **Kept both intents:**
    folded wtj's `WARM_TDM_PATH` env-var override (used by `install.sh`) into the
    shared `_setupLibPaths.py`.
  - `__init__.py` auto-merged cleanly (both `_TesBiasWaveform` and `_server`
    imports present); `operations/` package intact (28 exports).
  Verified in warm-tdm-env: `warm_tdm_api` + `warm_tdm_api.operations` import
  clean; `GroupConfig` `1<=maxRows<=2**rowAddrBits` guard works; scripts
  py_compile; full emulate-mode `GroupRoot` start/stop lifecycle (NumColumns=8,
  MaxRows=256, `TesBiasWaveformProcess` + renamed `RowMap` present). Next: Task 4.
- 2026-07-21: **Task 3 done** — renamed `warm_tdm_jupyter` → `warm_tdm_api.operations`
  (7b5946f) + docs (f5e22f6). git mv preserved history; `__init__` now explicit
  re-exports + `__all__` (28 names); dropped the redundant/broken import-time
  `addLibraryPath` in `streamreader.py`; no tracked importers needed updating.
  `operations` is NOT auto-imported by `warm_tdm_api` (keeps matplotlib/scipy off
  the server path) — explicit `import warm_tdm_api.operations`. Documented in
  AGENTS.md + SOFTWARE_GUIDE.md. Import-checked in warm-tdm-env.
- 2026-07-21: **Merged `wtj-cleanup-sw` → `wtj-refactor`** (merge 0491e7b,
  `--no-ff`) on the cosim result (user decision: merge now, bench later). Merge
  clean; post-merge import + emulate lifecycle re-verified on `wtj-refactor`
  (NumColumns=8, NumRows=256, TesBiasWaveformProcess present); firmware/ still
  untouched by Task 2. Task 2 complete. **Deferred, not skipped:** analog-domain
  bench validation (real tune on SQUIDs) now happens on the integrated branch.
- 2026-07-21: **Cosim validation passed.** Ran GroupTb in VCS + `warmTdmServer.py
  --sim` (TCP socket bridge, SRP port 10000+i*1000). User confirmed "everything
  seems to be working": config scalars (NumColumns=8, NumRows=256), raw SRP
  register access, the `GroupLinkVariable`/`GroupArrayLinkVariable`/`FastDacVariable`
  split (get/set roundtrips), and tuning-process startup all exercised against
  real RTL register maps (not emulate's MemEmulate). This validates the entire
  Task 2 register/software-integration layer. Not covered by cosim: analog-domain
  behavior (a real tune converging on SQUIDs) — that still wants the bench.
- 2026-07-21: Executed Task 2 code port on branch `wtj-cleanup-sw` (off
  `wtj-refactor`), by content per Option A (adapt firmware seam, no firmware
  track). Commits: 80aa394 (Group split → `_GroupVariables`/`_GroupConfig`,
  `_Mapping` removed, firmware seam adapted, maxRows=256, TesBiasWaveform
  re-applied), da07664 (`_Tuning` logging + tuning-process config-model renames
  + drop FllEnable widget), 6f41239 (unified `warmTdmServer.py`, remove
  `gui.py`/`warmTdmGui.py`), acdcf59 (remove stale `testGroup.py`). Held back:
  all `firmware/python` (0 files changed), `_AdcDspFp`, `PidDebugFileReaderFp.py`.
  Discovered mid-task that the cleanup software `_Group.py` is coupled to cleanup
  *firmware* `HardwareGroup` (threads `useFloatPid`/`maxRows` → `_AdcDspFp`);
  resolved via Option A — kept our `HardwareGroup(num_row_selects/num_chip_selects)`
  call, `maxRows` software-side only, `--floatPid` accepted-but-ignored w/ warning.
  **Validation (real warm-tdm-env, emulate mode, no hardware):** package imports
  clean; `arg_dict` binds to `GroupRoot`; full `GroupRoot` start/stop lifecycle
  succeeds; `NumColumns=8`/`NumRows=256`; `TesBiasWaveformProcess` node present;
  `--floatPid` warns and continues fixed-point. Remaining: **hardware gate**
  (real boards: server + tune/SaOffset + `--gui`), then merge `wtj-cleanup-sw`
  → `wtj-refactor`.
- 2026-07-21: Executed Task 1 (correctness fixes), one commit per fix on
  `wtj-refactor`: README install path (0a8f16f), scipy dep (5d097db), take_raw
  timeout (78a1946), dead pandas import (2f079de), TesBiasWaveform dynamic
  generator count (fd5d97a). All touched Python files py_compile-clean; no
  hardware needed for these. Next: Task 2 cleanup adoption (hardware-gated).
- 2026-07-21: Reviewed PR #61 (branch `wtj`). Findings: the package is
  mislabeled "jupyter" (only one incidental, unused-downstream Jupyter call);
  the central smell is the global-singleton `Client`; reusable hardware
  capabilities are trapped in the convenience layer instead of living on the
  rogue tree like `TesBiasWaveformProcess` does. User confirmed the
  single-system/global-`Client` limits are acceptable and asked to start a
  running list of capabilities that should move to `Group` methods (see PLAN.md
  "Capabilities to move to Group": G1–G8).
- 2026-07-21: Created `wtj-refactor` branch off `wtj` and scaffolded SPEC/PLAN/
  PROGRESS under `docs/plans/wtj-refactor/`. Awaiting decisions before executing.
- 2026-07-21: Scoped the cleanup software adoption. Resolved: `maxRows` pinned
  to 256 (derived from RTL — `2**ROW_ADDR_BITS_G`, default 8; `160Coord`
  overrides to 32). Deferred (not part of the software merge): the v1/retired
  register-driver deletions (firmware track). Adoption is by content (path-scoped
  diff), not commit cherry-pick, because the software refactor spans partial
  commits (e.g. f917982 mixes GroupConfig software changes with firmware-python
  deletions).
- 2026-07-21: Placed the cleanup adoption as **Task 2** (was unplaced — it lived
  only in MERGE-cleanup.md while the task list jumped to a Group-migration PoC).
  It's the structural foundation: it creates `_GroupVariables`/`_GroupConfig`,
  which the rename (Task 3) rehomes and the Group graduations (Task 5) target, so
  it must precede both. Dropped the old "PoC Group migration" task — the
  graduation reframing made it obsolete (nothing meets the move-now gate, and
  adopting cleanup's `_GroupVariables` split is what validates the architecture
  the PoC was meant to prove). Resequenced: 1 fixes → 2 cleanup (HW-gated) →
  3 rename → 4 analysis cleanup → 5 graduations → 6 verify.
- 2026-07-21: Resolved package name → **`warm_tdm_api.operations`** (subpackage,
  not sibling). It's the client-side operational layer, production-bound, not
  throwaway. Also captured the original author's key rationale: these functions
  were kept client-side deliberately for **runtime editability** (a `Group`
  method needs a server restart → drops tuning state → slow re-tune). Reframed
  the G-list as a **maturity-gated graduation list** with a client/server
  criterion: move now only if it needs server-side execution (loops/GUI/state,
  like the already-migrated `TesBiasWaveformProcess`); otherwise keep in
  `operations` and graduate as it stabilizes. Near-term: rehome everything into
  `operations`, graduate later. Noted the "make retuning MCE-fast" alternative as
  the deeper (out-of-scope) unblock.
- 2026-07-21: Reversed the launch-script deferral — the unified `warmTdmServer.py`
  consolidation (89c194f: GUI folded behind `--gui`, `gui.py`/`warmTdmGui.py`
  deleted, new `WarmTdmArgparse`/`arg_dict` surface) is now IN SCOPE. Corrected
  an earlier wrong note: that commit does NOT delete `testGroup.py`. Flagged that
  its `--floatPid`/`--maxRows` flags come in but must default to current
  (pre-FP) firmware values, and added a `--gui` GUI-launch check to the
  validation gate.
- 2026-07-21: Analyzed the `cleanup` branch for merge. Straight `git merge`
  rejected: 52 commits, merge-base predates `pre-release`, all conflicts are
  firmware/target-reorg (old target names vs our renames, submodule + AdcDsp +
  releases.yaml), and it would drag in untested firmware (AdcDspFp FP rewrite,
  accumulator split). The `software/` refactor itself auto-merges clean, but
  `GroupConfig.maxRows` couples to firmware `ROW_ADDR_BITS_G`, so it still needs
  hardware validation. Recommendation written to MERGE-cleanup.md: cherry-pick
  the software refactor (Group split → `_GroupVariables`/`_GroupConfig`, logging,
  ArgParser) on a gated branch, hold back firmware-python deletions and row-size
  reductions. This should precede the G1/G3 Group migrations since it changes
  where `GroupLinkVariable` lives.
- 2026-07-21: Merged `origin/pre-release` into `wtj-refactor` (merge `d9baabb`,
  no conflicts). Brought in the target-cleanup firmware reorg, root `AGENTS.md`,
  `firmware/FIRMWARE_GUIDE.md`, `software/SOFTWARE_GUIDE.md`, `docs/RELEASE.md`,
  and release automation. Reconciled the plan against these guides: added a
  Conventions & references section, adopted the documented `GroupLinkVariable`
  pattern for G1/G3, added doc-update steps to the rename task (both guides omit
  the new package), and pinned the PR target to `pre-release`.
