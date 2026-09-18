# Multiple integer flux wraps per visit

## Implementation status and configuration

September 17, 2026: implementation and local regressions are complete in `AdcDsp.vhd`,
`_AdcDsp.py`. The nominal wafer SQ1 period is now
23 uA (approximately 1239 DAC codes for the standard front end).
The user explicitly requested **software calculation of the reciprocal and
no FPGA validation of it**. Firmware trusts the supplied reciprocal and shift.

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
remain outstanding; simulation evidence is recorded below.

September 18 timing follow-up: the [two-state pipeline fix](TIMING_REVIEW.md)
adds `FLUX_COMMIT_S` and `DAC_ROUND_S` to every completion path, separating
wrap adjustment, clipped state updates and DAC rounding. The September 17
latency measurements below describe the original implementation; use the
timing review for the updated schedule and validation.

## Validation at the implementation revision

Working tree based on `channelization` commit `33599a9`. The maintained
software checks pass: **89 pytest cases plus 29 subtests** across integer/FP
configuration, debug format compatibility, supporting helpers and cosim checks.
The reciprocal property checks cover every supported quantum and all exact
quotient intervals across the complete candidate range, plus endpoints of
the approximate quotient intervals. They confirm at most one count correction
and at most five DAC codes of excess before that correction.

The direct RTL tests use GHDL, inferred RAM/FIFOs, actual AXI DAC writes,
retained RAM readback, v3 debug decoding and signed int32 PID stream outputs.
They exercise fractional threshold neighbors, counts above 16, full MAC/RAM
extrema, the correction case, 19-bit saturation, masked state, ordinary
configuration writes and per-visit snapshots. **67 cocotb cases pass** across
the final selected suite:

| Suite | Passing cocotb cases |
|---|---:|
| Multi-wrap boundaries, full MAC/RAM extrema, overflow/masks, register snapshots and timing | 10 |
| Fractional feedback | 18 |
| Integral/state lifecycle | 12 |
| DAC delivery under stalls | 2 |
| Historical comparison (golden unchanged) | 1 |
| Flux direction, count, readout and anti-windup | 16 |
| Basic PID/control regressions | 8 |

Two configurations cover eight rows/inverted DAC and 256 rows/normal DAC;
the historical and basic-control suites retain their existing single
configurations. The original aggregate runs exposed obsolete test assumptions
about debug delivery and one-wrap counting. The corrected timing cases were
rerun individually in both configurations; the corrected basic-control suite
was rerun in full. No RTL change was needed for those test corrections.
The wafer update separately passed all six WaferModelTb checks.

Timing regression, measured from the rising edge accepting the accumulation:

| Path | Minimum accepted visit interval | DAC-register sink latency |
|---|---:|---:|
| Ordinary visit | 16 clocks / 128 ns | 20 clocks / 160 ns |
| Reciprocal multi-wrap visit | 21 clocks / 168 ns | 25 clocks / 200 ns |

Both minimum intervals accept all ten visits in a burst; a one-clock-shorter
interval accepts five. The clock is 125 MHz, the DAC sink is ready, and debug
is disabled for throughput measurement. The debug FIFO can pause diagnostics
independently: an initial burst test incorrectly required ten debug frames
and observed seven while all ten control writes/readout samples arrived.
Isolated arithmetic tests still check every debug frame. These measurements
do not establish board timing closure or the physical DAC settling deadline.

Logs: `/private/tmp/warm-tdm-multi-flux-rtl.log`,
`/private/tmp/warm-tdm-multi-flux-timing.log` and
`/private/tmp/warm-tdm-pid-regression.log`; the final basic-control rerun is
`/private/tmp/warm-tdm-pid-base-regression.log`. Vivado 2024.1 is unavailable in this
workspace. Full GroupTb closed-loop, generated-IP filtering, synthesis,
implementation and hardware acceptance remain open under issue #70.

## Scope and decisions

September 17, 2026: investigate replacing AdcDsp's one-quantum wrap with a
bounded calculation covering the full candidate range of the current PID
arithmetic. The user clarified that 8 or 16 jumps was an estimate of likely
excursions, not a requirement or implementation limit. Do not impose a
16-jump cap or require a separate algorithm above that count.
The user explicitly chose to retain the +/-7862 threshold, rather than use
the FP controller's centered remainder. The analysis below records the design
leading to the implementation described above.
Issue #70 remains the feature acceptance owner.

