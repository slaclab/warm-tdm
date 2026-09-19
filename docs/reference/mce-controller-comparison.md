# MCE feedback-law comparison — 2026-09-16

## Scope and result

Compared Warm TDM `ef81760` with the public UBC MCE documentation and firmware
at `99c68e29f1f415c2fbaf6f7cf2f4276c5812c36a` (2025-01-31). This is a source
and equation review, not an MCE simulation or a controller modification.

The sampling strategy is similar: co-add baseline-subtracted ADC samples within
a row visit and apply new feedback on that row's next visit. The controller
recurrence differs: MCE directly assigns its PID sum as the new feedback,
whereas Warm TDM adds its PID sum to the previous feedback. Consequently,
MCE I-only resembles Warm TDM P-only in ideal arithmetic. The complete PID
controllers are not equivalent merely by relabeling gains.

This distinction already exists in the frozen pre-split Warm TDM reference
(`golden_refs/presplit_rtl/AdcDsp.vhd:774`); it was not introduced by the recent
accumulator split or its fixes.

## Sources

- [UBC MCE Readout Card Technical Description, revision 2.5, page 10,
  equation 1](https://phas.ubc.ca/~mce/mcedocs/hardware/tech_description/SC2_ELE_S582_501_readout_card_description.pdf#page=10)
  specifies the co-added error, direct PID feedback calculation, and division
  by 4096 before applying the DAC command.
- [MCEWiki: Data mode](https://e-mode.phas.ubc.ca/mcewiki/index.php/Data_mode)
  documents the later leaky-P extension.
- [MCEWiki: MCE commands](https://e-mode.phas.ubc.ca/mcewiki/index.php/MCE_commands#pterm_decay_bits)
  documents `pterm_decay_bits` and its default setting.
- Public firmware:
  [fsfb_processor.vhd](https://github.com/multi-channel-electronics/mce_firmware/blob/99c68e29f1f415c2fbaf6f7cf2f4276c5812c36a/cards/readout_card/fsfb_calc/source/rtl/fsfb_processor.vhd#L315),
  [fsfb_proc_pidz.vhd](https://github.com/multi-channel-electronics/mce_firmware/blob/99c68e29f1f415c2fbaf6f7cf2f4276c5812c36a/cards/readout_card/fsfb_calc/source/rtl/fsfb_proc_pidz.vhd#L448),
  and [dynamic_manager_data_path.vhd](https://github.com/multi-channel-electronics/mce_firmware/blob/99c68e29f1f415c2fbaf6f7cf2f4276c5812c36a/cards/readout_card/adc_sample_coadd/source/rtl/dynamic_manager_data_path.vhd#L313).

The public repository was cloned to `/private/tmp/warm-tdm-mce-comparison/`
and the actual source was inspected. GitHub page retrieval through the browser
failed for individual source files; the successful git clone supplied them.

## Equations

Let `E[n]` be the baseline-subtracted ADC sum for visit n to one row, and
`S[n] = S[n-1] + E[n]`. Ignore arithmetic limits, quantization, flux wrapping,
and exceptional reset/disabled states for the following comparison.

MCE with the P-decay extension disabled:

```text
u[n+1] = (gainp * E[n]
          + gaini * S[n]
          + gaind * (E[n] - E[n-1])) / 4096
```

Source confirmation:

- `dynamic_manager_data_path.vhd:313-316` forms the current integral from
  current co-add plus previous integral, subject to its clamp.
- Lines 371 and 393-398 form current-minus-previous error and pass the current
  integral to the feedback calculator.
- `fsfb_proc_pidz.vhd:325-337` selects P, I, and D operands; lines 454-472 and
  638-646 sum their products.
- `fsfb_processor.vhd:315-320` selects that result directly in lock mode.
  The previous-feedback input is used by the separate ramp path.

Warm TDM integer path, with lowercase gains denoting its raw coefficients:

```text
delta[n] = p * E[n] + i * S[n-1] + d * (E[n-1] - E[n])
u[n+1]  = u[n] + delta[n]
S[n]    = S[n-1] + E[n]    # when I is enabled and integration is permitted
```

Relevant Warm TDM lines in `firmware/common/warm_tdm/rtl/AdcDsp.vhd`:
682 loads the previous sum; 712-724 select I and D operands; 751 updates the
sum; 769 adds the correction to the current row's feedback. With I zero, the
stored sum is explicitly cleared. The FP path also retains the extra feedback
accumulation (`AdcDspFp.vhd:740-744` starts its FMA with previous feedback).

The N-sample co-add is a finite measurement window in both systems. It is not
the source of the additional integration across visits in Warm TDM.

## Consequences and qualifications

1. **I-only terminology.** For MCE, subtracting consecutive I-only commands
   yields `u[n+1] - u[n] = gaini/4096 * E[n]`. This is the ideal recurrence of
   Warm TDM P-only. Warm TDM I-only instead adds an accumulated error to an
   already accumulated output.
2. **P history option.** Later MCE firmware replaces the P operand with
   `q[n] = E[n] + b*q[n-1]`, with `b = 1 - 2**(-k)` and
   `k = pterm_decay_bits`. The default k=0 gives b=0 and ordinary P. This
   optional leaky history does not add the complete PID result to the previous
   command.
3. **I timing and D sign.** MCE uses the sum including the current visit;
   Warm TDM integer uses the prior sum. MCE's D operand is current-minus-previous;
   Warm TDM uses previous-minus-current. Physical polarity still depends on
   DAC convention and plant slope.
4. **Fractional corrections.** MCE retains the error integral and calculates
   a wide feedback result before DAC scaling. Warm TDM integer P-only starts
   each visit from the 14-bit applied DAC value and rounds the new command to
   `sfixed(13 downto 0)`. Sub-DAC-code corrections are not retained by that
   feedback path. A repeated sub-half-code correction can therefore produce
   a deadband in Warm TDM even though ideal MCE I-only would eventually move.
   The diagnostic `sq1FbFull` signal does not supply the next integer feedback
   starting point. This qualification is separate from the sample averaging.
5. **Numeric gains are not directly portable.** MCE applies its integer gains
   to co-added errors with a 4096 divisor. Warm TDM raw gains use 23 fractional
   bits, and its user-facing normalized gains additionally incorporate N.
   ADC/DAC physical scale, error polarity, and revisit period must also match.

Thus the earlier advice that Warm TDM P-only is a sensible FLL starting point
stands, but it does not establish full numerical equivalence to MCE I-only.

## Floating-point comparison and fractional-state check

Follow-up review compared `AdcDspFp` against the same two implementations.
The user clarified that loop performance, rather than exact MCE compatibility,
is the objective. No controller change has been selected or implemented.

### Where the fractions go in AdcDsp

`pidResult` has 23 fractional bits, and the per-row PidResults RAM saves those
bits (`AdcDsp.vhd:760-761`). However:

- `pidRamOut` is connected to that RAM's system output but is never consumed
  elsewhere in the RTL. The stored correction is available for diagnostics,
  not carried into the next control update.
- At line 687, `sq1Fb` is loaded from the captured 14-bit DAC code.
- At line 769, the fractional correction is added and resized to
  `sq1Fb : sfixed(13 downto 0)`, which has no fractional bits.
- The separate `sq1FbFull : sfixed(31 downto 0)` also has no fractional bits.
  It is not a per-row feedback RAM and does not supply the controller's next
  starting value. The integer data stream reconstructs unwrapped feedback from
  the DAC command and flux-jump count instead.

Thus AdcDsp retains a fractional *correction record*, but not fractional
*feedback state across row visits*. A wide sfixed register only contains
fractions when its low index is negative.

A GHDL probe on the actual current accumulator + DSP confirmed this distinction.
It used one row, I=D=0, one accumulated ADC sample per visit, and fed each observed
DAC write back as the next visit's applied value:

| Stimulus | Visits | Error | PidResults RAM | Observed DAC writes |
| --- | ---: | ---: | ---: | --- |
| raw P=0.25, ADC sample=1 | 8 | 1 each visit | 0.25 each visit | 8191 on every visit |
| raw P=0.5, ADC sample=2 | 3 | 2 each visit | one-code correction | 8190, 8189, 8188 |

The wrapper uses inverted DAC encoding: code 8191 is controller zero and
decreasing DAC codes correspond to increasing controller values. The second
case is a positive control proving that updates are live and previous writes
are carried forward. The fractional result was read directly from RAM at
0x3000/0x3004; the instantaneous PidResult debug register is repurposed later in
the pipeline and is not the right place to sample this correction after drain.

Probe: `/private/tmp/warm-tdm-pid-review/fractional_feedback_probe.py`;
runner: `run_probe.py current fractional_feedback_probe` in that directory,
using the repository `.venv/bin/python`. Result JSON and log are
`fractional_feedback.json` and `fractional_feedback.log`. GHDL 6.0.0 / cocotb
2.0.1: one diagnostic test passed, including all eight fractional visits and
three whole-code control visits. Production RTL and checked-in tests were
unchanged.

### How AdcDspFp differs

The FP path reads per-row `sq1FbFullRamOut` at line 708, uses it as the addend
of the P FMA at lines 740-744, adds `iCoef * sumAccumFp` at lines 766-770, and
writes the resulting unwrapped `sq1FbNewFp` back at lines 927-928. Conversion to
an integer DAC value is a separate output path and does not replace this state.

Ignoring finite arithmetic, limits, and wraps:

```text
F[n+1] = F[n] + p*E[n] + i*S[n-1]
S[n]   = S[n-1] + E[n]        # subject to anti-windup / I-enable behavior
```

This is the same incremental PI control law as integer AdcDsp with D=0, but
with a different retained feedback state. It is not the MCE absolute PI law.
Repeated quarter-code corrections are expected to advance FP state by
0.25, 0.50, 0.75, 1.00, etc. even while individual DAC writes repeat; this
expectation is from source/arithmetic, not a local FP-IP simulation result.

| Property | MCE | AdcDsp | AdcDspFp |
| --- | --- | --- | --- |
| Controller output | Absolute PID sum | Previous applied DAC + PID correction | Previous unwrapped float feedback + PI correction |
| State allowing sub-DAC corrections to accumulate | Running error integral before gain/scaling | No fractional feedback carry in P-only | Per-row float32 unwrapped feedback |
| I operand | Sum including current error | Previous sum | Previous sum |
| D operand | Current minus previous error | Previous minus current error | No D |
| Error used for arithmetic | 32-bit co-add | Final sum saturated to signed 18 bits | Full shared 32-bit sum converted to float32 |
| Integral state | 32-bit integer, configurable sticky clamp | Signed 18-bit, saturating and conditional integration | Float32, conditional integration |
| DAC wrapping | Threshold/count correction of absolute result | Threshold near +/-7862, at most one quantum per update | Recompute quotient from unwrapped feedback and subtract whole quanta |

Other FP differences that matter for a fair performance comparison:

1. **Startup:** StartRun, explicit clear, and enabling the loop clear the FP
   feedback RAM to zero. `accumIn.sq1FbDac` is unused in AdcDspFp. The integer
   loop starts each update from the applied DAC. Identical DAC-table seeds
   therefore do not establish identical controller initial conditions.
2. **Anti-windup:** integer AdcDsp tests the proposed command against DAC limits
   before flux wrapping; FP tests the converted wrapped command after wrapping.
   FP still commits unwrapped feedback when its DAC output clips. These paths
   cannot be assumed equivalent under large excursions or a mis-sized quantum.
3. **I disabled:** integer RTL zeros SumAccum; FP holds the old SumAccum.
   Integer RTL also clears state on a raw I-coefficient change; FP RTL does not
   have that same coefficient-change trigger. Software clear commands can mask
   these differences, so test direct writes and operational APIs separately.
4. **Precision grows coarser with unwrapped magnitude:** FP retains fractions
   within its float32 resolution, not with a constant number of fractional
   bits. At magnitude 2^23 DAC codes the spacing is one code; smaller increments
   can then disappear despite wrap keeping the physical DAC near zero. Test
   the largest expected net excursion as well as local lock. The user later
   clarified an expected bound of 256 flux jumps; the quantified assessment in
   [FP_REVIEW.md](../design/controllers/floating-point.md) favors retaining the present architecture and
   verifying its precision margin, rather than redesigning it speculatively.
5. **Pipeline timing:** FP serializes several FMA and conversion operations.
   It needs more time per update than the integer path. Check that every
   enabled row's DAC write arrives before its next visit at the shortest
   required schedule; nominal arithmetic agreement alone is insufficient.

### FP conversion rounding is inconsistent with its comments

`Fp2Int.xci` selects Floating-Point Operator 7.1 `Float_to_fixed`, single to
Int32. The RTL and FP plan call this truncation toward zero. However,
[AMD PG060, Rounding Modes, printed page 6](https://docs.amd.com/api/khub/documents/ym1A7qsltTGP_saZFTrikQ/content)
specifies round-to-nearest for float-to-fixed conversion. There is no explicit
round-toward-zero override in the checked-in XCI.

Based on that IP contract, `J = round(F/Q)` and `W = F-J*Q` would wrap near
half-quantum boundaries into approximately [-Q/2, Q/2], instead of the documented
truncate-to-zero scheme's approximately (-Q, Q) range. Either interval may be
intentional, but the implementation expectation must be made explicit. Verify
the actual generated IP around positive and negative half-integers and integer
boundaries under VCS before claiming the comments describe its behavior.
The same IP also performs final DAC conversion.

FP and MCE were reviewed statically; neither was simulated in this follow-up.
The new runtime evidence applies to integer AdcDsp only.

### XCI configuration follow-up

Inspected the complete `firmware/common/warm_tdm/ip/Fp2Int/Fp2Int.xci`, including
its generated model parameters, rather than relying on the RTL comments:

| XCI field | Value |
| --- | --- |
| component_reference / ip_revision | xilinx.com:ip:floating_point:7.1 / 18 |
| Operation_Type | Float_to_fixed |
| A_Precision_Type | Single |
| Result_Precision_Type | Int32 |
| C_Result_Fraction_Width | 0 |
| Generated C_HAS_FLT_TO_FIX | 1 |
| Generated C_RESULT_WIDTH / C_RESULT_FRACTION_WIDTH | 32 / 0 |
| Generated C_HAS_OPERATION | 0 |
| C_Latency | 2 |
| Runtime SWVERSION | 2024.1 |

No rounding or truncation parameter appears anywhere in the XCI. PG060's
Rounding Modes section specifies nearest-even for most operators and explicitly
includes float-to-fixed; its user-parameter table does not offer a rounding-mode
selection. The separately named accumulator operator uses toward-zero rounding,
but this instance is a converter, not that accumulator operator. Zero output
fraction bits specifies the result format, not a truncation policy. The
configuration and documented contract therefore support nearest-even, rather
than an unobserved truncation setting. No generated Fp2Int simulation products
were found under the local `firmware/build` directory, so this remains a
configuration/documentation conclusion pending the proposed IP boundary test.

### Integer fractional-feedback change assessment

The dedicated [integer fractional-feedback design](../design/controllers/integer-feedback.md)
records the implemented arithmetic, per-row state lifecycle and GHDL checks.
The implementation stores full-precision feedback and seeds it from the applied
DAC after a clear; the original rounding-remainder proposal below is historical.
The earlier comparisons in this document describe the baseline integer RTL,
before retained feedback was added. The following preserves the original
assessment summary.

This is a localized state/arithmetic change, not a new controller design. A
small per-row signed rounding-remainder RAM would retain the existing applied-
DAC starting point and the diagnostic meaning of PidResults. For each enabled
visit, in signed controller coordinates:

```text
candidate = appliedDAC + remainder[row] + pidCorrection
limited   = clamp(candidate, DAC_MIN, DAC_MAX)
quantized = roundNearestEven(limited)
remainder[row] = limited - quantized
nextDAC   = existingIntegerFluxWrap(quantized)
```

Clamping before remainder extraction avoids retaining a large discarded
overrange command as if it were a fractional remainder. The proposed clamp
placement preserves the current saturate-before-flux-wrap ordering; it does
not attempt to redesign that ordering. The anti-windup command calculation
must include the old remainder too. An in-range integer-quantum flux wrap does
not change the fractional remainder.

`sfixed(0 downto -23)` provides a sign bit and 23 fractional bits and can hold
both +/-0.5 ties. That is 24 stored bits per row (6,144 bits per 256-row DSP),
plus RAM/control and arithmetic overhead; physical resource mapping and timing
require synthesis. No new multiplier is required. Read the RAM alongside the
existing per-row state, clear it with the existing PID-state clear sweep, and
commit only for enabled updates. Define clearing on row masking/manual DAC
re-seeding so a stale remainder is not unexpectedly restored. PidResults RAM
should continue recording the current correction rather than silently changing
its software-visible meaning.

Widening sq1Fb alone would fail because PREP_PID reloads it from the integer
DAC each visit. Conversely, feeding the previous full pidResult back in would
reapply its whole-code correction. The required new state is the residual of
the accumulated command, not the previous correction.

Meaningful verification would cover repeated positive/negative sub-code
corrections and half ties, alternating rows, reset/enable/mask behavior with a
nonzero DAC seed, positive/negative flux wraps, and clipping/recovery. Preserve
the old golden as a historical reference; fractional-carry cases intentionally
change behavior and need an independently specified new expectation. Existing
row-coupling/overflow checks should still be exercised. See the dedicated design
note for the subsequent implementation and regression coverage.

## Next decisions and validation

Use measured loop performance to choose any changes. MCE compatibility is not
a requirement. Establish fractional-state behavior, matched initial conditions,
and the FP conversion/wrap contract before interpreting an integer-versus-FP
lock comparison.

An isolated controller comparison should first use prescribed per-visit errors
(constant, impulse, and sub-DAC-code corrections), with the feedback writes
carried into subsequent visits. Verify reset/seed behavior and arithmetic
precision separately from the nonlinear wafer model.

If MCE semantics are desired, two mathematical implementations are available:

- Directly compute the absolute PID command from current error, current
  running sum, and current-minus-previous difference.
- Use its equivalent incremental form (ordinary P, fixed gains):
  `delta = Kp*(E[n]-E[n-1]) + Ki*E[n]
  + Kd*(E[n]-2*E[n-1]+E[n-2])`.

These are algebraically equivalent only with consistent initial conditions and
ideal arithmetic. A real implementation must preserve suitable fractional
state and explicitly define the tuned starting point, sum limits/anti-windup,
and unwrapped feedback versus flux-jumped DAC state. Simply removing the
previous-feedback addition would leave the existing I timing, D sign, and
startup conventions unresolved.

No RTL, software, or golden references were changed for this comparison.
