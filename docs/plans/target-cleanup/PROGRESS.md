# Target Cleanup — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: implemented — awaiting Vivado build

| Task | Description | Status | Commit |
|---|---|---|---|
| 1 | Move shared board code (tops, TB, pinouts) into `common/warm_tdm/` | ✅ | d328c51 |
| 2 | Rewrite + rename the five Column targets (thin, common-sourced) | ✅ | ca2546d |
| 3 | Rewrite + rename the Row targets (thin, common-sourced) | ✅ | 5571b42 |
| 4 | Archive legacy `*Module*` targets to `targets/legacy/` | ✅ | 3e00992 |
| 5 | Update aggregate `firmware/targets/Makefile` | ✅ | 0a7951c |
| 6 | Update `firmware/releases.yaml` | ✅ | e8b6590 |
| 7 | Update AGENTS.md xdc-convention note + fix stale .gitignore | ✅ | 5d4fcb0 |
| 8 | Full verification (linter 0 errors, config checks) | ✅ | — |
| — | Fix simulations regression found in final review | ✅ | 9f90cb0 |

**Remaining:** a clean Vivado 2024.1 build of the four release targets is the
definitive check that the shared-code move didn't break synthesis/constraints
(the static checks and linter can't prove that). This is the user's rebuild step.

## Log

- 2026-07-20: Spec and plan written. Awaiting execution decision.
- 2026-07-20: Revised scope — every active target carries an explicit `160`/`325`
  part token; AwaXe gets full `325AwaXeCoord10G`.
- 2026-07-20: Adopted the shared-code fix (Option B): board tops + testbench +
  pinouts move into `common/warm_tdm/`, and every target `ruckus.tcl` becomes a
  uniform thin file (explicit `set_property top` + own pinout by path, no `../`
  refs). This is the real fix for the fragile canonical-dir pattern and makes the
  renames mechanical. A Vivado 2024.1 build remains the definitive correctness
  check for the source move.
- 2026-07-20: Executed all 8 tasks via subagent-driven development (implementer
  + spec review + code-quality review per task). Linter reports 0 errors; the
  8 active targets are thin, `../`-free, and each loads exactly one pinout.
- 2026-07-20: Final holistic review caught a regression the per-task reviews
  missed — the plan only grepped `targets/`, but `firmware/simulations/{GroupTb,
  StackTb,RowTb}` reference target dirs by absolute path and broke on the
  rename/move. Fixed in 9f90cb0 (GroupTb now relies on common auto-load; StackTb/
  RowTb repointed to `targets/legacy/`). Note: GroupTb's Column TB lost its
  explicit `-fileType "VHDL 2008"` flag (common loads sim without it) — sim-only,
  no release impact, but verify if GroupTb sim is run.
