# Warm-TDM RTL Regression Progress

## Summary
- Current phase: Phase-1 scaffold, salvaged onto `fp-pid`
- Current focus modules: `AdcDsp` (fixed-point) and `AdcDspFp` (floating-point)
- Base branch: `rtl-cocotb-regression` (off `origin/fp-pid`)
- Last updated: 2026-08-14

## Current Frontier
- Ported the interface-independent infra as-is from `pid-fixes`: root `Makefile`,
  `ruckus.tcl`, `pytest.ini`, `pip_requirements_regression.txt`, `scripts/`
  (bootstrap + GHDL import + proc override), `tests/common/` (regression_utils +
  unisim stub), and all package `__init__.py` files.
- Bootstrapped `./.venv` (cocotb 2.0.1, cocotb-test, cocotbext-axi) and validated
  `make rtl_import` -> `build/SRC_VHDL/{surf,warm_tdm}` under GHDL 1.0.0.
- Re-applied the `SIMULATION_G` / `ite(..., "inferred", "xpm")` FIFO hook onto
  BOTH `AdcDsp.vhd` and `AdcDspFp.vhd` current FIFO instantiations. Hardware
  default is unchanged (`xpm`).
- Re-authored `AdcDspCocotbWrapper.vhd` and added `AdcDspFpCocotbWrapper.vhd`
  against the NEW accumulator-split interface (`accumIn : AdcAccumResultType`
  + `accumValid` + `timingRxData : LocalTimingType`; flattened `ACCUM_*` ports).
- Re-authored `tests/warm_tdm/adc_dsp/test_AdcDsp.py` to drive the accum
  interface (present an `AdcAccumResultType`, pulse `accumValid`) instead of raw
  ADC samples. Added `tests/warm_tdm/adc_dsp/test_AdcDspFp.py` covering the FP
  variant analogously.

## Status
- `test_AdcDsp` (GHDL): **GREEN, 5/5 checks pass.**
  - `I_Coef = 0` does not accumulate
  - `I_Coef` write clears integrator state
  - `startRun` clears integrator state
  - `clearPidState` register clears integrator state
  - positive-rail anti-windup holds the integrator at 0
- `test_AdcDspFp` (VCS): **authored + structurally complete, SKIPPED under
  GHDL.** GHDL analyzes/imports `AdcDspFp` + its wrapper cleanly (only
  `-Wbinding` warnings for the unbound `FpMac`/`Int2Fp`/`Fp2Int` IP), so the
  interface is proven correct; it cannot elaborate the FP IP. Gated on
  `WARM_TDM_SIM=vcs`. Checks authored: I=0 no-accumulate, I!=0 accumulates,
  startRun clear, clearPidState clear, basic P-term response.

## Fixes made to RTL
- `AdcDsp.vhd`: fixed a latent width-mismatch in the fixed-point accumulator
  refactor -- `to_ufixed(slv(accumIn.numSamples), ...)` (8-bit slv into 32-bit
  ufixed) tripped `fixed_pkg`'s bounds check. Switched to the numeric
  `to_ufixed(accumIn.numSamples, ...)` overload (resizes), matching `AdcDspFp`.
- `AdcDsp.vhd` + `AdcDspFp.vhd`: added `SIMULATION_G` and used
  `STREAM_FIFO_SYNTH_MODE_C` for the three stream FIFO `SYNTH_MODE_G` values in
  each.
- `tests/common/regression_utils.py`: added a `simulator` argument +
  `WARM_TDM_SIM` env override so a bench can select VCS/XSIM instead of GHDL.

## Known Gaps
- FP bench not yet executed green: needs Vivado 2025.2 compiled FP-IP sim libs
  wired into a VCS run (recipe documented in the handoff). No compiled sim libs
  were found pre-built in the sandbox.
- No validated full timing loopback bench yet.
- Explicit SURF file allowlist per bench rather than a dependency-closure solver.

## Notes To Preserve
- Keep the direct `LocalTimingType` + `accumIn` injection style so PID failures
  stay attributable to the DSP.
- Fixed-point coefficient encoding: `sfixed(0 downto -23)`, near-unity positive
  = `(1<<23)-1`. FP coefficient: IEEE-754, unity = `0x3F800000`.
- Use `./.venv/bin/python` for local commands. The default imported HDL path is
  `build/SRC_VHDL/` from the repo-root GHDL import surface.
