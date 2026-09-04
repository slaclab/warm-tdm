# FAS Tune Recovery Plan

**Status:** In progress

**Branch:** `fix-fas-tune`

**Base:** `sensor-wafer-sim` at `c6fe5516`

**Scope:** Restore production FAS characterization, `RowDacDriver2` manual
control, programming, and validation for single- and two-level row selection.

## Bottom line

The current `FasTuneProcess` does not work. It is not a nearly-complete tune that
needs one small repair: it is old scaffolding whose software model no longer
matches the row-driver hardware.

The replacement should tune **physical row-select and chip-select lines**, not
logical detector rows. It should sweep select current while the SA feedback loop
holds the readout at a fixed point, detect the periodic FAS response, choose
robust OPEN and CLOSED operating points, program the physical `FasOn`/`FasOff`
memories, and validate the resulting selection margins. Two-level selection
requires a bootstrap step because a row FAS cannot be observed unless its chip
FAS is also open, and vice versa.

## What is broken now

### Immediate runtime failures

- `fasSweep()` writes `group.FasFluxOn`, but `Group` no longer defines
  `FasFluxOn` or `FasFluxOff`. Its first sweep point therefore raises an
  attribute error.
- `fasSweep()` calls `saFbServo()`. That helper requires `ServoKp`, `ServoKi`,
  `ServoKd`, `ServoPrecision`, and `ServoMaxLoops`, but `FasTuneProcess` defines
  none of them.
- The process iterates `range(group.MaxRows.get())`, the logical address-space
  capacity, instead of the active logical rows in `RowIndexOrderList`/`RowMap`.

### Wrong abstraction even if those attributes are restored

- Current firmware stores 32 `FasOn` and 32 `FasOff` currents on each physical
  `RowDacDriver2`. A logical row maps to an `(rsBoard, rsAddr)` and, for
  two-level selection, an optional `(csBoard, csAddr)` pair.
- One physical select line can be shared by many logical detector rows. A tune
  result must therefore be keyed by physical line and combined across the
  logical contexts and detector columns that use that line.
- The old code chooses `argmin()` of each curve and takes the median x value.
  This assumes a response polarity and does not find the center or width of a
  valid operating region.
- It only derives an ON value. It never determines or validates the OFF value,
  despite the firmware requiring both.
- It has no two-level row/chip-select orchestration, no convergence or quality
  criteria, no rollback, and no test coverage.
- The current PyDM `FasTuningTab` is only the generic process panel plus the old
  `SweepPlot` and `TunePlot`. It has no physical-line or RS/CS selection, seed
  view, operating-margin display, truth-table result, or structured failure
  status. Its plots are indexed by logical `PlotRow` and label the selected
  point as a curve minimum.
- The legacy `.ui` and Control tab still bind removed logical
  `ConfigSelect.FasFluxOn/FasFluxOff` nodes.

### How it became stranded

The original implementation dates from the older row-control hierarchy. In
March 2023, `saFbServo()` was changed to read its PID parameters from its caller,
but those fields were added only to `Sq1TuneProcess`. In February 2024, the old
logical-row FAS access variables were commented out while row control moved to
`RowDacDriver2`; the tune still calls the removed names. Later plotting and stop
handling fixes made the scaffolding cleaner but did not restore its hardware
path or algorithm.

There is no open or closed GitHub issue/PR specifically tracking FAS tune as of
this plan. The sensor/wafer simulation plan correctly records production FAS
tuning as unimplemented.

### Useful implementation assets already present

| Area | Repository source | What it provides |
|---|---|---|
| Broken acquisition/selection | `software/python/warm_tdm_api/_Tuning.py` | Existing SA-feedback servo and the FAS scaffolding to replace |
| Process and plots | `software/python/warm_tdm_api/_FasTune.py` | Existing remote process/UI attachment point |
| Logical-to-physical topology | `software/python/warm_tdm_api/_Group.py` | Authoritative `RowMap`, active `RowIndexOrderList`, and manual activate/deactivate commands |
| Physical current registers | `firmware/python/warm_tdm/_RowDacDriver2.py` | Per-board, 32-line `FasOn.Current` and `FasOff.Current` arrays |
| Row-driver behavior | `firmware/common/warm_tdm/rtl/RowDacDriver2.vhd` | Logical map decoding, row-before-chip sequencing, and manual-mode behavior |
| Write-safety analysis | `docs/design/fastdac-override-race.md` | Why tuning must stop the run and wait for the driver idle state |
| FAS device oracle | `firmware/common/warm_tdm/sim/WaferSimPkg.vhd` | Independent periodic row- and chip-FAS parameters and branch models |
| Direct model tests | `firmware/simulations/WaferModelTb/tb/WaferModelTb.vhd` | Known half-period response, periodicity, and two-level truth-table checks |
| Integrated simulation | `firmware/simulations/GroupTb/` | Production register tree connected to the sensor/wafer model |

