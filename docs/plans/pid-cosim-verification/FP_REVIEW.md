# Floating-point controller fix assessment — 2026-09-16

The consolidated design is in [FP_FIX_PLAN.md](FP_FIX_PLAN.md); current fixes
and validation are in [FP_FIX_IMPLEMENTATION.md](FP_FIX_IMPLEMENTATION.md).
The assessment below records the earlier source revision; startup seeding has
since been implemented and reviewed in [FP_SEED_REVIEW.md](FP_SEED_REVIEW.md).

## Scope

Source review of Warm TDM `ef81760`, following the fractional-feedback and MCE
comparison in [MCE_COMPARISON.md](MCE_COMPARISON.md). The objective is reliable
FLL operation and meaningful integer/FP performance comparisons. Exact MCE
semantics are not a requirement. No production changes are implemented here.
The following FP behaviors were traced in source; they have not been reproduced
with the generated Xilinx FP IP in this session.

## Recorded design intent and available verification

Read the complete FP [plan](../fp-dsp-pid/PLAN.md),
[progress history](../fp-dsp-pid/PROGRESS.md), and
[demo outline](../fp-dsp-pid/DEMO_OUTLINE.md), alongside the accumulator-split
plan/progress, PID verification plan/progress, sensor-model coefficient note,
cosim tuning settings and PID analyzer plan. The relevant decisions are:

- Unwrapped floating-point feedback is intentionally the primary state, not an
  accidental substitute for a separate fine-feedback state and flux offset.
- The May 19 redesign replaced iterative multi-quantum handling with a bounded
  sequence of reciprocal multiply, integer conversion and wrapping operations.
- The May 20 simplification removed FLUX_OFFSET RAM and the jump-count LUT,
  derives the jump count directly from full feedback, removes D and FpAdd, and
  shares one FpMac. The two PI FMAs include previous feedback directly.
- Configurable N-quantum wrapping is intended to reduce jump frequency within
  the available DAC span. It is independent of adopting MCE's controller law.
- Passing the float stream directly to BiquadFilter and moving accumulation
  into a parallel front end avoid redundant conversion and let sample collection
  overlap controller computation.

The ~34-cycle and LUT-saving figures are design targets/estimates in these
documents, not measured acceptance results. Earlier iterative-loop warnings,
FluxOffset maps, D-term references and 40-byte full-frame descriptions belong
to older revisions; the later design and tagged-header integration supersede
them. The rounding/truncation mismatch remains a specific contract issue.

The user's statement that there is no ready comparison harness agrees with
the repository: `test_AdcDspFp.py` exists, but verification progress records the
VCS/VHDL runner blocker. Its current tests cover basic P/I and clearing, not
large-offset fractional response. GroupTb provides system infrastructure, but
the controlled FP comparison is not complete. The analyzer/comparison functions
in [PID_ANALYZER_PLAN.md](../channelization/PID_ANALYZER_PLAN.md) remain planned;
no implementations of those named functions were found in `software`.

Consequently the precision experiment below is possible future verification,
not an immediately available test or a prerequisite imposed on retaining the
chosen design. Arithmetic bounds and the stated 256-jump operating envelope
support keeping the existing architecture. Splitting the state again would
reintroduce bookkeeping deliberately removed in May; no demonstrated need
currently justifies that change. Address specific startup/masking/configuration
issues within the selected architecture.

## Recommended fixes before interpreting FP lock performance

### 1. Adopt the tuned feedback when initializing each row

`AdcDspFp.vhd:574-617` clears Sq1FbFull on StartRun, explicit clear, and the
rising enable edge. The feedback DAC carried in `accumIn` is never used.
`WAIT_INT2FP_S` reads the cleared RAM at line 708; the P FMA uses it at 740-744.
Consequently the first command is calculated around zero even if software
seeded the physical DAC to a nonzero tuned point. The Python I-coefficient
setter also calls ClearPidState, making this relevant to gain tuning.

Recommended change: per-row initialization state that loads signed, correctly
decoded `accumIn.sq1FbDac` on the first accepted enabled visit after a clear.
Keep the retained fractional state on subsequent visits. Define separately
whether a live I-gain change clears only error history or also reinitializes
feedback. A general state clear must have an explicit operating-point policy.

Acceptance: with a nonzero seed inside the selected wrap interval, zero gains
and zero error, the first and subsequent DAC commands retain the seed. Repeat
with multiple rows, both DAC polarity settings, and each clear/enable path.

### 2. Prevent state drift while a row is masked

The mask is captured at line 650 and gates DAC writes at 888 and stream output
at 942. It does not gate the feedback/integrator/flux-count RAM writes at
924-930. A masked row continues calculating and storing corrections without
applying them. Re-enabling its mask without a global clear therefore resumes
from feedback that can differ substantially from the actual DAC.

Recommended change: gate control-state updates for masked visits; allow error
telemetry to update independently. Define whether unmasking resumes the held
state or re-seeds from the DAC, especially after manual DAC changes.

Acceptance: nonzero repeated errors on a masked row must not accumulate
unapplied feedback. Other enabled rows must continue normally; unmasking must
not release corrections accumulated during the masked interval.

