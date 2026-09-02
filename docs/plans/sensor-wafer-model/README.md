# Sensor Wafer Simulation Model

## Status

- Investigation and architecture contract reviewed as of 2026-09-02.
- The first implementation slice is present on `sensor-wafer-sim`: typed and
  independent SSA/SQ1/row-FAS/chip-FAS parameters, ideal low-`L` transfer
  functions, exact and reduced nested MUX solvers, configurable detector
  modules, and an eight-channel `WaferSim` compatibility wrapper.
- `GroupTb` selects complete `WAFER`/BICEP3/NIST-50-row/BA4 or load-board
  presets with its single `LOAD_G` generic. Lower-level model interfaces retain
  custom topology, device parameters, and deterministic per-pixel TES input.
- Focused GHDL tests pass for the primitive curves, two-level selection,
  selected-pixel isolation, the compatibility wrapper, an 8-column `6x10`
  slice, full 12-column BICEP3/NIST/BA4 profile elaboration, a one-detector
  `8+4` warm harness, and the dual-BA4 `8+8+(4+4)` maps.
- Full VCS `GroupTb` elaboration and the open-loop/fixed-PID co-simulation have
  not been run because Vivado/VCS are unavailable on the development machine.
- Multi-board integration into `GroupTb`, model dynamics, a static electrical
  TES solution, per-device variation, and measured calibration remain future
  work.
- The supplied circuit diagrams are sufficient to begin a behavioral model.
- Legacy SQUID and FAS equations have been checked against the published RCSJ,
  SQUID-array, and NIST switch-MUX literature; the accepted limits and required
  replacements are documented below.
- Near-term detector-module dimensions and a representative two-module warm
  wiring arrangement have now been supplied by a project colleague.
- Exact device parameters, polarity conventions, NIST bank factorization, and
  the formal group boundary still need confirmation before the model can be
  called calibrated.

## Goal

Replace the resistive `ColumnLoadBoard` approximation in `GroupTb` with a
deterministic, topology-aware behavioral model of the cold TES/SQUID system.
The model should exercise the same control and observation paths used by the
real tuning and readout software:

- SA bias and feedback;
- SQ1 bias and feedback;
- a controllable row-select/FAS response suitable for developing a future
  row-select tuning procedure;
- two-level row-select plus chip-select addressing;
- per-pixel TES signal coupling into the selected SQ1; and
- settling between row transitions and ADC samples.

The first implementation is an FPGA/system verification model, not a
microscopic Josephson-junction or cryogenic thermal simulator.

## Evidence Reviewed

### Project sources

- `firmware/simulations/GroupTb/tb/GroupTb.vhd`
- `firmware/common/warm_tdm/sim/WaferSim.vhd`
- `firmware/common/warm_tdm/sim/SquidColumn.vhd`
- `firmware/common/warm_tdm/sim/Sq1.vhd`
- `firmware/common/warm_tdm/sim/Squid.vhd`
- `firmware/common/warm_tdm/sim/ColumnLoadBoard.vhd`
- `firmware/common/warm_tdm/sim/RowLoadBoard.vhd`
- the column and row FEB simulation models
- `RowDacDriver2.vhd` and the Python row-map definitions
- SA and SQ1 tuning code, plus incomplete FAS-tuning scaffolding, under
  `software/python/warm_tdm_api/`
- the introduction and short follow-up of the existing SQUID simulation in
  commits `1e0ba923` and `cfd7dea`

### Circuit references

- The two rough circuit diagrams supplied with this investigation.
- Project colleague's configuration note: BICEP3 `22r x 12c` single-level,
  NIST `50r x 12c` two-level, BA4 `60r x 12c` two-level, and the described
  two-BA4-to-three-readout-module column fanout.
- Reintsema et al., *High-Throughput, DC-Parametric Evaluation of
  Flux-Activated-Switch-Based TDM and CDM SQUID Multiplexers* (NIST, 2019),
  especially Figure 2:
  <https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=927441>
- Clarke and Braginski, eds., *The SQUID Handbook, Volume I* (Wiley-VCH,
  2004), especially Sections 2.1, 2.2, and 4.3:
  <https://web.pa.msu.edu/people/edmunds/SQUID_Controller/References/sq_hb.pdf>
- Tesche and Clarke, *dc SQUID: Noise and Optimization* (Journal of Low
  Temperature Physics, 1977), the primary RCSJ treatment used by the
  handbook: <https://escholarship.org/uc/item/1xs8x5m9>
- Durkin et al., *Symmetric time-division-multiplexed SQUID readout with
  two-layer switches for future TES observatories* (NIST, 2023):
  <https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=935895>
- CMB-S4 modular readout description (2022), especially its TES-bias and
  two-level switching discussion around Figure 4:
  <https://lss.fnal.gov/archive/2022/conf/fermilab-conf-22-607-ppd.pdf>

The general one-level/two-level circuit structure below is considered confirmed
by the supplied diagrams and those references. Profile-specific bank counts,
numerical parameters, physical packaging boundaries, and warm-interface
polarities are confirmed only where explicitly noted.

## Reconstructed Topology

### Signal path for one column

```text
TES bias source
    |
    +-- series chain of detector bias cells
        each cell = Rshunt || (Lnyquist + RTES + SQ1 input coil)
                                      : magnetic coupling
                                      v
SQ1 bias source -- 1 ohm column shunt || series MUX column -- SSA input coil
                                             |
                                             +-- one SQ1/FAS cell per row
                                             +-- common SQ1 feedback coupling

SSA bias source --> SSA --> differential voltage --> warm preamp/ADC
                      ^
                      +-- SA feedback coupling
```

TES current and SQ1 bias current are separate electrical circuits. A selected
pixel's TES current affects its SQ1 through mutual inductance.

### One-level MUX

The older diagram has 11-row MUX chips, with six chips producing 66 rows. Each
row cell places an SQ1 branch in parallel with a flux-activated switch (FAS).
With no row-select flux, the superconducting FAS bypasses the SQ1. Driving the
row-select FAS resistive diverts the column bias through that row's SQ1. The
cells and chips form a series column, and an approximately 1 ohm resistor
shunts the complete MUX column.

### Two-level MUX

The newer diagram groups approximately ten row cells on a chip. It adds a
chip-select FAS that bypasses the entire bank. Selecting a detector therefore
requires both:

1. its shared row-select line; and
2. the chip-select line for its bank.

`RowDacDriver2` already supports this electrically: each logical row-map word
contains two independent physical DAC addresses, and its sequencer turns both
the old pair off and the new pair on. No separate FPGA ports for row and chip
select are required.

Current software mappings imply these useful model profiles:

| Profile | Physical line interpretation | Logical rows |
| --- | --- | ---: |
| `1x32` | 32 direct row-select lines | 32 |
| `6x10` | 10 shared row-select + 6 chip-select | 60 |
| `7x10` | 10 shared row-select + 7 chip-select | 70 |
| `8x10` | 10 shared row-select + 8 chip-select | 80 |
| `2x6x10` | group schedule for two independent `6x10` modules | 120 |

The proposed model should describe the physical line-to-bank mapping as data,
not infer it from hard-coded line-number ranges.

`1x32`, `6x10`, `7x10`, and `8x10` describe detector-local row topologies.
`2x6x10` is different: it describes a group-level logical schedule and physical
row harness for two detector modules. It must not be represented as a single
detector topology.

### Near-term detector-module profiles

The colleague's note establishes that the detector module, not the eight-column
warm readout module, is the natural cold-model boundary:

| Detector profile | Rows | Columns | Select topology | Row lines/module | Modules per 32-line row board |
| --- | ---: | ---: | --- | ---: | ---: |
| BICEP3 | 22 | 12 | single-level | 22 | 1 |
| NIST | 50 | 12 | probably 5 banks x 10 RS | 15 inferred | 2 inferred |
| BA4 | 60 | 12 | 6 banks x 10 RS | 16 | 2 |

The row and column counts and selection levels are supplied facts. The NIST
`5x10` factorization is an inference from the 50-row total, the ten-row bank
shown in the supplied diagram, and the existing software mappings; it still
needs confirmation. The BA4 `6x10` interpretation is strongly corroborated by
the existing `RowMap6x10` and `RowMap2x6x10` definitions. Any single 12-column
detector needs two warm column modules if kept alone. Two detector modules can
pack their 24 columns without unused channels into three warm column modules.

