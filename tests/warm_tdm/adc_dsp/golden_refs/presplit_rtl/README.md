# Pre-split `AdcDsp` snapshot — bit-exact golden reference

These four files are a **verbatim snapshot** of the column-board integer DSP core
as it stood **immediately before the accumulator split**, used as the model-free
golden reference for the Layer 1 bit-exact re-qualification (see
`docs/plans/pid-cosim-verification/`).

## Provenance

Extracted from git commit **`5645f7e`** ("Clean up delayed timing paths. Properly
delay sq1FbDacs to ADC modules and WaveformCapture…"), the last commit before
`1a6d588` ("Started on accumulator split") touched the DSP datapath. At that
commit the accumulation (baseline subtract + per-row sample sum) still lived
*inside* `AdcDsp` in an `sfixed` accumulator; the split later moved it into
`AdcAccumulator` as a `signed(31:0)` accumulator. This snapshot is the "known
good" integer PID whose behavior the split must preserve.

Files (paths at `5645f7e`, all under `firmware/common/warm_tdm/rtl/`):
- `AdcDsp.vhd`
- `TimingPkg.vhd`
- `WarmTdmPkg.vhd`
- `FixedPkg.vhd`

`FrameHeaderPkg` did not exist yet at this commit; the snapshot needs only the
three warm_tdm packages above plus (current) surf.

## Modifications (both sim-build only, behavior-preserving)

`AdcDsp.vhd` has two deliberate, flagged edits versus the original source. Both
are simulator-build accommodations for GHDL that do not touch the accumulation
or PID numerics or the mAxil SQ1-FB-DAC output. Each is marked inline with a
`SNAPSHOT-LOCAL` comment. No other lines were changed.

1. **Added `use ieee.std_logic_unsigned.all;`.** The original left `numeric_std`
   commented out and relied on the synopsys `std_logic_unsigned` package being in
   scope (from its contemporaneous build) to resolve the `slv`
   `pidStateRamAddr + 1` counter increment. Restoring the `use` clause lets the
   snapshot elaborate under today's GHDL; the operator it supplies is an unsigned
   increment, the faithful reading for a RAM-address counter.

2. **Three stream FIFOs `SYNTH_MODE_G => "xpm"` -> `"inferred"`** (the PID-debug,
   PID-data, and mAxil-write FIFOs). The pre-split core hardcoded `"xpm"`, which
   makes surf's `FifoXpmDummy` assert "FifoXpm not supported" under GHDL. The
   *current* AdcDsp makes exactly this swap through its `SIMULATION_G` generic
   (`STREAM_FIFO_SYNTH_MODE_C := ite(SIMULATION_G, "inferred", "xpm")`), and its
   own source comment states SYNTH_MODE is "the only functional difference"
   SIMULATION_G makes — i.e. inferred vs XPM changes only the underlying RAM
   primitive, not FIFO semantics. This snapshot bakes in the inferred choice
   because the pre-split entity has no `SIMULATION_G` generic to flip.

## Do not "fix" or refactor these files

They are a frozen historical reference. Any change (naming, types, cleanup)
destroys the value of the bit-exact comparison. If the reference commit itself is
ever revised, re-extract from git rather than hand-editing here.

## How it is compiled

The capture bench compiles these into a GHDL `warm_tdm` library (so the old
`AdcDsp`'s `library warm_tdm;` references resolve to the snapshot packages), in a
pytest run/`sim_build` separate from the current-RTL compare bench so the two
`warm_tdm` libraries never coexist.