### 3. Make feedback state follow actual DAC saturation

`DAC_CONVERT_S:880-886` clips the wrapped command. `RAM_WRITE_S:913-928` can
freeze the error integral but always stores the original unwrapped command.
P-only mode can therefore continue accumulating feedback beyond what was
applied when the wrapped command clips. This is particularly reachable when
the configured wrap period exceeds the usable DAC span, or wrapping is off.

Recommended change: back-calculate or conditionally limit the feedback state
on actual clipping, consistently with the applied command and flux count.
Do not clamp unwrapped feedback itself to the 14-bit DAC range: valid flux
wrapping must still allow the cumulative signal to exceed that range.
Keep the existing I-term anti-windup decision consistent with that policy.

Acceptance: drive into both rails and reverse the error, in P-only and PI
modes. Verify recovery and agreement between saved feedback, flux count and
applied DAC. Separately verify that an ordinary valid flux wrap does not
trigger saturation handling or discard signal.

### 4. Specify and test the actual wrap/conversion contract

The checked-in Fp2Int XCI plus AMD PG060 specify nearest-even conversion;
the comments and plan describe truncation. Prefer correcting the description
and testing centered wrapping if that is the intended operating behavior.
Choosing truncation instead requires explicit implementation work; there is no
rounding-mode switch in this XCI. See the comparison note for exact fields and
the AMD reference.

The Python flux-quantum setter writes Q and 1/Q separately. It leaves the
old reciprocal when Q becomes zero; changing the local WrapMultiplier alone
does not rerun that setter. Make the operating contract explicit: coherent
pair updates while disabled (or an atomic staged update), defined wrap-disable
behavior, and validation of the selected interval against the DAC limits.

Acceptance: use the generated IP for both signs around half-integers and full
integer boundaries, verify DAC conversion and quotient conversion separately,
and cover parameter changes. No converter simulation has been run locally.

## Precision budget: retain the current architecture for now

The user clarified that the unwrapped floating-point design was intentional
and real operation is not expected to exceed 256 flux jumps. Interpret that
as approximately +/-256 physical quanta of net excursion for this assessment;
if it instead denotes 256 multi-quantum wraps, include WrapMultiplier in the
excursion. It is the magnitude of the retained state that determines spacing,
not elapsed run time or the lifetime count of alternating wrap events.

With 24 significant binary digits, float32 spacing near a nonzero normal value
F is `2**(floor(log2(abs(F))) - 23)`. At exactly F=256*Q, illustrative results
are:

| Q (DAC codes per physical quantum) | F (DAC codes) | Float32 spacing (DAC codes) |
| ---: | ---: | ---: |
| 1,000 | 256,000 | 0.015625 |
| 4,000 | 1,024,000 | 0.0625 |
| 8,000 | 2,048,000 | 0.125 |

These were calculated and checked with Python float32 pack/unpack arithmetic,
not RTL simulation. For the standard frontend defaults and the cosim's 10 uA
quantum, the driver conversion gives Q=538 DAC codes; spacing at 256Q is
0.015625 DAC code. This is a default-configuration calculation, not a readback
of the live hardware settings. Initial offsets and powers-of-two boundaries
should be included when establishing the actual worst-case bound.

Recommendation revised: keep the current unwrapped-float architecture and
treat precision as an acceptance measurement, not a demonstrated defect or a
reason to redesign. It retains sub-DAC-code resolution over the stated range
and avoids separately managing fine feedback and cumulative flux state.
The remaining check is whether the smallest required per-visit correction is
resolved at the largest excursion. For example, at F=256*4000, repeated +0.01
DAC-code updates round away, while the spacing is 0.0625; a Python arithmetic
probe confirmed no movement after 1,000 such updates. This is a substantially
smaller deadband than integer feedback rounded every visit, but its impact on
the low-gain residual and noise still needs a loop test.

Compare equivalent plant points near 0 and +/-256 quanta at the lowest intended
gain, measuring residual, small-signal response and noise. Bounded fractional
state plus an integer flux count remains an alternative only if that test
exceeds the required error/noise budget or the expected excursion increases.

## Supporting changes and checks

- `Session.set_pid` in `operations/session/_setup.py:144-155` unconditionally
  requires PidD_Gain, although FP exposes P/I. Allow supported P/I writes and
  explicitly handle a requested unsupported D gain before FP tuning through
  this API.
- `accumValid` is accepted only in IDLE; the DAC FIFO overflow is unconnected.
  Add separate missed-visit and write-overflow diagnostics. Existing dropCount
  concerns PID-debug backpressure, not these control-path losses. Verify actual
  conversion/FSM/write latency against the minimum supported row schedule.
- Define direct-register I-disable/re-enable behavior. FP currently holds old
  SumAccum with positive-zero I; it does not clear on a raw I-coefficient change.
  The Python setter clears all state and therefore masks that distinction.

Implement and validate operating-point initialization, masked-row state, and
clipping recovery first. Add the converter/wrap boundary tests before comparing
closed-loop performance. The incremental PI law and absence of D need no change
solely for MCE compatibility.
