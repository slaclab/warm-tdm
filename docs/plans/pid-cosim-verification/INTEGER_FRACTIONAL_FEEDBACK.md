# Integer PID: retained fractional SQ1 feedback

## Purpose and scope

Design from the September 16, 2026 controller review, based on Warm TDM
`ef81760`, implemented in `AdcDsp.vhd` on the `43a5bee` working tree. Retain
fractional feedback between visits to each row so repeated sub-DAC-code
corrections can eventually move the DAC. Implementation details and the
reproducible regression command are recorded below. FPGA synthesis and system
acceptance are separate from the unit arithmetic checks.

Store full-precision SQ1 feedback per row. Seed it from the captured applied
DAC after a state clear, then use the retained value for each subsequent update,
quantizing only the DAC output. Keep the existing incremental PID equation,
sample-window accumulation and coefficient normalization. Apply the single
integer-quantum flux adjustment to full-precision feedback before the DAC clamp
and conversion. This does not change the error integral SumAccum or introduce another
integration stage.

The FP controller deliberately retains unwrapped floating-point feedback. Its
design is separate and remains intact; see [FP_REVIEW.md](FP_REVIEW.md) for the
recorded rationale and the user's expected 256-jump operating envelope. MCE
compatibility is not a requirement for either controller.

Related feature context: [Issue #70](https://github.com/slaclab/warm-tdm/issues/70)
and the [RTL regression framework, Issue #90](https://github.com/slaclab/warm-tdm/issues/90).
This document supplies design guidance; implementation and acceptance tracking
belong on the owning issue under [the workflow policy](../../WORKFLOW.md).

## Baseline behavior and evidence (before this change)

In `firmware/common/warm_tdm/rtl/AdcDsp.vhd`:

- `pidResult` has 23 fractional bits and is saved in the per-row PidResults RAM
  at lines 760-761. Its RAM output, `pidRamOut`, is not consumed by the controller.
- PREP_PID_S reloads `sq1Fb` from the captured 14-bit DAC at line 687.
- SQ1FB_ADJUST_S adds the correction and resizes it to
  `sq1Fb : sfixed(13 downto 0)` at line 769. The fraction is rounded away.
- `sq1FbFull : sfixed(31 downto 0)` also has no fractional bits and does not
  provide per-row feedback state for the next update.

A GHDL diagnostic on the baseline accumulator plus integer DSP fed each actual
DAC write back as the next visit's applied value, with I=D=0:

| Per-visit stimulus | Visits | Observed result |
| --- | ---: | --- |
| E=1, raw P=0.25 | 8 | PidResults stores 0.25 each visit; DAC stays unchanged |
| E=2, raw P=0.5 | 3 | DAC advances by one controller code each visit |

The first case encoded P as `1 << 21` in Q1.23 and read the fractional result
from PidResults RAM at 0x3000/0x3004. With the wrapper's inverted DAC encoding,
controller zero was DAC 8191; fractional-case writes all remained 8191, while
the whole-code control produced 8190, 8189, 8188. This confirms a fractional
correction record exists but fractional feedback does not accumulate.

The diagnostic passed under GHDL 6.0.0 / cocotb 2.0.1. Scratch files were
`/private/tmp/warm-tdm-pid-review/fractional_feedback_probe.py`,
`fractional_feedback.json`, and `fractional_feedback.log`; these are temporary,
not durable test assets. The checked-in fractional bench now covers this
stimulus and its intended new expectations. This evidence establishes
the baseline behavior, not validation of the change.

## Expected improvement: quantitative estimate

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

## Arithmetic

For each enabled row, let F be its saved full-precision feedback and delta its
current PID correction. The P/I/D equation, old SumAccum usage, derivative sign
and intermediate PID saturation remain unchanged:

```text
F = savedFeedback[row] if valid[row] else signed(appliedDAC)
candidate = F + delta
j = +1 if candidate > 7862 else -1 if candidate < -7862 else 0
F_next = clamp(candidate - j*Q, -8192, 8191)
nextDAC = roundNearestEven(F_next)
savedFeedback[row] = F_next
valid[row] = true
```

`Q` retains its existing signed 14-bit interpretation, and the existing flux
counter updates by j. There are only two feedback values: `sq1FbFull` is the
working and retained fractional state; `sq1Fb` is the integer DAC input/output
value. Add the PID correction, wrap the full value, clamp it, and convert it
once with nearest-even rounding. There is no separate integer wrap path.

This deliberately simplifies the baseline's clamp/round/wrap ordering:

- 8500.25 with Q=2000 becomes 6500.25, retaining its fraction instead of first
  clamping to 8191 and then shifting to 6191.
- A fractional excursion past +/-7862 wraps immediately; exactly +/-7862 does
  not wrap. The threshold no longer depends on a rounded DAC value.
- A half tie is rounded after the flux shift. For example, 7863.5 minus an odd
  Q=2001 gives 5862.5, whose DAC code is 5862. Separately rounding before the
  shift would give 5863.

The threshold value, one-quantum-per-visit policy, signed-Q interpretation and
flux-count arithmetic remain unchanged. Multi-quantum recovery is outside this
change. An excursion that one wrap cannot recover is clipped in both the saved
state and the DAC output, so discarded overrange values cannot wind up.

The unclipped candidate includes the complete retained feedback in the existing
directional I anti-windup check, which remains a conservative pre-wrap rail
check. Keep signed 18-bit SumAccum.

The addition expression keeps its carry and all 23 fractional bits. Its
anti-windup comparisons use the full expression; the feedback-update state
resizes directly into `sq1FbFull`, whose guard bit permits one flux adjustment
before the final DAC clamp. No `sq1FbCommand` or `sq1FbWrapped` temporary is
needed, and there is no three-operand addition after the MAC.

For example, starting at zero with +0.25 per visit and no clipping/wrapping:

| Visit | Saved full-precision feedback | Integer DAC coordinate |
| ---: | ---: | ---: |
| 1 | 0.25 | 0 |
| 2 | 0.50 | 0 |
| 3 | 0.75 | 1 |
| 4 | 1.00 | 1 |

The rounding residue R used in the quantitative estimates above is F minus the
applied integer DAC. It is useful for the error bound, but is not separately
stored in the implementation.

## Storage and lifecycle

`U_Sq1FbFullRam` is a `surf.AxiDualPortRam` with a three-cycle read,
using the same logical-row address and existing state-RAM wait. Each entry has
`sfixed(14 downto -23)` feedback plus a validity bit: 39 bits total, or 4,992
bits at 128 rows and 9,984 bits at 256 rows per DSP, before physical mapping.
The extra integer guard bit accommodates a correction beyond a DAC rail before
the flux adjustment. It does not enlarge the DAC's range or change the existing
flux-count limits. Saved feedback is clamped to [-8192, 8191].

Width audit: the data payload is 38 bits (sign, 14 integer magnitude bits and
23 fractional bits), representing `[-16384, 16384 - 2^-23]`. The RAM word is
39 bits including validity. For example, +/-8500.25 must survive until a
Q=2000 wrap brings it back to +/-6500.25. A `sfixed(13 downto -23)` working
value would saturate prematurely, losing part of that correction.

The largest positive signed Q is 8191. A positive correction exceeding the
38-bit range still exceeds the positive DAC rail after subtracting 8191, even
if it first saturates at `16384 - 2^-23`. Likewise, a correction below -16384
still falls below the negative DAC rail after adding 8191. A negative Q moves
these outlying values farther from the range. Thus saturating at the guard-bit
range cannot change the final DAC-clamped result for one signed 14-bit quantum.
The guard width must be reassessed if the design later allows multiple wraps
per visit or a larger quantum; it does not need the entire PID result range
under the current single-wrap rule.

Hardware selects XPM block RAM; GHDL uses the inferred model. The new read/write
AXI window is `0x7000 + 8*row`: bits 37:0 hold signed Q15.23 feedback, bit 38
is valid, and bits 63:39 read zero. Existing windows retain their addresses.
The Python driver exposes `Sq1FbFull` (`pr.Fixed(38, 23)`) and
`Sq1FbFullValid`, including per-row status links. Host edits require idle row
sequencing after any clear has completed; write the full value and mark it
valid to use it on the next visit, or invalidate it to adopt the captured DAC.
A running-loop 64-bit AXI read comprises two 32-bit transactions and is not
an atomic snapshot; use the debug stream for a coherent per-visit value.

PREP_PID_S loads the saved value or the initial
DAC seed; SQ1FB_ADJUST_S adds the correction; FLUX_JUMP_S shifts, clamps and
converts it once, then commits it with the enabled DAC command. No new multiplier or
FSM cycle is introduced. Synthesis must establish the actual BRAM mapping and
timing cost of this wider per-row state.

| Event | Feedback-state behavior |
| --- | --- |
| First enabled update after clear | Adopt that row's captured applied DAC, compute the update and mark state valid |
| Subsequent enabled update | Use and update the saved full-precision value |
| Masked-row visit | Hold existing state; do not initialize an invalid row |
| Global PID disabled | No feedback-state updates |
| StartRun, explicit ClearPidState, rising PID enable | Invalidate all rows with the existing clear sweep |
| Raw I-coefficient change | Follow the existing clear trigger and invalidate all rows |
| P/D changes, or normal I=0 operation | Preserve feedback state |
| Reset | FLL is disabled; rising enable clears the RAM before the first accepted update |
| Manual DAC reseeding | Clear PID state before resuming so the new applied DAC becomes the seed |

After initialization, an external DAC write by itself does not replace the
controller's saved feedback. This is an intentional difference from the baseline,
which adopted the captured DAC every visit. It is also why the initial proposal
to store only a rounding remainder was replaced by full feedback state during
implementation review: full state provides the requested precision directly,
with a single base-plus-correction addition and simpler arithmetic.

As before, the transport must deliver each DAC command before the row's next
sampled visit. FIFO overflow, failed writes or unexpected external DAC changes
are not reconciled by this state scheme.

PidResults RAM continues to report the current correction, with its 23 fractional
bits; DAC/readout formats and existing register offsets remain unchanged. The integer
`sq1FbFull` name now denotes the retained full-precision value backed by this
per-row RAM. Its previous integer-only, shared accumulation had no consumer
and is gone. Unlike FP's unwrapped `sq1FbFullFp`, the integer value receives
the same flux shift as the DAC, retaining local fractional precision. The
independent FP implementation is unchanged.

Keep the per-row PidResults RAM for debugging for now. It is a candidate for
later removal or reuse: the controller never consumes `pidRamOut`, and the
correction is already present in the PID-debug stream. Revisit this only with
the corresponding software register/RowPidStatus updates; per-row polling is
an existing diagnostic feature. The temporary `pidResult` calculation register
would still be required.

## Fractional feedback diagnostics

The fixed PID-debug format is now version 3 (type `0x01`, version `0x03`),
96 bytes including the 16-byte identity header. One 64-bit word is inserted
immediately after `pidResult`, at body byte 48 / frame byte 64. It contains
`sq1FbFull` **after flux wrapping and clamping, before DAC rounding**, with the
38-bit signed Q15.23 value sign-extended to 64 bits. This is in signed controller
DAC-code units, independent of output inversion. No validity bit is included.
For enabled rows it is the value committed to RAM; masked visits report the
computed value without committing it, like the existing `sq1FbEnd` diagnostic.
The word uses the existing `DATA_STREAM_FLUX_JUMP_0_S` cycle, adding no FSM state.
Version 3 also preserves the complete nine-bit flux count as a sign-extended
int32 in the following word; versions 1 and 2 transmitted only eight bits.

`PidDebug.from_numpy()` validates the version and exact length, preserves the
existing fields, and exposes `fields['sq1FbFull']` as an exact Python float in
DAC-code units. The live `PidDebugger` and its per-row views expose `Sq1FbFull`.
The offline StreamReader automatically retains the new field in its timeseries.
Version-1 integer captures (88 bytes) remain readable: the offline field is
absent and the live value is NaN because those captures contain no fractional
feedback. Version-2 captures retain their original full-feedback/eight-bit-count
layout in the decoder. Readout, FP PID-debug and waveform remain version 1.
See [the flux-jump review](FLUX_JUMP_REVIEW.md) for the counting, signed-readout
and quantum-conversion fixes and the retained −256..255 net-count limit.

## Reproducible regression checks

Run from the repository root, with GHDL and the cocotb test dependencies:

```bash
make rtl_import
.venv/bin/python -m pytest -q \
  tests/warm_tdm/adc_dsp/test_AdcDsp_fractional.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_bitexact_compare.py
.venv/bin/python -m pytest -q software/tests/test_pid_debug_formats.py
```

The whole-path fractional bench drives ADC samples through AdcAccumulator and
feeds actual DAC writes into subsequent visits. Explicit expected sequences and
exact rational arithmetic cover:

- Both DAC encodings, 8-row and 256-row RAM configurations, independent rows and
  the final address of the clear sweep.
- Positive/negative quarter-code corrections, half ties on odd/even codes, a
  1/64-code correction, and crossing a tie by one LSB at fractional bit 23.
- State clear, start-run, disable/enable, reset, I changes, masking and explicit
  initial-seed/manual-reseed behavior.
- Positive/negative flux wraps with odd/even Q, exact and fractional threshold
  crossings, half ties after wrapping, both DAC rails, clipping and reversal.
- Overrange commands recovered by one wrap (including the retained fraction),
  signed-Q extremes and corrections too large for even the largest positive Q.
- Fractional anti-windup and combined P/I/D arithmetic, including unchanged
  PidResults diagnostic readback.
- AXI full-feedback read/write, validity and clear behavior; real FIFO debug
  frames decoded by the production parser, including signed fractions, the
  23rd fractional bit, wraps, clipping and masked-row non-commit behavior.

The quarter-code regression failed on the baseline RTL: eight writes stayed at
the seed. Retaining feedback gives two codes of movement over eight visits, for
both signs. The 1/64-code example first moves on visit 33.

The regression has nine fractional-feedback cases each at
`ROW_ADDR_BITS_G=3, INVERT_SQ1FB_G=true` and
`ROW_ADDR_BITS_G=8, INVERT_SQ1FB_G=false`, five existing PID property cases,
and the historical-stimulus compare (11 writes). These are four pytest
parameterized configurations, with 24 cocotb cases total. No frozen reference RTL
or golden data was changed. All 24 cases passed on September 16, 2026 under
GHDL 6.0.0 / cocotb 2.0.1 with the AXI dual-port RAM and initial v2 debug
stream. The later v3 flux review and expanded checks are recorded in
[FLUX_JUMP_REVIEW.md](FLUX_JUMP_REVIEW.md) and PROGRESS.md. The
new 8-row debug case was rerun alone after correcting its standalone decoder
import; the other eight cases had already passed in the full run. The 256-row
configuration passed all nine together.

At that revision, the 16 host-format tests passed for v1/v2 frames, signed fractional
feedback, invalid lengths/versions, unchanged FP frames, and the live receiver
with a memory-store fake. Six existing cosim-check tests also pass (including
12 subtests). NumPy is included in the regression dependencies because the
RTL capture test calls the production decoder. Full PyRogue device-tree
construction was not exercised on this Mac (PyRogue is unavailable).
`feedback_width_boundaries` exercises the guard bit
and final clamp; `least_significant_fraction_bit` verifies the 23rd fractional
bit. The payload remains 38 bits with an explicit 39-bit RAM-width constant.
PidResults remains available for debugging, with possible later removal
documented beside its RAM instance.

The frozen pre-split golden remains unchanged. Its shared stimulus forces a new
applied DAC at every visit, which deliberately differs from the new saved-state
contract after initialization. The historical compare therefore keeps the
first three per-row seed checks and both overflow-rail expectations from that
golden, and specifies six independently calculated later writes for retained
feedback. It does not regenerate expected results from modified RTL. The new
actual-write feedback tests provide the fractional-state coverage.

Vivado 2024.1 resource/timing checks, the shortest supported row schedule, and
closed-loop residual/noise measurements require the FPGA/system environment.
Unit arithmetic checks do not establish those results; the historical cosim
lock and step-response captures predate retained feedback. Ongoing acceptance
belongs on the linked issue, not this design note.
