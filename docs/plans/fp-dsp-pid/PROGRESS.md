# FP DSP PID — Progress

## 2026-05-20: PI-Only Simplification (single FpMac, 34-cycle pipeline)

### Completed

- Major rewrite of `AdcDspFp.vhd`: PI-only (D-term removed), single FpMac for all FP operations
- Removed FpAdd IP entirely (commented out in `ruckus.tcl`); saves ~1800 LUTs × 8 instances
- Removed FLUX_OFFSET RAM (no incremental offset tracking)
- Reduced AXIL crossbar from 6 to 5 masters (LOCAL, ACCUM_ERROR, SUM_ACCUM, SQ1FB_FULL, FLUX_JUMP)
- New linear state machine: IDLE → WAIT_INT2FP → INTEGRATOR → PID_P → PID_I →
  FLUX_DIVIDE → FLUX_TRUNCATE → FLUX_INT2FP → WRAP → DAC_CONVERT → RAM_WRITE → DATA_STREAM
- Folded PI+SQ1FB into 2 FpMac ops: FpMac(P, error, sq1FbFull) then FpMac(I, sumAccum, prev) → sq1FbNew directly
- Direct flux jump computation: numFluxJumps = trunc(sq1FbNew * invFluxQuantum),
  single FMA wrap: FpMac(numFluxJumpsFp, -fluxQuantum, sq1FbNew) → wrappedFp
- Eliminated jumpCountToFloat LUT (Int2Fp reconversion instead)
- Software-configurable wrap period via `WrapMultiplier` in `_AdcDspFp.py`:
  firmware register gets N * physicalQuantum, reducing flux jump frequency
- 5-word (40-byte) debug stream: accumErrorFp, sq1FbFullFp, sumAccum before/after,
  sq1FbNew, numFluxJumps, sq1FbInt (DAC), accumSamples, dropCount
- Created `_PidDebuggerFp.py` — live pyrogue DataReceiver for 40-byte FP debug frames
- Created `PidDebugFileReaderFp.py` — offline numpy-based file reader
- Updated `_AdcDspFp.py`: removed D_Coef, updated RAM offsets, added WrapMultiplier,
  outputMode '11' now outputs NewSumAccum (integrator state)
- Preserved existing `_PidDebugger.py` and `PidDebugFileReader.py` unchanged (AdcDsp path)
- Updated `PLAN.md` to reflect final PI-only architecture

### Not Yet Done

- Synthesis run to verify timing closure and utilization
- Simulation verification (cycle count, PI response, flux jumping)
- Hardware validation
- Verify BiquadFilter still receives correct float stream

## 2026-05-19: Constant-Time Redesign (35-cycle all-float pipeline)

### Completed

- Rewrote `AdcDspFp.vhd` state machine: 35 cycles constant, no conditional branches
- Added `FpAdd` IP core (Xilinx FP v7.1, Add/Sub, 2-cycle latency, NonBlocking)
  - New file: `firmware/common/warm_tdm/ip/FpAdd/FpAdd.xci`
  - Updated `ruckus.tcl` to load FpAdd
- Replaced iterative flux jump loop with constant-time all-float approach:
  - FpMac reciprocal multiply (`wrappedFp * invFluxQuantumFp`)
  - Fp2Int truncation for integer jump count
  - Combinatorial LUT (±4 → IEEE 754) avoids Int2Fp entirely
  - FMA incremental offset update: `newOffset = oldOffset + jumps * quantum`
- Moved add/subtract operations from FpMac to FpAdd (2 cycles vs 4):
  D-diff, integrator, SQ1FB-add, wrapping, DAC-wrap
- Speculative integrator: always computed, apply/discard at RAM_WRITE via mux
- Debug packets emit during FpMac wait cycles (zero overhead)
- Merged IDLE + PREP_PID (RAM latency hides in Int2Fp wait)
- Software already compatible (InvFluxQuantumFp register exists at 0x44)

### Not Yet Done

- Synthesis run to verify timing closure and utilization
- Simulation verification (cycle count counter)
- Hardware validation

## 2026-05-19: Accumulator Split Refactor

### Completed

- Removed accumulation states (`WAIT_ROW_STROBE_S`, `WAIT_FIRST_SAMPLE_S`,
  `ACCUMULATE_S`) — replaced by `IDLE_S` waiting on `accumValid`
