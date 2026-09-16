# FP seed fix and merged-branch review — 2026-09-16

## Scope and conclusion

Reviewed `b37ff8c` after fetching and fast-forwarding `channelization`. The new
FP implementation is `f6f1e55`; `1a1bfe5` records its cosim result. Also checked
the integer property tests merged since the retained-feedback commit `4248929`.
This review changes documentation only; it does not fix the findings below.

The FP startup fix addresses item 1 in [FP_REVIEW.md](FP_REVIEW.md): the first
post-clear visit now adopts the applied DAC instead of using feedback zero.
The reported cosim result is useful evidence for that fix. It does not complete
the outstanding masking, saturation, conversion-boundary or step-response
checks. No new defect in the normal enabled-row seed conversion was found by
source inspection. Generated-IP behavior was not independently simulated here.

## What the fix does

- StartRun, explicit clear and the rising FLL-enable edge write `0x7FC00000`
  (a NaN sentinel) into each row's full-feedback RAM.
- Each accepted visit captures `accumIn.sq1FbDac`. If the row's RAM still has
  the sentinel, `SEED_CONVERT_S` converts the decoded signed DAC value through
  the existing Int2Fp core before launching the PI calculation.
- Subsequent visits use retained unwrapped float feedback. The PI arithmetic,
  wrap calculation, register map and FP debug format are unchanged.
- The first visit has an additional conversion wait; steady-state visits do
  not. Minimum-row-period qualification must include that first-visit latency.

The input conversion sign-extends the 14-bit result of `convOffsetBin`, which
is identical to the integer controller's function and is also used for DAC
output encoding. A Python arithmetic check exhaustively round-tripped all
16,384 codes under both inversion settings. This checks the mapping, not the
Xilinx converter or the new FSM's runtime behavior.

## Findings

### 1. Merged integer regression has an obsolete feedback assumption

`tests/warm_tdm/adc_dsp/test_AdcDsp.py:413-435`, added in `888762f`, drives three
visits with external feedback 7860, error 50, P approximately 1, and Q=500. It
expects one jump per visit. After `4248929`, that external feedback only seeds
the first visit: saved feedback is approximately 7410, 7460, 7510, so the correct
final count is one. GHDL reproduced **expected 3, got 1**; the other seven cases
passed. This is an integration failure in the test stimulus/expectation, not
evidence that retained feedback is broken.

Update the repeated-crossing test to drive enough actual correction to cross
on each visit and check the resulting saved feedback as well as the count.
The dedicated `test_AdcDsp_flux.py` already exercises retained-state wrapping.

### 2. FP startup behavior still lacks a targeted automated regression

`f6f1e55` changes only RTL; the FP unit bench was not updated. Its
`drive_accum` always supplies raw DAC code zero, which the default inverted
encoding now decodes to **+8191**, not signed feedback zero. Its P-response
check asserts only `sq1_new != 0`, which can pass from the seed alone even if
the proportional correction is missing. It also omits `FrameHeaderPkg.vhd`
from its explicit source allowlist, in addition to the previously documented
vendor-simulator runner blocker.

Before treating the unit bench as qualification, repair its DAC encoding and
source/runner setup. Check exact seed-plus-correction results, zero gains,
positive/negative seeds, independent rows, both polarities, all clear paths,
subsequent retention and first-visit latency with the generated IP.

### 3. The reported P-sign difference has no demonstrated RTL explanation

The new progress entry says the float datapath sign differs. Both controllers
receive the same accumulator, add `P*error` to feedback, and use identical DAC
polarity conversion. The shared gain normalization divides by a positive sample
count and does not invert sign. The source therefore does not establish an
intrinsic reversal between integer and FP controllers.

The reported positive FP gain remains an observation, but its cause is open.
Measure error versus signed DAC feedback around each *actually applied*
operating point, including FP's startup wrap; record raw coefficient readbacks,
sample count, Q, reciprocal and amplifier inversion. Then capture a controlled
disturbance and recovery. A small residual at P=0 establishes a good initial
null, not active rejection of a disturbance. These measurements distinguish a
plant/model operating-point difference from gain/configuration differences.

### 4. Keep the startup flux count consistent with unwrapped state

The suggested cosmetic pre-wrap of `sq1FbFull` in the progress notes would
change the primary readout reference. For example, full feedback 377 and Q=538
give J=1 and local feedback -161; `-161 + 538 = 377` preserves the chosen full
feedback. Replacing full feedback with -161 to force J=0 shifts the primary
output by a quantum. Keep the existing behavior unless changing that reference
is explicitly intended and accounted for. J is the current wrap quotient, not
necessarily a count of physical events since enable.

### 5. Earlier FP state/configuration issues remain open

These predate the seed fix; see [FP_REVIEW.md](FP_REVIEW.md) for the assessment:

- `RAM_WRITE_S` still commits feedback, integral and flux count for masked
  rows, while the DAC write is gated by `rowEnabled`. A masked first visit can
  now consume the seed sentinel and retain unapplied corrections. Seed/commit
  on the first enabled visit and hold control state while masked.
- DAC clipping still leaves the unwrapped feedback command unchanged in RAM;
  P-only state can wind up when wrapping is disabled or the interval is too
  large. Test both rails and reversal without discarding valid unwrapped signal.
- `Session.set_pid` still requires absent `PidD_Gain` on a PI-only group.
- The FP quantum setter still uses the old absolute-DAC conversion, writes
  Q/reciprocal separately, and does not refresh the reciprocal when Q becomes
  zero. The integer driver's period-conversion fix has not reached this path.

## Validation and next steps

Local checks at `b37ff8c`:

```bash
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp/test_AdcDsp.py -q
# GHDL/cocotb: 8 cases, 7 pass, 1 fails as described above.

cd tests/sim_build/warm_tdm/adc_dsp/adcdsp_accum_pid_v1
ghdl -a --std=08 -fsynopsys -frelaxed-rules -fexplicit --work=warm_tdm \
  ../../../../../firmware/common/warm_tdm/rtl/AdcDspFp.vhd \
  ../../../../../firmware/common/warm_tdm/wrappers/AdcDspFpCocotbWrapper.vhd
# Pass, using the libraries compiled by the integer test.
# Analysis only: no FP IP elaboration or functional simulation.
```

The reported FP cosim lock and residual range were read from `PROGRESS.md`, not
reproduced locally. No Xilinx FP runtime, Vivado 2024.1 synthesis/timing, or
hardware acceptance was available in this review.

Recommended order: reconcile the integer test, add precise FP startup/masking
coverage and fixes, repair `set_pid`, then measure local plant gain and capture
FP step-up/step-back recovery at fixed visit counts. Preserve the unwrapped-FP
architecture; this review supplies no reason to replace it.
