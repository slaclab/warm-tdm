# Integer PID retained feedback

`AdcDsp` retains local fixed-point SQ1 feedback between visits to each logical
row, so repeated sub-code corrections can eventually move the DAC. This
preserves the incremental P/I/D law and sample-count normalization; it does
not add another error integrator. The current implementation includes the
later multi-wrap and lifecycle changes, superseding the original single-wrap
proposal from September 16, 2026.

## Arithmetic and limits

For each enabled row, use saved feedback F when valid, otherwise decode the
captured applied DAC. Let E be the saturated 18-bit row error, S its old
integral history, and E_previous its previous error. The MAC computes the
existing fixed-point correction, with its defined intermediate saturation:

```text
delta = P*E + I*S + D*(E_previous-E)
C = F + delta
W, dJ = wrap(C, Q, reciprocal, shift)
F_next = clamp(W, -8192, 8191)
DAC = nearest_even(F_next)
J_next = saturating_signed_19bit(J + dJ)
readout = nearest_even(F_next) + J_next*Q
```

The wrap trigger is strictly beyond +/-7862, not at equality. Q=0 disables
wrapping. Positive Q is 1..8191; host code must supply the matching reciprocal
and shift. [Multi-wrap arithmetic](integer-flux-wrapping.md) recovers the whole
candidate before clipping and defines the sticky count-overflow indication.
The 43-bit `fluxCandidate` preserves the full correction until wrapping; the
38-bit retained RAM value is not a sufficient intermediate for that operation.

For example, 8500.25 with Q=2000 becomes 6500.25 before rounding. Rounding
occurs after the flux shift: 7863.5 minus an odd Q=2001 gives 5862.5, whose DAC
code is 5862. Rounding the first value before subtracting Q would give 5863.

The error integral uses old S in this visit's correction. Its next value is
zero for I=0; otherwise the directional anti-windup check admits the new error
only when it does not drive farther into an actual post-wrap rail clip.
Recoverable multi-wrap excursions must not suppress integration merely because
the unwrapped candidate exceeded a rail. Masked visits hold control state.

With no wraps or clipping, +0.25 per visit from zero gives retained values
0.25, 0.50, 0.75, 1.00 and DAC coordinates 0, 0, 1, 1. The rounding remainder
is part of F; it is not a separate stored variable.

## Storage, lifecycle and diagnostics

`U_Sq1FbFullRam` holds `sfixed(14 downto -23)` plus validity: 38 payload bits
and one valid bit. The three-cycle RAM read uses the logical-row state access
sequence. Committed feedback is clamped to the DAC range. Hardware mapping
and timing must still be verified for the selected target and row depth.

The AXI window is `0x7000 + 8*row`: bits 37:0 contain signed Q15.23 feedback,
bit 38 is valid, and upper bits read zero. The driver exposes `Sq1FbFull`
(`pr.Fixed(38, 23)`) and `Sq1FbFullValid`. A 64-bit live read comprises two
32-bit bus transactions; use the debug stream for a coherent visit snapshot.
Host edits require stopped sequencing and completed clears; mark a supplied
value valid, or invalidate it to seed from the next captured applied DAC.

Masking, integral-only clears, full clears and disable/re-enable behavior are
specified in [integer lifecycle](integer-lifecycle.md). Ordinary visits reuse
retained F instead of reloading the quantized DAC. Manual changes while masked
need an explicit full clear/reseed before resuming that operating point.

Integer v3 PID-debug frames are 96 bytes including the 16-byte shared header.
The word after `pidResult` contains post-wrap/post-clamp, pre-rounding F as a
38-bit signed fixed-point value sign-extended to 64 bits. The following count
is signed int32 on the wire; the current controller supplies all 19 count bits.
Masked visits can report a calculated candidate without committing it.
Version 1 lacks fractional feedback; version 2 has the historical narrower
count encoding. The production decoder retains those format distinctions.
See [channelization](../../../firmware/common/DataChannelization.md).

`PidResults` remains a per-row diagnostic for the correction; it is not the
feedback state consumed on the next visit. Removing that RAM requires a
separate decision about its existing driver/polling interface.

## Completion and delivery

Wrap/bypass paths register the wide candidate, jump count and direction.
`FLUX_COMMIT_S` then evaluates post-wrap clipping and anti-windup, updates the
saturating net count, and registers clamped retained feedback. `DAC_ROUND_S`
rounds that registered value and queues the DAC write. Preserve those clock
boundaries; folding wrap adjustment, clamp/count logic and rounding into one
combinational tail recreates the long completion path.

The accumulation input is unbuffered. Qualify the complete visit interval,
RAM/FIFO transport and DAC deadline for the selected row schedule. Behavioral
cycle measurements and source-level multiplier sharing do not establish
Vivado timing closure or resource use. Results belong on #70.

## Quantitative rationale


The strongest predictable benefit is removing the per-visit actuator-rounding
deadband, especially in P-only operation. This is a numerical prediction, not
a measured improvement in hardware noise or closed-loop bandwidth.

### Baseline P-only deadband

Let `e = E/N` be mean ADC error in one row window, `p` the stored hardware
coefficient and `K = N*p` the effective normalized P gain exposed through
`PidP_Gain`. Away from limits and wraps, the correction is `delta = K*e` DAC
codes per visit. The baseline integer feedback remains stationary whenever:

```text
abs(K*e) < 0.5
abs(e)   < 0.5 / abs(K)
```

Half-code equality depends on nearest-even parity. Noise may occasionally push
an error across the threshold; the statement describes a persistent noiseless
error, not a measured noise floor. These are illustrative normalized settings,
not new gain recommendations for the current plant:

