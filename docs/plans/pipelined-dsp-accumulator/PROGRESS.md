# Progress

## 2026-05-19 — Initial Analysis and Planning

### Completed

- Analyzed PID cycle counts for both integer and float paths
  - Integer PID: 12 cycles deterministic
  - Float PID: 36-54 cycles (40 typical, unbounded worst case due to flux jump loop)
- Analyzed timing constraints from TimingTx (rowPeriod, sampleStartTime, sampleEndTime, stageNextRowLead)
- Calculated row rate improvements from pipelining (see PLAN.md table)
- Identified unbounded flux jump iteration as a safety issue (tracked as follow-up)
- Decided on architecture: `AdcAccumResultType` record with seqStart/daqReadoutStart flags for frame termination
- Decided baseline RAM moves into AdcAccumulator
- Decided no flow control (dropped-row counter instead)

### Prerequisite Work Completed (same session)

Refactored DataPath/AdcDsp/AdcDspFp/WaveformCapture to eliminate tuser bit packing:
- Timing signals now flow as `LocalTimingType` records through the FIR filter sideband
- `sq1FbDac` is now a dedicated port (delayed through the sideband)
- `bypassedAdcStreams` eliminated
- DataPath generate structure cleaned up (no redundant mux in no-filter case)

These changes simplify the eventual accumulator split since the ADC stream no longer carries timing metadata.

### Not Yet Started

- Implementation of `AdcAccumulator` entity
- Modifications to AdcDsp/AdcDspFp to accept `AdcAccumResultType`
- DataPath rewiring
- New PyRogue device `_AdcAccumulator.py` (baseline registers, status counters)
- Update `_AdcDsp.py` / `_AdcDspFp.py` to remove baseline-related registers (moved to accumulator)
- Simulation verification
