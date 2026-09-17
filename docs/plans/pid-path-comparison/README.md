# Integer and floating-point DSP comparison

## Scope and status

Review requested September 17, 2026: compare the current `AdcDsp` and
`AdcDspFp` implementations, including numerical behavior, loop performance,
latency, throughput and expected FPGA cost. Feature acceptance remains with issue #70,
as indexed by [integer PID](../integer-pid/README.md) and
[FP PID](../fp-dsp-pid/README.md).

Review completed against `channelization` revision `996aae6`. The measurements
below describe that baseline. The subsequent user-requested
[integer lifecycle correction](../integer-pid/LIFECYCLE.md) aligns masking and
I changes with FP; see that record for implementation and validation.
Earlier 12/34/40-cycle sketches predate these implementations.

## Sources and decisions

- `firmware/common/warm_tdm/rtl/AdcAccumulator.vhd`: shared sampling front end.
- `AdcDsp.vhd`: fixed-point PID, retained fractional local feedback, one wrap
  per visit and signed nine-bit net wrap count.
- `AdcDspFp.vhd`: float32 PI, retained unwrapped feedback, reciprocal-based
  centered wrapping, per-visit coefficient snapshots and delivery diagnostics.
- `DataPath.vhd`, `BiquadFilter.vhd`: parallel column instances and downstream
  format handling.
- [Integer fractional feedback](../pid-cosim-verification/INTEGER_FRACTIONAL_FEEDBACK.md),
  [flux review](../pid-cosim-verification/FLUX_JUMP_REVIEW.md), and
  [FP architecture](../fp-dsp-pid/PLAN.md): current design/evidence records.

Both controllers now retain fractional feedback. Compare current fixed-point
behavior rather than the historical integer implementation that rounded its
state back to the applied DAC on every visit.

## Validation and remaining limits

`make rtl_import` completed. A temporary GHDL/cocotb probe ran both controllers
through the existing `AdcDspFpCocotbWrapper`, selecting `USE_FLOAT_PID_G`, with
eight rows, inverted DAC encoding, inferred memory/FIFOs, a ready DAC-register
sink, an 8 ns clock, and the existing test-only `FpPidModels.vhd`. Both probe
simulations completed. This was a targeted measurement, not a full regression
run or generated-Xilinx-IP qualification.

The probe drove isolated visits, then bursts of ten pre-seeded visits. Timed
inputs and outputs were sampled 2 ns after clock edges. Working scripts/logs
are temporary at `/private/tmp/warm-tdm-pid-comparison/` (`run.py`, `probe.py`,
`probe.log`); the results below are the retained evidence summary.

| Measurement | Fixed | FP |
|---|---:|---:|
| Minimum steady interval accepting all ten visits | 16 clocks | 44 clocks |
| One-clock-shorter interval | 15: accepted 5/10 | 43: accepted 5/10 |
| Seeded-row steady input-to-DAC-register-sink observation | 20 clocks | 51 clocks |
| First visit after clear | 20 clocks | 54 clocks |
| Retained-state clipped visit | 20 clocks | 56 clocks |
| First visit after clear, clipped | 20 clocks | 59 clocks |
| Integral after three masked visits, E=4, I=0.125 | 12 | 0 |

The 51/54/56 FP observations differ by one clock from the existing bench's
52/55/57 reporting convention. Use the approximate 0.41/0.44/0.45 us latencies
for comparison; neither count establishes a hardware transport bound. The
steady acceptance interval is a separate measure: 16 clocks = 128 ns, or
7.8125 million visits/s; 44 clocks = 352 ns, or 2.8409 million visits/s.
The FP seed conversion adds three occupied clocks and clipping adds five;
reserve both when establishing a schedule. Removing debug transport does not
remove the FSM's debug states in the present RTL.

## Arithmetic and behavioral comparison

For each row, let E be its current summed error, S its previous integral and F
its saved feedback. Away from saturation, wrapping and rounding:

```text
fixed: candidate = F + P*E + I*S + D*(E_previous - E)
float: candidate = FMA(I, S, FMA(P, E, F))
both:  S_candidate = S + E
```

Both use old S for the current correction and conditionally admit S_candidate
for the next visit. These are incremental-feedback controllers: even P-only
adds an error-dependent correction to retained F each visit. The FP path is
PI-only. Compare it with fixed D=0 and the same effective P/I gains, sample
count, row revisit period, polarity and operating point.

- Fixed error and S are signed 18-bit values, saturating to -131072..131071.
  The current error is clamped on entry from the shared 32-bit accumulator.
  At 128 samples this begins around a mean error magnitude of 1024 ADC codes.
  `AccumShift` is exposed but its arithmetic stage is commented out.
- Fixed P/I/D are signed Q1.23 (-1 through 1-2^-23), with step 2^-23.
  Normalized software gains divide by sample count before storage; at N=128
  their resolution is 128*2^-23 = 1.52587890625e-5.
- Fixed feedback is a 38-bit `sfixed(14 downto -23)` working/retained value,
  plus a RAM validity bit. It is wrapped locally and finally bounded to the
  DAC range. Its fractional step remains 2^-23 DAC code at all excursions.