The physical 12-column count is profile metadata, not a required simulation
extent. Because columns have independent bias, feedback, TES, MUX, SSA, and ADC
paths and share only the row-control inputs, the same row topology can be
instantiated with 1, 8, 12, or another requested number of columns. Useful
extents are:

| Simulated columns | Purpose |
| ---: | --- |
| 1 | fast device, tuning-curve, and selected-row unit tests |
| 8 | one complete warm column-board integration test |
| 12 | one physically complete detector-module and harness test |
| 24 | two physical detector modules across three warm column boards |

An 8-column BA4-like instance is therefore a deliberately reduced wafer slice,
not a claim that a physical BA4 module has eight columns.

### Likely two-BA4 group assembly

Two BA4 modules expose 24 detector columns. Three eight-channel warm readout
modules cover those columns exactly as described:

```text
Warm column module 0, channels 0..7 -> BA4 module 0, columns 0..7
Warm column module 1, channels 0..7 -> BA4 module 1, columns 0..7
Warm column module 2, channels 0..3 -> BA4 module 0, columns 8..11
Warm column module 2, channels 4..7 -> BA4 module 1, columns 8..11
```

One 32-line row module can also fit two independent BA4 select networks:

```text
row lines  0.. 9 -> BA4 module 0 shared RS 0..9
row lines 10..15 -> BA4 module 0 CS 0..5
row lines 16..25 -> BA4 module 1 shared RS 0..9
row lines 26..31 -> BA4 module 1 CS 0..5
```

This is exactly the address allocation produced by `RowMap2x6x10`. That is
strong evidence that the intended assembly is one row module plus three column
modules serving two BA4 detector modules. Whether the project formally calls
that complete assembly one `Group` is not yet confirmed.

`RowMap2x6x10` contains 120 logical time slots: the first 60 select module 0 and
the next 60 select module 1. Therefore each warm column channel is connected to
one detector module and should be insensitive during the other module's slots.
The shared third column module is mixed at channel granularity, not switched
between detector modules at runtime. This profile requires `maxRows >= 120` and
an RTL row-address width of at least seven bits.

The software already provides `RowMap6x10` and `RowMap2x6x10`. It does not
currently provide named `1x22` or `5x10` helpers, so BICEP3 and NIST will need
either explicit custom `RowMap` values or small convenience commands. That is a
software configuration gap, not a limitation of the proposed wafer model.

## Assessment of the Existing Attempt

`WaferSim`/`SquidColumn` contain a recognizable sketch of the one-level circuit,
but they should be treated as a prototype rather than repaired in place.

The prototype did preserve one important design intent: SSA, SQ1, and row-FAS
SQUIDs were separately parameterized. Its `WaferSim` defaults were:

| Legacy role | `RN_G` | `IC0_G` | `PHINOT_G` equivalent current |
| --- | ---: | ---: | ---: |
| SSA | 14 ohm | 55 uA | 35 uA |
| SQ1 | 14 ohm | 20 uA | 10 uA |
| row-select FAS | 14 ohm | 20 uA | 300 uA |

These values are useful evidence about the intended parameter categories, not
calibrated constants. `PHINOT_G` is a usable input if it is defined explicitly
as the current interval corresponding to one flux quantum, rather than as flux
itself. The new model requires four independent parameter triples:

```text
SQ1      : IC0, RN, PHINOT
SSA/SA   : IC0, RN, PHINOT
row FAS  : IC0, RN, PHINOT
chip FAS : IC0, RN, PHINOT
```

No device type may inherit or alias another type's triple. A profile may choose
equal numerical values deliberately, but it must still specify them through
separate typed records. Chip-select FAS parameters are new because the legacy
prototype represented only one selection level.

Confirmed problems include:

- TES bias inputs are unused and every SQ1 receives `iMeas => 0.0`, so a TES
  signal can never reach the ADC.
- `SquidColumn` mixes resistance and conductance in the MUX/shunt current
  division. The calculation is dimensionally invalid.
- `WaferSim` returns a voltage derived from SA-bias current and an arbitrary
  200-ohm load instead of returning the SSA output voltage.
- Several internal `real` signals in `Squid` are uninitialized. A minimal GHDL
  elaboration/run reaches a bound-check failure at time zero.
- Zero bias can lead to division by zero in the SQUID equation.
- The reported effective resistance and output-voltage equations are not
  mutually consistent when series resistance is present.
- SQ1 and row-FAS series resistances are hard-coded to 1.0 and 0.1 ohm while
  SSA inherits a different default, so those curve-defining values cannot be
  calibrated or varied per device.
- Delayed concurrent assignments create hidden analog feedback loops. These
  are fragile, difficult to initialize, and simulator-dependent.
- The model only represents a single row-select level; it has no chip-select
  bank bypass.
- Generic names conflate physical flux with equivalent input-current periods,
  leaving units unclear.

The load-board model remains useful as a simple electrical-interface smoke test
and should remain selectable as a separate `GroupTb` load profile.

## Literature Verification of the Device Equations

The equations in the old `Squid.vhd` are not a general dc-SQUID model. They can
be recovered from the published resistively and capacitively shunted junction
(RCSJ) treatment only in the symmetric, negligible-loop-inductance,
overdamped, zero-noise limit. The replacement must name that approximation and
must not silently apply it to devices whose fitted curves include finite-loop,
asymmetric, hysteretic, or noisy behavior.

Use the magnetic flux quantum

```text
Phi0 = h/(2e) approximately 2.067833848e-15 Wb
```

and calculate normalized applied flux either from mutual inductance or, more
directly for the parameters available to this project, from equivalent current
periods:

```text
phi_cycles = Phi_applied/Phi0
           = phaseOffsetCycles + sum_k(M_k * I_k / Phi0)
           = phaseOffsetCycles + sum_k(polarity_k * I_k/Iphi_k)
```

Here `Iphi_k`, named `currentPerPhi0Amp` in the new records, is precisely the
kind of parameter represented by legacy `PHINOT_G`; it is the canonical user-
facing input. At minimum, `k` distinguishes SQ1, SSA, row FAS, and chip FAS. If
mutual inductance is later available, the equivalent is
`Iphi_k = Phi0/abs(M_k)`. Within one modeled SQUID type, the old expression
`flux <= iMeas - iFb`, followed by that type's `PHINOT_G` divisor, is a
reasonable simplified model when its coupled currents are intentionally
assigned the same period and opposite polarities. Optional coil-specific
coupling ratios or period overrides can be added without ever collapsing the
four required type-level values. Bias-current self-flux and loop-arm asymmetry
are optional refinements when required by data.

For two identical junctions, each with critical current `I0` and shunt
resistance `R`, with `betaL << 1` and `betaC << 1`, the handbook gives

```text
IcSQUID(phi_cycles) = 2*I0*abs(cos(pi*phi_cycles))

V(Ibias, phi_cycles) = 0                                      if abs(Ibias) <= IcSQUID
                     = sign(Ibias)*(R/2)
                       * sqrt(Ibias^2 - IcSQUID^2)             otherwise
```

The factors of two matter: `2*I0` is the maximum critical current of the whole
SQUID, while `R/2` is the two equal junction shunts in parallel. The old model's
formula has the same algebraic shape only if `IC0_G` is reinterpreted as the
whole-SQUID maximum and `RN_G` as the whole-SQUID effective normal resistance.
Those conventions were undocumented, so the legacy numerical values cannot be
carried forward as junction parameters.

The ideal subcritical voltage is zero. Any physical series or parasitic
resistance belongs in the surrounding circuit and contributes `I*R` there; it
must not be inserted into the SQUID voltage law only on one branch. Also keep
the following quantities distinct:

```text
static resistance  Rstatic = V/I
dynamic resistance Rdyn    = dV/dI
```

For the ideal voltage-state equation above,
`Rstatic = (R/2)*sqrt(1-(IcSQUID/Ibias)^2)`, which is essentially what the old
model called `rEff`. It is not `Rdyn`; differentiating gives
`Rdyn = (R/2)*abs(Ibias)/sqrt(Ibias^2-IcSQUID^2)` when `IcSQUID` is locally
independent of bias. The distinction matters in the SQ1-to-SSA settling pole.

The standard dimensionless physical parameters are

