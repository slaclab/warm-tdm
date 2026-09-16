# SQUID V–Φ shaping in the wafer model

## Problem

The behavioral SQUID model computes the flux-to-voltage (V–Φ) transfer in one
function, `idealSquidVoltage()` in
[`firmware/common/warm_tdm/sim/WaferSimPkg.vhd`](../../../firmware/common/warm_tdm/sim/WaferSimPkg.vhd):

```
ic   = criticalCurrentAmp · |cos(π · phaseCycles)|
vOut = normalResistanceOhm · √(iBias² − ic²)      (0 while |iBias| ≤ ic)
```

This ideal RSJ curve is **steepest right at its minima** (`ic → iBias` gives
`dV/dic → −∞`, a near-vertical tangent), with flat, rounded maxima. Real SQUIDs,
smeared by thermal fluctuations and finite loop inductance, look far more
**sinusoidal** — steepest at the *mid-slope* zero-crossings, flat at both
extrema.

That mismatch broke the closed-loop PID cosim lock (see
`docs/plans/pid-cosim-verification/`): a flux-lock loop's gain is proportional to
the local V–Φ slope, and the tune point (fit against real, sinusoidal curves)
places the *model* on its near-vertical region. There the effective loop gain is
enormous and strongly nonlinear, so the servo oscillates / winds up at any
coefficient or sign — exactly what was observed (`SumAccum` saturating, error
swinging full-scale, `sq1Fb` railing regardless of gain). Re-tuning does not
help: tuning just re-finds that ungovernable steep-near-minimum spot.

## What is implemented (option 1: fundamental-harmonic blend)

`idealSquidVoltage()` now blends the ideal curve toward a **pure fundamental
sinusoid with the same min/max envelope**, controlled by one global package
constant `SQUID_SINUSOID_BLEND_C` (in `WaferSimPkg.vhd`):

```
vMax   = Rn · |iBias|                                   (ic → 0,  half-integer phase)
vMin   = Rn · √(iBias² − criticalCurrentAmp²)           (ic max, integer phase; 0 if below Ic)
sinMag = (vMax+vMin)/2 − (vMax−vMin)/2 · cos(2π · phaseCycles)
vOut   = sign(iBias) · [ (1−blend)·ideal + blend·sinMag ]
```

- `SQUID_SINUSOID_BLEND_C = 0.0` → bit-identical to the previous ideal model.
- `= 1.0` → pure sinusoid: steep, monotonic, roughly-linear mid-slope lock region
  like real hardware, so the real-hardware tune point + gain (incl. the observed
  `≈ −0.0006` raw P sign) should transfer and the loop can lock.
- The envelope is matched to the ideal curve, and the phase (`−cos(2π·phase)`)
  aligns to `ic = criticalCurrentAmp·|cos(π·phase)|`, so no min/max/phase shift.

**Why a single package constant, not a per-squid field or a generic:** the V–Φ
math is centralized in `idealSquidVoltage`, so the reshape lives entirely there.
Adding a `SquidParamsType` record field instead would force updating every
aggregate that builds that record (the synthetic profiles in `WaferSimPkg`, the
positional aggregates in `WaferSim.vhd`, and the `WaferModelTb` cores) for no
functional gain here. The constant applies to all SQUIDs (SSA, SQ1, FAS); the
servoed SSA/SQ1 are what matter, and shaping the (non-servoed) FAS SQUIDs the
same way is harmless.

### Making it finer-grained later

If per-SQUID control or a build-time/GroupTb knob is wanted (e.g. keep FAS ideal,
or sweep the blend from the testbench like `USE_FLOAT_PID`/`VARIATION_SEED`):

- **Per-SQUID:** add `sinusoidBlend : real` to `SquidParamsType`, set it in the
  synthetic profile constants (SSA/SQ1 = 1.0, FAS = 0.0), and read
  `params.sinusoidBlend` in `idealSquidVoltage`. Cost: update every
  `SquidParamsType` aggregate (WaferSimPkg profiles, `WaferSim.vhd`,
  `WaferModelTb`). The variation-resolve functions already copy `nominal.squid`
  through, so the field rides along per device automatically.
- **Build-time generic:** thread a `real` generic from `GroupTb` down the same
  path as `VARIATION_SEED_G` (→ `GroupDetectorHarnessSim` → the resolve calls)
  and override `squid.sinusoidBlend` there; wire it in `GroupTb/ruckus.tcl` from
  an env var.

## Other options considered (for revisiting)

### Option 2 — flux-domain smoothing (physically motivated low-pass)

Convolve `vOut(Φ)` with a Gaussian of width `σΦ` (a few % of Φ0): this *is* a
low-pass filter in flux and is the most physical "refinement" — it literally
models flux-noise / thermal smearing rounding the curve. It rounds the cusp and
moves the steep region to mid-slope for the same reason as the sinusoid blend,
but with a tunable `σΦ` rather than a fixed harmonic content.
- Pro: physically meaningful; `σΦ` maps to a real flux-noise number.
- Con: real-time convolution in VHDL is awkward — you'd average several
  flux-shifted evaluations of `idealSquidVoltage` per sample, or precompute a
  lookup, which is more code and cost than the fundamental blend.

### Option 3 — round the cusp directly (softened radical)

Keep the ideal form but soften the vertical tangent at the minimum:
`vOut = Rn · (√(iBias² − ic² + δ²) − δ)`, with a small `δ` (e.g. a fraction of
`criticalCurrentAmp`). This is also a one-function change and directly tames the
near-vertical slope that makes the loop ungovernable.
- Pro: smallest change; targets the exact pathology (the √ tangent).
- Con: not globally "sinusoidal" (maxima stay flat-ish), and `δ` is a somewhat
  arbitrary magic number without a clean physical mapping.

### Option 4 — add the real physics (βL / thermal rounding)

Replace the ideal `Ic(Φ)` and I–V with a screened, thermally-rounded model
(finite `βL = 2·L·Ic/Φ0`, `kT/EJ` smearing). Most faithful to real devices and
would reproduce the sinusoidal shape from first principles.
- Pro: most realistic; single knob (`βL`) with physical meaning.
- Con: largest change; needs added device parameters and validation against
  measured curves.

## Recommendation order if revisiting

1. Fundamental blend (implemented) — enough to get a governable mid-slope lock.
2. If a physical flux-noise story is wanted → option 2 (`σΦ`).
3. If matching measured curves becomes important → option 4 (`βL`/thermal).
Option 3 is a quick fallback if only the cusp needs taming.
