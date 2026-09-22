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

The [ring RX buffer characterization](warm_tdm/pgp_ring/test_rx_buffer.py) runs
directly from the checked-out SURF sources with GHDL:

```bash
.venv/bin/python -m pytest tests/warm_tdm/pgp_ring/test_rx_buffer.py -q -n 3
```

It checks one versus multiple queued 4 KiB read-sized replies, a blocked sink,
the simulation ready-handshake mismatch, and framing of fresh probes after
loss. Some cases deliberately expect overflow/loss: passing these tests records
the limitation, not full-ring stability. GTX, SRP request admission, router
arbitration and RSSI are outside this bench. See the
[ReadAll investigation](../docs/plans/register-timeout/README.md#width-10-bound-investigation).

The production ring control and recovery suite is:

```bash
.venv/bin/python -m pytest tests/warm_tdm/pgp_ring/test_ring_control.py -q -n 3
```

The runner builds isolated GHDL libraries from the checked-out sources. Cocotb
owns stimulus and scoreboards in `ring_control_cocotb.py`; `pgp_ring/tb/` contains
only topology, clock/link models and flattened production interfaces.

All five new ring fixtures use this split: collection/broadcast, router
admission, congestion, overflow recovery and native PGP status. Their behavioral
checks belong in cocotb, including packet construction, scoreboards, fault
injection and parameter sweeps. VHDL remains appropriate for record packing,
multi-board connectivity, clocks and PHY/status transport models. These are
test-specific topologies, rather than reusable production interface wrappers.
The older RX characterization bench remains a historical reproducer; it does
not need conversion to add the new behavioral coverage.

This follows [SURF's regression guidance](../firmware/submodules/surf/tests/README.md)
with a deliberately isolated launcher. It reuses one source analysis per pytest
worker, supports a temporary compact-record package, and owns the GHDL process
group so a timeout also terminates LLVM GHDL's child executable. The separate
pytest and cocotb files keep that build/cache machinery out of the simulator
module. Case-specific logs/results and worker-specific libraries isolate runs.
The small stream driver handles packed lanes and sixteen SSI user bits; it
drives on falling edges and checks ready at the accepting rising edge, before
registered outputs change after `TPD_G`. A helper that checks ready after that
delay would observe capacity for the next transfer instead.

It checks 2/3/8-board collection and broadcast, congestion with delayed status,
packet admission and forwarding, missing-tail recovery, and ordered overflow
termination without subsequent traffic. It also checks native PGP status
latency with both VCs active and idle, and analyzes PgpCore against the real
SURF entity interfaces. Unlike the characterization above,
healthy flow-control cases must not overflow and fresh recovery probes must all
arrive correctly. See the [ring guide](../firmware/common/warm_tdm/doc/PGP_RING.md#isolated-regression)
for model limits and the `WARM_TDM_RING_FULL_RECORDS=1` option. The default build
reduces unused AXI record capacity in a temporary package for simulation speed;
configured stream and FIFO widths are unchanged.

Integer coefficients use signed Q1.23: `1 << 23` is -1, while `(1 << 23)-1`
is the largest positive coefficient. FP coefficients are binary32.
Match coefficient encoding, DAC polarity and row width to each bench.

The [frozen reference](warm_tdm/adc_dsp/golden_refs/presplit_rtl/README.md)
is historical evidence. Do not regenerate it to make changed arithmetic pass.
Retained-feedback comparisons use a shared historical prefix and independent
expectations for intentionally different later visits. Keep exact state,
stream-format and exactly-once DAC-delivery assertions alongside that comparison.

## Generated IP and full-system simulation

The [Ethernet bandwidth regression](warm_tdm/ethernet/test_bandwidth.py) checks
the shared SRP/data payload budget at 1G and 10G, both full-duplex directions,
partial beats, sidebands, stalls, idle credit and reset using the real SURF
SimLink pacer. It also checks the GroupTb build selector:

```bash
.venv/bin/python -m pytest tests/warm_tdm/ethernet/test_bandwidth.py -q
```

This isolated GHDL test excludes sockets, RSSI/UDP/MAC overhead and vendor IP.
See [Ethernet bandwidth](../firmware/simulations/GroupTb/README_cosim.md#ethernet-bandwidth)
for build selection and the payload model's limits.

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