```text
betaL = 2*L*I0/Phi0
betaC = 2*pi*I0*R^2*C/Phi0
Gamma = 2*pi*kB*T/(I0*Phi0)
```

for symmetric junctions under the handbook's conventions. `L` is total SQUID
loop inductance, `C` and `R` are the capacitance and shunt resistance of one
junction, and `Gamma` measures thermal fluctuations. An asymmetric device also
needs the two junctions' `I0`, `R`, and `C` values and the two arm inductances,
or equivalent mean-plus-asymmetry parameters. Store primitive values and
derive these dimensionless quantities, or store resolved dimensionless
metadata with provenance; do not make both independently configurable.

Finite `betaL`, finite `betaC`, thermal noise, and junction or loop asymmetries
change the modulation depth, curve shape, phase, hysteresis, and positive/
negative-bias response. Published treatments solve the coupled RCSJ junction
and fluxoid equations numerically; there is no justification for making
`betaL` or `betaC` an arbitrary scale factor on the cosine law.

For this model's purpose, it is reasonable to adopt the symmetric,
overdamped, negligible-loop-inductance equation as the default behavioral
approximation. It supplies the periodic curve, bias dependence, extrema, and
two useful slopes needed by tuning and closed-loop tests without a costly
junction solver. The simplification must be explicit in the type/profile name
and documentation, but users should not have to supply `L`, `C`, `betaL`, or
`betaC` merely to run it.

Keep the transfer interface extensible to two curve families:

1. `IDEAL_OVERDAMPED_LOW_L`, implementing only the equations and validity
   conditions above; and
2. `PERIODIC_SURFACE_FIT`, a measured or offline-RCSJ-derived periodic response
   versus flux and bias, represented by compact Fourier coefficients or a
   small table suitable for both GHDL and VCS.

A full time-domain RCSJ solver is valuable as an offline reference but is not
part of the first HDL regression model. `PERIODIC_SURFACE_FIT` is also not
required for the first implementation; add it when measured curves show that
the ideal approximation is inadequate for a tuning decision. `betaL`, `betaC`,
temperature, junction spread, and asymmetry remain optional provenance for a
fit unless a later validated solver consumes them. The ideal profile documents
its assumption rather than pretending those omitted effects are zero-valued
measurements.

An SSA or SQ1 series array is not merely a scalar gain. Its voltage is

```text
Varray(Ibias, phi) = sum_i(Velement_i(Ibias, phi_i))
```

and becomes `N*Velement` only for `N` identical, coherently coupled elements.
Critical-current, coupling, bias, and trapped-flux spread distort and reduce
the array response. Both `SsaParams` and `Sq1Params` therefore need an active
element count and optional deterministic element/phase spread. The count is
profile-specific: published NIST devices include four-element and two-element
SQ1 implementations, while SSAs commonly contain much larger series arrays.

The FAS literature verifies the switching mechanism but not a universal
sigmoid equation. A low-`betaL` FAS array is superconducting or low-resistance
near integer `Phi0` and reaches maximum resistance near half-integer `Phi0`;
its effective resistance is periodic, bias-dependent, and broadened by element
critical-current spread. For the initial model, evaluate the same ideal
low-inductance SQUID equation and derive `Rstatic = V/I` for the FAS branch,
with explicit zero-bias handling and surrounding parasitic resistance. Row and
chip FAS devices retain independent effective parameters. A later calibrated
model may replace this with fitted `Rfas(Icolumn, phi)` surfaces and measured
closed/open resistances. A logistic activation may be retained only as a
clearly synthetic fixture, not as a physical law.

Finally, the NIST circuit measurement places the SQ1/FAS MUX device in parallel
with the approximately 1-ohm column shunt, so the static operating point obeys

```text
Vdevice(Idevice, selects, fluxes) = (Ibias - Idevice)*Rshunt
```

This must be solved as a branch-current operating point (or represented by a
fit already parameterized by applied column bias). It is not a resistance-
conductance division. In a two-level device, row and chip switches are nested
current-bypass networks. Multiplying two normalized enables is acceptable only
as a reduced model after it matches all four measured/simulated select states;
the literal network or a four-state fitted surface is the reference.

The resulting verdict on the legacy equations is:

| Legacy behavior | Literature verdict | Replacement |
| --- | --- | --- |
| `(iMeas-iFb)/PHINOT` used as flux | reasonable simplification for equal/opposite coil coupling and one common current period | accept `PHINOT` as current-per-`Phi0`; allow per-coil values |
| `Ic0*abs(cos(pi*phi))` | valid only with `Ic0 = 2*I0` in the low-`L` symmetric limit | explicit convention and validity assertion |
| `Rn*sqrt(Ibias^2-Ic^2)` | valid only with `Rn = R/2` in the same limit | explicit whole-device or per-junction convention |
| `Ibias*Rseries` below `Ic` | not the ideal SQUID voltage | zero SQUID voltage plus separate circuit resistor |
| old `rEff` | static `V/I`, not dynamic `dV/dI` | expose separately named values if needed |
| ad hoc `betaL`/`betaC` curve tweaks | not supported | use the documented ideal approximation, or an offline RCSJ/measured fit |
| FAS logistic/enable product | useful synthetic approximation only | bias-dependent periodic switch surface and validated nested-network reduction |

### Validation performed during investigation

The existing `SimPkg`, `Squid`, `Sq1`, `SquidColumn`, and `WaferSim` sources
were analyzed with GHDL 6.0.0. A temporary minimal `SquidColumn` testbench then
failed at time zero with a bound check at `Squid.vhd:47`, confirming the
uninitialized-`real` problem. No production source was changed by that test.
This also demonstrates why GHDL is useful during development: every new pure
function, device component, column, detector module, and harness should receive
a focused GHDL elaboration/run as soon as it exists. The replacement must also
support VCS for the final Vivado-exported `GroupTb` integration flow.

## What "Adequate" Means

The initial model is adequate if it reproduces the observable transfer behavior
needed by firmware and tuning software, while remaining fast and deterministic:

- periodic SA output versus SA feedback, with bias-dependent amplitude;
- periodic SQ1 response versus SQ1 feedback, with bias-dependent amplitude;
- a clear FAS transition versus row-select current;
- the two-level row/chip-select truth table and useful off-row isolation;
- TES current coupling only to the addressed SQ1;
- configurable polarity, periods, offsets, gains, and per-channel variation;
- finite but configurable settling after DAC or row changes; and
- bounded, initialized behavior at zero bias and at all legal DAC values.

It does not initially need to predict junction switching, RF behavior,
stochastic flux jumps, detailed noise spectra, or TES electrothermal dynamics.
Those effects can be added after DC tuning and row switching work reliably.

## Proposed Model Architecture

### Configuration strategy

Parameterization is a primary requirement. Keep seven configuration domains
separate so changes in one domain do not become changes to device equations:

| Domain | Examples | Owner |
| --- | --- | --- |
| Detector row topology | rows, banks, local RS/CS terminals | detector model |
| Simulated extent | instantiated columns, physical column identities | detector model |
| Device parameters | SQ1, FAS, SSA, TES, shunts, select lines | parameter package |
| Instance variation | weak SQ1, dead TES, gain spread | resolved parameter arrays |
| Cold/warm harness | board/channel to detector terminal | group harness |
| Logical row schedule | time slot to two physical DAC addresses | software and `RowDacDriver2` |
| Runtime stimulus/state | TES steps/pulses and electrical state | testbench/model ports |

The model must not merge the last three maps. The detector sees only currents
on its local terminals. It does not know which warm board generated a current
or which logical row slot caused the firmware to drive it.

Describe detector-local cells independently of warm wiring:

```vhdl
type RowCellMapType is record
   bankIndex : natural;
   rowIndex  : natural;
   rsInput   : natural;
   csInput   : integer;  -- -1 means a single-level cell
end record;

type RowCellMapArray is array (natural range <>) of RowCellMapType;
```

Describe the cold/warm harness with separate endpoint records:

```vhdl
type SelectKindType is (ROW_SELECT_INPUT, CHIP_SELECT_INPUT);

type RowConnectionType is record
   rowBoard     : natural;
   warmLine     : natural;
   detectorIndex : natural;
   selectKind   : SelectKindType;
   selectIndex  : natural;
end record;

type ColumnConnectionType is record
   columnBoard    : natural;
   warmChannel   : natural;
   detectorIndex : natural;
   detectorColumn : natural;
end record;
```

