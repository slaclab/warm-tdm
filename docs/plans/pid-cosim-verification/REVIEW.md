# PID cosim review — 2026-09-15

## Scope and status

Review of `channelization` at `94215d62889d56ca4f15bca8ed72be59f06cd5c8`,
following AGENTS.md, the project Markdown documentation, and the current
firmware/software paths. The objective is to explain the observations in
PROGRESS.md and prioritize discriminating experiments. This is an investigation,
not a production fix or a new closed-loop acceptance result.

Two local GHDL counterexamples show that the existing nine-write golden test
does not establish general equivalence to the pre-split DSP. The feedback-capture
counterexample is the leading explanation for non-independent row behavior.
The large-error counterexample can explain part of the sample-window dependence.
Neither has yet been correlated with the failing VCS run.

Production RTL, software, and the checked-in golden were not changed. A temporary
accumulator copy was used to isolate the capture issue. The model changes called
"uncommitted" in PROGRESS.md are committed in the reviewed HEAD; that status
description is stale.

## Finding 1: feedback is captured before the new row's DAC value is visible

Source chain:

- `AdcAccumulator.vhd:122-125` captures `sq1FbDac` at `rowStrobe`.
- `FastDacDriver.vhd:352-356` registers `dacOutNext` into `dacOut` in response
  to that same strobe. Its new value is visible after the sampling edge.
- `ColumnFpgaBoard.vhd` connects that `dacOut` to DataPath's `sq1FbDacs`.
- `DataPath.vhd:386-414` delays timing and DAC readback through equivalent
  `SlvDelay` instances. Equal delay preserves the one-clock relative offset;
  it does not make the DAC update arrive before the strobe.
- `AdcDsp.vhd:679` uses the captured value as the starting feedback for the
  current row's correction.
- The pre-split DSP sampled feedback in `PREP_PID_S`, after accumulation
  (`golden_refs/presplit_rtl/AdcDsp.vhd:692`).

Diagnostic stimulus: enable DSP, set P/I/D and ADC error to zero, and drive
three different offset-binary DAC values one clock after their row strobes.
Keep each value stable through its sample window. Initial DAC value is 8192.
Observe actual mAxil writes through the existing capture/compare wrappers:

| Row | DAC during the row's samples | Pre-split write | Current write | Temporary firstSample capture |
| --- | ---: | ---: | ---: | ---: |
| 0 | 8483 | 8483 | 8192 | 8483 |
| 1 | 9029 | 9029 | 8483 | 9029 |
| 2 | 9575 | 9575 | 9029 | 9575 |

The current datapath copies the preceding row's feedback even with zero error
and zero gains. Moving just the capture into `WAIT_FIRST_SAMPLE_S` in a temporary
copy eliminates this counterexample. This identifies the capture-time change;
it does not constitute qualification of a proposed fix at every timing setting.

The existing `_pid_bitexact.py` stimulus holds `SQ1FB_DAC = 0x2000` throughout
all visits, so it cannot detect this difference. It also does not close the
feedback path by applying the observed DAC writes on later visits.

Likely implication: independent per-row feedback becomes coupled to visit
order. Uniform initial conditions can hide the problem until row errors or
setpoints differ. This fits correlated errors and unstable repeatability, but
does not by itself establish why rows 5–7 were the visibly worst rows.

## Finding 2: large accumulated errors wrap instead of saturating

The old DSP resizes its running sum into an 18-bit `sfixed` using the package's
saturating arithmetic. The new front end accumulates in 32 bits, then
`AdcDsp.vhd:617` takes only bits 17:0 and reinterprets them as signed. That is
modulo truncation, not saturation.

A second diagnostic drives constant +1000 ADC codes with the shared driver's
nominal 250-sample visit and P = 1/1024, I = D = 0. That driver actually produces
249 accumulated beats for this call, yielding a mathematical sum of +249000:

| Observable | Pre-split | Current |
| --- | ---: | ---: |
| Signed accumulated error | +131071 | -13144 |
| AccumError register's unsigned 18-bit pattern | 131071 | 249000 |
| SQ1 feedback mAxil write, offset binary | 8064 | 8205 |

