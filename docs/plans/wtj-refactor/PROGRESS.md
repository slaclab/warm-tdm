# warm_tdm_jupyter refactor — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: planning — awaiting approval to execute

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
