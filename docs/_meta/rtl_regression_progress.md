# Warm-TDM RTL Regression Progress

## Summary
- Current phase: Phase-1 scaffold
- Current focus module: `AdcDsp`
- Last updated: 2026-04-23

## Current Frontier
- Added the initial `_meta` planning scaffold.
- Added the regression bootstrap script and repo-local `./.venv` convention.
- Added repo-local VS Code regression tasks patterned after `~/surf/.vscode/tasks.json`.
- Added `tests/common/regression_utils.py`.
- Added the first cocotb-facing `AdcDsp` wrapper and direct-drive PID bench.
- Validated the repo-root `make rtl_import` flow under the local macOS sandbox by routing SURF/ruckus Tcl proc loads through a repo-local override.
- The direct-drive bench now runs under `./.venv/bin/python -m pytest -n 0 -q tests/warm_tdm/adc_dsp/test_AdcDsp.py`.
- The `AdcDsp` regression uses a pruned SURF/warm-tdm import set plus a local `unisim.vcomponents` stub instead of importing the entire generated tree.
- `AdcDsp` now has a simulation-only FIFO path guarded by `SIMULATION_G`, preserving the hardware default while avoiding SURF XPM stubs in the cocotb wrapper flow.
- Five direct-drive PID checks now pass: `I_Coef = 0` does not accumulate, `I_Coef` writes clear state, `startRun` clears state, `clearPidState` clears state, and positive-rail anti-windup blocks integration.
- The earlier anti-windup failure was a bench encoding bug, not an RTL clamp defect: `AdcDsp` coefficients use `sfixed(0 downto -23)`, so `1 << 23` encoded `-1.0`, not `+1.0`.
- Timing realism remains the next follow-on item, not a blocker for the first PID regression.

## Known Gaps
- No validated full timing loopback bench yet.
- No committed graph- or queue-driven rollout artifacts yet.
- The shared helper currently uses an explicit SURF allowlist for `AdcDsp`; later benches may want a more general dependency-closure mechanism.

## Notes To Preserve
- `AdcDsp` should keep one deterministic bench with direct `LocalTimingType` injection.
- Real timing integration should be added as a second bench so PID failures stay attributable.
- Use `./.venv/bin/python` for local commands to match the repo-local virtualenv workflow.
- The default imported HDL path is `build/SRC_VHDL/` from the repo-root GHDL import surface.
