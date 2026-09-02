# Pipelined DSP Accumulator

## Scope

Split the integer accumulation front-end out of `AdcDsp`/`AdcDspFp` into a standalone `AdcAccumulator` entity. This allows accumulation and PID computation to overlap, removing PID latency from the critical path for row rate.

## Motivation

Currently AdcDsp/AdcDspFp use a single sequential state machine:
```
rowStrobe → accumulate samples → PID compute → write RAMs → next rowStrobe
```

Minimum row period = sample_window + PID_latency. By pipelining the accumulator, minimum row period drops to `max(sample_window, PID_latency)`.

## Affected Subsystems

### Firmware
- `firmware/common/warm_tdm/rtl/DataPath.vhd` — instantiation changes
- `firmware/common/warm_tdm/rtl/AdcDsp.vhd` — remove accumulation states
- `firmware/common/warm_tdm/rtl/AdcDspFp.vhd` — remove accumulation states
- `firmware/common/warm_tdm/rtl/WarmTdmPkg.vhd` — new `AdcAccumResultType` record
- New: `firmware/common/warm_tdm/rtl/AdcAccumulator.vhd`

### Software (PyRogue)
- New: `firmware/python/warm_tdm/_AdcAccumulator.py` — device for the new accumulator (baseline RAM access, dropped-row counter, status)
- `firmware/python/warm_tdm/_AdcDsp.py` — remove baseline-related registers (moved to accumulator)
- `firmware/python/warm_tdm/_AdcDspFp.py` — same
- `firmware/python/warm_tdm/__init__.py` — export new device

## Approach

### New Entity: AdcAccumulator

Free-running front-end. Owns the baseline RAM. Outputs a record on `lastSample`:

```vhdl
type AdcAccumResultType is record
   accumError      : signed(31 downto 0);   -- Saturating 32-bit
   numSamples      : unsigned(7 downto 0);
   rowIndex        : slv(7 downto 0);
   sq1FbDac        : slv(13 downto 0);      -- Captured SQ1FB DAC value
   seqStart        : sl;                    -- First row of new sequence
   daqReadoutStart : sl;                    -- Also starts DAQ readout
end record;
```

State machine: `IDLE → WAIT_FIRST_SAMPLE → ACCUMULATE → (output) → IDLE`

Uses saturating 32-bit accumulation. No flow control — if PID can't keep up, a dropped-row counter increments.

### Modified PID Modules

Remove `WAIT_ROW_STROBE_S`, `WAIT_FIRST_SAMPLE_S`, `ACCUMULATE_S`. Replace with:
```
IDLE_S → (accumValid) → PREP_PID_S → PID stages → IDLE_S
```

Frame termination (`seqStart` flag) flows through the `AdcAccumResultType` record.

### DataPath Integration

```
adcStreams(i) → AdcAccumulator(i) → AdcDsp(i)/AdcDspFp(i)
                     ↑
             selectedTimingRxData(i)
```

ADC streams no longer route to AdcDsp directly. WaveformCapture still receives them.

## Row Rate Analysis

| Sample window | Before (int/fp) | After (int/fp) |
|---------------|-----------------|----------------|
| 128 clocks | 140/168 | 128/128 |
| 64 clocks | 76/104 | 64/64 |
| 32 clocks | 44/72 | 32/**40** |
| 16 clocks | 28/56 | 16/**40** |

PID hard floors: Integer = 12 clocks (10.4 MHz), Float typical = 40 clocks (3.1 MHz).

## Known Issues (follow-up)

- **Unbounded flux jump iteration in AdcDspFp**: `FLUX_JUMP_CHECK_S` loops per quantum jump with no cap. If float PID diverges, this is unbounded. Fix: cap iterations or use constant-time reciprocal multiply.

## Validation Plan

1. Synthesis on ColumnFpgaBoard target
2. StackTb simulation (full-system timing + ADC + DSP)
3. Reduce `rowPeriod` in simulation below current minimum, verify no dropped rows
4. Verify identical PID outputs vs. baseline (bit-exact for integer PID)
