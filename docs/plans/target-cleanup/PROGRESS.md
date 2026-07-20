# Target Cleanup — Progress

Plan: [PLAN.md](PLAN.md) · Spec: [SPEC.md](SPEC.md)

## Status: not started

| Task | Description | Status |
|---|---|---|
| 1 | Move shared board code (tops, TB, pinouts) into `common/warm_tdm/` | ☐ |
| 2 | Rewrite + rename the five Column targets (thin, common-sourced) | ☐ |
| 3 | Rewrite + rename the Row targets (thin, common-sourced) | ☐ |
| 4 | Archive legacy `*Module*` targets to `targets/legacy/` | ☐ |
| 5 | Update aggregate `firmware/targets/Makefile` | ☐ |
| 6 | Update `firmware/releases.yaml` | ☐ |
| 7 | Update AGENTS.md xdc-convention note | ☐ |
| 8 | Full verification (linter, config checks) — plus a Vivado build (user) | ☐ |

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