The wrappers retain the DSP's default inverted-feedback convention; compare
the opposite correction directions rather than transferring these raw output
codes directly to the board's non-inverted configuration. The temporary
firstSample change leaves this second failure unchanged, separating the causes.

For a genuine 250-sample window, the positive 18-bit limit is reached at only
about 524 mean ADC codes, or 64 mV at the ADC input. At 20 samples the analogous
limit is about 800 mV. Thus shortening the window can remove a sign-reversing
overflow even when normalized loop gain is preserved. The earlier -93000
observation itself is within the signed range and does not require overflow.

Restoring equivalence requires deciding the intended accumulation semantics.
Clamping only the final 32-bit result does not reproduce sample-by-sample
saturation for waveforms that hit a rail and then reverse sign. Boundary
regressions should include those trajectories. Nonzero-baseline subtraction
also deserves coverage: the new expression subtracts two 14-bit signed operands
before resizing, whereas the old fixed-point subtraction can grow a bit.

## Qualifications to the current progress interpretation

### P/I structure and sample count

The intended per-row recurrence is `u_next = u + P*E + I*S`,
`S_next = S + E`. P-only already integrates the error at the actuator; I-only
adds a second integration and lacks damping in the local static-plant model.
The earlier [coefficient derivation](../sensor-wafer-model/PID_COEFFICIENTS.md)
already explains this and gives a stable PI region. I-only failure does not
show that an additional small I term with P is intrinsically unusable.

With normalized P gain K, `P_raw = K/N`; therefore `P_raw*sum(error)` is
approximately `K*mean(error)`. Going from 250 to 20 samples should not reduce
nominal P loop gain by 12.5x. It changes overflow exposure and the sample-window
placement: with 400 cycles and a 100-cycle end offset, the window changes from
50–300 to 280–300. Those are separate hypotheses to test.

The recorded descending slope supports positive P for the current board
configuration. Do not transfer signs from another operating branch or an
inverted DAC convention. Likewise, 8.48 uA cannot be declared intrinsically
unlockable from the supplied sweep: it was measured on a monotonic slope.
Mid-slope is a sensible reproducible seed; changing several settings together
does not establish that moving the seed alone cured lock failure.

### Residual error is not established as the ADC quantization floor