The existing [flux contract](../pid-cosim-verification/FLUX_JUMP_REVIEW.md) and
[lifecycle correction](LIFECYCLE.md) provide the baseline. Preserve fractional
feedback and masked-row commit gating. The user subsequently reopened the
nine-bit net-count limit, allowing expansion within the multiplier's capacity.
The refined recommendation is a 19-bit signed net count and a normalized
configured reciprocal requiring at most one exact correction subtraction.
The earlier fixed-2^17 reciprocal and its three-correction proof remain below
as analysis history. Neither design imposes an 8/16-jump cap.

## Implementation interpretation

Use the same reciprocal count calculation for every multi-wrap visit:

1. Preserve the full candidate and calculate its magnitude above the threshold.
2. Multiply by the configured reciprocal to estimate the complete jump count n.
3. Multiply n by Q and subtract that entire shift from the candidate at once.
4. If the remainder is still beyond the threshold, subtract one more Q and
   increment n. One correction suffices with the normalized reciprocal below.
5. Apply the sign, update the total signed count, reconstruct readout from the
   final state pair and issue one final DAC command.

For example, a visit needing 100 jumps does not execute 100 subtraction states.
The two products handle the bulk shift, followed by at most one correction
step with the refined reciprocal. No comparison against 16 is necessary in
the datapath. Zero/one-wrap
bypasses can reduce the work on ordinary visits without constraining larger
ones. Total state-machine latency still includes setup, framing and commits.

The accumulated count is a separate finite range. Full-range per-visit wrap
arithmetic does not make readout lossless after that count saturates. The
current user guidance permits expansion; the proposed width and its output
implications are recorded below. Explicit overflow behavior remains necessary.

## Refined reciprocal: one correction over the entire candidate range

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
The one conditional correction enforces the exact +/-7862 result. Omitting it
is a viable intentional tolerance of up to five codes beyond the trigger;
it does not create a fractional reconstruction error. The recommendation
retains the correction to preserve the stated exact threshold contract.

A Python model checked 7,231,480 boundary probes over all Q=1..8191 and the
full candidate bound, including exact and estimated quotient transitions.
Maximum count underestimate was one. Maximum uncorrected local magnitude
was 7867 (Q=1005, m=270349, shift=26, R=66774). These checks supplement the
proof and are not RTL or hardware qualification. Reproducer/log:
`/private/tmp/warm-tdm-multi-flux/check_normalized.py` and `normalized.log`.

## Wider count within multiplier and stream limits

The existing count occupies the signed 18-bit MAC input after sign extension.
An 18-bit retained count (-131072..131071) fits that assignment directly.
Putting J on the existing 24-bit input and Q on the 18-bit input supports a
24-bit signed count without increasing multiplier width. The readout stream
is an independent constraint: with Q up to 8191, 24-bit J requires more than
32 signed output bits.

Recommend signed 19-bit J (-262144..262143), on the 24-bit operand, with Q on
the 18-bit operand. It expands the count range by 1024 while preserving the
current int32 readout for every supported Q and local DAC value:

```text
minimum = (-262144)*8191 - 8192 = -2147229696
maximum =    262143*8191 + 8191 =  2147221504
```

Both fit int32, and the raw-bit product/addition fits the current 42-bit MAC
result. The addition J+dJ needs a wider temporary and explicit overflow
handling; a sufficiently large visit or sustained net excursion can still
exhaust any finite count. RAMs, registers and Python fields must widen
together. Existing v3 debug has a signed 32-bit count field and can carry it.
Binary32 filtering loses integer-code resolution at large absolute readout
(up to 128 DAC codes per float step near the proposed extreme), despite the
fixed-point controller retaining fine local feedback precision.

## Operating example and accepting an approximate wrap count

The pre-update `verify_cosim_pid.py`/`cosim_pid.example.json` integer profile
used a 10 uA quantum, raw P=-0.0006, I=-2e-5, D=0, and by default 20 ADC
samples per row visit. `SetCosimTunePoints` seeds operating points; the PID
setup script explicitly programs the quantum. With default FpgaColFeb
SQ1FbAmp conversion (0.0185662358835 uA/DAC code), integer Q rounds to 539.
These are repository simulation defaults, not a measured hardware distribution.

The user subsequently requested a 23 uA nominal model period. Current profiles
now use that period with the same gains and a phase-scaled 16.1 uA seed;
integer Q is approximately 1239 codes with the default amplifier. The Q=539
arithmetic examples below are retained as historical examples of the earlier
fixture, not the current operating quantum.

The subsequent [hardware notebook investigation](HARDWARE_SCALE.md) recovered
September 11 SQ1 curves with an approximate 21–22 uA period and a saved scale
of 18571 pA/code: approximately 1170 codes per quantum, or 14 quanta across
the DAC. The 539-code example below remains specific to the simulation fixture.

