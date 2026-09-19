# Software and RTL regressions

Run commands from the repository root. Test results describe the exact source,
submodule and configuration used; a unit-model pass is not vendor-IP,
full-system, synthesis or physical acceptance.

## Environment and collection

Install Python, make and GHDL, initialize the repository submodules, then use:

```bash
bash scripts/setup_regression_env.sh
make rtl_import
.venv/bin/python -m pytest software/tests -q
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp -n 4 -q
```

The bootstrap creates `.venv`, installs the repository/regression dependencies,
and links an existing `~/ruckus` or clones ruckus at the repository root.
The GHDL import populates `build/SRC_VHDL/{surf,warm_tdm}`. This import tree is
distinct from Vivado's `firmware/build/<Target>` outputs.
`WARM_TDM_IMPORT_ROOT` can select another imported source tree.

`pytest.ini` defaults to `tests`, so name `software/tests` explicitly when
running the software suite. Use pytest collection for pytest modules;
`unittest discover` does not collect their module-level test functions.
Rogue/MemEmulate scripts named `rogue_*_smoke.py` are explicit runtime checks,
not ordinary pytest collection. See the [operations guide](../docs/operations-api.md#local-regression-checks)
for their environment and commands. Do not launch hardware-connected scripts
as part of a generic unit-test run.

## Deterministic RTL checks

The shared runner is [regression_utils.py](common/regression_utils.py).
Benches use explicit SURF source allowlists and thin VHDL wrappers. DSP unit
benches inject decoded timing/accumulation records; whole-path benches include
the real accumulator and feed emitted DAC writes back to subsequent visits.
This isolates arithmetic/state failures from timing-PHY or wafer-model behavior.

| Coverage | Maintained entry point |
|---|---|
| Integer P/I/D and reset behavior | `warm_tdm/adc_dsp/test_AdcDsp.py` |
| Fractional state, ties, seed and RAM/debug behavior | `warm_tdm/adc_dsp/test_AdcDsp_fractional.py` |
| Masking and integral-only clears | `warm_tdm/adc_dsp/test_AdcDsp_lifecycle.py` |
| Flux direction, signed transport and anti-windup | `warm_tdm/adc_dsp/test_AdcDsp_flux.py` |
| Multi-wrap boundaries, configuration and scheduling | `warm_tdm/adc_dsp/test_AdcDsp_multi_flux.py` |
| Queued DAC writes under AXI stalls | `warm_tdm/adc_dsp/test_AdcDsp_delivery.py` |
| Frozen pre-split stimulus and intentional differences | `warm_tdm/adc_dsp/test_AdcDsp_bitexact_compare.py` |
| FP controller with explicit binary32 models | `warm_tdm/adc_dsp/test_AdcDspFp.py` |
| Independent arithmetic oracle | `warm_tdm/adc_dsp/test_fp_models.py` |
| Native acceptance bench with local test models | `warm_tdm/adc_dsp/test_AdcDspFp_native.py` |

`SIMULATION_G` selects inferred FIFO/RAM paths where needed by GHDL; it does
not model Xilinx arithmetic cores. The FP pytest explicitly requires GHDL and
uses test-only finite binary32 models. Their oracle uses independent exact
arithmetic. Do not select VCS through `WARM_TDM_SIM` to turn this into a
generated-IP test: use the native target below.

Integer coefficients use signed Q1.23: `1 << 23` is -1, while `(1 << 23)-1`
is the largest positive coefficient. FP coefficients are binary32.
Match coefficient encoding, DAC polarity and row width to each bench.

The [frozen reference](warm_tdm/adc_dsp/golden_refs/presplit_rtl/README.md)
is historical evidence. Do not regenerate it to make changed arithmetic pass.
Retained-feedback comparisons use a shared historical prefix and independent
expectations for intentionally different later visits. Keep exact state,
stream-format and exactly-once DAC-delivery assertions alongside that comparison.

## Generated IP and full-system simulation

Run [AdcDspFpTb](../firmware/simulations/AdcDspFpTb/README.md) with generated
Xilinx cores for converter/FMA boundaries and scheduling. Its GHDL model run
checks the bench, not vendor equivalence. Record source/XCI/submodule revisions
and actual simulator/tool versions; include both signs around half-integers,
wrap boundaries, first-visit seeding and clipping paths.

For the full system use [GroupTb build/server instructions](../firmware/simulations/GroupTb/README_cosim.md)
and [client/harness instructions](../software/scripts/hwtest/README_cosim.md).
The documented tool split is Vivado 2025.1 + VCS X-2025.06 for GroupTb simulation
and Vivado 2024.1 for bitfiles. The old `_meta` VCS/cocotb recipe is superseded.

Record integer/FP selection, source/submodule revisions, fixture profile,
variation seed, response shaping, TES scaling, logical/physical row map,
sample timing, gains and applied initial DAC state. Measure the local plant
slope before interpreting gain sign or comparing controllers. A low error at
P=0 is not disturbance rejection. Compare matched visit counts, step/reversal
stimuli and loss counters; different model operating points do not establish
an intrinsic fixed/FP performance difference.

Exercise direct and VirtualClient trees, save/restore, enabled columns, masks,
start/stop/reseed and readout. The active [SQ1 investigation](../docs/plans/pid-cosim-verification/SQ1_RETUNE.md)
and [TES-scaling handoff](../docs/plans/tes-scaling/PROGRESS.md) explain unresolved
fixture/capture questions. Historical tuning values are not universal presets.

## Builds, physical acceptance and evidence

Build the affected integer/FP target matrix with **Vivado 2024.1**, including
supported row depths, PID-debug/memory options and release packaging. Record
timing, utilization, image identity/checksum and software/register compatibility.
Modeled cycle measurements do not bound XPM, AXI or physical DAC latency.

[#90](https://github.com/slaclab/warm-tdm/issues/90) owns framework/CI work;
[#70](https://github.com/slaclab/warm-tdm/issues/70) owns controller/system/build
acceptance; [#82](https://github.com/slaclab/warm-tdm/issues/82) owns frame/file
acceptance. Store revision-specific results there, including failed or skipped
checks and coverage limits. Physical lock/noise/bandwidth and board coverage
remain separate from simulation. Follow the [workflow](../docs/WORKFLOW.md).
