# Warm-TDM RTL Regression Handoff

## Objective
- Build a Python-first cocotb regression flow for `warm-tdm`.
- Keep executable test logic in Python and VHDL limited to wrappers and required sim models.

## Current Snapshot
- This framework was salvaged from the stale `pid-fixes` branch and rebased onto
  the `fp-pid` firmware (branch `rtl-cocotb-regression`, off `origin/fp-pid`).
- The regression environment is bootstrapped with `scripts/setup_regression_env.sh`
  (creates a repo-local `./.venv`; does NOT use conda).
- Shared Python utilities live in `tests/common/regression_utils.py`.
- Two benches target the ADC DSP: the fixed-point `AdcDsp` bench
  (`tests/warm_tdm/adc_dsp/test_AdcDsp.py`) and the floating-point `AdcDspFp`
  bench (`tests/warm_tdm/adc_dsp/test_AdcDspFp.py`).
- Both benches drive `LocalTimingType` directly (deterministic PID validation,
  no timing PHY simulation).

## Interface drift handled during the salvage
- `pid-fixes` was written against the OLD `AdcDsp`, which consumed a raw ADC
  AXI-stream (`ADC_AXIS_*`) and drove PID from per-sample data.
- `fp-pid` split accumulation out into a separate `AdcAccumulator` entity.
  `AdcDsp` (and the new `AdcDspFp`) now consume a decoded
  `accumIn : AdcAccumResultType` qualified by `accumValid`, plus a decoded
  `timingRxData : LocalTimingType`. See `WarmTdmPkg.AdcAccumResultType`
  (accumError / numSamples / rowIndex / sq1FbDac / seqStart / daqReadoutStart)
  and `DataPath.vhd` (GEN_FIXED_PID / GEN_FLOAT_PID) for the reference wiring.
- The re-authored cocotb wrappers therefore flatten `AdcAccumResultType` into
  scalar `ACCUM_*` ports and pulse `ACCUM_VALID`, instead of feeding ADC
  samples. The benches present one accumulation result per PID iteration.

## SIMULATION_G FIFO hook (applied to BOTH DSP entities)
- `pid-fixes` added a `SIMULATION_G : boolean := false` generic plus
  `constant STREAM_FIFO_SYNTH_MODE_C : string := ite(SIMULATION_G, "inferred", "xpm");`
  to `AdcDsp`, then used it for the `SYNTH_MODE_G` of the AXI-stream FIFOs
  (hardcoded `"xpm"`, which GHDL cannot elaborate).
- On `fp-pid` this pattern was re-applied onto the CURRENT FIFO instantiations
  of BOTH `AdcDsp.vhd` AND `AdcDspFp.vhd` (each has three stream FIFOs: the
  PID_DEBUG AxiStreamFifoV2, the DATA AxiStreamFifoV2, and the SQ1FB `Fifo`).
  Hardware builds still default to `xpm`; simulation selects `inferred`.
- NOTE: `SIMULATION_G` only swaps the AXI-stream FIFOs. It does NOTHING for the
  Xilinx FP IP cores (`FpMac`, `Int2Fp`, `Fp2Int`) that `AdcDspFp` instantiates.

## Simulator per bench (important)
- `AdcDsp` (fixed-point): **GHDL**. No vendor IP; the `SIMULATION_G` inferred
  FIFOs are sufficient. This bench runs GREEN (5/5 checks) today.
- `AdcDspFp` (floating-point): **VCS** (or XSIM). `AdcDspFp` instantiates the
  Xilinx `FpMac`/`Int2Fp`/`Fp2Int` IEEE-754 IP cores as VHDL `component`s. GHDL
  can ANALYZE and IMPORT the entity + wrapper cleanly (only `-Wbinding`
  warnings: the FP IP instances are unbound), but it CANNOT ELABORATE/simulate
  the IP. VCS (with the Vivado compiled sim libraries) can. The `test_AdcDspFp`
  pytest is authored and structurally complete but SKIPPED unless
  `WARM_TDM_SIM=vcs` (or `xsim`) is exported.

## Coefficient encodings
- Fixed-point `AdcDsp` PID coefficients use `sfixed(0 downto -23)`, so `1 << 23`
  encodes `-1.0`, not `+1.0`; benches that want a near-unity positive
  coefficient use `(1 << 23) - 1`.
- Floating-point `AdcDspFp` coefficients are IEEE-754 float32, so a near-unity
  coefficient is simply `1.0 == 0x3F800000`.

## Latent RTL bug found + fixed during the salvage
- `fp-pid`'s refactored fixed-point `AdcDsp` (never previously simulated)
  reinterpreted the 8-bit `accumIn.numSamples` as a 32-bit `ufixed` via
  `to_ufixed(slv(accumIn.numSamples), v.accumSamples)`. The `to_ufixed(slv,
  size_res)` overload requires matching vector widths, so GHDL's `fixed_pkg`
  bounds check aborted the run ("Vector lengths do not match. Input length is 8
  and output will be 32 wide"). Fixed to the numeric `to_ufixed(unsigned,
  size_res)` overload (which resizes), matching how `AdcDspFp` already handled
  it. See `AdcDsp.vhd` IDLE_S state.

## Running
1. `bash ./scripts/setup_regression_env.sh`   (builds `./.venv`, clones ruckus)
2. `make rtl_import`                            (populates `build/SRC_VHDL/`)
3. `./.venv/bin/python -m pytest -n 0 -q tests/warm_tdm/adc_dsp/`
   - `test_AdcDsp` runs green under GHDL; `test_AdcDspFp` skips.

### Running the FP bench under VCS (recipe)
1. `source /sdf/group/faders/tools/synopsys/vcs/X-2025.06/settings.sh`
   (sets VCS_HOME + PATH; do not hand-roll VCS_ARCH_OVERRIDE).
2. `source /sdf/group/faders/tools/xilinx/2025.2/Vivado/2025.2/settings64.sh`
   (Vivado 2025.2 provides the compiled FP-IP simulation libraries; note this
   is distinct from the 2024.1 used for synthesis).
3. Compile the Xilinx sim libs for VCS (`compile_simlib -simulator vcs ...`) if
   not already available, and put the resulting `floating_point_v7_*` /
   `xil_defaultlib` libraries on the VCS search path so `FpMac`/`Int2Fp`/`Fp2Int`
   bind. surf ships the VCS/XSIM cosim shims under
   `firmware/submodules/surf/axi/simlink/sim/` (+ C shims in `.../src/`).
4. `WARM_TDM_SIM=vcs ./.venv/bin/python -m pytest -n 0 -q tests/warm_tdm/adc_dsp/test_AdcDspFp.py`
   (`regression_utils.run_warm_tdm_vhdl_test` honors `WARM_TDM_SIM`.)

## Known caveats
- The env installs the latest cocotb (2.0.x). The benches run under it; a few
  cocotbext-axi DeprecationWarnings are emitted but are non-fatal.
- The helper uses an explicit SURF file allowlist per bench rather than a
  general dependency-closure solver.
- Full `TimingTx`/`TimingRx` serialized loopback is not the default path for the
  ADC DSP regression; direct `LocalTimingType` injection keeps PID failures
  attributable to the DSP.

## Read Order
1. `docs/_meta/rtl_regression_handoff.md`
2. `docs/_meta/rtl_regression_progress.md`
3. `docs/_meta/rtl_regression_plan.md`
4. `docs/_meta/rtl_regression_inventory.yaml`
