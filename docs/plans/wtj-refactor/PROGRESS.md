# warm_tdm_jupyter refactor — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: Tasks 1–3 done + `pre-release` merged into `wtj-refactor` (2026-08-10). Task 4 (analysis/operations cleanup) next. Analog bench deferred to integrated branch.

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
| 4 | Analysis + `operations` structural cleanup | ⬜ | — |
| 5 | Group graduations (G-items, as they mature — deprioritized) | ⬜ | — |
| 6 | Verification | ⬜ | — |

**Blocked on user decisions:** constants home (PLAN open decision 3) and the
bench board for the Task 2 HW gate. Package name resolved (`operations`); cadence
resolved (rehome-first, graduate-later).

## Log

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