- FP converts the full shared 32-bit error sum to float32 for its arithmetic;
  the 22-bit `accumError` register is a diagnostic copy, not the FP MAC input.
  FP gains, S and unwrapped F have much wider dynamic range, with 24-bit
  significand precision. It is not uniformly finer absolute precision.
- Both retain feedback fractions and use nearest-even DAC conversion. The
  old fixed path's per-visit DAC-rounding deadband is already addressed.

NumPy float32 spacing calculations give 0.00048828125 DAC code at F=8191,
0.03125 at F=512000 (256*2000), and 0.0625 at F=1024000 (256*4000). Thus at
512000, a correction below about 0.015625 may disappear when added to F,
despite the retained fraction. This is a numerical prediction, not a measured
noise floor; I accumulation and actual error/noise sequences affect behavior.
The fixed path retains much smaller corrections, although its gain and S
quantization/range can dominate instead. Both still drive the same 14-bit DAC.

### Flux and output

Fixed wraps once when candidate exceeds +/-7862, subtracting/adding integer
Q, then clamps and rounds the DAC. Its signed net count saturates at -256/+255;
further outward wraps lose a quantum in reconstructed output. Output is the
integer rounded local DAC coordinate plus J*Q, with no retained fractional
feedback in the primary stream.

FP recomputes J=nearest_even(candidate/R), using stored float32 reciprocal,
and W=FMA(float32(J), -R, candidate). R is a fractional-code period and may
be a positive integer multiple of physical Q. W stays approximately within
half a period of zero; multiple periods require no additional iteration.
J is int32, and F remains unwrapped. Its primary output is that fractional
float32 F; BiquadFilter skips the integer-to-float input conversion. This is
controller state, not a higher-resolution physical DAC measurement.

Fixed I anti-windup tests the pre-wrap candidate, so it can freeze S even when
one wrap would recover an in-range command. FP tests actual post-wrap,
rounded-DAC clipping and back-calculates F only if clipping occurs. Fixed
clamps F before rounding; FP can retain a fractional excursion beyond a rail
if it still rounds to a valid DAC code.

### Lifecycle differences at the reviewed baseline

The first three points below prompted the subsequent
[integer lifecycle correction](../integer-pid/LIFECYCLE.md). In the updated
working tree, both paths hold masked integral state, clear only S on an actual
I change, snapshot visit coefficients and drain accepted visits on disable.
Integer now exposes ControlBusy; the remaining FP delivery/loss diagnostics
are still additional functionality.

- Masking suppresses DAC/output and feedback/count commits in both. Fixed
  still writes S and previous error; FP holds S while updating error telemetry.
  The masked-S difference above was observed directly through RAM readback.
- An I change clears all fixed PID state, including feedback/count, whereas
  FP completes the accepted visit and clears only S. FP snapshots P/I/R/inverse
  per visit; fixed coefficients and Q remain live during processing.
- FP disabling drains the accepted visit and exposes control/DAC busy bits,
  missed/discarded-visit and DAC overflow/error counters. Fixed does not provide
  equivalent delivery observability and its FSM is gated by enable.
- Both receive an unbuffered accumulation-valid pulse. Busy visits cannot be
  retried. Integer debug `dropCount` is not a control-missed-visit counter.

## Expected system performance and FPGA cost

With matched gains, no numerical limits, D=0 and all writes meeting the next
row preload deadline, their nominal per-visit control law is the same. Float
does not inherently improve bandwidth or RMS noise. Its advantages are range,
gain/period configuration and multi-period recovery; fixed has more processing
headroom and finer absolute feedback resolution.

AdcAccumulator is shared and overlaps the next window with PID work; eight
columns have independent DSP instances. Actual row-rate limits also include
the sampling schedule, shared AXI DAC writes, FastDacDriver preload timing,
and downstream filter/transport. A 400-clock row period leaves ample local
DSP processing time for either implementation, but is not itself a full
system throughput test. Physical DAC updates occur on the row schedule, so
the measured RAM-sink latency is not directly the closed-loop delay.

FP uses one shared FpMac, Int2Fp and Fp2Int per column. Expected arithmetic
logic cost is higher, but no defensible utilization/power ratio is available.
State memory alone is comparable in raw width: fixed has five banks totaling
126 bits/row (18+18+42+9+39); FP has four banks totaling 128 bits/row. Actual
BRAM packing depends on bank widths and implementation. FP debug frames are
56 bytes versus fixed v3's 96 bytes, about 42% less payload at equal rates.

No current Column target synthesis/implementation reports are available under
the local `firmware/build/`. Actual timing closure, resource/power differences
and matched closed-loop hardware noise/bandwidth remain unmeasured here.
Separate processing occupancy from latency to the DAC-register write and from
the physical DAC's row revisit schedule.

Next evidence required for quantitative system claims: generated-IP simulation,
Vivado 2024.1 utilization/timing, and matched per-row step/reversal, residual,
noise and flux-excursion measurements with no lost visits or DAC writes.
