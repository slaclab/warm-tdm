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
| FpAdd (new) | A±B | 2 cycles | Add/subtract — D-diff, integrator, SQ1FB-add, wrapping |
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

### State Machine (35 cycles constant)

```
Cyc 0:  IDLE_S
        -- accumValid fires. Capture accumIn record (accumError, rowIndex, sq1FbDac,
        -- seqStart, daqReadoutStart). Present rowIndex to all state RAM read addresses.
        -- Launch Int2Fp(accumError) — converts 32-bit integer accumError to IEEE 754 float.
        -- Int2Fp result will be ready in 2 cycles (end of cycle 2).
        -- RAM read latency is 1 cycle — outputs valid next cycle.

Cyc 1:  WAIT_INT2FP_S (first wait cycle)
        -- RAM outputs now valid: capture lastAccumErrorFp, sumAccumFp, sq1FbFullFp,
        -- fluxOffsetFp, numFluxJumps from their respective RAM data ports.
        -- Int2Fp still computing (1 of 2 cycles elapsed).

Cyc 2:  WAIT_INT2FP_S (second wait cycle)
        -- Int2Fp result valid: capture accumErrorFp.
        -- All inputs for PID computation now available:
        --   accumErrorFp (from Int2Fp), lastAccumErrorFp (from RAM),
        --   sumAccumFp (from RAM), sq1FbFullFp (from RAM),
        --   fluxOffsetFp (from RAM), numFluxJumps (from RAM),
        --   P/I/D coefficients (from registers)

Cyc 3-4:  PID_COMPUTE_S — FpAdd: D-diff, FpMac: P-term (launched in parallel)
        -- FpAdd computes: lastAccumErrorFp - accumErrorFp → dErr
        --   (derivative error for D-term; 2-cycle FpAdd latency)
        --   Sign bit of accumErrorFp is flipped to perform subtraction.
        --   Result (dErr) ready at end of cycle 4.
        -- FpMac computes: P * accumErrorFp + 0.0 → P_term
        --   (proportional contribution; 4-cycle FpMac latency, continues through cyc 6)

Cyc 5-6:  PID_COMPUTE_S — FpAdd: integrator (speculative)
        -- FpAdd computes: accumErrorFp + sumAccumFp → newSumAccum
        --   (speculative integrator update; 2-cycle FpAdd latency)
        --   This runs unconditionally. Anti-windup logic at RAM_WRITE decides
        --   whether to commit or discard this result.
        --   Result (newSumAccum) ready at end of cycle 6 — held in register.
        -- FpMac still computing P-term (cycles 3-6, result ready end of cycle 6).

Cyc 7-10: PID_I_S — FpMac: I-term
        -- FpMac computes: I * sumAccumFp + P_term → PI_result
        --   (integral contribution accumulated with proportional; 4-cycle latency)
        --   P_term available from end of cycle 6. sumAccumFp from RAM (cycle 1).
        --   Result (PI_result) ready at end of cycle 10.
        -- FpAdd idle.

Cyc 11-14: PID_D_S — FpMac: D-term
        -- FpMac computes: D * dErr + PI_result → pidResult
        --   (derivative contribution accumulated with PI sum; 4-cycle latency)
        --   dErr available from end of cycle 4. PI_result from end of cycle 10.
        --   Result (pidResult) = full PID output, ready at end of cycle 14.
        -- FpAdd idle.

Cyc 15-16: SQ1FB_ADD_S — FpAdd: update feedback state
        -- FpAdd computes: pidResult + sq1FbFullFp → sq1FbNew
        --   (apply PID correction to unwrapped SQ1 feedback; 2-cycle latency)
        --   pidResult from end of cycle 14. sq1FbFullFp from RAM (cycle 1).
        --   Result (sq1FbNew) = new unwrapped feedback value, ready end of cycle 16.
        --   This is the primary output to BiquadFilter.
        -- FpMac idle.

Cyc 17-18: WRAP_S — FpAdd: initial wrapping with current offset
        -- FpAdd computes: sq1FbNew - fluxOffsetFp → wrappedFp
        --   (subtract current flux offset; 2-cycle FpAdd latency)
        --   sq1FbNew from end of cycle 16. fluxOffsetFp from RAM (cycle 1).
        --   Sign bit of fluxOffsetFp flipped for subtraction.
        --   Result (wrappedFp) used to determine how many flux quanta to jump.
        -- FpMac idle.

Cyc 19-22: FLUX_RECIPROCAL_S — FpMac: compute jump count in float
        -- FpMac computes: wrappedFp * invFluxQuantumFp + 0.0 → jumpsFp
        --   (multiply by reciprocal of flux quantum to get fractional jump count)
        --   invFluxQuantumFp is a software-set register (= 1.0 / fluxQuantumFp).
        --   Result (jumpsFp) is a float close to an integer value.
        --   Ready at end of cycle 22.
        -- FpAdd idle.

Cyc 23-24: FLUX_TRUNCATE_S — Fp2Int: truncate jump count to integer
        -- Fp2Int computes: jumpsFp → additionalJumps (signed 32-bit integer)
        --   (2-cycle latency, truncate-toward-zero mode)
        --   This truncation IS the rounding — it gives the integer number of
        --   flux quanta that wrappedFp exceeds the range by.
        -- Combinatorial (same cycle as Fp2Int output, end of cycle 24):
        --   numFluxJumps += additionalJumps  (integer add for state tracking)
        --   additionalJumpsFp = LUT[additionalJumps]  (small ROM: maps ±4 → IEEE 754)
        --     LUT entries: -4.0=0xC0800000, -3.0=0xC0400000, -2.0=0xC0000000,
        --       -1.0=0xBF800000, 0.0=0x00000000, 1.0=0x3F800000,
        --       2.0=0x40000000, 3.0=0x40400000, 4.0=0x40800000
        --     If |additionalJumps| > 4: saturate (system diverged, cap correction)

Cyc 25:  OFFSET_UPDATE_S — Launch FpMac + debug pkt 0
        -- FpMac launched: FMA(additionalJumpsFp, fluxQuantumFp, fluxOffsetFp) → newFluxOffset
        --   (incrementally update offset: newOffset = oldOffset + jumps * quantum)
        --   additionalJumpsFp from LUT (cycle 24). fluxQuantumFp from register.
        --   fluxOffsetFp from RAM (cycle 1). Result ready end of cycle 28.
        -- Debug stream (if pidDebugEnable): emit packet 0
        --   tData = sq1FbNew(31:0) & pidResultFp(31:0)
        --   tValid = pidDebugEnable, tLast = '0'

Cyc 26:  OFFSET_UPDATE_S — FpMac wait + debug pkt 1
        -- FpMac still computing (cycle 2 of 4).
        -- Debug stream (if pidDebugEnable): emit packet 1
        --   tData = numFluxJumps(15:0) & accumSamples(7:0) & additionalJumps(7:0) & pad
        --   tValid = pidDebugEnable, tLast = '0'

Cyc 27:  OFFSET_UPDATE_S — FpMac wait + debug pkt 2
        -- FpMac still computing (cycle 3 of 4).
        -- Debug stream (if pidDebugEnable): emit packet 2
        --   tData = dropCount(15:0) & rowSeqCount(15:0) & pad
        --   tValid = pidDebugEnable, tLast = '1' (closes debug burst)

Cyc 28:  OFFSET_UPDATE_S — Capture FpMac result
        -- FpMac result valid: capture newFluxOffset.
        --   This is the updated fluxOffset written to RAM for next iteration.

Cyc 29-30: DAC_WRAP_S — FpAdd: compute final DAC value in float
        -- FpAdd computes: sq1FbNew - newFluxOffset → dacValueFp
        --   (final wrapped value using corrected offset; 2-cycle FpAdd latency)
        --   sq1FbNew from cycle 16. newFluxOffset from cycle 28.
        --   Result (dacValueFp) = the correctly-wrapped DAC output as float.

Cyc 31-32: DAC_CONVERT_S — Fp2Int: final conversion to DAC integer
        -- Fp2Int computes: dacValueFp → sq1FbInt (signed 32-bit integer)
        --   (2-cycle latency, truncate toward zero)
        --   This is the ONLY integer conversion in the entire pipeline —
        --   everything else stays in float domain.
        -- On result (end of cycle 32):
        --   Clip sq1FbInt to DAC range [SQ1FB_MIN_C, SQ1FB_MAX_C] (14-bit signed)
        --   Set saturatedHigh/saturatedLow flags for anti-windup decision.

Cyc 33:  RAM_WRITE_S — Anti-windup decision + write all state RAMs
        -- Anti-windup (combinatorial mux, no branching):
        --   if (iCoef=0) or (saturatedHigh and sameSign) or (saturatedLow and sameSign):
        --     writeSumAccum = old sumAccumFp    (discard speculative integrator)
        --   else:
        --     writeSumAccum = newSumAccum        (commit speculative integrator)
        -- RAM writes initiated:
        --   accumErrorRam[rowIndex]  ← accumErrorFp    (for next iteration's D-term)
        --   sumAccumRam[rowIndex]    ← writeSumAccum   (integrator state)
        --   sq1FbFullRam[rowIndex]   ← sq1FbNew        (unwrapped feedback)
        --   fluxOffsetRam[rowIndex]  ← newFluxOffset   (updated offset)
        --   fluxJumpRam[rowIndex]    ← numFluxJumps    (updated jump count)
        -- Assert sq1FbValid with clipped sq1FbInt for DAC output path.

Cyc 34:  DATA_STREAM_S — Output to BiquadFilter, return to IDLE
        -- Emit pidStreamMaster packet:
        --   tData = sq1FbNew (or accumErrorFp/pidResult per outputMode)
        --   tId = rowIndex
        --   tValid = rowEnabled
        -- Transition → IDLE_S (ready for next accumValid)
```

Design notes:
- IDLE and PREP_PID merged: RAM read latency (1 cycle) hides inside Int2Fp wait (2 cycles).
- FpAdd and FpMac run on independent hardware — parallel operations have no resource conflict.
- All flux jump math stays in float domain. Only Fp2Int calls are: truncating jumpsFp to
  get the integer jump count (cycle 23-24), and the final DAC output conversion (cycle 31-32).
- No Int2Fp in the pipeline at all (eliminated by LUT for small jump counts).
- No DSP48 integer math. The FpMac handles the reciprocal multiply natively.
- Debug packets emit during FpMac wait window (cycles 25-27) at zero cycle cost.
- The state machine always executes exactly 35 cycles regardless of PID dynamics,
  flux jump activity, or anti-windup state. No conditional branching anywhere.
- The downstream BiquadFilter (48 cycles/row) remains the throughput bottleneck;
  35 cycles gives comfortable margin.

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
   become proper FP additions on a 2-cycle adder: D-diff, integrator, SQ1FB-add,
   initial wrap, DAC wrap. Frees FpMac for multiplies (P, I, D, reciprocal, offset).

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