The user subsequently questioned the DAC range implied by this quantum.
539 is the integer physical-period estimate, not the integer controller's
permitted feedback range: its wrap trigger stays at +/-7862, subtracting Q
when crossed. A sustained one-direction ramp consequently cycles through a
Q-wide band near that rail, but local feedback is not constrained to +/-Q/2.
FP defaults WrapMultiplier to 1 and centers over a single quantum, so with
this fixture it does constrain local DAC output to approximately +/-269.3
codes. Its existing multiplier can instead center over N physical quanta.
For N=30 and the fractional FP Q=538.6121378, the period is approximately
16158.364 DAC codes (local +/-8079.182), within the driver's 16380-code limit.
That increases the utilized DAC span without changing the physical quantum
or the DAC steps per quantum. Increasing steps per physical quantum would
require a different analog current-per-code scale. No multiplier setting or
wafer-model parameter was changed by this discussion.

After Q1.23 coefficient quantization and with 18-bit E/S saturation, this
profile bounds |delta| by 81.265625 DAC codes. From normally bounded stored
feedback, that permits at most one wrap per visit. Large multi-wrap events
and their reciprocal cleanup cannot occur under these assumptions. Changing
the gains or manually writing overrange state invalidates that particular
operating bound. ADC error E is a sum; for N=20, P-only delta is approximately
-0.012 times the mean ADC error. DAC codes and ADC codes are different units.

Even the earlier fixed-2^17 reciprocal (R=243 for Q=539) underestimates by
at most one over the entire conservative candidate range. Exhaustive m
enumeration gives uncorrected local magnitude <=8058, i.e. 196 above the
trigger but below the DAC rail. For counts <=16 the bound is 7868 (six codes
above the trigger). Other Q values do not share this property: for Q=4000,
the earlier reciprocal can leave local=14198, clipping 6007 positive DAC
codes. This is why Q and the residual, not simply the number of correction
iterations, determine clipping risk.

For any integer estimate n, updating the local feedback and count coherently
preserves the full-precision reconstructed coordinate before clipping/count
overflow, whether n is the minimal exact quotient or not:

```text
(C-sign(C)*n*Q) + (J+sign(C)*n)*Q = C+J*Q
```

An omitted cleanup can therefore leave a command above the trigger yet inside
the DAC rails with no flux-accounting error. A subsequent visit can perform
the remaining wrap even with zero ADC error. Existing DAC rounding still
introduces its usual half-code quantization; odd-Q half ties can change its
parity. Physical equivalence also assumes a correctly calibrated period and
adequate analog settling.

If the residual clips, the algebra no longer preserves the original
candidate. A later PID visit might correct a phase error, but recovery of the
original unwrapped flux branch is not guaranteed. Heavy low-pass filtering
can suppress a short transient; it does not repair persistent count/branch
errors. The actual biquad impulse response and row revisit rate, not readout
rate alone, determine transient attenuation. `DownsampleFilters` programs a
fourth-order Butterworth using RowSequenceRate and FilterCuttoffFreq.

## Required result

Let C=F+delta be the unsaturated candidate, T=7862, and Q a positive integer
quantum in 1..8191 DAC codes. Q=0 retains the wrapping-disabled behavior.

```text
n  = 0                              if abs(C) <= T
n  = ceil((abs(C)-T)/Q)              otherwise
dJ = sign(C)*n
F_next = C-dJ*Q
J_next = J+dJ
```

This chooses the minimum number of same-direction wraps, preserving the
existing strict threshold. It is not round(C/Q), which would implement a
different centering policy. Before clipping or net-count saturation:

```text
F_next + J_next*Q = F + J*Q + delta
```

Only one final physical DAC write is required. For C=11000 and Q=2000, n=2
and F_next=7000. For C=9862 exactly, n=1 and F_next=7862; one fractional LSB
above 9862 requires two wraps. Both signs use the same magnitude calculation.

## Earlier reciprocal analysis: fixed 2^17 scale

Compute the reciprocal of Q once when configuring it; reciprocals of the jump
counts 1..16 are not needed. For Q>=2, choose a downward-rounded Q1.17
reciprocal and swap the usual operand roles: the excess uses the MAC's wider
24-bit input, and the reciprocal uses its signed 18-bit input.

```text
R = floor(2^17/Q)                    # positive Q1.17 reciprocal, raw bits
m = ceil(abs(C)-T)-1                 # nonnegative integer excess minus one
h = floor(m*R/2^17)                  # multiplier operation 1
n = h+1
A = n*Q                             # multiplier operation 2
W = abs(C)-A
repeat at most 3 times:
    if W <= T: break
    W -= Q                          # exact correction for reciprocal error
    n += 1
F_next = sign(C)*W
```