The SURF ADC model uses 14 bits across -1 to +1 V, matching the
[AD9681 specification](https://www.analog.com/en/products/ad9681.html).
One ADC LSB is about 122 uV. An accumulated error of 1000 over 20 samples is
50 mean ADC codes, approximately 6.1 mV, not one ADC LSB.

Actuator-code quantization, rounding away fractional P corrections, wrong-row
feedback, and dynamic limit cycles can impose larger residuals. With normalized
P = 0.05, corrections below roughly 10 mean ADC codes round below half a DAC
code; that is a controller deadband, distinct from ADC resolution. Characterize
the observed floor with raw sample/code traces rather than assigning its cause.

### Open-loop measurement must stay live

With `PidEnable = false`, integer AdcDsp does not process ordinary
`accumValid` events or refresh its per-row AccumError RAM; see the gating at
`AdcDsp.vhd:597-602`. "PID off" register readings can therefore be stale unless
that phrase means enabled DSP with zero coefficients.

For diagnostics, distinguish those modes explicitly. Keeping the DSP enabled
with zero coefficients provides telemetry, but until finding 1 is resolved it
does not preserve distinct row feedback settings. Raw waveform capture or
direct simulator accumulator traces are alternatives that avoid that writeback.

The integer `dropCount` increments in IDLE when PID-debug FIFO pause is asserted.
It is not a direct count of all missed accumulator results. Verify visits and
DAC writes directly instead of interpreting an unchanged count as proof of no
lost PID work.

### Repeatability and fixture state

`cosim_pid_lock.py` does not configure row order, row map, FAS on/off currents,
SA/SQ1 bias tables, or the column selection. `--rows` selects monitored/optionally
seeded entries, not the active timing schedule. Feedback reseeding is optional.
The script sleeps 0.4 seconds after EndRun without confirming completion and
compares snapshots at wall-clock seconds rather than completed row visits.

Also, writing per-row feedback RAM while stopped does not itself apply that
value to the physical DAC. The subsequent SA null can therefore use an analog
state left by a prior run rather than the newly seeded table. Make the stopped
analog state explicit and verify actual DAC outputs before nulling.

`SetCosimTunePoints` still contains earlier settings (FAS 163 uA, SQ1 bias
100 uA, SA feedback 64.8 uA) rather than all the latest recorded fixture values.
It should not be assumed to reproduce the live setup described in PROGRESS.md.

FluxQuantum is important for deliberate wrap tests, but the integer code only
applies its correction beyond about +/-7862 signed DAC codes. If a run stays
inside those thresholds, setting FluxQuantum cannot explain improved local
small-signal stability. Zero quantum also does not explicitly disable jump
count updates when a threshold is crossed.

## Proposed next experiments, in order

1. **Confirm feedback association in the full timing/DAC chain.** Use distinct
   row values and zero gains. Trace logicalRow, rowStrobe, actual dacOut,
   delayed DAC readback, accumOut.sq1FbDac, and each mAxil write. Include the
   first visit and sequence wrap. Then exercise an isolated capture-time fix
   against both the new counterexample and the original golden/property tests.
2. **Expand arithmetic equivalence coverage.** Positive/negative 18-bit limits,
   crossing a limit and returning, baseline extremes, and sample-count
   boundaries. Resolve the intended saturation contract before treating Layer 1
   as complete. Independently assert actual sample count in the stimulus.
3. **Make one run reproducible.** Establish/read back the complete fixture,
   confirm timing stopped, initialize actual analog outputs for nulling, seed
   every active feedback row, clear PID state, and capture a fixed number of
   complete row visits with tagged PID-debug records. Preserve configuration
   and build identity with the capture.
4. **Distinguish row identity from visit position.** Compare one-row schedules
   for rows 0 and 6, then `[0, 6]` and `[6, 0]`, then a permutation of 0–7.
   Move the physical row-map assignment independently of the logical label.
   A fault following the physical line suggests FAS/harness behavior; one
   following the predecessor or sequence position suggests timing/state
   association; one following the logical label suggests RAM/mask addressing.
   Check physical FAS currents at the sampling window and all unscheduled lines.
5. **Measure each row's local plant gain before choosing P.** With feedback
   association correct, use +/-2, +/-4, and +/-8 DAC-code perturbations around
   a known point. Compare mean ADC errors per visit and choose conservative
   P-only poles using `z = 1 + g*K` (g in ADC codes per controller DAC code).
   Compare short and long windows at fixed normalized gain, then move a fixed
   short window through the row to separate timing from gain/overflow effects.
6. **Run the centerpiece test.** After reproducible lock, apply a modest TES
   step; measure settling in row revisits, residual, per-row independence,
   wraps, and missing telemetry. Then repeat for FP and later with variation.

Before FP comparison, inspect two concrete differences: `Session.set_pid`
currently requires `PidD_Gain` even though FP exposes only P/I; it logs and
returns before writing gains. Also, FP clears its own Sq1FbFull RAM at StartRun
and does not initialize it from `accumIn.sq1FbDac`. Verify whether the first FP
update preserves the desired tuned starting point; integer-style DAC-table
seeding alone does not establish that.

## Local validation and artifacts

- GHDL 6.0.0, LLVM backend; Python 3.13.2; cocotb 2.0.1.
- Diagnostic probes compiled the current RTL and frozen pre-split RTL into
  separate libraries using the existing cocotb wrappers and SURF allowlist.
  Both completed and produced the discrepancies above. A third run used only
  the temporary firstSample-capture change and removed finding 1's discrepancy.
- The existing `compare_to_presplit_golden` test was rerun and passed all nine
  expected writes without changing the golden. Its passing result alongside
  these counterexamples demonstrates the limits of the current stimulus.
- All six `WaferModelTb` tests passed with the current sinusoid/FAS changes.
  This is focused model coverage, not closed-loop or physical validation.
- Scratch scripts, JSON results, and logs are in
  `/private/tmp/warm-tdm-pid-review/`. The stimulus and observed values above
  preserve the essential reproduction if temporary files are removed.
- No VCS GroupTb lock/step run, synthesis, or hardware testing was performed
  during this review. Hardware and integration acceptance remain open.
