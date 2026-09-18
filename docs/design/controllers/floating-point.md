# Floating-point PI (AdcDspFp)

## Scope and implementation

IEEE 754 single-precision PI servo for TES SQUID readout, selected by
`DataPath.USE_FLOAT_PID_G`. Keep unwrapped float32 feedback as the primary
per-row state, including its fractional part, for the stated approximately
±256 physical-quantum operating envelope. There is no planned conversion to
bounded feedback plus a separate accumulated flux offset.

The implementation is carried by `channelization` / PR #106. The older
34-cycle and truncation sketches are superseded. Candidate-specific evidence
and remaining qualification are recorded on
[#70](https://github.com/slaclab/warm-tdm/issues/70); the historical implementation
and cleanup revisions are `07a87d0` and `fae7151`.

## Architecture

One shared FpMac performs each floating-point operation in sequence. The current
XCIs request FpMac latency 4, Int2Fp latency 2, and Fp2Int latency 2. State-machine
handshakes, RAMs and transport add cycles beyond the sum of core latencies.

For row-window error sum E, old accumulated error S and full feedback F:

```text
S_candidate = FMA(1, E, S)
F_P         = FMA(P, E, F)
F_candidate = FMA(I, S, F_P)         # uses old S
quotient    = FMA(inverse_R, F_candidate, 0)
J           = nearest_even_int32(quotient)
W           = FMA(float32(J), -R, F_candidate)
D_rounded   = nearest_even_int32(W)
D           = clamp(D_rounded, -8192, 8191)
F_next      = F_candidate           # preserves fraction across ordinary rounding
if D != D_rounded:
    F_next  = FMA(float32(J), R, float32(D))
```

R=N*Q is the configured wrap period in controller DAC-code units, Q is the
physical quantum and N the positive integer WrapMultiplier. The reciprocal is
float32, so boundary behavior must be tested with the actual stored pair.
R=0 disables wrapping, even if a raw client left a stale inverse. J counts
periods of R, not individual crossing events; N*J is physical quanta.

For enabled rows, save F_next/J and issue D. Save S_candidate unless the
existing anti-windup sign check says I*E would drive farther into the clipped
rail; in that case retain old S. I=±0 saves zero S. Masked rows hold F/S/J and
issue neither DAC nor primary data, while error telemetry/debug may update.

The loop is deliberately PI-only. Normalized software gains divide by the row
sample count; this changes the summed row-window error into an effective mean.
Retaining feedback across visits is distinct from summing ADC samples within
one visit. No control-law or MCE-equivalence change is part of these fixes.

### State and lifecycle

| Per-row RAM | Format | Purpose |
|---|---|---|
| ACCUM_ERROR | float32 | Last error, telemetry |
| SUM_ACCUM | float32 | Integral history S |
| SQ1FB_FULL | float32 | Unwrapped feedback F, including fraction |
| FLUX_JUMP | signed int32 | Last recomputed wrap quotient J, diagnostic |

Full clear, StartRun and rising enable mark F unseeded with `0x7FC00000` and
clear the other state. On its first enabled visit, a row seeds F through Int2Fp
from the captured/decoded applied DAC. Masked visits leave the marker intact.
Full clearing deliberately starts a new unwrapped reference.

An actual I-coefficient change clears **only S**, after the accepted visit
completes; same-value writes do not clear. P/I/R/inverse are captured per visit.
Incoming visits during the integral RAM sweep are counted as intentional
discards. Disabling drains the accepted calculation and DAC queue; use both
busy bits before reconfiguration. Full clearing does not flush that queue.

### Execution path

```text
IDLE → DEBUG_HDR1 → DEBUG_BODY → WAIT_INT2FP
     → [SEED_CONVERT when unseeded]
     → INTEGRATOR → PID_P → PID_I → FLUX_DIVIDE → FLUX_ROUND
     → FLUX_INT2FP → WRAP → DAC_CONVERT
     → [CLIP_FEEDBACK if DAC command clipped]
     → RAM_WRITE → DATA_STREAM → IDLE
```

The seed and clipped paths reuse the existing cores; no new arithmetic core
is instantiated. Model-based measurements to the bench DAC sink are 52 clocks
steady, 55 seeded and 57 clipped steady, at 125 MHz with inferred RAM/FIFOs and
a ready AXI slave. A first visit that clips incurs both extra paths. These are
observations from the test configuration, not vendor timing or worst-case
transport guarantees. Qualify the complete path against the row schedule.

## Registers and software

| Offset | Field |
|---|---|
| 0x00[0] | fllEnable |
| 0x00[9:8] | outputMode: F_next, error, sequence count, speculative new S |
| 0x04 / 0x08 | float32 P / I |
| 0x10 / 0x18 / 0x20 / 0x28 / 0x2C | Integer error / old S / F_next / old F / integer DAC debug readbacks |
| 0x30[0] | ClearPidState |
| 0x34[0] / [1] | ControlBusy / DacWriteBusy |
| 0x38[0] | ResetCounters |
| 0x40 / 0x44 | float32 R / inverse R |
| 0x50[0] | PidDebugEnable |
| 0x60–0x7C | 256-bit row mask |
| 0x80 / 0x84 | MissedVisitCount / DiscardedVisitCount |
| 0x88 / 0x8C | DacOverflowCount / DacErrorCount |
| 0x1000 / 0x2000 / 0x3000 / 0x4000 | Error / S / F / J RAMs, four-byte stride |

The public FluxQuantum is a nonnegative current **difference**. Convert using
`abs(currentPerLsb())`, preserve fractional codes, and configure R/inverse
coherently only while disabled and drained. Zero clears both registers.
WrapMultiplier changes preserve physical Q and recompute the pair. Configuration bounds are described below.
`Session.set_pid` supports P/I, omitted/zero D, and debug-only FP calls; it
rejects nonzero D before writes. Tree construction and configuration round-trip must be qualified on the selected candidate.

## Debug stream

FP v1 is **56 bytes**: two 64-bit shared header words plus five body words.
The headers carry identity/version and timestamp as specified in
[DataChannelization.md](../../../firmware/common/DataChannelization.md).

| Body word | Low bits | High bits |
|---|---|---|
| 0 | Column [3:0], row [15:8] | Reserved |
| 1 | Error float32 | Old F float32 |
| 2 | Old S float32 | Speculative new S float32 |
| 3 | F_next float32 | J signed int32 |
| 4 (last) | Signed DAC [13:0], samples [23:16] | Debug dropCount |

Body word 3 is emitted after any clipping back-calculation. New S remains a
speculative value before anti-windup selection. Masked-row debug fields are
computed candidates; they are not applied DAC/control state. Debug dropCount
counts actual visits suppressed by debug pause, separately from control loss.

## Configuration envelope and delivery

Gains/periods must be finite, Q nonnegative and N a positive integer. Positive
R is at most 16380 DAC codes, preserving headroom near the centered upper
endpoint. `_PidFpConfig.py` rejects periods whose int32 quotient could overflow
within any 14-bit seed plus the stated +/-256 physical-quantum envelope.
That is not a bound on arbitrary gain/error transients: intermediates and
conversions must remain finite and representable. Exceptional-value recovery
for NaN/Inf/denormals is not specified as an ordinary operating mode.

Recompute R and its float32 reciprocal together, deriving the reciprocal from
the represented R. Public writes require PID disabled, ControlBusy=0 and
DacWriteBusy=0; raw clients must honor the same quiescent configuration rule.
Re-enabling deliberately reseeds. `setup_mux` is an explicit setup/reset
operation, while routine `set_pid` preserves the reference except for the
specified integral-only clear on an actual I change.

Both controller DAC paths pop one FIFO command only when the request/ack
handshake is idle, hold it through acknowledgement, and wait for ack release
before consuming another. Error/overflow counters do not roll back saved
state or retry failed writes. The supported visit schedule must keep delivery
lossless; masked telemetry is distinct from applied control state.

FP MissedVisitCount counts enabled visits arriving while busy;
DiscardedVisitCount counts disabled/clearing discards; DacOverflowCount counts
rejected FIFO writes; DacErrorCount counts non-OK completed AXI writes.
These are wrapping uint32 counters reset by hardware reset, StartRun or
ResetCounters. Debug dropCount counts visits suppressed by debug pause, not
idle paused clocks. DacWriteBusy includes FIFO pointer transit.

## Design and maintenance rationale

Retaining unwrapped F preserves fractional corrections without a separate
bounded-feedback/offset architecture. Keep this design unless measured
precision or performance fails the stated operating envelope. A recomputed
J=1 immediately after seeding need not be a fault: F=377 and R=538 gives
W=-161 while preserving F. Forcing J=0 would change the readout reference.

Nearest-even applies independently to the quotient and final DAC conversion;
truncation would be a different algorithm. Clipping back-calculates accepted
F, but ordinary rounding must not erase its fraction. Clearing only S on an
I change avoids silently losing the operating point and unwrapped reference.

## Qualification

- Run the [native generated-IP bench](../../../firmware/simulations/AdcDspFpTb/README.md).
- Verify PyRogue construction, dependency updates and configuration round-trip.
- Measure plant slope and fixed-visit step/reversal recovery at matched gains,
  sample counts, polarity, period and operating point; assess residual/noise
  near zero and ±256 physical quanta.
- Verify lossless scheduling, complete system transport and BiquadFilter output.
- Synthesize with Vivado **2024.1**, check timing/utilization, then complete
  hardware lock, bandwidth and noise acceptance under issue #70.
