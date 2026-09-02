# Sensor Wafer Simulation Model

## Status

- Investigation and architecture proposal complete as of 2026-09-02.
- No RTL implementation has started.
- The supplied circuit diagrams are sufficient to begin a behavioral model.
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
- row-select/FAS tuning;
- two-level row-select plus chip-select addressing;
- per-pixel TES signal coupling into the selected SQ1; and
- settling between row transitions and ADC samples.

The first implementation is an FPGA/system verification model, not a
microscopic Josephson-junction or cryogenic thermal simulator.

## Evidence Reviewed

### Project sources

- `firmware/simulations/GroupTb/hdl/GroupTb.vhd`
- `firmware/common/warm_tdm/sim/WaferSim.vhd`
- `firmware/common/warm_tdm/sim/SquidColumn.vhd`
- `firmware/common/warm_tdm/sim/Sq1.vhd`
- `firmware/common/warm_tdm/sim/Squid.vhd`
- `firmware/common/warm_tdm/sim/ColumnLoadBoard.vhd`
- `firmware/common/warm_tdm/sim/RowLoadBoard.vhd`
- the column and row FEB simulation models
- `RowDacDriver2.vhd` and the Python row-map definitions
- SA, SQ1, and FAS tuning code under `software/python/warm_tdm_api/`
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
- CMB-S4 modular readout description (2022), especially its TES-bias and
  two-level switching discussion around Figure 4:
  <https://lss.fnal.gov/archive/2022/conf/fermilab-conf-22-607-ppd.pdf>

The topology below is considered confirmed by the supplied diagrams and those
references. Numerical parameters and warm-interface polarities are not yet
considered confirmed.

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
| `2x6x10` | two independent groups of 10 row-select + 6 chip-select | 120 |

The proposed model should describe the physical line-to-bank mapping as data,
not infer it from hard-coded line-number ranges.

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
- Delayed concurrent assignments create hidden analog feedback loops. These
  are fragile, difficult to initialize, and simulator-dependent.
- The model only represents a single row-select level; it has no chip-select
  bank bypass.
- Generic names conflate physical flux with equivalent input-current periods,
  leaving units unclear.

The load-board model remains useful as a simple electrical-interface smoke test
and should remain selectable as a separate `GroupTb` load profile.

### Validation performed during investigation

The existing `SimPkg`, `Squid`, `Sq1`, `SquidColumn`, and `WaferSim` sources
were analyzed with GHDL 6.0.0. A temporary minimal `SquidColumn` testbench then
failed at time zero with a bound check at `Squid.vhd:47`, confirming the
uninitialized-`real` problem. No production source was changed by that test.

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

Parameterization is a primary requirement. Keep six kinds of configuration
separate so topology changes do not become changes to device equations:

| Layer | Examples | Representation |
| --- | --- | --- |
| Row topology | rows, banks, rows per bank, selection level | profile plus map records |
| Simulated extent | instantiated columns and physical-column identities | scalar plus column-ID map |
| Group harness | warm board/channel to detector/column; row-board lines | endpoint map records |
| Nominal devices | SQ1, row FAS, chip FAS, SSA, TES, column shunt | typed parameter records |
| Instance variation | one weak SQ1, column gain spread, dead TES | arrays of parameter records |
| Runtime stimulus/state | TES pulse, temperature state, selected rows | ports and clocked state |

Do not encode `6x10`, `8x10`, and similar arrangements as separate behavioral
generate trees. Flatten a column into logical-pixel entries and describe each
entry with a topology record resembling:

```vhdl
type PixelMapType is record
   detectorIndex : natural;
   bankIndex     : natural;
   rowIndex      : natural;
   rsBoard       : natural;
   rsLine        : integer;
   csBoard       : natural;
   csLine        : integer;  -- -1 means no chip-select level
end record;

type PixelMapArray is array (natural range <>) of PixelMapType;

type ColumnConnectionType is record
   columnBoard   : natural;
   warmChannel  : natural;
   detectorIndex : natural;
   detectorColumn : natural;
end record;

type ColumnConnectionArray is
   array (natural range <>) of ColumnConnectionType;
```

