# Warm-TDM RTL Regression Progress

## Summary
- Current phase: Phase-1 scaffold
- Current focus module: `AdcDsp`
- Last updated: 2026-04-22

## Current Frontier
- Added the initial `_meta` planning scaffold.
- Added the regression bootstrap script and repo-local `./.venv` convention.
- Added `tests/common/regression_utils.py`.
- Added the first cocotb-facing `AdcDsp` wrapper and direct-drive PID bench.
- The direct-drive bench is the current source of truth for PID behavior.
- Timing realism remains the next follow-on item, not a blocker for the first PID regression.

## Known Gaps
- No validated full timing loopback bench yet.
- No committed graph- or queue-driven rollout artifacts yet.
- No confirmed imported HDL cache in the working tree yet; local users must generate it before running cocotb.

## Notes To Preserve
- `AdcDsp` should keep one deterministic bench with direct `LocalTimingType` injection.
- Real timing integration should be added as a second bench so PID failures stay attributable.
- Use `./.venv/bin/python` for local commands to match the repo-local virtualenv workflow.
- The default imported HDL path assumes `firmware/targets/RowFpgaBoard0/build/SRC_VHDL/`.
