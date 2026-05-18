# FP DSP PID — Progress

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
  debug views (AdcBaseline, AccumError, SumAccum, Sq1FbFull, FluxOffset, FluxJumps)
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

## Not Yet Done

- Synthesis run (target is configured, needs `make` in Vivado environment)
- Testbench/simulation
- Hardware validation

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
