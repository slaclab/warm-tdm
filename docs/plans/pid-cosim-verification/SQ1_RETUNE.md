# SQ1 retune investigation — September 18, 2026

## Scope and status

Investigate the reported flat/ramping SQ1 and FAS cosim sweeps and the failure
to carry a static ADC null into muxed PID operation after the nominal SQ1
period changed to 23 uA. Controller acceptance remains on #70; this record
does not establish GroupTb lock or replace its acceptance checks.

The cold model passes a focused nominal-period regression. The full-board
failure remains unresolved. No production seed, amplifier, or PID change is
justified by treating the direct-model currents as DAC commands without
checking the conversion and the applied operating state.

## Confirmed findings

- FAS select near 150 uA makes the FAS resistive and exposes SQ1. At 0/300 uA
  the FAS shunts SQ1. The existing 163 uA seed is near the selected extremum.
  The old contrary note in `cosim-tuning-settings.md` was stale, including its
  resistance estimates from before the row-FAS critical-current increase.
- With standard `FpgaBoardColumnFebChannel` defaults, the SQ1-bias DAC tops
  out near 76.87 uA in software units. The present FEB/harness model delivers
  about 75.95 uA Norton current at that code. Asking for 100 uA saturates the
  DAC; directly driving `DetectorModuleSim` with 100 uA bypasses that limit.
- The standard software SQ1-feedback resistance is 15,779.4 ohm, while the
  present FEB/harness uses 16,158.8 ohm: `ColumnReadoutFebModel` adds 149.7 ohm
  to `SHUNT_R_G`, `ColumnFebFastDacAmp` adds another 149.7 ohm, and the harness
  cable load is 200 ohm versus the driver's 120 ohm. Consequently, a nominal
  physical 23 uA period is approximately 23.55 uA in current software command
  units. This small mismatch does not explain a one-sided ramp.
- `SetSimSaTunePoint` writes SA feedback into the row RAMs, then calls
  `saOffset` without explicitly loading those values into the force DACs.
  `SetSimSq1TunePoint` then changes the row SQ1 settings and SA feedback to
  64.8 uA. The static force state used by the offset loop and the subsequent
  muxed row state need not match. `verify_cosim_pid.apply_lock` also calls
  `sa_offset` after row-table writes without explicitly loading a selected
  row's complete physical state.
- SQ1 tuning normally measures the **SA feedback servo current**, not raw
  SA output voltage. `ServoDisable=True` selects raw `SaOut`. The servo logs
  convergence failure but returns its last attempted current; the sweep
  still appends and fits that value. A monotonic curve can therefore be a
  controller trajectory, rather than an equilibrated transfer curve.

## SA feedback and the shared offset

The nominal SSA phase depends on `muxCurrent - ssaFeedbackCurrent`. A single
SA-offset DAC per column is compatible with different per-row operating
points: the per-row SA feedback compensates the changed SQ1/MUX input so that
every row presents the same SA operating phase and voltage to that offset.

With the current nominal coupling signs/scales, preserving the same SA branch
requires increasing SA feedback by the change in MUX input current. If SA
tuning was done at zero SQ1 bias, its MUX input is zero. The approximately
9 uA SA-only tune value is then a reference, not generally the final feedback
for a biased, selected SQ1. Blindly replacing 64.8 with 9 is not a demonstrated
fix either. `sq1Tune` already obtains the compensated value as `yOut` and
applies it per row when `SetAfterFinish=True`.

A focused 32-row `TdmMuxColumnModel` probe with no device variation, physical
SA bias 55 uA, SA feedback 9.13 uA, FAS select 163 uA, and finite bias-source
resistances found:

| Physical SQ1 column bias | SQ1 feedback | MUX current | Intrinsic SA voltage |
|---:|---:|---:|---:|
| 50 uA | 5 uA | 5.874 uA | 0.548 mV |
| 75 uA | 5 uA | 8.811 uA | 0.0054 mV |
| 100 uA | 5 uA | 11.748 uA | 0.358 mV |
| 75 uA | 16.951 uA | 8.015 uA | 0.0659 mV |

At 75 uA bias, 5 uA feedback and unchanged 9.13 uA SA feedback place the SSA
close to its voltage minimum. Adding the MUX current to SA feedback restores
the SA-only voltage of 3.517 mV in every probed case. These are **physical
model currents**, not directly usable software command values. The same
probe found nonzero local slopes at both 5 and 16.951 uA; which point is useful
depends on the entire cascade, bias, SA phase, and device variation.

## Durable validation

`firmware/simulations/WaferModelTb/tb/Sq1FeedbackTb.vhd` exercises the actual
`GroupDetectorHarnessSim` with one column and 32 rows, variation disabled:

- Three-period physical SQ1 feedback sweep, including negative currents.
- 23 uA periodicity, polarity symmetry, modulation, and turnover.
- Physical column bias 50/75 uA and row select 150/163 uA.
- SA sense-voltage spans of approximately 1.07 mV at 50 uA and 2.07 mV at
  75 uA for 163 uA row select. Thus useful modulation is present below the
  standard DAC's ceiling in this configuration.

All seven WaferModelTb GHDL testbenches passed locally. These checks exclude
the board DAC driver, ADC, software servo, and muxed PID integration. The
temporary operating-point probe additionally verified SA-phase compensation;
its table above records the result without adding generated logs to Git.

## Next discriminating capture

The subsequent [hardware notebook review](../../reference/hardware-tuning-sequence.md) found
that the recorded hardware workflow applies all three SQ1 fit results and
preserves the tuning offset into readout. Its matching helper calls
`saOffset` before the SQ1 row sweeps, then servos SA feedback at each point.
It has no unconditional post-SQ1 `sa_offset()` call. The extra call in the
cosim lock helpers is therefore a specific difference to check first; an
offset established against a different force state can invalidate the fit's
ADC reference.

Use one selected row, timing stopped and PID disabled. Capture the requested
values, `SQ1Fb.DacRawNow`, `SQ1Bias.DacRawNow`, `SAFb.DacRawNow`, selected FAS
state, offset DAC value, raw `SaOutAdc`, and any servo convergence warnings.
Readbacks of the override shadow alone do not establish the applied output.

Load the same SQ1 bias, SQ1 feedback, and compensated SA feedback used by that
row's readout RAMs before comparing a static null with a muxed visit. Preserve
the common SA operating phase with per-row SA feedback, and establish the
offset against that phase. Verify a small SQ1-feedback perturbation gives a
nonzero ADC slope before enabling the PID. Then compare the first muxed
visit's DAC values, sample count, baseline, and accumulated error with the
static state. This distinguishes an operating-point mismatch from an
accumulator, row-address, or DAC-update fault without another full tune.
