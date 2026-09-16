# Sensor-wafer simulation model

The cold TES/SQUID model provides a deterministic plant for tuning, row
selection, and PID verification through the real warm-electronics interfaces.
It is a behavioral verification fixture; its synthetic parameters do not
establish calibrated detector behavior.

The foundation was integrated into `pre-release` through the sensor-wafer work
recorded on [#98](https://github.com/slaclab/warm-tdm/issues/98). Later seeded
variation, V–Φ shaping, and PID fixture changes are carried by the
`channelization` integration. This document describes the architecture in this
checkout; it does not claim those later changes or acceptance have landed.
Current closed-loop comparison work belongs to
[#70](https://github.com/slaclab/warm-tdm/issues/70); see the
[verification index](../../../../docs/plans/pid-cosim-verification/README.md).

## Boundaries and topology

The signal path is:

```text
physical row/chip-select currents + per-pixel TES current
  -> SQ1/FAS MUX column and column shunt
  -> SSA and its bias load line
  -> differential SSA-plus-cable voltage
  -> existing warm preamp, ADC, DSP, and feedback DAC
```

TES current and SQ1 column-bias current are separate electrical circuits. TES
current couples magnetically into the pixel's SQ1. A row FAS bypasses that SQ1
when superconducting; select flux drives the FAS resistive and routes current
through the SQ1. A two-level topology adds a chip FAS bypassing a whole bank,
so both row and chip selection matter. The complete MUX column is shunted by
approximately 1 ohm in the synthetic profile.

Keep detector topology, simulated extent, device parameters, instance variation,
warm/cold wiring, logical row schedule, and runtime stimulus separate. The cold
model responds to physical currents and must not take a firmware logical row
as an analog shortcut. That separation lets simulation exercise the actual row
mapping, switching sequence, sample window, and inactive-module slots.

| Entity/package | Responsibility |
|---|---|
| [WaferSimPkg](WaferSimPkg.vhd) | Typed parameters, topology/harness builders, deterministic variation, pure device and network functions |
| [TdmMuxColumnModel](TdmMuxColumnModel.vhd) | One column's SQ1/FAS network, column shunt, and SSA load-line solution |
| [DetectorModuleSim](DetectorModuleSim.vhd) | Independent columns sharing detector-local row/chip-select inputs |
| [GroupDetectorHarnessSim](GroupDetectorHarnessSim.vhd) | Board/channel wiring, source/load conversion, TES input, and warm voltage sense |
| [WaferSim](WaferSim.vhd) | Legacy eight-channel compatibility wrapper |

The detector module is a functional cold-readout boundary, not an assertion
that TES/MUX and SSA devices share a physical substrate or temperature.

## Profiles and harness mapping

`GroupTb.LOAD_G` accepts `LOAD_BOARD`, `WAFER`/`WAFER_32`, `BICEP3`,
`NIST_50R`, and `BA4`. `LOAD_BOARD` retains the simple resistive fixture.
Detector dimensions describe the physical device; a simulation can instantiate
a smaller column slice without changing its row topology.

| Profile | Rows | Physical columns | Selection |
|---|---:|---:|---|
| WAFER | 32 | 8 | One level |
| BICEP3 | 22 | 12 | One level |
| NIST_50R | 50 | 12 | Provisional 5 banks × 10 rows |
| BA4 | 60 | 12 | 6 banks × 10 rows |

The NIST factorization still requires confirmation against the mask schematic.
An eight-column BA4 slice is a reduced simulation extent, not a different
physical detector. Keep 1/8-column configurations for fast tests and full
12/24-column harness cases for connectivity checks.

Warm columns flatten as `board * 8 + channel`. One twelve-column detector uses
an `8+4` connection. The dual-BA4 preset maps three warm boards as follows:

| Warm endpoint | Detector endpoint |
|---|---|
| Board 0, channels 0–7 | Detector 0, columns 0–7 |
| Board 1, channels 0–7 | Detector 1, columns 0–7 |
| Board 2, channels 0–3 | Detector 0, columns 8–11 |
| Board 2, channels 4–7 | Detector 1, columns 8–11 |

Detector 0 uses row lines 0–9 and chip lines 10–15; detector 1 uses row lines
16–25 and chip lines 26–31. `RowMap2x6x10` schedules 120 logical slots across
the two modules. It is a group schedule, not a single detector topology, and
needs at least seven row-address bits. The third warm board is split by channel
and is not switched between detectors at runtime. The physical assembly's
formal Group boundary still needs confirmation.

## Analog interface and units

`SimPkg` defines `TheveninSourceType`, `DifferentialSourceType`,
`ColumnCryoDriveType`, and `ColumnCryoSenseType`. The historical `CurrentType`
name aliases a Thevenin source: open-circuit voltage plus series impedance,
not a measured current. Use `currentDiff()` with the cable/coil load when
converting feedback and select drives.

SQ1 and SSA bias need the source resistance inside the nonlinear load-line
solve. The harness supplies the Norton-equivalent short-circuit current and
total FEB-plus-cable resistance. Zero source resistance is an explicit ideal
current-source compatibility mode for focused tests.

The warm preamplifier senses the entire SSA bias loop, including cable drop:

```text
Issa   = Inorton - Vssa / Rsource_total     (finite source resistance)
Vsense = Vssa + Issa * Rcable
senseP = +Vsense / 2
senseN = -Vsense / 2
```

Omitting the cable term loses the DC voltage even when the intrinsic SSA is
superconducting. The symmetric voltage drive and polarity are model assumptions
to check against hardware. `ColumnFebSaBiasAmp` derives both output polarities
and offset from the P DAC leg to model a known circuit modification; its N
inputs remain for compatibility.

TES bias is already a pair of real currents from `ColumnFebTesBiasAmp`, with
P/N intentionally swapped by its caller. The harness takes half their
difference, scales it by `TES_CURRENT_SCALE_G`, and adds per-pixel stimulus and
the seeded baseline. This is direct current injection, not a solved TES
shunt/Nyquist/electrothermal circuit. Scaling it to exercise multiple flux jumps
is a test aid, not physical calibration.

Each row-select line has one electrical source/load calculation. Its current
fans out magnetically to all connected FAS devices; it is not divided by the
number of modeled columns. Unused warm endpoints have an explicit termination
policy, and the harness checks connection ranges and uniqueness.

## Device equations and parameter conventions

SSA, SQ1, row FAS, and chip FAS own independent typed parameter records, even
when they use the same pure mathematics. Their periods, critical currents,
resistances, phases, and polarities must not silently share defaults. Use SI
units and unit-bearing field names. Normalize coupled currents as:

```text
phi = phaseOffsetCycles + sum(polarity * couplingScale * I / currentPerPhi0Amp)
currentPerPhi0Amp = Phi0 / abs(M)          (when mutual inductance is known)
```

The foundational ideal law is the symmetric, overdamped, negligible-loop-
inductance dc-SQUID approximation. With effective whole-SQUID parameters:

```text
Ic(phi) = criticalCurrentAmp * abs(cos(pi * phi))
V       = 0                                             if abs(I) <= Ic(phi)
        = sign(I) * normalResistanceOhm * sqrt(I^2-Ic^2) otherwise

criticalCurrentAmp = 2 * per-junction I0
normalResistanceOhm = per-junction R / 2
```

Legacy `IC0`/`RN` values map to those whole-device quantities without an extra
factor of two. Series/parasitic resistances belong in the surrounding circuit,
not only on the subcritical branch of the voltage law. `V/I` is static
resistance, distinct from the dynamic `dV/dI` used in a settling analysis.

The current branch additionally applies `SQUID_SINUSOID_BLEND_C` (default 1.0)
to smooth the V–Φ curve. The ideal law above describes the zero-blend reference,
not the present default response. The rationale, envelope, and validation
limits are in the [V–Φ shaping design](../../../../docs/design/squid-vphi-shaping/README.md).
Neither that synthetic blend nor an arbitrary change to `betaL`/`betaC`
substitutes for a validated RCSJ solution or measured curve fit.

Array voltage is the sum of element voltages. Multiplication by `elementCount`
assumes identical coherent elements. Use `elementCount=1` when parameters
already describe a lumped array. The synthetic SSA's effective 120-ohm `RN`
with 55 µA onset bias gives a 6.6 mV ideal peak-to-peak envelope, anchored to
the observed 5–8 mV preamplifier range. This is a single-point amplitude anchor,
not a measured normal-state resistance or full bias-dependent calibration.

FAS behavior is periodic and bias dependent. The model derives its static
resistance from the SQUID curve plus parasitics. A logistic switch or a product
of row/chip enables may be a synthetic approximation but is not a universal
physical law. The exact nested-network solver is the reference for reductions;
`useExactNetworkSolver=false` selects the faster resistance approximation.
Changes to that approximation need checks at all four RS/CS states and across
the relevant bias range. The shunted column obeys a branch-current load line,
`Vdevice(Idevice) = (Ibias - Idevice) * Rshunt`, not a conductance-division
shortcut for a nonlinear device.

## Determinism and fidelity limits

Seeded builders resolve device arrays before passing them through the harness,
detector, and column: one SSA per column, one SQ1 and row FAS per pixel, one
chip FAS per bank, and one TES baseline per pixel. `VARIATION_SEED_G=0` restores
identical nominal devices. Nonzero seeds deterministically vary critical
current, resistance, current period, phase, and TES baseline. The controls are
`DEVICE_SPREAD_C`, `PHASE_SPREAD_CYCLES_C`, and `TES_BASELINE_AMP_C` in
`WaferSimPkg`. `DetectorVariationTb` checks determinism and observable spread.

The present cold model uses static transfer functions and bounded iterative
load-line solves. It does not implement physical settling, a dynamic TES
circuit, noise spectra, or microscopic junction dynamics. If dynamics are
added, use explicitly initialized state, a declared model time step, and
bounded updates; avoid mutually dependent concurrent `real` equations and
chains of delayed assignments as an analog solver. Record any accelerated
settling separately from physical time constants.

Measured profiles should identify the detector/mask, hardware revision, data
source/date, SI units, fit method, valid bias range, and residuals. Fit each
device role separately. Keep large measured data outside the HDL tree and
generate compact parameter/reference-vector packages. Remaining calibration
inputs include authoritative harness polarities, row maps, device periods and
resistances, measured sweeps, and TES electrical parameters.

## Validation and references

Use the focused [WaferModelTb suite](../../../simulations/WaferModelTb/README.md)
for pure curves, selection/isolation, bias load lines, cable voltage, profiles,
and harness mappings. The full ADC/DSP/DAC and host path uses
[`GroupTb`](../../../simulations/GroupTb/tb/GroupTb.vhd) and the
[cosimulation procedure](../../../../software/scripts/hwtest/README_cosim.md).
Keep scalar presets at the GroupTb boundary and resolved record arrays below
it so vendor simulator overrides remain manageable. HDL and server board
counts, row-address width, and row capacity must agree.

The original topology/equation investigation used the supplied circuit diagrams
and these references (retained as provenance, not revalidated by doc cleanup):

- [The SQUID Handbook, Vol. I](https://web.pa.msu.edu/people/edmunds/SQUID_Controller/References/sq_hb.pdf), §§2.1, 2.2, 4.3: limited-case device law and array conventions.
- [Tesche and Clarke, 1977](https://escholarship.org/uc/item/1xs8x5m9): dc-SQUID RCSJ treatment.
- [Reintsema et al., 2019](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=927441), Fig. 2: FAS/MUX network and column shunt.
- [Durkin et al., 2023](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=935895): two-layer switching.
- [CMB-S4 modular readout, 2022](https://lss.fnal.gov/archive/2022/conf/fermilab-conf-22-607-ppd.pdf), Fig. 4: TES bias and two-level selection.

The [PID coefficient analysis](../../../../docs/plans/sensor-wafer-model/PID_COEFFICIENTS.md)
retains a static derivation; its numerical examples predate later plant and
controller fixes. Measure the local end-to-end slope for the actual tuned
revision before selecting coefficients.