Handle abs(C)<=T and Q=0 before this path. Q=1 needs a bypass: R=2^17 would
encode -1 in signed Q1.17; here n=m+1 directly. Negative raw Q encodings are
unsupported operational configurations and need an explicit policy rather
than being fed to the reciprocal estimator.

The integer reduction is exact because Q is integral:

```text
ceil((abs(C)-T)/Q) = floor((ceil(abs(C)-T)-1)/Q)+1
```

The original 23-bit fraction stays in C, so calculating the quotient from m
does not discard it. In particular, this is CEILING of the excess, not the
default nearest-even conversion used by fixed_pkg resize. Quotient extraction
from the positive product must FLOOR, also explicitly.

The current retained feedback representation is bounded in magnitude by
2^14, including manually written overrange RAM values, and the saturated PID
result by 2^18. Thus abs(C)<=278528 and m<=270665. That excess fits the signed
24-bit operand. For Q>=2, R<=65536 fits the signed 18-bit operand. No wider
multiplier is required.

Because R is rounded downward, h never overestimates floor(m/Q). Its
real-valued error is less than m/2^17:

- For n<=16, m<16Q<=131056<2^17, so the integer quotient is at most one low.
- Across the entire current candidate range, m/2^17<2.066, so the integer
  quotient is at most three low.

The exact W>T check corrects these possible errors. Do not omit it even for
an accurate reciprocal: strict fractional boundary behavior requires exact
counting. Exit as soon as W<=T. If it remains above T after three corrections,
the configured reciprocal or a width assumption is invalid; define an explicit
fault/clamp result, never an unbounded loop. These bounds assume the correctly
configured floor reciprocal, not an arbitrary AXI-written value.

Both multiplications deliberately reinterpret the datapath's raw bits, as its
current J*Q readout calculation already does. In the first, put integer m's
raw bits on the 24-bit input, R on the 18-bit input, and extract the raw product
above bit 16. In the second, put integer n on the 24-bit input and integer Q
on the 18-bit input. This requires explicit scaling/bit extraction, not an
ordinary numerical conversion of m into a Q1.23 gain. Clear the MAC accumulator
for each product and retain wide C separately while reusing the product
register. Temporary n needs 19 unsigned bits and signed dJ needs 20 bits;
neither is restricted to the retained nine-bit net count.

Configuration would add an AXI reciprocal field and per-visit snapshot,
configured coherently with Q while quiescent. The interface must specify how
raw writes keep the pair coherent; the ordinary physical-unit setter alone
is insufficient. Q changes require a clear/reseed of the old flux reference
as part of configuration. FPGA reciprocal generation at
configuration time is another possibility, but is not needed for a host-
configured design. The actual sharing/resource result requires synthesis.

## Earlier bounded-count alternative: four shifted-quantum comparisons

This option was considered when exploring an 8/16-jump assumption. The
four-step version alone does not meet the clarified full-range requirement;
the recommended reciprocal path above does.

For the same m with m<16Q, floor(m/Q) is a four-bit result. Compute it by
subtracting shifted copies of Q:

```text
h = 0
remainder = m
for bit in [3, 2, 1, 0]:
    if remainder >= (Q << bit):
        remainder -= Q << bit
        h += 1 << bit
n = h+1
F_next = C-sign(C)*n*Q
```

This performs exact comparisons against 8Q, 4Q, 2Q and Q. It needs no
reciprocal storage or reciprocal-error correction. Accumulate the selected
Q multiples alongside h to obtain n*Q without a multiplier, or use the MAC
once for the final product. Widen Q before shifting; a shift on the existing
14-bit vector alone would truncate the multiples.

With one comparison per clock, this takes four comparison steps for counts
up to 16, or three for counts up to 8. Setup, final subtraction and commit
may add states. A parallel bank of thresholds/priority encoding could reduce
latency at increased logic cost. The 0/1-wrap path can bypass multi-wrap
calculation to preserve common-case throughput.

This is a strong alternative for a small bounded quotient: a few comparison
cycles, exact arithmetic and simpler configuration. To cover visits requiring
more than 16 wraps, it needs a larger shift sequence or a bounded fallback;
a general restoring divider needs at most 19 quotient steps for the current
candidate magnitude bound. The reciprocal proposal handles those visits with
at most two extra correction subtractions beyond its <=16 case. Both options
need RTL scheduling and Vivado evidence before asserting an exact cycle count
or resource saving.