- Changed port interface: `adcAxisMaster` → `accumIn : AdcAccumResultType` + `accumValid`
- Removed ADC baseline RAM from AdcDspFp (moved to new `AdcAccumulator` entity)
- AXI-Lite crossbar reduced from 7 to 6 masters; RAM offsets shifted down:
  - AccumError: 0x2000 → 0x1000
  - SumAccum: 0x3000 → 0x2000
  - Sq1FbFull: 0x4000 → 0x3000
  - FluxOffset: 0x5000 → 0x4000
  - FluxJumps: 0x6000 → 0x5000
- Updated `_AdcDspFp.py` to match new offsets and removed AdcBaselines variable
- Removed AdcBaseline from `RowPidStatusFp` per-row views

## 2026-05-18: Software Integration & Polish

### Completed

- Added `--floatPid` CLI argument to `WarmTdmArgparse`
- Threaded `useFloatPid` flag through full software stack:
  `arg_dict` → `GroupRoot` → `Group` → `HardwareGroup` → `ColumnFpgaBoard` → `DataPath`
- `DataPath` conditionally instantiates `AdcDspFp` or `AdcDsp` based on flag
- Exported `AdcDspFp` from `warm_tdm/__init__.py`
- Added `USE_FLOAT_PID_G` generic to `ColumnFpgaBoard.vhd` entity, passed to DataPath
- Set `USE_FLOAT_PID_G=true` in ColumnFpgaBoard325Coordinator10G target ruckus.tcl
- Added `RowPidStatusFp` / `RowPidStatusFpArray` to `_AdcDspFp.py` for per-row
  debug views (AccumError, SumAccum, Sq1FbFull, FluxOffset, FluxJumps)
- Matched original `_AdcDsp.py` coefficient pattern: all three P/I/D use
  hidden Raw RemoteVariables with LinkVariable wrappers (`_setCoef` helper)
- Replaced standalone `setFluxQuantum()` method with a proper `FluxQuantum`
  LinkVariable (in μA) that internally writes `FluxQuantumIntRaw`,
  `FluxQuantumFpRaw`, and `InvFluxQuantumFpRaw` registers

## 2026-05-15: Initial Implementation

### Completed

- Created `firmware/common/warm_tdm/ip/Fp2Int/Fp2Int.xci` — Float-to-int32 IP
  core (NonBlocking, 2-cycle latency, mirrors Int2Fp)
- Created `firmware/common/warm_tdm/rtl/AdcDspFp.vhd` — Full FP PID module with:
  - FpMac/Int2Fp/Fp2Int instantiation (1 each, shared via state machine)
  - Per-row state in 32-bit RAMs (accumError, sumAccum, sq1FbFull, fluxOffset, fluxJumps)
  - Iterative multi-quantum flux jump support
  - Anti-windup via sign-bit comparison
  - Float output to downstream BiquadFilter
  - AXI-Lite register interface with float coefficients
  - DAC output via existing FIFO+AxiLiteMaster pattern
- Added `PID_DATA_FP_AXIS_CFG_C` (4-byte float stream) to `WarmTdmPkg.vhd`
- Modified `DataPath.vhd` — `USE_FLOAT_PID_G` generic with generate blocks
- Modified `BiquadFilter.vhd` — `INPUT_IS_FLOAT_G` generic skips Int2Fp
- Updated `ruckus.tcl` to load Fp2Int IP
- Created `firmware/python/warm_tdm/_AdcDspFp.py` — PyRogue device driver

## Resolved Questions

- **accumShift**: Dropped. Never quite worked, and float handles dynamic range
  natively.
- **BiquadFilter output to EventBuilder**: No issue. BiquadFilter outputs
  `y1_active` (float32) in `tData(31:0)` and original input in `tData(63:32)`
  on the 8-byte `DOWNSAMPLE_DATA_AXIS_CFG_C` stream. EventBuilder is
  format-agnostic — it packs bits into the event frame without interpretation.
  Software-side data parsing (`_DataFormats.py`) will need to interpret the
  payload as float when `--floatPid` is active, but that's a separate concern
  for the data analysis layer.

## Not Yet Done

- Synthesis run (target is configured, needs `make` in Vivado environment)
- Testbench/simulation
- Hardware validation
- Software data format parsing awareness of float payloads