Named builders or constants should provide standard row maps such as
`TOPOLOGY_1X22_C`, `TOPOLOGY_5X10_C`, `TOPOLOGY_6X10_C`, and
`TOPOLOGY_2X6X10_C`. A custom map must be accepted through the same interface.
This makes the profile names convenient presets rather than limitations in the
model. Column count remains independent of these row-map presets.

Use separate parameter records for each physical device class. Candidate
fields are listed below; the final names and units should be fixed during
Phase 0.

```text
Sq1Params
  bias onset/optimum/rolloff, feedback period, input-current period,
  self-coupling, phase offset, response gain, harmonic/asymmetry terms,
  selected and unselected leakage

FasParams
  select-current period or transition center, transition width, phase,
  on/off conductance or effective enable, residual leakage

SsaParams
  bias onset/optimum/rolloff, input-current period, feedback period,
  phase offset, voltage gain/offset, harmonic terms, output clamp

TesParams
  shunt resistance, TES resistance or resistance-model selection,
  Nyquist inductance, SQ1 mutual-input scale, initial current,
  optional thermal parameters

MuxColumnParams
  full-column shunt, series parasitic, polarity conventions,
  optional column settling time
```

The hierarchy of defaults and overrides should be:

```text
named nominal device model
    -> per-column array
        -> per-bank array
            -> per-pixel array
```

The leaf entities should receive fully resolved parameter records; they should
not contain hidden rules about which override wins. A testbench can change one
device with an aggregate such as:

```vhdl
constant SQ1_PARAMS_C : Sq1ParamsArray(0 to NUM_PIXELS_C-1) := (
   17     => SQ1_WEAK_C,
   others => SQ1_NOMINAL_C);
```

For eight columns, flatten two-dimensional parameter arrays and provide index
helpers such as `pixelIndex(column, logicalRow)`. This avoids unnecessary
dependence on advanced indefinite-record or generic-package features while
still supporting every device independently. An array of records whose bounds
depend on an earlier generic was checked successfully with GHDL 6.0.0; the
chosen form must also receive a small XSIM compatibility test before the main
implementation.

Suggested generic structure for one detector-module or wafer-slice instance:

```vhdl
generic (
   ROW_PROFILE_G    : RowTopologyProfileType := HIERARCHICAL_6X10;
   NUM_PIXELS_G     : positive := pixelCount(ROW_PROFILE_G);
   NUM_COLUMNS_G    : positive := 8;
   NUM_BANKS_G      : positive := bankCount(ROW_PROFILE_G);
   COLUMN_ID_MAP_G  : NaturalArray(0 to NUM_COLUMNS_G-1) :=
                         identityMap(NUM_COLUMNS_G);
   PIXEL_MAP_G      : PixelMapArray(0 to NUM_PIXELS_G-1) :=
                         makePixelMap(ROW_PROFILE_G, NUM_PIXELS_G);
   COLUMN_PARAMS_G  : MuxColumnParamsArray(0 to NUM_COLUMNS_G-1) :=
                         (others => MUX_COLUMN_NOMINAL_C);
   SSA_PARAMS_G     : SsaParamsArray(0 to NUM_COLUMNS_G-1) :=
                         (others => SSA_NOMINAL_C);
   SQ1_PARAMS_G     : Sq1ParamsArray(0 to NUM_COLUMNS_G*NUM_PIXELS_G-1) :=
                         (others => SQ1_NOMINAL_C);
   ROW_FAS_PARAMS_G : FasParamsArray(0 to NUM_COLUMNS_G*NUM_PIXELS_G-1) :=
                         (others => ROW_FAS_NOMINAL_C);
   CS_FAS_PARAMS_G  : FasParamsArray(0 to NUM_COLUMNS_G*NUM_BANKS_G-1) :=
                         (others => CHIP_FAS_NOMINAL_C);
   TES_PARAMS_G     : TesParamsArray(0 to NUM_COLUMNS_G*NUM_PIXELS_G-1) :=
                         (others => TES_NOMINAL_C));
```

The group-level harness should separately accept arrays of detector-module
profiles, row-line maps, and `ColumnConnectionType` entries. Thus a BA4 remains
a coherent `60 x 12` object even though its columns terminate on two different
warm column modules. The two-BA4/three-column-module arrangement is then just a
named harness preset, not special behavior in the SQUID model.