| Normalized P, K | Baseline deadband half-width, mean ADC codes | Persistent error needed to reach a half-code correction over 100 visits with carry |
| ---: | ---: | ---: |
| 0.01 | 50 | 0.50 |
| 0.015625 | 32 | 0.32 |
| 0.02 | 25 | 0.25 |
| 0.05 | 10 | 0.10 |

The last column assumes zero initial remainder and approximately constant
error until the first DAC movement. Exact threshold ties can require another
visit. Use actual gain readback for an exact prediction because Q1.23
coefficient encoding slightly changes most decimal settings. ADC-window error
granularity, at best 1/N mean code, also limits realizable constant stimuli.

### Retained correction and finite observation time

With carry, a nonzero representable correction accumulates until it moves the
DAC. For a constant correction starting at an integer command, the first move
occurs after approximately `0.5 / abs(delta)` visits, subject to the half-tie
rule. Over M visits the corresponding persistent-error threshold is about:

```text
abs(e) ~= 0.5 / (M * abs(K))
```

Thus 100 visits provide sensitivity to persistent errors about 100 times
smaller than the baseline single-visit threshold. This is not a claim of 100x
better RMS noise or settling time. Once the DAC moves, the plant changes the
error and a closed-loop calculation is needed.

For an arbitrary sequence of already-computed corrections without clipping or
wrapping, the retained-remainder recurrence gives the exact identity:

```text
u[M] - u[0] = sum(delta[n]) + R[0] - R[M]
```

Starting with R[0]=0, accumulated command error due to DAC rounding is bounded
by half a DAC code, regardless of visit count. The baseline scheme can lose up
to half a code on every visit. This bound concerns the accumulated command
versus the same correction sequence; it is not an unconditional bound on the
physical plant's time-averaged error.

The new state preserves a correction lattice of `2^-23`, approximately
`1.19e-7` DAC code. The physical DAC still has its original one-code steps,
and very small corrections need many visits to become visible. The extra
fraction bits must not be described as extra physical DAC resolution or an
8-million-fold system-performance improvement.

### Exact arithmetic examples

A Python integer-arithmetic calculation used the proposed 23-bit fractional
state and nearest-even rounding, with N=128 and raw P=1024. These settings are
exactly representable: hardware p=1/8192 and normalized K=1/64. Starting from
controller zero, I=D=0, with prescribed constant errors:

| Mean ADC error | Correction per visit, DAC codes | Baseline first movement | With fractional carry |
| ---: | ---: | --- | ---: |
| 16 | 0.25 | Never | Visit 3 |
| 1 | 0.015625 | Never | Visit 33 |
| 1/128 | 1/8192 | Never | Visit 4,097 |

The calculation ran 10,000 visits per case and checked both the accumulated
command identity and the half-code remainder bound. This is arithmetic-model
evidence, not a simulation of modified RTL. As a timing example, 32 rows at
400 clocks/row and 125 MHz revisit a row every 102.4 us; 33 visits are about
3.38 ms. The same visit count takes a different time under another schedule.

### Closed-loop illustration and the noise tradeoff

A separate illustrative arithmetic model used a noiseless static plant
`e[n] = -32*(u[n] - target)`, N=128, raw P=512 (normalized K=1/128), I=D=0,
and initial u=0. Each applied DAC controls the next visit's error. The selected
targets make every ADC error integer, so there is no fractional ADC assumption.
There is no clipping or wrapping. Results below summarize the final 3,072
visits of 4,096, after discarding the first 1,024 visits:

| Ideal target, DAC codes | Baseline mean ADC error | With carry, mean ADC error | Baseline raw error RMS | With carry, raw error RMS |
| ---: | ---: | ---: | ---: | ---: |
| 1.00 | 32 | 0 | 32 | 0 |
| 0.75 | 24 | 0 | 24 | 13.86 |
| 0.25 | 8 | 0 | 8 | 13.86 |

At the integer target, carry permits a correction that the baseline controller
rounds away, then holds the correct DAC quietly. At fractional targets, carry
alternates between adjacent DAC codes with mean commands 0.75 and 0.25. This
eliminates mean measured error in this ideal model, but introduces visit-to-visit
ripple; raw RMS can improve or worsen. In-band noise depends on the resulting
spectrum, analog dynamics, sampling and downstream filtering. This model is
not a calibrated representation of the corrected cosim plant.

The nominal gains, linear control law and pipeline delay are not improved by
retaining fractions. Large-signal settling need not become faster; the benefit
is completing small corrections that otherwise stall. With I enabled, the
existing error integral can already grow until it overcomes DAC rounding, so
the P-only deadband table is not a universal PI residual bound. Fractional
carry still removes the final feedback-rounding loss without relying on that
extra integrator to do so.

These calculations support expecting better low-gain DC accuracy and slow
tracking. They do not assign a fraction of the current cosim residual to this
effect or guarantee a specific improvement in noise/bandwidth. No full FP or
wafer-model comparison harness is needed for the arithmetic estimates above.


## Verification and historical evidence

The maintained fractional bench drives the real accumulator, feeds actual
DAC writes back into later visits and checks independent rows, both encodings,
8/256-row configurations, 23rd-bit fractions, half ties, clipping, reset and
stream decoding. Lifecycle, multi-wrap and delivery benches extend that
coverage; use the [regression guide](../../../tests/README.md).

The original baseline lost repeated quarter-code corrections; the retained
state advances two codes over eight such visits. The unchanged historical
golden covers a common seed/overflow prefix, while independently calculated
expectations cover intentional later differences. Unit arithmetic does not
establish physical noise, bandwidth, row scheduling or FPGA timing.
Revision-specific results and remaining acceptance belong to
[#70](https://github.com/slaclab/warm-tdm/issues/70) and
[#90](https://github.com/slaclab/warm-tdm/issues/90).
