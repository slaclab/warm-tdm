# Multiple integer flux wraps per visit

The integer controller preserves the +/-7862 trigger and local fractional
feedback. It handles the full PID candidate range with bounded work, without
an 8/16-jump cap or one state per subtracted quantum. This differs from FP's
centered remainder. The current contract supersedes the earlier single-wrap,
signed-nine-bit-count design.

## Configuration and implementation

`AdcDsp.vhd` and `_AdcDsp.py` share this register/configuration contract.
The nominal wafer-model SQ1 period is
23 uA (approximately 1239 DAC codes for the standard front end).
Software calculates the reciprocal; firmware trusts the supplied reciprocal
and shift without validating them.

Software calculates `shift = 16 + (quantum-1).bit_length()` and
`reciprocal = (1 << shift) // quantum` for quantum=1..8191; for zero it
writes zero to both. These are ordinary read/write registers, with no
staging register or commit transaction:

| Address | Register | Behavior |
|---|---|---|
| 0x40 | FluxQuantumRaw, bits 13:0 | Quantum in DAC codes; zero disables wrapping |
| 0x44 | FluxJumps_DBG, bits 18:0 | Signed net count, widened from nine bits |
| 0x48 | FluxReciprocalRaw, bits 16:0 | Software-computed normalized reciprocal |
| 0x4c | FluxReciprocalShift, bits 4:0 | Software-computed binary scale |
| 0x54 | FluxCountOverflow, bit 0 | Sticky loss of count history, reset by full clear/reset |
| 0x6000 + 4*row | FluxJumps[row], bits 18:0 | Signed 19-bit count; stride unchanged |

There is no divider, reciprocal generator, validation multiplier, validation
state machine, configuration-error flag or special commit decoder. Raw clients
must supply a correct configuration and quantum in 0..8191; behavior with
invalid configuration is outside the arithmetic contract. The `FluxQuantum`
physical-unit setter calculates and writes all three registers. Direct
`FluxQuantumRaw` clients must also set `FluxReciprocalRaw` and
`FluxReciprocalShift` themselves.

Configure with PID disabled and `ControlBusy=0`, then finish all register writes
before enabling it. The same rule applies to cached/YAML block writes. The
physical-unit setter waits for the resulting state clear. Register readback
does not imply hardware validation. Per-visit active copies keep an accepted
visit consistent with its starting configuration. Changes to the reciprocal
registers are ordinary writes and do not request a clear.

A changed quantum requests a full per-row clear at the visit boundary, since
old counts cannot be reinterpreted using a different quantum. Rewriting the
same quantum preserves row state. The stream and v3 debug formats remain
unchanged; debug already has a signed 32-bit count. The live debugger's memory
view now exposes all 32 bits rather than truncating the count to nine bits.

For a 1239-code quantum, software writes `FluxReciprocalRaw=108327` and
`FluxReciprocalShift=27`.

Implementation uses a 43-bit `fluxCandidate`, the existing 24x18 MAC for
`excess * activeReciprocal` and `visitFluxJumps * activeQuantum`, one exact
cleanup, and a 19-bit saturating `numFluxJumps`. Zero/one-wrap and quantum=1
bypasses retain the ordinary state sequence; other multi-wrap visits add
five states regardless of their jump count. Anti-windup admits `sumAccum`
based on post-wrap clipping. Readout remains
`round_even(sq1FbFull) + numFluxJumps*activeQuantum`, with `numFluxJumps`
on the MAC's 24-bit operand. Vivado 2024.1 resource/timing and hardware acceptance
remain separate acceptance on issue #70.

