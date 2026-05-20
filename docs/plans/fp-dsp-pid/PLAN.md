# Floating-Point PID (AdcDspFp)

## Scope

Convert the AdcDsp PID servo loop from fixed-point to IEEE 754 single-precision
floating-point arithmetic. The new module (`AdcDspFp.vhd`) is port-compatible
with AdcDsp and selectable via a `USE_FLOAT_PID_G` generic in DataPath.

Goals:
- Improved dynamic range for PID coefficients and state
- Simpler software interface (coefficients are standard floats)
- Multi-quantum flux jump support (enabled by float's wider range)
- Constant-time execution (deterministic 35 cycles, no variable-length loops)
- Path toward FP16 configurability in future

## Affected Subsystems

- `firmware/common/warm_tdm/rtl/AdcDspFp.vhd` (new — PID-only, receives `AdcAccumResultType`)
- `firmware/common/warm_tdm/rtl/DataPath.vhd` (generic added, instantiation rewired)
- `firmware/common/warm_tdm/rtl/BiquadFilter.vhd` (float input bypass)
- `firmware/common/warm_tdm/rtl/WarmTdmPkg.vhd` (stream config, `AdcAccumResultType`)
- `firmware/common/warm_tdm/ip/Fp2Int/` (IP core)
- `firmware/common/warm_tdm/ip/FpAdd/` (new IP core — FP Add/Sub, 2-cycle latency)
- `firmware/common/warm_tdm/ruckus.tcl`
- `firmware/python/warm_tdm/_AdcDspFp.py`

## Architecture

### IP Cores (per instance)

| Core | Operation | Latency | Notes |
|------|-----------|---------|-------|
| FpMac (existing) | A*B+C | 4 cycles | Fused multiply-add — P, I, D terms + flux offset |
| FpAdd (new) | A±B | 1 cycle | Add/subtract — D-diff, integrator, SQ1FB-add, wrapping |
| Int2Fp (existing) | int32 → float32 | 2 cycles | For accumError conversion (entry point only) |
| Fp2Int (existing) | float32 → int32 | 2 cycles | Flux jump truncation + final DAC output |

### Per-Row RAM State (within AdcDspFp)

| RAM | Width | Contents |
|-----|-------|----------|
| ACCUM_ERROR | 32-bit | Previous accumError as float (for D-term) |
| SUM_ACCUM | 32-bit | Integral accumulator (float) |
| SQ1FB_FULL | 32-bit | Unwrapped SQ1FB (float, primary state) |
| FLUX_OFFSET | 32-bit | Accumulated flux offset (float, incremental update) |
| FLUX_JUMP | 16-bit | numFluxJumps (integer, for readback/diagnostics) |

Note: ADC_BASELINE moved to the upstream `AdcAccumulator` entity.

### State Machine (~38 cycles)

```
Cyc 0:  IDLE_S
        -- accumValid fires. Capture accumIn record (accumError, rowIndex, sq1FbDac,
        -- seqStart, daqReadoutStart). Present rowIndex to all state RAM read addresses.
        -- Launch Int2Fp(accumError) — converts 32-bit integer accumError to IEEE 754 float.
        -- Int2Fp result will be ready in 2 cycles (end of cycle 2).
        -- RAM read latency is 3 cycles (READ_LATENCY_G=3) — outputs valid cycle 4.

Cyc 1-4: WAIT_INT2FP_S (4 wait cycles)
        -- Wait for RAM read latency (READ_LATENCY_G=3) and Int2Fp (C_Latency=2).
        -- Poll int2FpOutValid each cycle; capture accumErrorFp when it fires.
        -- At wc=3 (cycle 4): RAM outputs valid. Capture lastAccumErrorFp,
        -- sumAccumFp, sq1FbFullFp, fluxOffsetFp, numFluxJumps.
        -- Write accumErrorFp to RAM (for next iteration's D-term).
        -- Launch FpAdd (D-diff) and FpMac (P-term) in parallel.

Cyc 5+:  PID_COMPUTE_S — FpAdd: D-diff, FpMac: P-term (launched in parallel)
        -- FpAdd computes: lastAccumErrorFp - accumErrorFp → dErr
        --   (derivative error for D-term; 1-cycle FpAdd latency)
        -- FpMac computes: P * accumErrorFp + 0.0 → P_term
        --   (proportional contribution; 4-cycle FpMac latency)
        -- After D-diff arrives (wc=1), launch speculative integrator on FpAdd:
        --   accumErrorFp + sumAccumFp → newSumAccum (1-cycle FpAdd latency)
        -- Poll at wc=3 for both FpAdd (integrator) and FpMac (P-term).
        -- FpMac result may take 1 extra cycle; FSM polls until both valid.

Cyc ~10-13: PID_I_S — FpMac: I-term
        -- FpMac computes: I * sumAccumFp + P_term → PI_result
        --   (integral contribution accumulated with proportional; 4-cycle latency)

Cyc ~14-17: PID_D_S — FpMac: D-term
        -- FpMac computes: D * dErr + PI_result → pidResult
        --   (derivative contribution accumulated with PI sum; 4-cycle latency)
        --   Result (pidResult) = full PID output.

Cyc ~18-19: SQ1FB_ADD_S — FpAdd: update feedback state
        -- FpAdd computes: pidResult + sq1FbFullFp → sq1FbNew
        --   (apply PID correction to unwrapped SQ1 feedback; 1-cycle latency)
        --   This is the primary output to BiquadFilter.

Cyc ~20-21: WRAP_S — FpAdd: initial wrapping with current offset
        -- FpAdd computes: sq1FbNew - fluxOffsetFp → wrappedFp
        --   (subtract current flux offset; 1-cycle FpAdd latency)
        --   Result (wrappedFp) used to determine how many flux quanta to jump.

Cyc ~22-25: FLUX_RECIPROCAL_S — FpMac: compute jump count in float
        -- FpMac computes: wrappedFp * invFluxQuantumFp + 0.0 → jumpsFp
        --   (multiply by reciprocal of flux quantum to get fractional jump count)
        --   invFluxQuantumFp is a software-set register (= 1.0 / fluxQuantumFp).

Cyc ~26-27: FLUX_TRUNCATE_S — Fp2Int: truncate jump count to integer
        -- Fp2Int computes: jumpsFp → additionalJumps (signed 32-bit integer)
        --   (2-cycle latency, truncate-toward-zero mode)
        -- Combinatorial (same cycle as Fp2Int output):
        --   numFluxJumps += additionalJumps  (integer add for state tracking)
        --   additionalJumpsFp = LUT[additionalJumps]  (small ROM: maps ±4 → IEEE 754)
        --     LUT entries: -4.0=0xC0800000, -3.0=0xC0400000, -2.0=0xC0000000,
        --       -1.0=0xBF800000, 0.0=0x00000000, 1.0=0x3F800000,
        --       2.0=0x40000000, 3.0=0x40400000, 4.0=0x40800000
        --     If |additionalJumps| > 4: saturate (system diverged, cap correction)

Cyc ~28-31: OFFSET_UPDATE_S — FpMac: flux offset + debug packets
        -- FpMac: FMA(additionalJumpsFp, fluxQuantumFp, fluxOffsetFp) → newFluxOffset
        --   (incrementally update offset: newOffset = oldOffset + jumps * quantum)
        -- Debug stream emitted during FpMac wait (3 packets, zero extra cost).

Cyc ~32-33: DAC_WRAP_S — FpAdd: compute final DAC value in float
        -- FpAdd computes: sq1FbNew - newFluxOffset → dacValueFp
        --   (final wrapped value using corrected offset; 1-cycle FpAdd latency)

Cyc ~34-35: DAC_CONVERT_S — Fp2Int: final conversion to DAC integer
        -- Fp2Int computes: dacValueFp → sq1FbInt (signed 32-bit integer)
        --   (2-cycle latency, truncate toward zero)
        -- On result:
        --   Clip sq1FbInt to DAC range [SQ1FB_MIN_C, SQ1FB_MAX_C] (14-bit signed)
        --   Set saturatedHigh/saturatedLow flags for anti-windup decision.

Cyc ~36:  RAM_WRITE_S — Anti-windup decision + write state RAMs
        -- Anti-windup (combinatorial mux, no branching):
        --   if (iCoef=0) or (saturatedHigh and sameSign) or (saturatedLow and sameSign):
        --     writeSumAccum = old sumAccumFp    (discard speculative integrator)
        --   else:
        --     writeSumAccum = newSumAccum        (commit speculative integrator)
        -- RAM writes initiated:
        --   sumAccumRam[rowIndex]    ← writeSumAccum   (integrator state)
        --   sq1FbFullRam[rowIndex]   ← sq1FbNew        (unwrapped feedback)
        --   fluxOffsetRam[rowIndex]  ← newFluxOffset   (updated offset)
        --   fluxJumpRam[rowIndex]    ← numFluxJumps    (updated jump count)
        -- Note: accumErrorRam was written earlier in WAIT_INT2FP_S.
        -- Assert sq1FbValid with clipped sq1FbInt for DAC output path.

Cyc ~37:  DATA_STREAM_S — Output to BiquadFilter, return to IDLE
        -- Emit pidStreamMaster packet:
        --   tData = sq1FbNew (or accumErrorFp/pidResult per outputMode)
        --   tId = rowIndex
        --   tValid = rowEnabled
        -- Transition → IDLE_S (ready for next accumValid)
```

Design notes:
- IDLE and PREP_PID merged: WAIT_INT2FP_S handles both RAM read latency (3 cycles)
  and Int2Fp conversion (2 cycles) in a single 4-cycle wait phase.
- FpAdd and FpMac run on independent hardware — parallel operations have no resource conflict.
- All flux jump math stays in float domain. Only Fp2Int calls are: truncating jumpsFp to
  get the integer jump count (cycle 23-24), and the final DAC output conversion (cycle 31-32).
- No Int2Fp in the pipeline at all (eliminated by LUT for small jump counts).
- No DSP48 integer math. The FpMac handles the reciprocal multiply natively.
- Debug packets emit during FpMac wait window (cycles 25-27) at zero cycle cost.
- The state machine executes in ~38 cycles (varies by ±1 depending on IP valid
  alignment). No conditional branching; variation is only from polling alignment.
- The downstream BiquadFilter (48 cycles/row) remains the throughput bottleneck;
  ~38 cycles gives comfortable margin.

### Key Design Decisions

1. **Track unwrapped sq1FbFull as primary state** — eliminates the awkward
   reconstruction step. BiquadFilter receives smooth float directly.

2. **Float pass-through to BiquadFilter** — `INPUT_IS_FLOAT_G` generic skips
   BiquadFilter's Int2Fp, saving 2 cycles and 8 IP instances.

3. **All-float flux jump computation** — The reciprocal multiply
   (`wrappedFp * invFluxQuantumFp`) uses the existing FpMac. Fp2Int truncates
   to get the integer jump count. A combinatorial LUT converts it back to float
   for the offset FMA. No DSP48 integer math, no Int2Fp in the pipeline.

4. **Incremental fluxOffset update** — `fluxOffset += additionalJumps * quantum`
   via FMA. The LUT provides `additionalJumps` as float (bounded ±4). Avoids
   Int2Fp entirely. Exact since LUT values are exact IEEE 754 representations.

5. **Speculative integrator** — Always compute `newSumAccum = error + sumAccum`
   on FpAdd. Anti-windup applies/discards at RAM_WRITE via combinatorial mux.
   No state machine branching.

6. **FpAdd for true add/sub operations** — Five operations that used FpMac(x, ±1.0, y)
   become proper FP additions on a 1-cycle adder (C_Latency=1): D-diff, integrator,
   SQ1FB-add, initial wrap, DAC wrap. Frees FpMac for multiplies (P, I, D,
   reciprocal, offset).

7. **Anti-windup via sign-bit check** — `iCoef(31) XOR accumErrorFp(31)`
   determines I-contribution direction without an extra FP operation.

8. **Hex constants for FP values** — uses `X"3F800000"` (1.0), `X"BF800000"`
   (-1.0), `X"00000000"` (0.0) directly, matching BiquadFilter convention.

9. **Debug packets during FpMac wait** — 3-packet debug stream emits during
   cycles 25-27 at zero cost. `sq1FbInt` exposed via AXI-Lite register readback.

### Flux Jump LUT

Maps `additionalJumps` (small signed integer from Fp2Int) to IEEE 754 float:
```
  -4 → 0xC0800000    -3 → 0xC0400000    -2 → 0xC0000000    -1 → 0xBF800000
   0 → 0x00000000     1 → 0x3F800000     2 → 0x40000000     3 → 0x40400000
   4 → 0x40800000
```
If `|additionalJumps| > 4`: saturate to ±4. Bounds correction per iteration.
In practice, a well-tuned PID produces jumps of ±1 at most. The ±4 cap is a safety net.

### Resource Impact (8 instances, XC7K325T)

- DSP48: ~68 (unchanged — no new DSP48 usage)
- LUT: +~1800 (8× FpAdd + 8× small LUT)
- BRAM: ~276 tiles (unchanged)
- Timing: pipelined FP cores have no long comb paths; should be neutral

### Future FP16 Path

The module uses `slv(31 downto 0)` for all FP state. Switching to FP16 requires:
1. Create half-precision FpMac16/FpAdd16/Int2Fp16/Fp2Int16 IP cores
2. Change RAM widths and register sizes to 16 bits
3. State machine structure is unchanged

## Coding Guidelines

- **Comment every state** in the VHDL with cycle number, active IP cores, data
  produced/consumed, and dependencies. The schedule above is the template.
- Use `-- Cycle N:` comment style to make timing explicit in RTL.

## Validation Plan

1. Synthesize ColumnFpgaBoard325Coordinator10G with `USE_FLOAT_PID_G => true`
2. Compare utilization and timing against baseline
3. Cycle-count verification: counter register must always read 35
4. Functional: inject patterns that cause multi-quantum flux jumps, verify constant-time
5. Regression: `USE_FLOAT_PID_G => false` must still build unchanged
6. Hardware: lock PID on real SQUID, compare noise/bandwidth with fixed-point
7. Software: verify `FluxQuantum` LinkVariable computes and writes `invFluxQuantumFp`

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
0x4C[13:0]    fluxQuantumInt (integer, for threshold reference only)
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
