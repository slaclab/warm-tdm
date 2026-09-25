# Cosim tuning settings (sinusoidal SQUID model)

**2026-09-18 investigation:** the cold-model SQ1 response is periodic at
23 uA, including negative feedback. FAS select near 150 uA selects the row;
0/300 uA shunts SQ1. The standard SQ1-bias DAC cannot supply the 100 uA used
by direct-model probes: that command clips near 77 uA. Static force-DAC
settings also need to match the muxed row settings before an ADC null is
meaningful. See [the retune investigation](SQ1_RETUNE.md) for measured
GHDL results, current-scale differences, and the remaining integration check.

**2026-09-17 model update:** the nominal SQ1 feedback period is now **23 µA**.
The PID profiles use `FluxQuantum=23 µA` and `Sq1FbCurrent=16.1 µA`, preserving
the old 0.7-period seed. `SetSimSq1TunePoint` uses 16.951 µA (the old 7.37 µA
seed scaled by 23/10); the default SQ1 sweep is -34.5..+34.5 µA with 31 points.
The measured results below belong to the **old 10 µA fixture**. Gains and
thresholds are retained starting values, awaiting a rebuilt GroupTb run;
these historical results do not establish lock/settling at the new period.

Operating points and tuning-process settings for the closed-loop PID cosim on the
**sinusoidal** wafer model (`SQUID_SINUSOID_BLEND_C=1.0`, `VARIATION_SEED=0`,
integer PID). Measured 2026-09-15 against GroupTb (1 col + 1 row board, 32 rows)
under Vivado 2025.1 + VCS.

## Closed-loop muxed-PID gains — RE-TUNED 2026-09-21 (ring cosim, both paths)

Re-tuned over the **PGP-ring** GroupTb cosim (`SIM_PGP_GT_C=true`, 1 col + 1 row,
32 rows, 23 µA period, Sq1Bias=50/Sq1Fb=2/SaFb=9) via a closed-loop sweep that
reads the **AXI `AccumError` register** live during a run (the PID-debug *stream*
yields too few visits — ~7-8 — to see the loop reach its floor). Values are
**raw** gains; the harness `PidP_Gain`/`PidI_Gain` path writes raw×SampleCount
(SampleCount=20). Both controllers share the additive-error P law, so **stable P
is NEGATIVE for both**; a positive P is positive feedback and diverges.

**Integer (`AdcDsp`) — recommended raw P = −0.010, I = 0, D = 0.**

| raw P (norm) | t to <800 | floor (counts) | settled spread |
|-------------:|----------:|---------------:|---------------:|
| −0.0025 (−0.05) | 30 s | ~360 | 265 |
| −0.0050 (−0.10) | 16 s | ~69 | 100 |
| **−0.0100 (−0.20)** | **8 s** | **~27** | **15** |
| −0.0200 (−0.40) | 6 s | ~26 | 20 |

−0.010 converges ~4× faster than the old −0.0025 and floors ~13× tighter with no
limit cycle; −0.02 is no better. P-only already floors far under the 800-count
threshold, so integer I is left 0.

**Float (`AdcDspFp`) — recommended raw P = −0.005, I = −1e-5, D = 0** (PI; the FP
path has no D). The old default `p_raw=+1e-4` was BOTH the wrong sign AND ~50×
too weak. FP needs a much larger |P| than integer:

| raw P (norm), I=0 | t to <800 | floor |
|------------------:|----------:|------:|
| −0.0005 (−0.010) | no lock in 40 s | ~7000 |
| −0.0010 (−0.020) | no lock in 40 s | ~1755 |
| −0.0020 (−0.040) | 32 s | ~228 |
| **−0.0050 (−0.100)** | **14–16 s** | **~90** |

I sweep at P = −0.005 (raw I):

| raw I | floor | spread | character |
|------:|------:|-------:|-----------|
| 0        | 92  | 100 | P-only |
| −5e-6    | 45  | 80  | tighter |
| **−1e-5**| **40** | **60** | **best floor+spread, no windup — recommended** |
| −3e-5    | 174 | 100 | over-integrated, floor rising |
| −6e-5    | 344 | 215 | windup / hunt onset |

"Floor" = `mean|AccumError|` after settling; "spread" = peak-to-peak of a few
post-settle reads (a coarse limit-cycle screen, not a full time-series analysis).
Both paths verified end-to-end over the ring (steady lock + step disturbance
rejection) in `verify_cosim_pid.py --mode verify` on 2026-09-21. These are the
values baked into that script's `DEFAULTS`.

The section below is the **older 2026-09-16 bypass-mode tuning**, retained for
provenance; its P=−0.0006/I=−2e-5 predates the ring cosim and this re-tune.

## Closed-loop muxed-PID gains (integer AdcDsp) — TUNED 2026-09-16 (superseded)

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

## Row-FAS set point — corrected September 18

The FAS is in parallel with SQ1. At **0/300 µA** select current, the nominal
FAS is superconducting below its critical current and shunts SQ1: **row off**.
At **150 µA**, its critical current reaches zero and the resistive FAS allows
SQ1 modulation to appear: **row on**. `SetCosimTunePoints`'s **163 µA** is near
this selected extremum and is consistent with the topology.

The former claim that this was a bad on-point was incorrect. Its weak
12.2–14.1 ohm resistance estimate also predates the nominal row-FAS
critical-current increase from 20 to 100 µA. At a 10 µA branch probe, the
current model gives approximately 0.1 ohm at zero select and 14.1 ohm at
150 µA select, including the FAS series resistance. These select currents
refer to physical model inputs; full-board command scaling must also be
accounted for.