The [completion pipeline](integer-feedback.md#completion-and-delivery)
adds `FLUX_COMMIT_S` and `DAC_ROUND_S` to every completion path, separating
wrap adjustment, clipped state updates and DAC rounding. Measured schedules
and their configuration limits belong to the candidate verification record
on #70.

## Arithmetic and bound

For candidate C, threshold T=7862 and positive excess D=abs(C)-T, define
`m = ceil(D)-1`; retain the fractional part separately in the wide candidate.
No wrap occurs when D<=0. Estimate the complete wrap count, subtract its
product with Q, then apply at most one exact correction. A visit requiring
100 jumps still uses two products and one bounded cleanup, not 100 states.

Choose the reciprocal scale for each configured Q, filling the positive range
of the existing signed 18-bit multiplier input:

```text
shift = 16 + ceil(log2(Q))          # Q >= 1; integer bit_length(Q-1)
K = 2^shift
R = floor(K/Q)                     # 65536 <= R <= 131071
n_est = floor(m*R/K) + 1
W = abs(C)-n_est*Q
if W > 7862:
    W -= Q
    n_est += 1
```

Q=0 bypasses wrapping. Q=1,2,4 (and other powers of two) have exact
reciprocals under this representation; Q=1 may still use an arithmetic bypass.
The hardware receives R and a shift selection, snapshots them with Q, and
extracts the quotient from the product at the selected bit position. This
uses the same 24x18 multiplier widths, adding selection logic/configuration
for the binary-point position. Actual resource sharing/timing needs synthesis.

For Q>=5, K>=2^19 and m<=270665, so the unrounded quotient error is less
than 0.517. Q=1,2,4 are exact. For Q=3, K=2^18 and R=87381; the error is
m/(3*2^18)<0.345. In every case the integer quotient can underestimate by
at most one. This is independent of the number of jumps in the visit.

The uncorrected local command also has a useful bound. Write the positive
excess as D=m+f, with 0<f<=1. Then

```text
W-T = D-Q*(floor(m*R/K)+1)
    < m*(1-Q*R/K)+f
    < m*Q/K+1 <= m/65536+1 < 5.131 DAC codes.
```

At fixed m the maximum occurs at f=1, where this excess is integral, so the
actual maximum is at most five DAC codes. Exact quotient subtraction never
exceeds the required count; the opposite end is bounded by T-Q>=-329.
Thus the uncorrected result lies within +/-7867 for every supported Q and
candidate, assuming valid matched configuration. It cannot clip the DAC.
The one conditional correction enforces the exact +/-7862 result and is
required by the threshold contract.

## Wider count within multiplier and stream limits

Putting J on the existing 24-bit MAC input and Q on the 18-bit input supports a
24-bit signed count without increasing multiplier width. The readout stream
is an independent constraint: with Q up to 8191, 24-bit J requires more than
32 signed output bits.

The implementation uses signed 19-bit J (-262144..262143), on the 24-bit
operand, with Q on the 18-bit operand. This preserves the current int32
readout for every supported Q and local DAC value:

```text
minimum = (-262144)*8191 - 8192 = -2147229696
maximum =    262143*8191 + 8191 =  2147221504
```

Both fit int32, and the raw-bit product/addition fits the current 42-bit MAC
result. The addition J+dJ uses a wider temporary and saturates on overflow;
a sufficiently large visit or sustained net excursion can still exhaust
the count. RAMs, registers and Python fields carry the same 19-bit value.
The v3 debug format has a signed 32-bit count field and can carry it.
Binary32 filtering loses integer-code resolution at large absolute readout
(up to 128 DAC codes per float step near that extreme), despite the
fixed-point controller retaining fine local feedback precision.

## Operating units and verification

A quantum is the feedback change corresponding to one physical flux period,
not the DAC's full permitted range. The nominal 23 uA fixture period is about
1239 controller codes with the standard conversion, but measured hardware
scale and actual applied current must be checked for the selected front end.
See [recovered hardware scale](../../reference/sq1-feedback-scale.md).

The live count is signed 19-bit (-262144..262143). Saturation sets
`FluxCountOverflow`; it preserves a bounded output but loses count history.
Full clear/reset clears that indication. A supported schedule must deliver
commands losslessly; count range alone is not a lifetime acquisition guarantee.

Software property tests cover all supported Q and quotient boundaries.
RTL tests cover full candidate extrema, correction cases, fractional threshold
neighbors, masks, register snapshots, count saturation, RAM/debug/readout and
backpressure. See [regression procedures](../../../tests/README.md) and
[#70](https://github.com/slaclab/warm-tdm/issues/70) for revision-specific results.
Earlier fixed-2^17/three-correction proposals and old fixture gains remain in
Git history; they are not alternative runtime modes or recommended presets.
