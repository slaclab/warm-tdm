# AdcDspFp cleanup

Baseline: `07a87d0`, which commits the FP correctness/configuration/delivery
fixes and their verification. This follow-up addresses source organization.

## Scope

Preserve arithmetic order, state transitions, clocks, register map, RAM
configuration, stream bytes and delivery behavior. Keep the shared FpMac and
unwrapped float feedback. No state-machine rescheduling or control-law changes.

- Generate the four identically configured state RAMs with named bank indices.
- Factor repeated FMA launches, debug word packing, clear-row writes and
  feedback completion into small local procedures.
- Share full/integral clear address progression while retaining their priority.
- Remove unused values and correct stale comments; group related registers.

No repository constraints or tests refer to the FP RAM instance names being
replaced. The generated instances will have different hierarchical names.

## Implementation

- `GEN_STATE_RAM` instantiates the same four AxiDualPortRam banks with their
  original parameters and addresses. Named bank indices select array entries
  for write enable/data and read data.
- `launchMac` makes each state's FMA operands explicit in one call;
  `emitDebugPair` centralizes the repeated two-field debug payload packing.
- `clearRowState` supplies the full or integral-only clear writes. One address
  advancement branch now serves both sweeps, preserving full-clear priority
  and queued I-change behavior.
- `completeFeedback` issues the DAC command and advances to RAM_WRITE on the
  original completion cycle, for both unclipped and clipped results. Each
  calling state emits the accepted-feedback debug word with a separate
  `emitDebugPair` call, keeping debug emission independently movable.
- Removed the write-only `wrappedFp` register, unused negative-one constant
  and unused unisim import. Grouped RegType fields by purpose and renamed the
  memory implementation selector to include its RAM use.

The source shrank from 1,312 to 1,193 lines. State names, transitions and core
latencies remain explicit; no extra pipeline stage or arithmetic core was added.
The local procedures only assign the existing next-cycle register variable.

## Validation and handoff

The initial cleanup passed the native bench with the explicit GHDL FP models
and all **18 FP cases** (9 each at 8/inverted and 256/normal rows), with
cycle-by-cycle comparison against `07a87d0`. The comparison used a temporary source overlay
containing renamed reference/current entities and an assertion wrapper, both
driven from the existing testbench. All six output records are compared at
each active 125 MHz clock (+2 ns): both AXI slave responses, both DAC AXI
masters, primary stream and debug stream, including payload and timing.
No mismatches were reported, including the stalled-write, FIFO-overflow,
mid-visit I-change and clear/reseed cases. Measured model-based input-to-DAC
latencies remain 52 clocks steady, 55 seeded and 57 clipped steady.
This checks the tested stimulus/configurations, not formal equivalence.

After moving debug emission out of `completeFeedback`, the focused seed/
fractional-feedback and clipping/reversal cases pass again in the 8-row,
inverted configuration, including their decoded debug-frame assertions.

Commands for the ordinary maintained regressions (without the temporary
reference/current comparison wrapper):

```bash
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp/test_AdcDspFp.py -n 2 -q
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp/test_AdcDspFp_native.py -q
```

`git diff --check` passes. Only AdcDspFp.vhd and this note changed after the
fix commit; this cleanup remains unstaged and uncommitted for review.

Generated-IP qualification and synthesis/timing remain pending as recorded in
[FP_FIX_IMPLEMENTATION.md](FP_FIX_IMPLEMENTATION.md). RAM hierarchy names have
changed, so external saved waveform configurations may need updating.

Keep this follow-up separate from the committed fixes for review.