Chip-select FAS parameters should be indexed by flattened column and bank.
The topology map separately identifies the shared physical drive line. This
preserves the real distinction between several FAS devices receiving the same
control current and one shared device.

Topology presets should be tested for structural validity at elaboration:

- every RS/CS address is either absent or within the 32 physical line range;
- logical pixel addresses are unique;
- every used bank has exactly one valid chip-select for a hierarchical profile;
- array lengths agree with column, bank, and pixel counts; and
- no profile silently maps two simultaneously active pixels onto one column
  unless that collision is explicitly allowed for a fault test.

### 1. `WaferSimPkg`

Define explicit model configuration and pure helper functions:

- topology profile and physical row-line maps;
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

- applying its configured physical row/chip-select lines;
- instantiating one column model for each detector column;
- exposing one complete warm-interface bundle per detector column;
- accepting per-pixel runtime TES stimuli; and
- returning modeled SSA terminal voltages.

`COLUMN_ID_MAP_G` identifies which physical detector columns a reduced instance
represents, defaulting to `0 .. NUM_COLUMNS_G-1`. This permits per-physical-
column parameter sets and arbitrary slices without coupling the model to a warm
board. The present eight-column `WaferSim` port shape can be retained as a
compatibility wrapper around an eight-column `DetectorModuleSim` instance.

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

### 5. SQ1 and SSA transfer models

Use an equivalent-input-current phase rather than claiming to model physical
flux directly:

```text
phase_sq1 = k_fb * I_sq1fb + k_tes * I_tes + k_self * I_sq1bias + phase_offset
response  = bias_envelope(I_bias) * periodic_transfer(phase_sq1)

phase_sa  = k_in * I_mux + k_fb_sa * I_safb + phase_offset_sa
V_ssa     = V_offset(I_sa_bias) + bias_envelope_sa(I_sa_bias)
            * periodic_transfer(phase_sa)
```

The periodic transfer can begin as a sine plus an optional second harmonic.
That is sufficient to generate realistic maxima, minima, slopes, and locking
points without a nonlinear circuit solver. The bias envelope should include an
onset and a broad optimum so the existing bias-tuning algorithms have a real
maximum to find.

### 6. FAS selection

Model each FAS with a continuous activation value derived from select current:

```text
row_enable   = fas_activation(I_row_select)
chip_enable  = 1.0                         -- one-level profile
             = fas_activation(I_chip_select) -- two-level profile
pixel_weight = row_enable * chip_enable
```

A smooth transition is preferable to a Boolean threshold because FAS tuning
needs a measurable curve. Optional leakage and select-current periodicity can
be configuration parameters.

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

## GroupTb Integration Constraints

`GroupTb` currently hard-codes `LOAD_C := "WAFER"`. Make the load profile a
testbench generic so the resistive load board and wafer model can both remain
regression targets.

The testbench constants suggest multiple row and column boards, but its analog
arrays are not indexed by board. More than one board would therefore share or
multiply-drive the same modeled wires. The board analog interfaces must become
board-indexed or consistently flattened as `(board * 8) + channel` before the
near-term detector assemblies can be represented correctly.

Keep one-board/one-column configurations for fast focused tests, but make
multi-board connectivity part of the wafer-model integration rather than an
unrelated future change. The representative full-system profile should be two
BA4 modules connected to one row module and three column modules, subject to
confirmation of the formal group boundary.

## Implementation Plan

### Phase 0 - Freeze the interface contract

- Establish named detector presets for BICEP3 `22x12`, NIST `50x12`, and BA4
  `60x12`, with custom mappings remaining possible.
- Confirm whether NIST is specifically five 10-row banks and whether the
  two-BA4 one-row/three-column assembly is one firmware/software `Group`.
- Define topology records, device parameter records, nominal constants, and
  the override precedence described above.
- Compile a minimal record/array-generic example under both GHDL and XSIM before
  committing the public model interface.
- Document current directions, differential voltage polarity, physical units,
  row/chip-select mapping, and column-to-wafer grouping.
- Gather initial nominal parameters and at least one measured SA, SQ1, and FAS
  sweep if available.
