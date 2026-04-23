# Warm-TDM RTL Regression Handoff

## Objective
- Build a Python-first cocotb regression flow for `warm-tdm`.
- Keep executable test logic in Python and VHDL limited to wrappers and required sim models.

## Current Snapshot
- Checked-in planning scaffold now exists under `docs/_meta/`.
- The regression environment is bootstrapped with `scripts/setup_regression_env.sh`.
- Repo-local VS Code regression tasks live under `.vscode/`.
- Shared Python utilities live in `tests/common/regression_utils.py`.
- The first cocotb-facing wrapper and bench target `AdcDsp`.
- The first `AdcDsp` bench intentionally uses direct `LocalTimingType` injection.
- The direct-drive `AdcDsp` bench now executes under GHDL with a pruned import set and local `unisim` stub.
- The bench currently reports five passing PID checks, including anti-windup and software-triggered PID-state clearing.
- A follow-on bench should integrate the real timing subsystem without turning PID debugging into a PHY simulation problem.

## Current Constraints
- Imported HDL sources are not tracked in the repo and must be generated locally before cocotb runs.
- The default import path assumes `make rtl_import`.
- `make rtl_import` is now validated through a repo-local ruckus Tcl override that replaces sandbox-hostile shell calls with Tcl file operations.
- `AdcDsp` uses a simulation-only FIFO selection through `SIMULATION_G`; hardware builds still default to the original XPM-backed path.
- The current helper logic for `AdcDsp` uses an explicit SURF allowlist rather than a general dependency solver.
- `AdcDsp` PID coefficients use `sfixed(0 downto -23)`, so `1 << 23` encodes `-1.0`, not `+1.0`; benches that want a near-unity positive coefficient should use `(1 << 23) - 1`.
- Full `TimingTx` / `TimingRx` / serializer / deserializer loopback is not yet the default path for `AdcDsp` regression.

## Immediate Next Steps
1. Run `bash ./scripts/setup_regression_env.sh`.
2. Run `make rtl_import`.
3. Run `./.venv/bin/python -m pytest -n 0 -q tests/warm_tdm/adc_dsp/test_AdcDsp.py`.
4. If the direct-drive bench remains the authoritative PID source, add the narrower timing-integrated smoke bench next.
5. If coefficient-programming coverage expands, keep the signed fixed-point encoding rule explicit in the test helpers.

## Timing Integration Guidance
- Keep the direct-drive `AdcDsp` bench as the authoritative PID regression.
- Use a second bench for realism:
  - preferred first step: integrate the logical timing subsystem behavior,
  - later step: full serialized timing loopback if the simulator support is robust enough.

## Read Order
1. `docs/_meta/rtl_regression_handoff.md`
2. `docs/_meta/rtl_regression_progress.md`
3. `docs/_meta/rtl_regression_plan.md`
4. `docs/_meta/rtl_regression_inventory.yaml`