The firmware/software `RowMap` remains a companion test configuration. It maps
each logical time slot to the two eight-bit physical DAC addresses consumed by
`RowDacDriver2`; it is not an input to `DetectorModuleSim`. A group preset may
bundle an expected `RowMap` with harness data so a checker can prove they agree.

Named detector builders should provide `TOPOLOGY_1X22_C`,
`TOPOLOGY_5X10_C`, `TOPOLOGY_6X10_C`, and other local row maps. A named
`GROUP_DUAL_BA4_C` preset should provide two `6x10` detector instances, their
row/column harness connections, and the expected `RowMap2x6x10` schedule. A
custom map must be accepted through the same interfaces. Column count remains
independent of every row-topology preset.

Use a shared normalized curve description only for reusable mathematics, then
wrap it in distinct records for each physical device role. Do not use one
generic "SQUID params" record at the model boundary.

```text
SquidCurveParams
  curve family (IDEAL_OVERDAMPED_LOW_L by default, optional
  PERIODIC_SURFACE_FIT), effective whole-SQUID maximum critical current,
  effective whole-SQUID normal resistance, current per Phi0, phase offset,
  optional bias-indexed Fourier/table coefficients, positive/negative-bias
  behavior, output limits, and settling; optional physical/provenance metadata
  stays separate

SsaParams
  an independent SquidCurveParams core containing SSA IC0/RN/PHINOT, active
  series-element count and optional deterministic element spread, independent
  input/feedback polarities and optional relative coupling overrides, optional
  bias-to-flux self-coupling, voltage offset, output common mode, differential
  voltage clamps, and SSA-specific settling

Sq1Params
  an independent SquidCurveParams core containing SQ1 IC0/RN/PHINOT, active
  series-element count and optional deterministic element spread, independent
  TES/feedback polarities and optional relative coupling overrides, optional
  bias-to-flux self-coupling, selected leakage, and SQ1-specific settling

RowFasParams
  an independent switch SquidCurveParams core containing row-FAS
  IC0/RN/PHINOT, active element count and deterministic spread, select polarity,
  zero-select bypass resistance, half-flux activated resistance, usable
  plateau/period, residual SQ1-current fraction, surrounding series resistance,
  row-FAS settling, and optional fitted resistance-surface coefficients

ChipFasParams
  an independent switch SquidCurveParams core containing chip-FAS
  IC0/RN/PHINOT, active element count and deterministic spread, select polarity,
  zero-select bank-bypass resistance, half-flux activated resistance, usable
  plateau/period, bank leakage, inner/outer-loop series resistance as applicable
  to the device profile, chip-FAS settling, and optional fitted resistance-
  surface coefficients

TesParams
  shunt resistance, TES resistance/model, Nyquist inductance,
  SQ1 input coupling, initial current, optional thermal parameters

MuxColumnParams
  full-column shunt, series parasitic, baseline/gain, saturation,
  optional column settling time

SelectLineParams and CableParams
  cable/coil resistance and optional inductance, shared line loading,
  current polarity and optional settling
```

The canonical runtime coupling parameter is the measured or supplied current
period because that is what is available to this project:

```text
phaseContributionCycles = polarity * currentAmp/currentPerPhi0Amp
```

SQ1, SSA, row FAS, and chip FAS always have independent
`currentPerPhi0Amp` values. Within SQ1 or SSA, input and feedback contributions
use that type's value by default; optional relative coupling overrides can
represent unequal coils later. If mutual inductance is supplied instead, the
builder derives `currentPerPhi0Amp = Phi0/abs(M)` and stores only the resolved
period. Phase offsets use cycles.

The ideal curve family uses the exact limited-case equations in the literature-
verification section, with effective whole-SQUID parameters named so the
legacy values can be passed directly:

```text
criticalCurrentAmp         = 2*perJunctionI0
effectiveNormalResistance = perJunctionR/2
```

For each of the four device types, legacy-style `IC0_G` maps to that type's
`criticalCurrentAmp`, `RN_G` maps to its
`effectiveNormalResistanceOhm`, and `PHINOT_G` maps to its
`currentPerPhi0Amp`. No factor-of-two conversion is applied to those supplied
values because the new names explicitly define them as effective whole-device
quantities. When only an effective measured SSA or SQ1 curve is available, set
`elementCount = 1` and model the complete array as one lumped device. Use
`elementCount > 1` only when the curve parameters genuinely describe an
individual repeated element or deterministic element variation is being
tested.

The optional fit family uses a periodic surface such as

```text
y(Ibias, phi) = offset(Ibias)
              + sum_n(a_n(Ibias)*cos(2*pi*n*phi)
                    + b_n(Ibias)*sin(2*pi*n*phi))
```

with coefficients interpolated across bias. It is a compact representation of
measured or offline-solved data, not a new physical law. Both families feed the
same interface. `betaL` and `betaC` must never alter a curve through an ad hoc
formula. They are not inputs to the initial ideal behavioral model and are only
provenance for fitted data unless a later numerical solver is explicitly
implemented and validated. `SsaParams` refers to the cold series-array/SSA
device; its externally visible bias and feedback controls retain the project's
`SaBias`/`SaFb` naming.

All four devices may use the same pure curve helper, but their parameter
ownership is independent. `SQ1_SYNTHETIC_C`, `SSA_SYNTHETIC_C`,
`ROW_FAS_SYNTHETIC_C`, and `CHIP_FAS_SYNTHETIC_C` each contain their own
`criticalCurrentAmp`, `effectiveNormalResistanceOhm`, and
`currentPerPhi0Amp`; none may be an alias or fallback for another. Their
periods, resistances, critical currents, phase offsets, bias behavior, and
settling may all differ. The typed wrapper records prevent an SSA parameter
record from being passed where a row-FAS or chip-FAS record is expected.

Use SI units throughout. Because VHDL `real` has no dimensional type checking,
field names should carry unit suffixes such as `Ohm`, `Amp`, `Volt`, and
`Second`, and elaboration assertions should reject invalid periods, negative
resistances/inductances, invalid element counts, reversed clamps, out-of-range
mappings, and inconsistent array sizes.

There is no single override chain that fits every parameter. Builders should
start from a named nominal model and return fully resolved arrays at the scope
where each device physically exists:

- module-level parameters;
- per-column MUX and SSA parameters;
- per-column/per-bank `ChipFasParams` parameters;
- per-column/per-row `Sq1Params` and `RowFasParams` parameters;
- per-column/per-row TES parameters; and
- per-physical-select-line cable/load parameters.

Leaf entities receive only resolved records. For example:

```vhdl
constant SQ1_PARAMS_C :
   Sq1ParamsArray(0 to NUM_COLUMNS_C*NUM_ROWS_C-1) := (
      pixelIndex(2, 17, NUM_ROWS_C) => SQ1_WEAK_C,
      others                        => SQ1_SYNTHETIC_C);
```

Flatten multi-dimensional arrays and provide checked index helpers. The chosen
record-array generic forms must pass GHDL during local development and the
actual Vivado 2025.1/VCS X-2025.06 flow before the public interfaces are
considered frozen.

Suggested generics for one detector-module or wafer-slice instance:

```vhdl
generic (
   ROW_PROFILE_G    : RowTopologyProfileType := HIERARCHICAL_6X10;
   NUM_ROWS_G       : positive := rowCount(ROW_PROFILE_G);
   NUM_COLUMNS_G    : positive := 8;
   NUM_BANKS_G      : positive := bankCount(ROW_PROFILE_G);
   COLUMN_ID_MAP_G  : NaturalArray(0 to NUM_COLUMNS_G-1) :=
                         identityMap(NUM_COLUMNS_G);
   ROW_CELL_MAP_G   : RowCellMapArray(0 to NUM_ROWS_G-1) :=
                         makeRowCellMap(ROW_PROFILE_G, NUM_ROWS_G);
   COLUMN_PARAMS_G  : MuxColumnParamsArray(0 to NUM_COLUMNS_G-1) :=
                         (others => MUX_COLUMN_SYNTHETIC_C);
   SSA_PARAMS_G     : SsaParamsArray(0 to NUM_COLUMNS_G-1) :=
                         (others => SSA_SYNTHETIC_C);
   SQ1_PARAMS_G     : Sq1ParamsArray(0 to NUM_COLUMNS_G*NUM_ROWS_G-1) :=
                         (others => SQ1_SYNTHETIC_C);
   ROW_FAS_PARAMS_G : RowFasParamsArray(0 to NUM_COLUMNS_G*NUM_ROWS_G-1) :=
                         (others => ROW_FAS_SYNTHETIC_C);
   CS_FAS_PARAMS_G  : ChipFasParamsArray(0 to NUM_COLUMNS_G*NUM_BANKS_G-1) :=
                         (others => CHIP_FAS_SYNTHETIC_C);
   TES_PARAMS_G     : TesParamsArray(0 to NUM_COLUMNS_G*NUM_ROWS_G-1) :=
                         (others => TES_SYNTHETIC_C));
```

