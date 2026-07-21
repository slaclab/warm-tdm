# warm_tdm_jupyter refactor — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: planning — awaiting approval to execute

See also: [MERGE-cleanup.md](MERGE-cleanup.md) — analysis + plan for adopting the
`cleanup` branch's software refactor (do NOT straight-merge; cherry-pick the
software side, gated on hardware validation).

Review of PR #61 complete. Branch `wtj-refactor` created off `wtj`. Plan set
scaffolded. No source code changed yet.

| Task | Description | Status | Commit |
|---|---|---|---|
| 0 | Review PR #61 + scaffold plan/branch | ✅ | — |
| 1 | Correctness fixes (README, scipy, take_raw timeout, dead import, num_generators) | ⬜ | — |
| 2 | Proof-of-concept Group migration (G2 all_off, G1 setup_mux) | ⬜ | — |
| 3 | Package rename / rehome away from "jupyter" | ⬜ | — |
| 4 | Remaining Group migrations (G3–G6) | ⬜ | — |
| 5 | Analysis + convenience structural cleanup | ⬜ | — |
| 6 | Verification | ⬜ | — |

**Blocked on user decisions:** package name/home, migration cadence, constants
home — see PLAN.md "Open decisions".

## Log

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