## Widths and behavior that must change with either option

1. **Keep the candidate wide until wrapping finishes.** The current
   `sfixed(14 downto -23)` working value saturates near +/-16384 before wrapping.
   This is safe only under the single-wrap contract. For example C=30000.25,
   Q=2000 is recoverable in 12 wraps to 6000.25 but is currently truncated early.
   A separate `sfixed(19 downto -23)` candidate (43 bits) preserves the complete
   sum of the current PID correction and feedback. Bounded feedback RAM,
   validity and the v3 debug format can retain their present widths.
2. **Bound the latency across the whole input range.** The refined normalized
   reciprocal supports all counts with at most one correction step; the
   earlier fixed-2^17 analysis required up to three.
   Preserve a bypass for 0/1 wrap so ordinary visits can avoid the quotient
   calculation. Qualify worst-case scheduling, including MAC setup, output
   framing and DAC queue interactions; arithmetic operation counts alone do
   not establish the complete visit latency.
3. **Admit the integral based on actual post-wrap clipping.** The current
   pre-wrap anti-windup check rejects updates that multi-wrap could recover.
   Delay that decision/commit until the wrapped command is known, while
   preserving directional anti-windup and the I=0/masked-row contracts.
4. **Expand and check the net-count range separately.** Propose the 19-bit
   count above, widen the update before saturation and report loss of
   reconstructable count. Audit every RAM/register/debug/driver use together
   and verify the int32 output bound. Expansion does not eliminate overflow.
5. **Keep common lifecycle behavior.** Capture configuration per visit, hold
   masked state and emit only the final DAC command. Intermediate subtraction
   steps must never become visible actuator writes.
6. **Reconstruct readout with the updated total count.** The existing stream
   is `round_even(F_next) + J_next*Q`, where J_next includes every wrap from
   this visit. Do not substitute the visit increment dJ for the net J. When
   reusing the MAC for quotient estimation, reset its accumulator/scaling for
   the final readout MAC. Check the actual output stream, including clipping
   and count saturation, as well as the DAC. Preserving fractional readout
   would require a separate interface/conversion change; see the
   [readout comparison](../pid-path-comparison/README.md#readout-into-the-biquad-september-17-follow-up).

## Arithmetic evidence and next steps

A first Python integer-arithmetic model checked **1,081,212 signed boundary cases**:
every Q=1..8191, each count boundary through 16, both signs, exact equality,
adjacent 2^-23 DAC-code LSBs, and half-code offsets. An initial Q1.23 reciprocal
variant and the four-step algorithm matched the exact ceiling-division result and preserved
F_next+dJ*Q=C. Of these probes, 490,680 required the reciprocal correction.
Another 98,292 signed cases were correctly classified as needing more than
16 wraps. This is boundary coverage plus the quotient-error proof above,
not exhaustive enumeration of all possible candidates or an RTL test.

The Q1.17 proposal was checked at **4,657,226 quotient-interval endpoints**
over every Q=2..8191 and m=0..270665. Within an interval where floor(m/Q)
is constant, the error cannot increase, so its lower endpoint bounds that
interval. The observed maximum was three corrections overall and one for
counts <=16, consistent with the analytic bounds above. One three-correction
case is Q=107, m=269747, R=1224.

A separate Q1.17 check covered **1,212,268 signed fractional boundary cases**:
every Q=1..8191, boundaries T+kQ for k=0..17 with offsets -LSB, zero, +LSB
and half a code, plus the conservative maximum candidate magnitude and its
neighboring LSB. Every result matched exact ceiling division, preserved
F_next+dJ*Q=C and landed within +/-T. The observed correction counts obeyed
the one/three bounds. Q=1 took its exact bypass. These are arithmetic-model
checks, not RTL simulation or measured FPGA timing.

The earlier temporary reproducers are `/private/tmp/warm-tdm-multi-flux/check.py`
and `/private/tmp/warm-tdm-multi-flux/check_wide.py`. Maintained normalized
reciprocal checks now live in `software/tests/test_int_pid_controls.py`;
direct RTL coverage is in `tests/warm_tdm/adc_dsp/test_AdcDsp_multi_flux.py`
and the existing fractional, flux, lifecycle and delivery suites.
Vivado 2024.1 and hardware flux-wrap acceptance remain necessary.

For hardware context, the 7-Series DSP48E1 provides a 25x18 signed multiplier
and a 48-bit accumulator; the existing 24x18 operands fit that geometry. See
[AMD UG479](https://docs.amd.com/v/u/en-US/ug479_7Series_DSP48E1).
