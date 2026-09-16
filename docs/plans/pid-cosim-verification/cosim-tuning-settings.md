# Cosim tuning settings (sinusoidal SQUID model)

Operating points and tuning-process settings for the closed-loop PID cosim on the
**sinusoidal** wafer model (`SQUID_SINUSOID_BLEND_C=1.0`, `VARIATION_SEED=0`,
integer PID). Measured 2026-09-15 against GroupTb (1 col + 1 row board, 32 rows)
under Vivado 2025.1 + VCS.

## Closed-loop muxed-PID gains (integer AdcDsp) — TUNED 2026-09-16

Measured against the **fixed** RTL (commit `0f8b13c`: feedback-capture + overflow
saturation fixes) with the clean per-point protocol: clear PID state
(`AdcDsp.ClearPids`), re-seed `Sq1FbCurrent=7.0 µA` for all rows while stopped,
`sa_offset` once, `setup_mux(num_pts=400, sample_num=20)`, then set **raw** AdcDsp
coefficients directly (`AdcDsp.P_Coef`/`I_Coef` are the raw values — do NOT confuse
with the normalized `Group.PidP_Gain`, which is raw×SampleCount).

- **Sign matters and is NEGATIVE.** Raw `P = −0.0006` (the hardware value). Positive
  normalized/raw P is positive feedback here → diverges. `set_pid` writes
  *normalized* gains (raw = norm/SampleCount), so normalized `P_norm=-0.012` at
  SampleCount=20 also yields raw −0.0006.
- **P-only** locks all 8 rows cleanly (FluxJumps=0) but leaves an actuator
  **deadband** residual ≈ `0.5/|P_raw|` counts (~700 at P=−0.0006): the correction
  rounds below one DAC code near null.
- **A small I closes the deadband** (first time I has worked — prior failures were
  windup from un-cleared state + wrong sign). At P=−0.0006, sweeping raw I:

  | raw I | 30 s residual (mean\|E\|) | character |
  |------:|--------------------------:|-----------|
  | 0        | 705 | deadband floor, clean |
  | −1e-5    | 540 | clean, uniform, slow |
  | **−2e-5**| **~120** | **clean monotonic, no hunt — recommended** |
  | −3e-5    | ~270 | quantization limit-cycle stepping begins |
  | −6e-5    | hunts (min ~100, overshoot ~320) | too high |

- **Recommended: raw P=−0.0006, I=−2e-5, D=0** → all 8 rows converge to ~120 counts
  (~0.7 mV, ~6 ADC codes), SumAccum bounded, FluxJumps=0. For faster nulling, a
  larger P (e.g. −0.0012, lower deadband) with I≈−2e-5 is a candidate not yet swept.
- Residual metrics are `mean(|per-row AccumError|)` over the 8 readout rows at
  SampleCount=20; note a large one-time StartRun transient (first ~1–2 s) before the
  first clean accumulation — ignore it when reading settling.

## Measured operating points (col 0, no variation → all rows identical)

- **SA tune:** SaBias = **55 µA**, SaFb (lock) = **9.03 µA** (≈ Φ0/4 of the 35 µA
  SSA flux period → the mid-slope steepest point, as intended for the sinusoidal
  curve). V–Φ span ≈ 6.5 mV at 55 µA bias, ≈ 2.4 mV at 85 µA (deeper modulation
  near Ic=55 µA). `SetSimSaTunePoint` updated to seed SaFb=9 µA (was 41 µA, which
  was for the pre-blend ideal curve).
- **SQ1 tune (row 0):** FittedSq1Fb = **9.19 µA** (SQ1 flux period 10 µA),
  FittedSq1Bias = **50 µA**, FittedSaFb = **−0.54 µA**. (`SetSimSq1TunePoint`
  currently seeds Sq1Fb=7.37, Sq1Bias=100, SaFb=64.8 — from the old ideal model;
  update to the sinusoidal-model fit once the SQ1 lock is confirmed.)

## Servo settings — why the sq1 tune was slow, and better values

The two SA-null servos are both proportional-only PIDs (Ki=Kd=0, output limits
±0.5) in `warm_tdm_api/tuning/_common.py`:

- `saOffset` (initial SA null): `SaOffsetProcess` Kp=−1.0, Precision=0.001,
  MaxLoops=100 → **converged in 5 loops**. Good reference.
- `saFbServo` (runs at every SQ1/FAS sweep point): gains from the calling process
  (`Sq1TuneProcess.ServoKp/Ki/Kd`, default Kp=−0.8, ServoMaxLoops **default 500**).

The 2026-09-15 sq1 tune took **863 s** because it was invoked with
`ServoMaxLoops=40` and `ServoPrecision=0.01`: 0.01 is right at the ADC-quant floor
(SaOutAdc LSB ≈ 0.004 → the servo limit-cycles at ±0.02), so it never dips below
0.01 and caps at 40 loops at all 64 sweep points. The **gain is fine** (−0.8 is
close to SaOffset's near-deadbeat −1.0); the slowness was the precision + loop cap
+ step count.

### Recommended settings for future runs (not yet applied)

- **`ServoPrecision` ≈ 0.03–0.05** (above the ~0.02 ADC-quant limit cycle) — the
  single biggest speedup: each point should then converge in a handful of loops
  instead of hitting the cap.
- **`ServoKp` = −1.0** (match SaOffset's near-deadbeat gain); keep Ki=Kd=0 (a
  nonzero Ki risks integral windup / limit cycles against ADC quantization).
- **`ServoMaxLoops` ≈ 60** (default 500 is fine but wasteful; with looser
  precision, 60 is plenty and bounds a stuck point).
- **Sweep steps (sim is slow):**
  - SA tune: SaFb 0–70 µA (2 flux periods) × ~24–32 steps; SaBias ~1–2 steps
    (the fit favored 55 µA). Used 55–85 µA × 2, SaFb 0–70 µA × 32 — fine.
  - SQ1 tune: Sq1Fb −15..15 µA (3 periods of the 10 µA SQ1) × **~24** steps
    (≈8/period is enough); **SaBias/Sq1Bias 1 step** (use the fitted 50 µA
    directly) instead of a 2-point ramp; tune only the rows you need.
  - Net: dropping Sq1FbNumSteps 32→24 and Sq1BiasNumSteps 2→1 is ~2.7× fewer
    points; looser ServoPrecision is another ~8×.

## Row-FAS set point — does NOT agree with the model

`SetCosimTunePoints` uses FasOn = 163 µA, but the synthetic row-FAS flux period is
`currentPerPhi0Amp` = **300 µA**, so 163 µA sits at ~0.54 Φ0 — essentially the
**max-resistance (≈half-quantum) extremum**, not a clean on/off point. Clean
extrema: min R (12.2 Ω) at 0 / 300 µA, max R (14.1 Ω) at 150 µA. Also the FAS
modulation is **weak** (12.2→14.1 Ω, ~15%), so it barely gates the row either way
— which is why sq1 tune still read a row with 163 µA. For model consistency the
FAS on/off should use the 300 µA-period extrema (which extreme is "on" depends on
the switch topology — confirm, or run `fas_tune`).