The simulation already distinguishes the row- and chip-FAS periods and proves
that a two-level path opens only when both lines are selected. The repair should
use those configured values as a test oracle; it does not need another synthetic
FAS model in Python.

## Physics and measurement basis

A FAS is the shunt switch around an SQ1 branch. With no applied row-select flux,
the superconducting switch bypasses the SQ1. Near a half-integer flux quantum,
the switch becomes resistive and diverts current through the SQ1 branch.

The NIST device-characterization procedure provides the basis for the tune:

1. Set SQ1 bias below the expected minimum SQ1 critical current.
2. Close the SA feedback loop.
3. Sweep row-select current over multiple flux periods.
4. Average/filter the SA-feedback response and find the prominent peaks. The
   peaks are centered on the optimal switch flux; peak spacing yields the FAS
   current period/mutual inductance.
5. Because a select current is shared by the switch elements on that physical
   line, combine their individual optima to choose the line's setting.
6. At operational SQ1 bias, sweep again and measure the current ranges for which
   the switch is acceptably OPEN and CLOSED. Select the centers of valid ranges,
   with margin from their edges.

This is a more defensible observable than the old unconditional `argmin()`. The
algorithm must accept either response polarity and detect prominence relative
to a local baseline.

For two-layer switching, both the row/pixel-select and chip/group-select switch
must be open to activate an SQ1. A logical detector row is consequently a pair
of independently driven physical FAS lines, and correct isolation requires all
three incomplete combinations to remain closed.

Primary references:

- C. D. Reintsema et al., [High-Throughput, DC-Parametric Evaluation of
  Flux-Activated-Switch-Based TDM and CDM SQUID Multiplexers](https://www.nist.gov/publications/high-throughput-dc-parametric-evaluation-flux-activated-switch-based-tdm-and-cdm-squid),
  IEEE TAS 29(5), 2019. The local PDF linked by NIST describes the low-bias peak
  measurement, period extraction, averaging by shared row line, and the later
  operational-margin scan.
- M. Durkin et al., [Symmetric time-division-multiplexed SQUID readout with
  two-layer switches for future TES observatories](https://www.nist.gov/publications/symmetric-time-division-multiplexed-squid-readout-two-layer-switches-future-tes),
  IEEE TAS, 2023. It states that both switching layers must be open and describes
  the `Nrows = NPS * NGS` addressing topology.
- C. S. Dawson et al., [Two-Level Switches for Advanced Time-Division
  Multiplexing](https://doi.org/10.1109/TASC.2019.2903394), IEEE TAS 29(5),
  2019. It introduces the group-select plus row-select architecture and measured
  operating margins.

## Required behavior

### Terminology

- **Logical row:** index used by the timing/readout sequence.
- **Physical select line:** one DAC output identified by
  `(kind, board, address)`, where `kind` is `row` or `chip`.
- **Context:** a logical row and its partner select line(s), used to observe a
  target physical line through one or more enabled detector columns.
- **OPEN / ON:** FAS resistive; current is routed through the SQ1 path.
- **CLOSED / OFF:** FAS superconducting or low-resistance; SQ1 is bypassed.

### Operator sequence

The supported commissioning sequence should be:

1. SA offset and SA tune.
2. FAS discovery at a configurable, deliberately subcritical SQ1 probe bias.
3. SQ1 tune using the newly programmed FAS settings.
4. FAS validation at the selected operational SQ1 bias.
5. Enter normal timing/readout only if selection validation passes.

The FAS process may expose discovery and validation as separate commands, but a
full `fas_tune()` operation should return one result that records both phases.

### Safety and state handling

FAS tuning must not modify row memories during normal timing operation. The
manual row-override FSM only accepts writes in its idle state, and the same
write-loss hazard is already documented for fast-DAC overrides.

Before any sweep, a state guard must:

- stop an active run and wait until the coordinator and row drivers are idle;
- put every participating `RowDacDriver2` in manual mode;
- snapshot row-driver mode, selected row, all touched `FasOn`/`FasOff` values,
  SQ1 bias/feedback forces, SA feedback forces, and timing/run state;
- slew current rather than making unnecessarily large steps;
- verify memory readback after programming; and
- restore the snapshot on Stop, exception, or failed validation. On success,
  retain only the accepted FAS memory values and restore unrelated state.

The first implementation should explicitly reject live tuning. A future
live-tuning design would need additional arbitration with row timing. The
`ManualSet` interface below remains restricted to stopped runs: its purpose is
temporary physical-line actuation, not live updates.

## Minimal `RowDacDriver2` firmware support

The existing firmware is adequate for normal timed row switching. Its table
write-through behavior can also drive individual physical RS and CS lines in
manual mode, including the incomplete two-level combinations. The missing
capability needed by production tuning is narrower: a sweep should be able to
apply a temporary physical current without rewriting persistent `FasOn` or
`FasOff` memory.

Add a board-local `ManualSet` command. It addresses one physical line (0 through
31) and applies one temporary raw DAC code. It deliberately has no logical-row
input, `RowMap` decoding, RS/CS distinction, pair operation, source enum,
active-row tracking, firmware-managed clear, status, or acknowledgement.
Python already resolves physical ownership and sequences quasi-static tuning
operations.

Keep the existing `ActivateRowIndex`, `DeactivateRowIndex`, timing-mode FSM, and
`FasOn`/`FasOff` write-through behavior unchanged for compatibility.

### `ManualSet` write

Use one packed register at local offset `0x18`:

| Bits | Purpose |
|---|---|
| `4:0` | Board-local physical line address |
| `21:8` | Temporary raw DAC code |

The write captures both fields into a one-entry pending latch in
`timingRxClk125`, after the existing `AxiLiteAsync`. The pending bit stays
asserted until `IDLE_S` consumes it, so a request accepted while the existing
FSM finishes another operation cannot disappear. Reuse the existing
`MANUAL_RS_DATA_S`, `MANUAL_RS_WRITE_S`, and DAC update-clock states. There are
no commit, busy, done, error, applied-value, or version registers.

Ignore a write while another `ManualSet` is already pending, while
`Mode=TIMING`, or while `timingRxData.running=1`. Cancel a queued request if the
mode changes or timing starts before it is consumed. Tuning software serializes
writes and enforces stopped manual operation, so these cases are defensive and
do not require a firmware diagnostic interface.

The PyRogue helper exposes current rather than raw codes:

```python
driver.manual_set(address=physical_address, current=current_uA)
```

It uses the same per-line amplifier model as `FastDacMem.Current`, packs one
write, and returns the quantized request values for result recording. Raw codes
remain below this API. It does not claim completion or applied-value readback.
Older bitfiles have no register at `0x18`, so the first attempted `ManualSet`
fails as an AXI write error instead of silently rewriting a table.

### Multi-board and cleanup behavior

`RowMap` may place RS and CS on different row boards. Python calls `manual_set()`
only on each physical line's owning board. After issuing every required write,
it waits for the configured electrical/servo settling interval before
acquisition. That millisecond-scale delay is deliberately much longer than the
short firmware transaction. Nanosecond-level simultaneous updates are
unnecessary for quasi-static characterization.

There is no firmware clear command. Before changing contexts and during cleanup,
Python explicitly drives every touched physical line to its snapshotted or
candidate `FasOff` current with serialized `manual_set()` calls. The tuning state
guard remains responsible for the ordering and rollback policy.

### Firmware verification

Compile the modified RTL and exercise `ManualSet` during bench commissioning.
Confirm that a stopped manual-mode write actuates the requested physical line,
does not change either persistent FAS table, and that normal timing-mode and
activate/deactivate behavior remain unchanged. The existing state guard and
millisecond-scale settling interval provide the software-side safety checks.

## Proposed algorithm

### 1. Resolve topology before touching hardware

Read `RowMap`, `RowIndexOrderList`, and `ColTuneEnable`, then construct:

- active logical rows (preserving the configured readout list and rejecting
  out-of-range or unmapped indices);
- unique physical row-select targets;
- unique physical chip-select targets;
- all logical contexts that use each target; and
- enabled detector columns available to measure each context.

For two-level maps, represent this as a bipartite graph: physical RS and CS
lines are vertices and each active logical row is an edge connecting its mapped
pair. Do not assume the map is a complete rectangular product. Identify
connected components so split boards, sparse maps, and unused RS/CS combinations
are handled deliberately. Reject a `(board, address)` used as both an RS and a
CS line: both names would address the same physical `FasOn`/`FasOff` memory
entry and could not hold independent settings.

Use a stable key such as:

```python
FasLineKey(kind: Literal['row', 'chip'], board: int, address: int)
```

Do not manufacture a logical-row-sized `FasFluxOn` array. Read and write the
authoritative nodes directly:

```text
HardwareGroup.RowBoard[board].RowDacDriver.FasOn.Current[address]
HardwareGroup.RowBoard[board].RowDacDriver.FasOff.Current[address]
```

All public sweep limits and outputs are physical current values with explicit
units. DAC conversion remains in `FastDacMem.Current`; tuning code must not use
raw DAC codes. The low-level `manual_set()` helper packs the code into
`ManualSetRaw`, but derives it with the same physical-line amplifier model used
by `FastDacMem.Current` and exposes only a current-valued API to the tuner.

### 2. Bootstrap two-level selection

Single-level topology needs no bootstrap: sweep each row-select target directly.

Two-level topology has a circular dependency: the row response is hidden while
the chip FAS is closed, and the chip response is hidden while the row FAS is
closed. Resolve each connected component of the RS/CS graph as follows:

1. If a caller supplies previously validated/nominal partner ON values, use
   those as seeds and mark their provenance in the result.
2. Otherwise choose a logical probe-row edge in the component and run a coarse two-
   dimensional row-current × chip-current raster over configurable multi-period
   ranges.
3. Detect a prominent joint response region and choose its interior as
   provisional row and chip ON points.
4. If no joint region passes minimum contrast/prominence, stop without applying
   any settings and return a diagnostic raster.

Once one edge is seeded, traverse the component: tune every adjacent RS using a
known CS partner, then every newly reachable CS using a known RS partner, until
all vertices are characterized. Refine shared lines through their additional
edges/contexts and combine those measurements robustly. A component that cannot
be reached from a passing seed is a tune failure, not a reason to copy another
component's settings. One final alternating refinement pass should normally be
enough; require convergence within a configurable fraction of each line's own
measured period or report the target as unstable.

### 3. Acquire a line response

For each physical line and each selected context:

1. Use serialized `manual_set()` calls to drive every physical line touched by
   the previous context to its snapshotted or candidate OFF current.
2. Set each enabled column's SQ1 probe bias below expected `Icmin` for
   discovery.
3. Sweep the target select current over at least two expected flux periods.
4. At each point, call `manual_set()` on the physical target. For two-level
   discovery, first set the partner line to its provisional/tuned OPEN current;
   the bootstrap raster sets the physical RS and CS lines independently.
5. After issuing every required board-local `manual_set()`, wait for the
   configured electrical/servo settling interval, which also covers the short
   unacknowledged firmware transaction, then:
   - close/iterate the SA feedback servo toward zero SA output;
   - record the required SA feedback for every enabled column;
   - record servo convergence, loop count, SA residual, rail/clipping flags, and
     the requested physical line, packed raw code, and quantized current.
6. Explicitly drive all touched lines to OFF with serialized `manual_set()`
   calls before switching target/context.

Columns that are disabled, fail to converge, rail, or lack sufficient response
remain in the result but do not vote on the line setting.

The servo controls must be owned by `FasTuneProcess` (or by a shared,
well-defined servo configuration object), including `ServoKp`, `ServoKi`,
`ServoKd`, `ServoPrecision`, `ServoMaxLoops`, feedback-current limits, and a
settling delay. This removes the current caller/process mismatch.

### 4. Analyze discovery curves

Keep acquisition separate from pure numerical analysis so recorded curves and
synthetic tests use exactly the same code.

For each valid column/context curve:

- reject non-finite, clipped, too-short, or non-converged samples;
- remove a robust baseline/trend and lightly smooth with a configurable window;
- detect both positive and negative extrema by absolute prominence;
- require repeated features when the sweep covers multiple periods;
- estimate period from robust peak spacing (and optionally confirm with
  autocorrelation/FFT); and
- assign a candidate OPEN center and confidence without assuming signal polarity.

For each physical line:

- combine candidates across enabled columns with a robust median;
- for a shared row line, also combine or intersect results across its chip/bank
  contexts rather than silently trusting one bank;
- reject lines whose candidates disagree by more than a configured fraction of
  the measured period;
- choose the acceptable peak nearest a configurable nominal/previous setting to
  avoid jumping to an arbitrary equivalent lobe; and
- record period, polarity, prominence/contrast, spread, valid voter count, and
  rejected voters.

The default OFF candidate is the nearest integer-period CLOSED region, normally
the zero-current region if it passes validation. It must be represented as an
actual measured candidate, not silently hard-coded to zero.

### 5. Determine operational margins

After discovery—and again after SQ1 tune when running the full commissioning
sequence—repeat narrower sweeps at operational SQ1 bias.

Convert the response to a normalized switch metric between the observed CLOSED
and OPEN levels. Find contiguous intervals satisfying configurable thresholds,
for example:

- OPEN: response at least `open_fraction` of full contrast;
- CLOSED: response at most `closed_fraction` of full contrast.

Choose the center of the interval containing the discovery candidate, not the
single largest sample. Record left/right margins and reject an operating point
whose interval is too narrow, touches a sweep boundary, or conflicts across
columns/contexts.

This interval-based selection is the software equivalent of the OPEN/CLOSED
operating regions reported in the NIST characterization paper.

### 6. Program, verify, and validate selection

Only after every required target has a passing candidate should the process
program `FasOn.Current` and `FasOff.Current`. Batch writes per board, read them
back, and retain the original snapshot until validation completes. Persistent
table programming must not be used to actuate sweep points.

Validate every active logical row at least in its normal OFF and ON states:

- **Single level:** OFF suppresses the SQ1 response; ON exposes a response with
  the required contrast and margin.
- **Two level:** require OFF/OFF suppression and ON/ON response. Provide the
  four-state `(OFF, OFF)`, `(ON, OFF)`, `(OFF, ON)`, `(ON, ON)` isolation test as
  an optional commissioning check; it is not required to calculate the RS/CS
  operating points.
- Check all enabled columns, report per-column failures, and require a
  configurable minimum valid-column fraction.
- Optionally perform a short SQ1-feedback modulation scan to prove that the
  selected path is not merely a DC artifact and is usable by `Sq1Tune`.

Any required-line or enabled validation failure rolls all FAS settings back by
default. Provide an explicit diagnostic-only mode and an explicit expert
override for keeping partial settings; never keep partial values implicitly.

## Result and API shape

Do not continue using generic `CurveData` as the complete FAS result. It cannot
express physical line identity, contexts, two-dimensional seed data, margins,
or failure reasons.

Define serializable result types along these lines:

```python
@dataclass
class FasSweepResult:
    line: FasLineKey
    context_row: int
    partner: FasLineKey | None
    select_current: list[float]
    sa_feedback: list[list[float]]
    sa_residual: list[list[float]]
    converged: list[list[bool]]
    flags: list[list[str]]

@dataclass
class FasLineResult:
    line: FasLineKey
    contexts: list[int]
    on_current: float | None
    off_current: float | None
    period: float | None
    open_margin: tuple[float, float] | None
    closed_margin: tuple[float, float] | None
    valid_columns: list[int]
    rejected_columns: dict[int, str]
    passed: bool
    reason: str

@dataclass
class FasTuneResult:
    topology: dict
    seed: dict | None
    lines: list[FasLineResult]
    sweeps: list[FasSweepResult]
    truth_table: dict
    applied: bool
    rolled_back: bool
```

The PyRogue process publishes a JSON/dict form for remote clients and retains
plot variables for a selected physical line and context. Add an operations-layer
wrapper:

```python
result = session.fas_tune(block=True, ...)
```

The GUI should label plots and controls as select **current**, show physical
line plus logical contexts, plot the chosen ON/OFF intervals, and expose failure
reasons. Remove stale `ConfigSelect.FasFluxOn/FasFluxOff` bindings rather than
recreating misleading logical-row controls.

## PyDM FAS tuning workflow

Replace the minimal `FasTuningTab(TuningTab)` implementation with a dedicated
operator panel. It should still use PyRogue's `Process` widget for Start, Stop,
progress, message, and process-variable editing, but the normal tune should not
require navigating a raw device tree.

### Preflight and run controls

The tab should present, before Start:

- detected topology (`single-level` or `two-level`), active logical-row count,
  physical RS/CS line counts, and connected-component count;
- run/row-driver state and whether tuning can start safely;
- run mode: full discovery/program, diagnostic dry run, or post-SQ1 operational
  validation;
- separate RS and CS current ranges/point counts, plus coarse 2-D bootstrap
  resolution for two-level operation;
- SQ1 probe-bias and settling controls;
- SA-servo gains, precision, loop limit, and feedback rails;
- quality thresholds, minimum agreeing columns/contexts, and apply/rollback
  policy; and
- a clear Start/Stop action with phase-aware progress such as
  `Bootstrap component 1/2`, `RS board 0 line 7`, or `Validating row 23`.

Two-level-only CS/bootstrap controls should be disabled or hidden for a
single-level topology. Start remains guarded in the process implementation—the
widget is informative, not the only safety layer.

### Result navigation and plots

Replace logical `PlotRow` as the primary selector with process-backed selectors
for:

- physical line kind (`RS` or `CS`), board, and address;
- one of the mapped logical-row contexts for that line;
- detector column or the robust aggregate; and
- RS/CS connected component for bootstrap results.

The process should publish selector choices/enums so a remote PyDM client does
not reconstruct topology independently.

The tab should contain:

1. **Selected-line sweep:** all valid column/context curves, rejected curves
   visibly distinguished, detected peaks, chosen lobe, ON/OFF centers, and
   shaded valid operating intervals.
2. **Two-level seed heatmap:** RS current × CS current response for the selected
   component/seed edge, including the provisional joint operating point. Hide
   it for single-level results.
3. **Physical-line summary:** ON current, OFF current, measured period, margin,
   voter count/spread, and pass/fail for every RS and CS line. Never plot these
   values against logical row number.
4. **Validation view:** per logical context and enabled column, display the
   required OFF/OFF and ON/ON result and, when optional isolation validation is
   enabled, the ON/OFF and OFF/ON responses and verdict.
5. **Failure/detail panel:** stable reason text for nonconvergence, rail,
   insufficient contrast, narrow/boundary margin, context disagreement,
   register-write failure, rollback, and user Stop.

Plots must tolerate empty, partial, stopped, and failed results without raising
exceptions. A stopped tune should retain completed diagnostic samples, label
the result incomplete, and show whether rollback finished.

### Widget verification

Add tests for the widget independently of hardware:

- channel-construction/unit tests for the dedicated tab and its selector
  bindings;
- an offscreen Qt/PyDM smoke test that builds the tab from an emulated process;
- plot tests for empty, partial, complete one-level, complete two-level,
  rejected-column, failed-validation, and rolled-back results;
- topology-change tests proving CS/bootstrap controls appear only when
  applicable; and
- an end-to-end GroupTb/PyDM smoke test confirming Start, progress, Stop,
  selector updates, and final plot/status refresh over the same remote channels
  used by the normal GUI.

## Implementation plan

### Task 1 — Lock in failures and topology semantics with tests

**Files:**

- Add `tests/warm_tdm/fas_tune/test_topology.py`
- Add `tests/warm_tdm/fas_tune/test_analysis.py`
- Add or extend a PyRogue emulation-tree test for process construction

- [ ] Prove the current process has no valid `FasFluxOn` hardware path and lacks
  its servo controls.
- [ ] Test conversion of 1×32, 6×10, 8×10, split-board, sparse, and reordered
  `RowMap`/`RowIndexOrderList` configurations into unique physical targets and
  contexts.
- [ ] Test RS/CS bipartite connected-component discovery, including a complete
  grid, missing combinations, and independent split-board components.
- [ ] Test duplicate-line aggregation, invalid map entries, disabled columns,
  RS/CS physical-address aliasing, and no-row-board/no-column-board errors.
- [ ] Construct `FasTuneProcess` in emulation and verify every parameter needed
  by its acquisition path exists.

**Done when:** topology construction is pure, deterministic, and fully tested;
the old runtime failure is reproduced before replacement and absent afterward.

### Task 2 — Add minimal board-local `RowDacDriver2.ManualSet`

**Files:**

- Modify `firmware/common/warm_tdm/rtl/RowDacDriver2.vhd`
- Modify `firmware/python/warm_tdm/_RowDacDriver2.py`
- Update `docs/design/fastdac-override-race.md`

- [x] Define the single packed address/code write at local offset `0x18`.
- [x] Implement a one-entry pending request after `AxiLiteAsync`; consume it only
  from `IDLE_S` and reuse the existing manual DAC write/update states.
- [x] Ignore timing/running-mode writes and a second write while one request is
  pending; cancel a pending request if timing starts.
- [x] Preserve existing timing, activate/deactivate, and table write-through
  behavior unchanged.
- [x] Expose `manual_set(address, current)` using the physical-line amplifier
  model; keep raw codes below that API.
- [ ] Build an affected row target with Vivado 2024.1 and bench-test temporary
  actuation, table preservation, and the unchanged legacy paths before
  deployment.

**Done when:** a `ManualSet` accepted while the FSM is busy is retained and
eventually actuates the requested physical line without changing either FAS
table, while the established row-control paths remain unchanged.

### Task 3 — Add explicit physical-line access and transactional state guard

**Files:**

- Modify `software/python/warm_tdm_api/_Group.py`
- Modify `software/python/warm_tdm_api/_FasTune.py`
- Reuse sequencing from
  `software/python/warm_tdm_api/operations/session/_forcedac.py`
- Add `tests/warm_tdm/fas_tune/test_state.py`

- [ ] Implement a small physical FAS accessor keyed by `(kind, board, address)`;
  do not add a logical-row alias.
- [ ] Route each physical-line command only to its owning row board and surface
  an AXI write error clearly when firmware lacks `ManualSet`.
- [ ] Implement snapshot/restore, stopped-run/manual-mode entry, readback, and
  guaranteed cleanup with a context manager.
- [ ] Make Stop and every exception path restore state.
- [ ] Unit-test successful apply, dry run, Stop, write failure, validation
  failure, and partial-board failure.

**Done when:** no failed or interrupted operation can leave a mixed set of FAS
values or an unexpected timing/row-driver mode.

### Task 4 — Implement and test pure curve analysis

**Files:**

- Modify `software/python/warm_tdm_api/_FasTune.py`
- Add fixtures under `tests/warm_tdm/fas_tune/data/` only if real/anonymized curves
  become available
- Extend `tests/warm_tdm/fas_tune/test_analysis.py`

- [ ] Implement validation, detrending/filtering, polarity-independent peak
  detection, period estimation, robust aggregation, nominal-lobe selection, and
  OPEN/CLOSED interval extraction.
- [ ] Test positive and negative peaks, DC slope, noise/EMI spikes, missing
  points, rails, partial sweeps, multiple periods, disagreement across columns,
  narrow margins, and a peak at a sweep boundary.
- [ ] Generate clear quality metrics and stable failure reasons.

**Done when:** synthetic curves with known periods and valid intervals recover
their ON/OFF centers within explicit tolerances, and malformed curves fail
closed rather than returning a plausible-looking setting.

### Task 5 — Replace the one-level acquisition path

**Files:**

- Modify `software/python/warm_tdm_api/_FasTune.py`
- Remove or reduce FAS code in `software/python/warm_tdm_api/_Tuning.py` to a
  compatibility wrapper
- Add `tests/warm_tdm/fas_tune/test_acquisition.py`

- [ ] Implement low-SQ1-bias select-current sweep with SA feedback closed.
- [ ] Drive each point through serialized `manual_set()` rather than changing
  persistent `FasOn`/`FasOff` entries.
- [ ] Record convergence and actual current at every sample.
- [ ] Tune unique physical lines and combine enabled column results.
- [ ] Derive both ON and OFF candidates and support diagnostic-only execution.
- [ ] Make progress accounting derive from resolved targets/contexts/steps.

**Done when:** a mocked one-level group produces correct per-physical-line
settings, never touches unused lines, honors Stop promptly, and preserves full
diagnostic data.

### Task 6 — Add two-level bootstrap, refinement, and optional isolation validation

**Files:**

- Modify `software/python/warm_tdm_api/_FasTune.py`
- Extend `tests/warm_tdm/fas_tune/test_acquisition.py`

- [ ] Implement trusted-seed input and the fallback coarse 2-D bootstrap scan.
- [ ] Bootstrap every unseeded connected component, traverse known partners to
  every RS/CS vertex, then alternate row and chip sweeps and test convergence.
- [ ] Aggregate shared line results over multiple partner contexts.
- [ ] Implement normal OFF/OFF and ON/ON validation plus an optional four-state
  isolation test; roll back when any enabled validation fails.
- [ ] Cover RS and CS with different periods, polarities, physical addresses,
  and row boards; never derive CS settings from RS results.

**Done when:** two-level synthetic responses can be tuned from no prior ON
values, and no incomplete select combination is accepted as an active row.

### Task 7 — Repair the public process and operations API

**Files:**

- Modify `software/python/warm_tdm_api/_FasTune.py`
- Modify `software/python/warm_tdm_api/_Group.py`
- Modify `software/python/warm_tdm_api/operations/session/_tuning.py`
- Modify `software/python/warm_tdm_api/operations/session/__init__.py`
- Modify `software/python/warm_tdm_api/operations/__init__.py`
- Remove or update stale `software/scripts/interactivetest.py`
- Update `software/SOFTWARE_GUIDE.md`
- Modify `.github/workflows/warm_tdm_ci.yml` to run the new software tests

- [ ] Give `FasTuneProcess` all acquisition, servo, quality, safety, and apply
  controls with current units and usable defaults.
- [ ] Publish the structured result and physical-line/context plots.
- [ ] Add `Session.fas_tune()` and notebook-level export matching `sa_tune()` and
  `sq1_tune()` behavior.
- [ ] Document the required SA → FAS discovery → SQ1 → FAS validation sequence.
- [ ] Add the smallest CI environment that exercises pure analysis/topology and
  the emulated PyRogue tree; keep simulator-dependent tests in their existing
  dedicated flows.

**Done when:** server and remote `Session` invoke the same implementation and
return the same structured result without stale node paths.

### Task 8 — Rebuild the PyDM FAS tuning tab

**Files:**

- Rewrite `software/python/warm_tdm_api/widgets/_fas_tuning_tab.py`
- Modify `software/python/warm_tdm_api/widgets/_tuning_tab.py` only for genuinely
  reusable helpers
- Modify `software/python/warm_tdm_api/widgets/_control_tab.py`
- Verify/update `software/python/warm_tdm_api/widgets/_warm_tdm_display.py`
- Modify plot/result variables in `software/python/warm_tdm_api/_FasTune.py`
- Remove or update FAS bindings in
  `software/python/warm_tdm_api/warm_tdm_gui.ui`
- Add `tests/warm_tdm/fas_tune/test_widget.py`

- [ ] Build the preflight, run-mode, scan, servo, quality, and apply/rollback
  control groups described in “PyDM FAS tuning workflow.”
- [ ] Bind topology and run/manual state; surface a missing `ManualSet` register
  as a clear firmware-compatibility failure.
- [ ] Add process-backed physical RS/CS line, context, column/aggregate, and
  connected-component selectors.
- [ ] Replace the old logical-row/minimum plots with selected-line response,
  two-level seed heatmap, physical-line summary, and validation views.
- [ ] Show per-line quality/failure reasons, process phase, partial-result state,
  applied/rolled-back state, and manual-command errors.
- [ ] Hide/disable two-level-only controls and plots for single-level topology.
- [ ] Remove all stale `ConfigSelect.FasFluxOn/FasFluxOff` bindings and wording.
- [ ] Add channel-binding tests, offscreen Qt/PyDM construction, result/plot
  fixtures, topology-switch tests, and a GroupTb remote-channel smoke test.

**Done when:** an operator can configure, start, monitor, stop, inspect, and
validate one- or two-level FAS tuning from the normal PyDM display without using
the Debug Tree, and every displayed setting/result maps to the authoritative
process data.

### Task 9 — Exercise the real sensor/wafer model

**Files:**

- Extend `firmware/simulations/WaferModelTb/tb/WaferModelTb.vhd`
- Extend `firmware/simulations/WaferModelTb/tb/DetectorScaleTb.vhd`
- Extend the `firmware/simulations/GroupTb/` cosimulation harness/tests
- Update `firmware/simulations/WaferModelTb/README.md` and
  `firmware/simulations/GroupTb/README_cosim.md`

- [ ] Add direct response sweeps that expose the independently configured row-
  FAS and chip-FAS periods and polarity.
- [ ] Assert expected integer-flux CLOSED and half-integer-flux OPEN behavior.
- [ ] Drive production Python against the GroupTb tree with a reduced number of
  sweep points.
- [ ] Verify recovered settings against the known synthetic parameters.
- [ ] Cover both one-level and two-level maps, including optional four-state
  isolation validation and a failed/degraded column.

**Done when:** the production process, not a test-only reimplementation, tunes
the simulated physical FAS lines to known tolerances and survives Stop/rollback.

### Task 10 — Bench validation and release readiness

- [ ] Capture at least one real multi-period FAS sweep before fixing defaults;
  retain an anonymized curve fixture if permitted.
- [ ] Establish safe discovery SQ1 bias, select-current bounds, slew rate,
  settling time, and SA servo limits for each supported cryogenic configuration.
- [ ] Run single-level or two-level commissioning as applicable and compare the
  selected currents against expert/manual settings.
- [ ] Verify OPEN/CLOSED margins at operational SQ1 bias, row isolation, full
  SQ1 tune, normal timing transition, and repeatability after a fresh start.
- [ ] Exercise Stop and injected failure paths on hardware and confirm exact
  rollback.
- [ ] When the implementation becomes code-complete but awaits the bench, move
  its roadmap item to `Needs HW Test` and add/update the Hardware Verification
  wiki procedure per `AGENTS.md`.

**Done when:** a maintainer accepts the automatic settings and margins for real
hardware, a second run is repeatable within tolerance, and the hardware-
verification record is complete.

## Acceptance criteria

- `FasTuneProcess` runs without missing-variable errors.
- New firmware accepts the packed `ManualSet` write; an older bitfile produces a
  clear AXI write failure on first use.
- A `ManualSet` accepted while the existing row FSM is busy remains pending and
  is actuated when the FSM returns to idle.
- `ManualSet` can temporarily actuate any board-local physical RS or CS line
  without rewriting persistent tune tables.
- It tunes only active, mapped, unique physical select lines.
- It supports one- and two-level topologies across multiple row boards.
- It measures and programs both `FasOn` and `FasOff` in physical current units.
- It handles either response polarity and does not use an unconditional
  `argmin()`.
- It reports period, contrast/prominence, valid voters, OPEN/CLOSED margins, and
  explicit failure reasons per physical line.
- Stop, exceptions, write failures, and validation failures restore the original
  hardware state.
- Required two-level validation proves OFF/OFF suppression and ON/ON response;
  optional isolation validation checks both incomplete select combinations.
- Two-level bootstrap and refinement recover deliberately different RS and CS
  periods/polarities, including when the pair spans two row boards.
- The normal PyDM FAS tab can configure and run discovery or validation, Stop
  safely, navigate physical RS/CS results and logical contexts, display the 2-D
  seed and enabled validation data, and explain failures/rollback without the
  Debug Tree.
- The PyDM tab handles empty, partial, stopped, failed, one-level, and two-level
  result objects without plot or channel-binding errors.
- Pure unit tests, emulation-tree tests, firmware compilation, and GroupTb
  production-code cosimulation pass.
- A bench procedure verifies safe bounds, repeatability, isolation, and normal
  operation before the feature is called complete.

## Decisions that need real hardware data, not guesses

These should be configurable in the first implementation and promoted to
defaults only after bench measurements:

- safe low SQ1 bias for the discovery scan;
- row- and chip-select current bounds and expected periods by MUX generation;
- acceptable SA servo gains, settling time, and feedback-current rails;
- OPEN/CLOSED normalized-response thresholds and minimum interval width;
- minimum number/fraction of agreeing columns and partner contexts;
- preferred nominal lobe when several equivalent half-flux peaks are present;
- whether the optional four-state two-level isolation check should be enabled by
  default after commissioning experience; and
- whether an operational-margin validation should be part of `fas_tune()` or an
  explicit post-`sq1_tune()` operation in the normal commissioning UI.

None of these unknowns blocks building the topology, state-safety, analysis,
simulation, and diagnostic path. They do block claiming production-ready
hardware defaults.

## Non-goals

- Do not revive the legacy `RowDacDriver`/RowModule logical FAS variables.
- Do not tune raw DAC codes or duplicate the `FastDacMem.Current` conversion.
- Do not infer row/chip topology from arithmetic when `RowMap` is authoritative.
- Do not implement production two-level tuning by temporarily overwriting
  `FasOn`/`FasOff` RAM entries.
- Do not add a firmware logical-row pair transaction, RS/CS source matrix,
  active-row tracker, or firmware-managed clear; `ManualSet` remains a minimal
  board-local physical-line primitive.
- Do not put curve analysis, peak finding, or the complete sweep engine in
  firmware; firmware provides minimal physical actuation while Python owns the
  adaptable characterization algorithm.
- Do not add live-tuning behavior as part of this manual interface; live tuning
  would require explicit arbitration with the normal timing path.
- Do not declare success based only on PyRogue emulation; it validates the tree
  and writes, not the FAS physics.
