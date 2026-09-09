# Progress

## 2026-05-19 — Implementation

### Completed

- Created `AdcAccumulator.vhd` entity:
  - Free-running front-end with `IDLE → WAIT_FIRST_SAMPLE → ACCUMULATE → output` state machine
  - Owns baseline RAM (AXI-Lite accessible)
  - Outputs `AdcAccumResultType` record on `lastSample`
  - Saturating 32-bit accumulation
  - Ports: `timingRxData`, `adcValid/adcData`, `sq1FbDac`, `accumOut/accumValid`, AXI-Lite
- Added `AdcAccumResultType` record to `WarmTdmPkg.vhd` (accumError, numSamples, rowIndex, seqStart, daqReadoutStart)
- Modified `AdcDsp.vhd`: removed accumulation states, now starts at `IDLE_S` waiting for `accumValid`
- Modified `AdcDspFp.vhd`: same — removed accumulation states, accepts `AdcAccumResultType` input
- Rewired `DataPath.vhd`:
  - Instantiates `AdcAccumulator` per channel
  - Routes `accumResults`/`accumValids` signals to AdcDsp/AdcDspFp
  - ADC streams no longer route directly to PID modules
- Created `_AdcAccumulator.py` PyRogue device (AdcBaselines RAM, 14-bit, 32 rows)
- Updated `_AdcDsp.py` and `_AdcDspFp.py` — removed baseline-related registers (moved to accumulator)
- Exported `AdcAccumulator` from `warm_tdm/__init__.py`

### Initial Analysis and Planning (same session, earlier)

- Analyzed PID cycle counts for both integer and float paths
  - Integer PID: 12 cycles deterministic
  - Float PID: 36-54 cycles (40 typical, unbounded worst case due to flux jump loop)
- Analyzed timing constraints from TimingTx (rowPeriod, sampleStartTime, sampleEndTime, stageNextRowLead)
- Calculated row rate improvements from pipelining (see PLAN.md table)
- Identified unbounded flux jump iteration as a safety issue (tracked as follow-up)
- Decided on architecture: `AdcAccumResultType` record with seqStart/daqReadoutStart flags for frame termination
- Decided baseline RAM moves into AdcAccumulator
- Decided no flow control (dropped-row counter instead)

### Prerequisite Work Completed (prior commit)

Refactored DataPath/AdcDsp/AdcDspFp/WaveformCapture to eliminate tuser bit packing:
- Timing signals now flow as `LocalTimingType` records through the FIR filter sideband
- `sq1FbDac` is now a dedicated port (delayed through the sideband)
- `bypassedAdcStreams` eliminated
- DataPath generate structure cleaned up (no redundant mux in no-filter case)

These changes simplified the accumulator split since the ADC stream no longer carries timing metadata.

## Not Yet Done

- `AdcAccumulator` not yet added to ruckus.tcl (already covered — `loadSource -dir` loads all .vhd in rtl/)
- Synthesis run to verify utilization/timing
- Simulation verification (StackTb with reduced rowPeriod)
- Verify bit-exact integer PID outputs vs. baseline
- Hardware validation
