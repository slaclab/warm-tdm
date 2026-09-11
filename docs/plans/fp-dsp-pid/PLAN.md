# Floating-Point PI (AdcDspFp)

## Scope

IEEE 754 single-precision PI servo loop for TES SQUID readout. The module
(`AdcDspFp.vhd`) is port-compatible with AdcDsp and selectable via
`USE_FLOAT_PID_G` generic in DataPath.

Goals:
- Improved dynamic range for PI coefficients and state
- Simpler software interface (coefficients are standard floats)
- Software-configurable flux jump wrapping period
- ~34 cycle execution using a single FpMac IP
- Path toward FP16 configurability in future

## Architecture

### IP Cores (per instance)

| Core | Operation | Latency | Notes |
|------|-----------|---------|-------|
| FpMac | A*B+C | 4 cycles | All FP operations (PI, flux wrap, add/sub via ±1.0) |
| Int2Fp | int32 → float32 | 2 cycles | accumError entry + numFluxJumps reconversion |
| Fp2Int | float32 → int32 | 2 cycles | Flux truncation + DAC output |

### Per-Row RAM State

| RAM | Width | Contents |
|-----|-------|----------|
| ACCUM_ERROR | 32-bit float | Last accumErrorFp (debug readback only) |
| SUM_ACCUM | 32-bit float | Integral accumulator |
| SQ1FB_FULL | 32-bit float | Unwrapped SQ1FB (primary state) |
| FLUX_JUMP | 32-bit int | numFluxJumps (for debug readback) |

### State Machine (~34 cycles)

```
IDLE_S (1 cyc)
  -- accumValid fires. Launch Int2Fp(accumError). Present rowIndex to RAMs.
  -- Emit debug Word 0 (SOF): col, row, runTime.

WAIT_INT2FP_S (4 cyc, wc=0..3)
  -- Poll int2FpOutValid to capture accumErrorFp.
  -- At wc=3: RAM outputs valid. Capture sumAccumFp, sq1FbFullFp, numFluxJumps.
  -- Launch FpMac(1.0, accumErrorFp, sumAccumFp) → integrator.

INTEGRATOR_S (4 cyc)
  -- Wait for FpMac → newSumAccum.
  -- Emit debug Word 1: accumErrorFp | sq1FbFullFp.
  -- Launch FpMac(pCoef, accumErrorFp, sq1FbFullFp) → P-term + sq1FbFull.

PID_P_S (4 cyc)
  -- Wait for FpMac → P*error + sq1FbFull.
  -- Emit debug Word 2: sumAccumFp | newSumAccum.
  -- Launch FpMac(iCoef, sumAccumFp, prev) → sq1FbNew.

PID_I_S (4 cyc)
  -- Wait for FpMac → sq1FbNew (= P*err + I*sum + sq1FbFull).
  -- Launch FpMac(invFluxQuantum, sq1FbNew, 0) → jumpsFp.

FLUX_DIVIDE_S (4 cyc)
  -- Wait for FpMac → jumpsFp.
  -- Launch Fp2Int(jumpsFp) → numFluxJumps.

FLUX_TRUNCATE_S (2 cyc)
  -- Wait for Fp2Int → numFluxJumps (integer).
  -- Launch Int2Fp(numFluxJumps) → numFluxJumpsFp.

FLUX_INT2FP_S (2 cyc)
  -- Wait for Int2Fp → numFluxJumpsFp.
  -- Launch FpMac(numFluxJumpsFp, -fluxQuantum, sq1FbNew) → wrappedFp.

WRAP_S (4 cyc)
  -- Wait for FpMac → wrappedFp (DAC value as float).
  -- Emit debug Word 3: sq1FbNewFp | numFluxJumps.
  -- Launch Fp2Int(wrappedFp) → sq1FbInt.

DAC_CONVERT_S (2 cyc)
  -- Wait for Fp2Int → sq1FbInt.
  -- Clip to DAC range [SQ1FB_MIN, SQ1FB_MAX]. Set saturation flags.

RAM_WRITE_S (2 cyc)
  -- Anti-windup mux: commit or discard newSumAccum.
  -- Write SUM_ACCUM, SQ1FB_FULL, FLUX_JUMP RAMs.
  -- Emit debug Word 4 (EOF): sq1FbInt | accumSamples | dropCount.

DATA_STREAM_S (1 cyc)
  -- Emit pidStreamMaster (sq1FbNew or per outputMode).
  -- Return to IDLE_S.
```