`GroupTb` should expose only simple scalar/enum preset generics that are easy to
override in the Vivado/VCS flow. Package builder functions resolve those
presets into the record arrays passed to leaf entities. Custom configurations
may define new constants or a thin testbench wrapper without changing the
behavioral model.

Structural checks at elaboration must prove:

- local RS/CS indices exist and single-level cells have no CS input;
- detector-local row entries and physical column IDs are unique;
- every hierarchical bank has one valid local chip-select terminal;
- every warm row/column endpoint is in range and has at most one load;
- every required detector endpoint is connected exactly once;
- unused warm channels have an explicit termination policy;
- the expected logical `RowMap` selects the intended detector/local row; and
- all parameter-array lengths match their physical object counts.

### Analog interface contract

The model boundary must preserve the electrical meaning of the existing FEB
models. `SimPkg.CurrentType` is a Thevenin source represented by open-circuit
voltage and series impedance; it is not a measured current. SA bias, SA
feedback, SQ1 bias, SQ1 feedback, and row-select pairs must be converted with
`currentDiff(p, n, loadOhm)`, using a load derived from the modeled cable and
coil rather than the prototype's arbitrary 200-ohm value.

TES bias is the exception. `ColumnFebTesBiasAmp` already returns two `real`
current values, with equal and opposite signs in the nominal model, and its
caller intentionally swaps the schematic P/N connection. The harness should
reduce this pair to one documented positive detector-current direction and
warn if the two terminals cease to be equal and opposite within tolerance.
The sign must be checked against the column FEB schematic before calibration.

`saBiasInP/N` are voltage-sense inputs to the warm differential preamplifier,
not the voltage developed by a fictitious SA-bias load. The initial model will
return the modeled SSA output symmetrically:

```text
saBiasInP = commonMode + polarity * Vssa / 2
saBiasInN = commonMode - polarity * Vssa / 2
```

Common mode, polarity, and output clamps are parameters. Symmetric drive is a
functional assumption suitable for ADC-path testing; it must be updated if the
real SSA termination establishes a different common mode.

Each physical row-select line has one source/load calculation, even when its
flux couples to FAS devices in every detector column. The resulting current is
fanned out magnetically to all connected cells; it is not divided once per
FAS. Column circuits remain independent. Unconnected warm endpoints use an
explicit `OPEN`, `TERMINATED`, or `ERROR` policy so an accidental omission
cannot silently become a zero-current detector connection.

Use separate typed drive and sense records internally, even if compatibility
wrappers retain the present flat ports. This keeps input currents, returned
SSA voltages, and per-pixel stimuli from being interchanged accidentally.

### 1. `WaferSimPkg`

Define explicit model configuration and pure helper functions:

- detector topology, harness-map types, and checked builder functions;
- units and sign conventions;
- periodic SQUID transfer function;
- bias-dependent response envelope;
- FAS activation function;
- static TES bias-cell solution; and
- bounded/clamped arithmetic helpers.

All `real` state must have explicit initial values. Pure transfer functions
should be unit-tested independently of the full board simulation.

### 2. `DetectorModuleSim`

Make a cold detector/wafer module or a column slice of one the primary model
boundary. It has independently parameterized row topology and column count and
owns its TES, MUX, and SSA device instances. Its responsibilities are:

- accepting currents on its detector-local row/chip-select terminals;
- instantiating one column model for each detector column;
- exposing one complete warm-interface bundle per detector column;
- accepting per-pixel runtime TES stimuli; and
- returning modeled SSA terminal voltages.

`COLUMN_ID_MAP_G` identifies which physical detector columns a reduced instance
represents, defaulting to `0 .. NUM_COLUMNS_G-1`. This permits per-physical-
column parameter sets and arbitrary slices without coupling the model to a warm
board. The present eight-column `WaferSim` port shape can be retained as a
compatibility wrapper around an eight-column `DetectorModuleSim` instance.

The diagrams place the detector/TES assembly near 100 mK and the SSA near 4 K.
`DetectorModuleSim` is therefore a functional cold-readout boundary, not a
claim that all contained devices share one physical substrate or temperature.
Internally, `TdmMuxColumnModel` should keep TES/MUX and SSA stages separate so
the package boundary can be split later without changing the transfer model.

### 3. `GroupDetectorHarnessSim`

Add a group-level adapter between board-indexed warm signals and one or more
`DetectorModuleSim` instances. It should:

- convert each differential warm Thevenin-source record into a signed drive
  current using documented source/cable impedances;
- route each `(column board, channel)` bundle through the configured column
  connection map;
- route row-board output currents to the configured detector RS/CS lines;
- support unused warm channels explicitly; and
- return each SSA voltage to the correct warm channel, initially symmetrically
  as `saBiasInP = +Vssa/2` and `saBiasInN = -Vssa/2`.

The final voltage polarity is an assumption until checked against the column
FEB schematic or a known bench response.

### 4. `TdmMuxColumnModel`

Represent the MUX hierarchy directly:

- series bank/chip list;
- row SQ1/FAS cells within each bank;
- optional bank-level chip-select FAS;
- common SQ1-bias and SQ1-feedback coupling;
- full-column shunt;
- SSA input coupling, SSA bias, and SSA feedback; and
- one TES/input-current source per logical pixel.

The default solver should calculate an observable transfer from explicit state
and inputs. It should not build mutually dependent concurrent `real` equations.
If memory or runtime becomes significant, inactive cells can be collapsed to a
single equivalent off-state term.

For the fastest synthetic regression profile, compose the column response
explicitly:

```text
rowEnable[j]  = fasActivation(Irs[rowCell[j].rsInput])
chipEnable[j] = 1                                      -- single level
              = fasActivation(Ics[rowCell[j].csInput]) -- two level
weight[j]     = rowEnable[j] * chipEnable[j]

sq1Phase[j] = sq1PhaseCycles(Sq1Params[j], Isq1Fb,
                              Ites[j], Isq1Bias)
cell[j]     = weight[j] * sq1BiasEnvelope(Isq1Bias)
              * periodicTransfer(sq1Phase[j])

Imux = clamp(columnBaseline(Isq1Bias)
             + sum(cell[j] + configuredLeakage[j]))
saPhase = ssaPhaseCycles(SsaParams, Imux, IsaFb, IsaBias)
Vssa = clamp(saOffset(IsaBias)
             + saBiasEnvelope(IsaBias)*periodicTransfer(saPhase))
```

This is an observable plant model, not a literal resistance-network solution.
It deliberately has no instantaneous algebraic feedback. It is acceptable as
a fast test double only after comparison with the four-state nested-network
reference described below. If more than one cell is enabled, its configured
contributions sum and then clamp; the model also emits a warning unless the
selected test explicitly permits multi-select. Zero selected rows produce the
configured column baseline plus leakage.

The calibration/reference profile must represent each row FAS, SQ1 branch,
chip FAS, and placement-specific series resistor in its actual nested bypass
network. At each static update it solves

```text
Vdevice(Idevice, state) - (Ibias-Idevice)*Rshunt = 0
```

with a bounded deterministic bisection or monotonic table inversion. Any
reduced enable/weight coefficients used by routine regressions are generated
from or checked against that reference at all RS/CS combinations and across
the configured bias range. This gives both simulators a dimensionally correct
operating point without a continuous-time analog algebraic loop.

### 5. SQ1 and SSA transfer models

Resolve each physical coil coupling to normalized flux before applying the
device curve:

```text
phase_sq1_cycles = sq1FbPolarity * I_sq1fb / sq1FbCurrentPerPhi0Amp
                 + tesPolarity * I_tes / tesInputCurrentPerPhi0Amp
                 + biasToFluxCyclesPerAmp * I_sq1bias
                 + phaseOffsetCycles
response  = bias_envelope(I_bias) * periodic_transfer(phase_sq1)

phase_sa_cycles = inputPolarity * I_mux / inputCurrentPerPhi0Amp
                + feedbackPolarity * I_safb / saFbCurrentPerPhi0Amp
                + biasToFluxCyclesPerAmp * I_sa_bias
                + phaseOffsetCycles
V_ssa     = V_offset(I_sa_bias) + bias_envelope_sa(I_sa_bias)
            * periodic_transfer(phase_sa)
```

The periodic transfer is either the verified ideal low-inductance equation or
a bias-indexed periodic fit. A sine plus optional harmonics is permitted only
as a named synthetic `PERIODIC_SURFACE_FIT` fixture. Measured/offline-derived
fits should retain enough harmonics or table points to reproduce the positive
and negative slopes, extrema, asymmetry, and bias dependence within a declared
error bound. For an array, evaluate and sum the configured elements; only use
`elementCount*singleElementResponse` when the profile explicitly declares the
elements identical and coherently coupled. The bias axis must cover onset and
a broad optimum so the existing bias-tuning algorithms have a real maximum to
find.

SSA and SQ1 curve tests must sweep each coupling input independently over at
least three configured periods and sweep bias across onset, optimum, and
rolloff. They should recover period, peak-to-peak amplitude, maximum positive
and negative slope, phase offset, harmonic distortion, and clamp behavior.
Combined-input tests must demonstrate linear phase superposition before the
nonlinear periodic transfer. At least one test must assign visibly different
SSA and SQ1 periods, critical currents, bias optima, harmonic coefficients, and
polarities so accidental sharing of a record is detected.

### 6. FAS selection

Model each FAS first as a periodic, bias-dependent resistance derived from
select flux. The initial `periodic_switch_resistance` uses the ideal SQUID
equation and its static resistance; a later profile may use a fitted surface:

```text
fas_phase    = selectPolarity * I_select / selectCurrentPerPhi0Amp
               + phaseOffsetCycles
Rfas         = periodic_switch_surface(I_column_bias, fas_phase,
                                       RowFasParams or ChipFasParams)
row_enable   = normalize(Rfas, bypassResistance, activatedResistance)
chip_enable  = 1.0                         -- one-level profile
             = normalize(Rchip_fas)        -- reduced two-level profile
pixel_weight = row_enable * chip_enable
```

A smooth periodic resistance curve is preferable to a Boolean threshold
because FAS tuning needs a measurable curve. Integer-flux points must produce
the configured low-resistance state and half-integer points the configured
high-resistance state, subject to phase and polarity. Element spread and bias
dependence may broaden the transition. A logistic transition is allowed only
in a synthetic fixture and must still be embedded in a periodic curve.

Row- and chip-select tests must use deliberately different periods, phase
offsets, transition widths, resistance ratios, and polarities. Sweep each one
with the other held both active and inactive, and verify its own curve plus the
full nested-network four-state response. If the fast model uses a two-enable
product, verify it against those four reference states and a select-current
sweep to a configured error tolerance. This both detects parameter cross-
wiring and produces the known reference curves needed by future row- and
chip-select tuning software.

### 7. TES model in two stages

The first stage should support a direct, deterministic per-pixel input-current
stimulus. This isolates row addressing, SQ1 coupling, DSP, and frame readout
before adding thermal state.

The next stage can solve the electrical TES branch. For a bias cell containing
`Rshunt` in parallel with `RTES + Lnyquist`, a useful state equation is:

```text
Lnyquist * dItes/dt = Rshunt * Ibias - (Rshunt + Rtes) * Ites
```

Its DC limit is:

```text
Ites = Ibias * Rshunt / (Rshunt + Rtes)
```

Use a clocked or explicitly sampled update, with a bounded time step, rather
than an analog algebraic feedback loop. A later optional electrothermal model
may evolve TES temperature from optical power, Joule heating, heat capacity,
and bath conductance. It is not required for the first useful GroupTb model.

### Time, state, and stimulus contract

Static transfer functions are combinational and pure. Every dynamic quantity
is initialized and updated on an explicit `modelClk`/`modelRst` interface with
a declared `MODEL_STEP_SECOND_G`; do not use chains of `after` assignments as
an analog solver. A first-order state may use an exact exponential coefficient
or a bounded Euler coefficient:

```text
xNext = x + alpha * (target - x), where 0 <= alpha <= 1
```

Physical time constants and any acceleration factor are separate parameters.
If a regression scales settling to fit practical simulation time, its report
must state that scale rather than presenting the run as real-time fidelity.

Provide one equivalent TES-current stimulus per instantiated
`(column, row)`, in amperes, summed with the electrical TES solution before
SQ1 input coupling. Focused testbenches can drive this array directly.
`GroupTb` should initially offer deterministic built-in stimulus modes through
simple generics: `QUIET`, `STATIC_PIXEL`, `STEP_PIXEL`, and `PULSE_TRAIN`, with
target detector/column/row, amplitude, start time, and duration. A simulation-
only register-controlled stimulus may be added later if an end-to-end software
test needs runtime injection; it is not needed to validate the first model.

Stimulus assertions must define whether a change occurs before row selection,
during settling, or between ADC sample windows. This makes tests of the next
row visit and controller latency repeatable across simulator runs.

## GroupTb Integration Constraints

`GroupTb` currently hard-codes `LOAD_C := "WAFER"`. Make the load profile a
testbench generic so the resistive load board and wafer model can both remain
regression targets.

The testbench constants suggest multiple row and column boards, but its analog
arrays are not indexed by board. More than one board would therefore share or
multiply-drive the same modeled wires. The board analog interfaces must become
board-indexed or consistently flattened as `(board * 8) + channel` before the
near-term detector assemblies can be represented correctly.

Keep one-column and one-board configurations for fast focused tests, but make
multi-board connectivity part of the wafer-model integration rather than an
unrelated future change. The representative full-system profile should be two
BA4 modules connected to one row module and three column modules, subject to
confirmation of the formal group boundary.

Use two complementary simulation paths:

- GHDL is the local development and sanity-check simulator. Pure functions,
  SQUID/FAS devices, network solvers, cells, banks, columns, detector modules,
  and harnesses should have small self-checking GHDL tests that compile and run
  without Vivado-generated libraries.
- VCS X-2025.06 remains the system-integration simulator. Full `GroupTb` is
  exported by Vivado 2025.1 and run with VCS because it includes vendor
  simulation IP and the complete firmware/software co-simulation path.

The behavioral source should remain ordinary VHDL 2008 accepted by both
simulators. Simulator-specific scripts and vendor libraries belong in their
respective test harnesses, not in the device equations. XSIM support is not a
requirement. The common and `GroupTb` ruckus files should explicitly load new
simulation VHDL as VHDL 2008 so record-array generics are interpreted
consistently.

Complex record-array configuration should remain below `GroupTb`. Its public
generics should be simple values such as load profile, detector preset,
simulated column count, stimulus mode, and deterministic seed, because those
are robust to override in the exported VCS flow.

The VCS `GroupTb` test runner must start the existing TCP bridges, PyRogue
simulation server, and client test with matching column-board count, row-board
count, `rowAddrBits`, and `maxRows`. Capture those values once in each test
profile and derive both HDL generics and server arguments from it; a mismatched
server tree must fail before tuning begins. Automating this orchestration is
part of the integration work, because the current `README_cosim.md` flow is
manual.

## Muxed Readout, Fixed PID, and Tuning Coverage

The model can test multiplexed readout and the current fixed-point PID, but
only if the closed-loop signal path remains intact:

```text
physical row DAC currents
  -> modeled RS/CS activation and selected TES/SQ1
  -> modeled SSA differential voltage
  -> existing warm preamp and ADC model
  -> DataPath / fixed-point AdcDsp accumulator and per-row PID state
  -> existing fast DAC and SQ1-feedback current
  -> modeled SQ1 response on the next visit to that row
  -> EventBuilder / host readout
```

The detector model must not accept the firmware's logical `rowIndex` as an
analog shortcut. Responding to the actual row-line currents is what tests the
row map, turn-off/turn-on sequence, settling interval, ADC sample window, and
inactive-module slots.

