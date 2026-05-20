# Floating-Point PID (AdcDspFp)

## Scope

Convert the AdcDsp PID servo loop from fixed-point to IEEE 754 single-precision
floating-point arithmetic. The new module (`AdcDspFp.vhd`) is port-compatible
with AdcDsp and selectable via a `USE_FLOAT_PID_G` generic in DataPath.

Goals:
- Improved dynamic range for PID coefficients and state
- Simpler software interface (coefficients are standard floats)
- Multi-quantum flux jump support (enabled by float's wider range)
- Path toward FP16 configurability in future

## Affected Subsystems

- `firmware/common/warm_tdm/rtl/AdcDspFp.vhd` (new — PID-only, receives `AdcAccumResultType`)
- `firmware/common/warm_tdm/rtl/DataPath.vhd` (generic added, instantiation rewired)
- `firmware/common/warm_tdm/rtl/BiquadFilter.vhd` (float input bypass)
- `firmware/common/warm_tdm/rtl/WarmTdmPkg.vhd` (stream config, `AdcAccumResultType`)
- `firmware/common/warm_tdm/ip/Fp2Int/` (new IP core)
- `firmware/common/warm_tdm/ruckus.tcl`
- `firmware/python/warm_tdm/_AdcDspFp.py` (new)

## Architecture

### IP Cores (per instance, shared via state machine)

| Core | Operation | Latency | Notes |
|------|-----------|---------|-------|
| FpMac (existing) | A*B+C | 4 cycles | Fused multiply-add |
| Int2Fp (existing) | int32 → float32 | 2 cycles | For accumError conversion |
| Fp2Int (new) | float32 → int32 | 2 cycles | For DAC output |

### Per-Row RAM State (within AdcDspFp)

| RAM | Width | Contents |
|-----|-------|----------|
| ACCUM_ERROR | 32-bit | Previous accumError as float (for D-term) |
| SUM_ACCUM | 32-bit | Integral accumulator (float) |
| SQ1FB_FULL | 32-bit | Unwrapped SQ1FB (float, primary state) |
| FLUX_OFFSET | 32-bit | Cached `numFluxJumps * fluxQuantum` (float) |
| FLUX_JUMP | 16-bit | numFluxJumps (integer, widened from 9-bit) |

Note: ADC_BASELINE moved to the upstream `AdcAccumulator` entity.

### State Machine

```
IDLE_S              (wait for accumValid from upstream AdcAccumulator)
PREP_PID_S          (read RAMs, start Int2Fp of accumError)
WAIT_INT2FP_S       (2 cycles)
PID_P_S             (FMA: P * error + 0, 4 cycles)
PID_I_S             (FMA: I * sumAccum + result, 4 cycles)
PID_D_DIFF_S        (FMA: -1 * error + lastError, 4 cycles)
PID_D_S             (FMA: D * dError + result, 4 cycles)
SQ1FB_ADD_S         (FMA: result * 1 + sq1FbFull, 4 cycles)
DERIVE_WRAPPED_S    (FMA: fluxOffset * -1 + sq1FbFull, 4 cycles)
FP2INT_S            (2 cycles)
FLUX_JUMP_CHECK_S   (iterative integer loop, 1 cycle/quantum)
ANTI_WINDUP_S       (saturation check + sign test)
SUM_UPDATE_S        (conditional FMA: error * 1 + sumAccum, 4 cycles)
FLUX_OFFSET_UPDATE  (if jump: Int2Fp + FMA to recompute offset)
RAM_WRITE_S         (write all state RAMs)
DATA_STREAM_S       (output sq1FbFullFp to biquad)
```

Common case: ~38 cycles. Flux jump case: +~10 cycles.
Accumulation is handled by the upstream `AdcAccumulator` entity (pipelined).

### Key Design Decisions

1. **Track unwrapped sq1FbFull as primary state** — eliminates the awkward
   reconstruction step. BiquadFilter receives smooth float directly.

2. **Float pass-through to BiquadFilter** — `INPUT_IS_FLOAT_G` generic skips
   BiquadFilter's Int2Fp, saving 2 cycles and 8 IP instances.

3. **Iterative flux jump** — simple integer loop handles multi-quantum jumps.
   Cached `fluxOffsetFp` avoids per-cycle FMA for the common no-jump case.

4. **Anti-windup via sign-bit check** — `iCoef(31) XOR accumErrorFp(31)`
   determines I-contribution direction without an extra FP operation.

5. **Hex constants for FP values** — uses `X"3F800000"` (1.0), `X"BF800000"`
   (-1.0), `X"00000000"` (0.0) directly, matching BiquadFilter convention.

### Resource Impact (8 instances, XC7K325T)

- DSP48: +16-24 (68 → ~90 of 840)
- LUT: +~3200 (97K → ~100K of 204K)
- BRAM: +~12 tiles (264 → ~276 of 445)
- Timing: pipelined FP cores have no long comb paths; should be neutral

### Future FP16 Path

The module uses `slv(31 downto 0)` for all FP state. Switching to FP16 requires:
1. Create half-precision FpMac16/Int2Fp16/Fp2Int16 IP cores
2. Change RAM widths and register sizes to 16 bits
3. State machine structure is unchanged

## Validation Plan

1. Synthesize ColumnFpgaBoard325Coordinator10G with `USE_FLOAT_PID_G => true`
2. Compare utilization and timing against baseline
3. Functional: write float P/I/D, inject known ADC data, verify vs Python model
4. Regression: `USE_FLOAT_PID_G => false` must still build unchanged
5. Hardware: lock PID on real SQUID, compare noise/bandwidth with fixed-point

## Register Map (AdcDspFp local offsets)

```
0x00[0]       fllEnable
0x00[9:8]     outputMode (0=Sq1FbFull, 1=AccumError, 2=RowSeqCount, 3=PidResult)
0x04[31:0]    P coefficient (IEEE 754 float)
0x08[31:0]    I coefficient (IEEE 754 float)
0x0C[31:0]    D coefficient (IEEE 754 float)
0x10[31:0]    accumError readback (sign-extended integer)
0x14[31:0]    lastAccumErrorFp readback (float)
0x18[31:0]    sumAccumFp readback (float)
0x20[31:0]    pidResultFp readback (float)
0x28[31:0]    sq1FbFullFp readback (float)
0x2C[31:0]    sq1FbInt readback (integer DAC value)
0x30[0]       clearPidState
0x40[31:0]    fluxQuantumFp (float)
0x44[31:0]    invFluxQuantumFp (software-computed 1/quantum)
0x48[15:0]    numFluxJumps readback
0x4C[13:0]    fluxQuantumInt (integer for threshold loop)
0x50[0]       pidDebugEnable
0x60[255:0]   rowEnableMask
```

RAM arrays at AXIL crossbar offsets:
- 0x1000: AccumError (32-bit float, RO)
- 0x2000: SumAccum (32-bit float, RW)
- 0x3000: Sq1FbFull (32-bit float, RW)
- 0x4000: FluxOffset (32-bit float, RW)
- 0x5000: FluxJumps (16-bit int, RW)

Note: AdcBaselines moved to the upstream `AdcAccumulator` entity (see
pipelined-dsp-accumulator plan).