### Key Design Decisions

1. **PI only (no D-term)** — derivative action amplifies noise in SQUID FLL
   applications where the error signal is already band-limited by accumulator
   averaging.

2. **Single FpMac for all operations** — addition/subtraction expressed as
   FpMac(±1.0, x, y). Eliminates FpAdd IP (saves ~1800 LUTs × 8 instances).
   Operations serialize through the one FpMac in a linear chain.

3. **Folded PI+SQ1FB computation** — FpMac(P, error, sq1FbFull) followed by
   FpMac(I, sumAccum, prev) gives sq1FbNew directly without a separate add step.

4. **Direct flux jump computation** — numFluxJumps = trunc(sq1FbNew / fluxQuantum)
   computed fresh each iteration. No incremental offset tracking, no LUT. Single
   FMA wraps: FpMac(numFluxJumpsFp, -fluxQuantum, sq1FbNew).

5. **Software-configurable wrap period** — writing N*physicalQuantum into the
   fluxQuantum register reduces flux jump frequency (wraps every N quanta instead
   of 1). Equivalent to the original threshold-based approach but configurable.

6. **Anti-windup via sign-bit check** — `iCoef(31) XOR accumErrorFp(31)`
   determines I-contribution direction. Speculative integrator committed or
   discarded at RAM_WRITE.

7. **Debug stream during FpMac waits** — 5-word (40-byte) debug packets emitted
   at zero cycle cost during the 3 idle cycles of each FpMac operation.

### Resource Impact (8 instances, XC7K325T)

Compared to original AdcDsp + proposed PID+FpAdd design:
- Removes: 8× FpAdd IP (~1800 LUTs), 1 RAM (FLUX_OFFSET)
- Keeps: 8× FpMac, 8× Int2Fp, 8× Fp2Int, 4 RAMs per instance
- AXIL crossbar: 5 masters (was 6)
- Timing: single-IP pipelined path, no parallel timing constraints

## Register Map (AdcDspFp local offsets)

```
0x00[0]       fllEnable
0x00[9:8]     outputMode (0=Sq1FbFull, 1=AccumError, 2=RowSeqCount, 3=NewSumAccum)
0x04[31:0]    P coefficient (IEEE 754 float)
0x08[31:0]    I coefficient (IEEE 754 float)
0x10[31:0]    accumError readback (sign-extended integer)
0x18[31:0]    sumAccumFp readback (float)
0x20[31:0]    sq1FbNewFp readback (float)
0x28[31:0]    sq1FbFullFp readback (float)
0x2C[31:0]    sq1FbInt readback (integer DAC value)
0x30[0]       clearPidState
0x40[31:0]    fluxQuantumFp (float, software sets N * physicalQuantum)
0x44[31:0]    invFluxQuantumFp (float, software computes 1/fluxQuantumFp)
0x50[0]       pidDebugEnable
0x60[255:0]   rowEnableMask
```

RAM arrays at AXIL crossbar offsets:
- 0x1000: AccumError (32-bit float, RO — debug readback)
- 0x2000: SumAccum (32-bit float, RW)
- 0x3000: Sq1FbFull (32-bit float, RW)
- 0x4000: FluxJumps (32-bit int, RW)

## Debug Stream (40 bytes per row)

| Word | Contents | Purpose |
|------|----------|---------|
| 0 (SOF) | col[3:0] \| row[15:8] \| runTime[47:0] | Timing correlation |
| 1 | accumErrorFp[31:0] \| sq1FbFullFp[31:0] | Error + old feedback |
| 2 | sumAccumFp[31:0] \| newSumAccum[31:0] | Integrator before/after |
| 3 | sq1FbNewFp[31:0] \| numFluxJumps[31:0] | New feedback + wrapping |
| 4 (EOF) | sq1FbInt[13:0] \| pad \| accumSamples[7:0] \| pad \| dropCount[31:0] | DAC + metadata |

## Validation Plan

1. Synthesize with `USE_FLOAT_PID_G => true`, verify timing closure
2. Compare utilization against baseline (expect LUT reduction from FpAdd removal)
3. Simulate: step response, verify PI behavior and flux jumping
4. Hardware: lock PI on real SQUID, compare noise/bandwidth with fixed-point
5. Software: verify FluxQuantum LinkVariable computes and writes correctly