### Open-loop multiplexed readout

A deterministic TES offset or step on each selected pixel can verify:

- logical-row ordering and reported row tags;
- that the ADC sample after each row strobe belongs to the intended pixel;
- RS+CS addressing and off-row isolation;
- inactivity of detector 0 columns during detector 1 slots and vice versa;
- the mixed `4+4` third column-board harness; and
- sample accumulation and EventBuilder framing with the feedback loop off.

### Fixed-point PID closed-loop readout

Fixed-point `AdcDsp` is the required controller target on this branch. A
deliberately stable synthetic plant slope and polarity should allow tests that:

- each row's feedback memory converges independently toward its set point;
- a TES step is compensated on subsequent visits to that row;
- unselected rows retain their own feedback state without contamination;
- residual ADC error returns within a configured tolerance;
- fixed-point overflow boundaries, integral anti-windup limits, and flux-
  quantum wrapping behave as implemented;
- flux-jump detection/correction can be exercised with an opt-in phase step;
  and
- changing row dwell, settling, or sample timing produces the expected result.

The regression should compare the first few visits against a small reference
implementation of the fixed-point recurrence, then use bounded convergence
criteria rather than require a bit-exact analog waveform indefinitely.

### Tuning procedures

The implemented SA-feedback, SA-bias, SQ1-feedback, and SQ1-bias procedures
are immediate targets. Simulation profiles should use reduced sweep counts and
delays while preserving the production algorithm's decisions. Acceptance must
compare the recovered period, lock slope/polarity, and optimum bias with the
configured synthetic truth.

FAS/row-select tuning is not currently implemented in production software.
There is incomplete scaffolding under `_Tuning.py`, including a stale
`saFbServo()` call, but it is not a usable procedure and must not be treated as
an existing acceptance oracle. The model should instead provide a smooth,
parameterized FAS curve, known optimum/transition values, and direct GHDL sweep
tests. Those become the controlled plant and ground truth when the future
software procedure is designed; the completed algorithm can then be added as
an end-to-end acceptance test without changing the wafer model.

Floating-point PID is intentionally not an acceptance target on this branch.
The analog model should remain controller-agnostic so that a future branch can
run the same closed-loop tests against another DSP implementation without
changing the detector equations or harness.

## Implementation Plan

### Phase 0 - Freeze the interface contract

- Freeze the literature-verified flux normalization, ideal low-`L` equations,
  per-junction versus whole-device conventions, static/dynamic resistance
  names, and their validity assertions before choosing nominal values.
- Establish named detector presets for BICEP3 `22x12`, NIST `50x12`, and BA4
  `60x12`, with custom mappings remaining possible.
- Confirm whether NIST is specifically five 10-row banks and whether the
  two-BA4 one-row/three-column assembly is one firmware/software `Group`.
- Define detector-topology, harness, logical-schedule, device-parameter, time,
  and stimulus contracts independently.
- Compile a minimal record/array-generic example with GHDL immediately, then
  validate the same source with the actual Vivado 2025.1/VCS X-2025.06 flow
  before considering the public interface frozen.
- Explicitly load the relevant simulation sources as VHDL 2008.
- Document current directions, differential voltage polarity, physical units,
  row/chip-select mapping, and column-to-wafer grouping.
- Gather initial nominal parameters and at least one measured SA, SQ1, and FAS
  sweep if available.
- Support direct equivalent TES-current stimulus first and a static electrical
  TES solution second; do not make electrothermal behavior a prerequisite.

### Phase 1 - Stable transfer-function core

- Add `WaferSimPkg` and pure unit-tested helper functions.
- Implement the verified `IDEAL_OVERDAMPED_LOW_L` curve as the initial model,
  with published/reference vectors that catch the factors-of-two and static/
  dynamic-resistance errors. Reserve a clean curve-family interface for a later
  `PERIODIC_SURFACE_FIT`; measured-fit support does not block the first slice.
- Implement new explicit SQ1, FAS, MUX, and SSA transfer evaluations, including
  series-array element summation and a bounded column-shunt operating-point
  solve, rather than modifying the prototype algebra loop in place.
- Add one-level and two-level selection logic.
- Build focused self-checking GHDL testbenches that assert:
  - safe behavior at zero and extreme bias;
  - four deliberately different `IC0`/`RN`/`PHINOT` triples independently
    control SQ1, SSA, row-FAS, and chip-FAS curves;
  - SSA and SQ1 transfer periodicity, bias envelopes, curve shape, and expected
    polarity from deliberately different parameter records;
  - independent row-FAS and chip-FAS periods, transition widths, bias-dependent
    resistance ratios, element counts/spread, and polarities;
  - row-select-only and chip-select-only remain off for a two-level profile;
  - row-select plus chip-select activates exactly one pixel; and
  - any reduced two-enable approximation agrees with the nested-network
    reference across its declared operating range; and
  - SSA output is finite, bounded, and differential.

### Phase 2 - Column slices and one detector module

- Integrate one MUX column behind `DetectorModuleSim`.
- Add explicit model clock/reset and deterministic TES stimulus ports.
- Instantiate eight columns against one warm column module and run an open-loop
  multiplexed-readout `GroupTb` regression through ADC, DSP, and EventBuilder.
- Reconfigure the same entity for all 12 columns of one physical detector.
- Route that detector across two warm column modules using an `8+4` harness
  map, leaving the remaining four warm channels explicitly unused.
- Make the `GroupTb` load choice configurable.
- Run SA-bias/feedback and SQ1-bias/feedback tuning sweeps and compare extracted
  period, amplitude, optimum bias, and lock slope with model configuration.
- Run direct FAS response sweeps and record the configured transition/optimum
  as reference data for future row-select tuning development.
- Only then attempt the currently implemented software tuning sequence.

### Phase 3 - Fixed-point closed-loop readout

- Choose synthetic SQ1/SSA polarity and gain that form a stable plant with
  conservative fixed-point PID coefficients.
- Exercise the existing `AdcDsp` feedback loop through the ADC and fast-DAC
  models, without directly exposing logical row selection to the cold model.
- Compare early feedback updates with a reference fixed-point recurrence.
- Verify independent convergence and state retention for at least two rows in
  one column, then across all eight channels.
- Inject a TES step and verify correction on later visits to only that row.
- Add focused saturation, wrap, and optional flux-jump cases.

### Phase 4 - Dual-detector GroupTb profile

- Make all `GroupTb` analog signals board-indexed.
- Instantiate the two-BA4, three-column-module harness map.
- Configure `RowDacDriver2` with `RowMap2x6x10`; independently check that the
  harness currents select the expected module and detector-local row.
- Verify that only the currently selected logical row contributes to its
  column readout.
- Verify that columns attached to BA4 module 0 are inactive during module 1
  slots and vice versa, including the `4+4` shared warm module.
- Verify row tagging and DSP/event-builder output through `GroupTb`.
- Verify source-board identity on the ring/host stream before file writing.
- Add static `Rshunt || RTES` bias calculation and configurable per-pixel
  resistance/phase/gain variation.

### Phase 5 - Dynamics and non-idealities

- Add electrical `L/R` settling where the simulation time scale can resolve it.
- Add configurable SQUID/SSA settling if needed to expose sample timing bugs.
- Add `PERIODIC_SURFACE_FIT` only if measured or offline-RCSJ curves demonstrate
  a tuning-relevant error in the ideal approximation.
- Add opt-in leakage, stuck/open select, dead SQUID, flux offset, gain spread,
  and deterministic seeded noise.
- Consider an electrothermal TES model only if a concrete firmware or software
  test requires it.

- After the new regressions replace their useful coverage, either remove
  `Squid.vhd`, `Sq1.vhd`, and `SquidColumn.vhd` or mark them clearly as legacy.
  Keep `WaferSim` only as an eight-channel compatibility wrapper if existing
  targets still use its port shape.

## Verification Matrix

Use layered gates so most failures are caught locally without a full VCS system
run:

| Tier | Configuration | Simulator | Required result | Intended cadence |
| --- | --- | --- | --- | --- |
| 0 | pure transfer and map functions | GHDL | finite/bounded values, periods, polarity, map assertions | every change |
| 1 | one SQUID/FAS, cell, bank, and column | GHDL | analytic vectors, RS+CS truth table, operating point, isolation, settling | every change |
| 2 | detector module and cold/warm harness without board IP | GHDL | 1/8/12-column topology, mapping, stimulus routing | every change |
| 3 | one row board + one 8-channel column board | Vivado/VCS | open-loop mux order, ADC/DSP samples, frames, reduced tuning sweeps | routine integration |
| 4 | tier 3 with fixed `AdcDsp` enabled | Vivado/VCS | reference updates, per-row convergence, TES-step recovery | routine or scheduled |
| 5 | one 12-column detector over two boards | Vivado/VCS | `8+4` harness and unused-channel policy | scheduled |
| 6 | two BA4 detectors over three boards | Vivado/VCS | 120-slot schedule, all 24 columns, mixed `4+4` board | slow/manual initially |

Before implementation, record baseline wall time for the present load-board
`GroupTb`. Set numerical tolerances and runtime budgets per tier after the
first working slice; do not hide an impractical regression behind an undefined
"agreed runtime." Tuning tests may reduce points and software wait intervals,
but they must traverse the same control path and choose the same kind of lock
point as production code.

For tiers 5 and 6, distinguish board-level readout correctness from saved-file
identity. The ring already carries source-board identity, but the current host
writer merges every board's readout into file channel 9 and the EventBuilder
body carries only a board-local three-bit column. A full multi-board `.dat`
assertion therefore depends on the separate channelization work documented in
`firmware/common/DataChannelization.md`; the wafer-model test should still
verify analog routing, local column identity, and wire-level board tags.

## Acceptance Criteria

- No time-zero failures, divide-by-zero, non-finite values, or hidden
  combinational feedback loops in focused GHDL tests or under VCS integration.
- The interface package and all reusable model sources compile as VHDL 2008
  under GHDL and VCS; the exported Vivado/VCS `GroupTb` flow also elaborates and
  runs the selected integration profiles.
- One-level and hierarchical address profiles pass mapping tests.
- BICEP3 `22x12`, NIST `50x12`, BA4 `60x12`, and custom arrangements run from
  the same model sources with configuration-only changes.
- The same row topology runs with 1, 8, and 12 instantiated columns without
  changing model source, and `COLUMN_ID_MAP_G` can select a nonzero slice.
- One SQ1, SSA, FAS, or TES can be overridden without changing peer instances.
- The ideal SQUID family reproduces the published low-`L`, overdamped equations
  with explicit effective whole-device conventions, accepts legacy
  `IC0_G`/`RN_G`/`PHINOT_G` values through a documented compatibility mapping,
  and exposes no unsupported `betaL`/`betaC` curve knobs. Any later fitted
  curves carry source and residual metadata.
- SQ1, SSA, row-FAS, and chip-FAS records each require independent effective
  `IC0`, `RN`, and `PHINOT` values. A focused test assigns four visibly
  different triples and proves that each resulting curve uses only its own.
- SSA and SQ1 curves independently honor their core, element count/spread,
  coupling-coil, bias, harmonic, polarity, clamp, and settling parameters.
- Row-select and chip-select FAS curves independently honor their select
  period, phase, bias-dependent periodic resistance, transition, element
  count/spread, bypass/active resistance, leakage, polarity, and settling
  parameters; tests fail if either consumes the other's defaults.
- The hierarchical model requires both the configured row and chip select.
- The dual-BA4 preset maps all 24 detector columns exactly once onto the 24
  channels of three warm column modules, including the third module's `4+4`
  split.
- SA and SQ1 sweeps have configurable, repeatable optima and periods that the
  existing tuning code can recover.
- Direct FAS sweeps expose a configurable, repeatable transition/optimum and
  sufficient slope for a future row-select tuning procedure to recover; the
  absent software procedure is not an initial model acceptance requirement.
- A stimulus on one pixel appears only when that pixel is selected, apart from
  explicitly configured leakage.
- Open-loop mux tests preserve logical row order, sampling association, row
  tags, and frame contents through the production data path.
- Fixed-point `AdcDsp` maintains independent feedback state for each tested row,
  matches the reference recurrence during initial updates, converges within a
  configured bound, and corrects a single-row TES step without affecting peers.
- The modeled SSA voltage remains within the configured ADC/front-end range.
- Default stimuli and variation are deterministic for a configured seed, and
  every regression tier has a recorded runtime budget.
- `ColumnLoadBoard` remains available as a simpler comparison test.

## Parameter Provenance and Calibration

Synthetic defaults must be named accordingly, for example
`SQ1_SYNTHETIC_C`, and documented as numerically stable test fixtures rather
than measured hardware. Measured parameter sets should include detector/mask
or hardware revision, source file or notebook, acquisition date, SI units, fit
method, bias range, curve-family validity range, and fit residual. Distinguish
per-junction parameters from whole-SQUID and array-effective parameters in the
schema. Do not silently replace a synthetic constant with a number copied from
a plot. Record SSA, SQ1, row-FAS, and chip-FAS fits separately; do not infer one
device role's period, element count, or curve shape from another unless the
hardware documentation explicitly establishes that relationship.

Keep raw or large measured data outside the VHDL tree. Prefer a reviewed CSV or
YAML source plus a small generator that emits a compact VHDL parameter package
and reference vectors. The HDL simulation should not parse external data files
at runtime for its default regression. Per-device variation must be resolved
from explicit overrides or a documented deterministic seed.

Keep the VHDL equations deliberately simple and validate them against measured
sweep data or an offline coupled-RCSJ/SPICE reference. The offline model can
use finite loop inductance, capacitance, asymmetry, element spread, and thermal
noise without slowing every `GroupTb` run. Store only compact fitted parameters
and representative expected curves in the HDL regression. Each equation and
reference-vector set should cite its literature source or calibration artifact
in comments close to the implementation.

Validation should proceed from pure functions, to one cell, to one bank, to one
column, and finally to `GroupTb`. This makes a polarity or addressing failure
diagnosable without running a full-system simulation.

## Open Inputs Needed

Implementation can start without a complete production schematic, but the
following evidence is needed before calibration is complete:

1. MUX chip/mask details for each profile, including confirmation of the NIST
   bank factorization and whether each design is single-ended or fully
   differential.
2. The authoritative physical DAC line map for row select and chip select,
   including current polarity and nominal off/on values.
3. Confirmation that the dual-BA4 assembly uses one row module, three column
   modules, and 120 sequential logical row slots within one `Group`.
4. The authoritative column harness map and the SSA-to-column-FEB voltage
   polarity seen by the ADC.
5. Nominal SQ1, FAS, and SSA current periods; mutual-input equivalents;
   critical/normal current ranges; and relevant series/shunt resistances.
6. TES shunt resistance, expected TES resistance range, Nyquist inductance, and
   column bias-current range.
7. Representative measured SA, SQ1, and FAS sweeps, if available.
8. Whether optical-pulse/electrothermal behavior is a near-term requirement or
   whether controlled equivalent TES current is sufficient.

The most useful schematic pages would show one complete MUX bank with RS/CS
connections, the bank-to-bank/SSA column interconnect, the TES bias and Nyquist
branch, and connector names/polarities at the warm/cold boundary.

## Known Adjacent Issues

- Production FAS/row-select tuning is not implemented. Existing `_Tuning.py`
  fragments are incomplete and must not be used as the model oracle; focused
  GHDL sweep tests should establish the reference behavior for its future
  development.
- Multi-board analog connectivity in `GroupTb` is currently incorrect for more
  than one board and is now a prerequisite for the representative BA4 profile.
- Multi-board data is distinguishable on the wire but not in the current saved
  file-channel layout. End-to-end global-column file assertions depend on the
  channelization track; this does not block single-board mux/PID validation.
- Exact physical time constants may be far shorter than a practical HDL time
  step; settle-time scaling may be necessary and must be explicit.

## Recommended First Slice

Use the BA4 60-row/`6x10` row topology as the primary preset. First implement
pure transfer functions, the RS+CS truth table, one column, and direct
per-pixel TES current injection. Expand that unchanged model to eight columns
for the routine single-column-board `GroupTb` regression, then to 12 columns
for a physical detector and harness test. The first full multi-board target
should be the dual-BA4 `1 row module + 3 column modules` assembly, after its
group boundary is confirmed. This sequence preserves fast everyday tests while
still validating the real detector geometry and cabling.