- Decide whether the first TES interface is direct input current, static
  resistance, or both. Recommended: support both and keep direct current as the
  simplest test stimulus.

### Phase 1 - Stable transfer-function core

- Add `WaferSimPkg` and pure unit-tested helper functions.
- Replace the existing `Squid` algebra loop with explicit SQ1 and SSA transfer
  evaluations.
- Add one-level and two-level selection logic.
- Build focused GHDL testbenches that assert:
  - safe behavior at zero and extreme bias;
  - transfer periodicity and expected polarity;
  - row-select-only and chip-select-only remain off for a two-level profile;
  - row-select plus chip-select activates exactly one pixel; and
  - SSA output is finite, bounded, and differential.

### Phase 2 - Column slices and one detector module

- Integrate one MUX column behind `DetectorModuleSim`.
- Instantiate eight columns against one warm column module and run the normal
  one-board `GroupTb` tuning/readout regression.
- Reconfigure the same entity for all 12 columns of one physical detector.
- Route that detector across two warm column modules using an `8+4` harness
  map, leaving the remaining four warm channels explicitly unused.
- Make the `GroupTb` load choice configurable.
- Run SA-bias/feedback, FAS, and SQ1-bias/feedback sweeps and compare extracted
  period, amplitude, optimum bias, and lock slope with model configuration.
- Only then attempt the complete software tuning sequence.

### Phase 3 - Dual-detector GroupTb profile and TES signal path

- Make all `GroupTb` analog signals board-indexed.
- Instantiate the two-BA4, three-column-module harness map.
- Apply the two halves of `RowMap2x6x10` to their respective detector modules.
- Add deterministic per-pixel equivalent-current stimulus.
- Verify that only the currently selected logical row contributes to its
  column readout.
- Verify that columns attached to BA4 module 0 are inactive during module 1
  slots and vice versa, including the `4+4` shared warm module.
- Verify row tagging and DSP/event-builder output through `GroupTb`.
- Add static `Rshunt || RTES` bias calculation and configurable per-pixel
  resistance/phase/gain variation.

### Phase 4 - Dynamics and non-idealities

- Add electrical `L/R` settling where the simulation time scale can resolve it.
- Add configurable SQUID/SSA settling if needed to expose sample timing bugs.
- Add opt-in leakage, stuck/open select, dead SQUID, flux offset, gain spread,
  and deterministic seeded noise.
- Consider an electrothermal TES model only if a concrete firmware or software
  test requires it.

## Acceptance Criteria

- No time-zero failures, divide-by-zero, non-finite values, or hidden
  combinational feedback loops under GHDL.
- One-level and hierarchical address profiles pass mapping tests.
- BICEP3 `22x12`, NIST `50x12`, BA4 `60x12`, and custom arrangements run from
  the same model sources with configuration-only changes.
- The same row topology runs with 1, 8, and 12 instantiated columns without
  changing model source, and `COLUMN_ID_MAP_G` can select a nonzero slice.
- One SQ1, SSA, FAS, or TES can be overridden without changing peer instances.
- The hierarchical model requires both the configured row and chip select.
- The dual-BA4 preset maps all 24 detector columns exactly once onto the 24
  channels of three warm column modules, including the third module's `4+4`
  split.
- SA, SQ1, and FAS sweeps have configurable, repeatable optima and periods that
  the tuning code can recover.
- A stimulus on one pixel appears only when that pixel is selected, apart from
  explicitly configured leakage.
- The modeled SSA voltage remains within the configured ADC/front-end range.
- Default regressions are deterministic and complete within an agreed runtime.
- `ColumnLoadBoard` remains available as a simpler comparison test.

## Calibration and Validation Strategy

Keep the VHDL model deliberately simple and validate it against either measured
sweep data or a small offline Python/SPICE reference. The offline model can use
more expensive nonlinear equations without slowing every `GroupTb` run. Store
only compact fitted parameters and representative expected curves in the HDL
regression.

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

- The current FAS tuning path contains stale call/comment inconsistencies.
  Initial model validation should use focused sweep testbenches rather than
  making the production FAS tuner the only oracle.
- Multi-board analog connectivity in `GroupTb` is currently incorrect for more
  than one board and is now a prerequisite for the representative BA4 profile.
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
