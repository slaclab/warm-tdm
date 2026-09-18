# FAS tuning and two-level discovery

The repair integrated through [PR #102](https://github.com/slaclab/warm-tdm/pull/102)
restored one-level FAS characterization. Hardware acceptance and extensions are
owned by [#99](https://github.com/slaclab/warm-tdm/issues/99).
See the [software guide](../../software/SOFTWARE_GUIDE.md#fas-commissioning)
for the operations entry point.

## Algorithm and operating contract

With timing stopped, `FasTuneProcess` resolves each logical row in
`RowReadoutOrder` through `RowMap`, sweeps the physical row-select current,
and closes the SA feedback servo at each point. It finds the response minimum
for each enabled column and takes the median. `SetAfterFinish` controls whether
that result is programmed into the physical `FasOn.Current` table. Each
one-dimensional candidate is the midpoint of the contiguous region within
`FasMinimumTolerance` of the sampled minimum, aggregated across enabled columns.

The process exposes sweep bounds, points, settling delay, servo settings, and
provisional SQ1 bias. It publishes samples collected before Stop, does not apply
incomplete results, and restores state on cancellation, including a Stop racing
with final programming. It leaves `FasOff` untouched. Two-level maps use the
discovery/refinement path below; flat maps retain the one-level algorithm.

The original routine wrote the removed logical `group.FasFluxOn` variable and
lacked the parameters required by `saFbServo()`. The repair uses physical-line
actuation and explicit servo controls. The initial repair was restricted to
one selection level. The two-level extension is tracked in the
[active handoff](../plans/fas-two-level/README.md).

## Two-level operation

`FasTuneProcess` detects the topology from the active `RowMap` entries on every
run. The GUI Start button and `session.fas_tune()` use the same automatic path;
no FAS or Group mode flag needs to be set.

| Active map entries | Operation |
|---|---|
| RS only | One-level row-select sweep. |
| RS + CS | Discover both unknown on-currents, refine RS then CS, and verify the shared settings. |

Two-level runs validate the complete map before actuation and turn **every
mapped RS/CS line** off before acquisition, including lines belonging to inactive
logical rows and lines on other row boards. Each measurement activates only the
pair being characterized. Unmapped physical outputs are outside the tuner's
ownership and must already be inactive. Mixed one-level/two-level active lists
and physical outputs assigned both RS and CS roles are rejected. Run mixed
topologies in separate active-row sets.

The logical map and readout order are preserved. Each scan uses the logical
row's SA-tuned feedback seed. Two-level discovery uses no prior RS-on or CS-on
value. Configured **off currents must already provide isolation**; discovering
unknown on-currents does not discover off currents.

### Discovery and refinement

For each active two-level logical row, the tuner measures an RS×CS grid using
`DiscoveryNumSteps` points per axis. RS bounds come from `FasFluxLowOffset` and
`FasFluxHighOffset`; CS bounds come from `CsFluxLowOffset` and
`CsFluxHighOffset`. Each point runs the SA feedback servo with the temporary
`Sq1BiasCurrent`. A servo timeout or non-finite enabled-column sample fails the
run, preserving acquired diagnostics and leaving the tables unchanged.

The bootstrap pair is an actual measured point near the center of one connected
minimum region. Column offsets are removed before taking the median response.
Separate periodic minima are not averaged together. Every enabled column must
show more than `FasMinimumResponse` variation along **both** axis slices through
the chosen pair; a flat surface, closed companion, or insufficient grid
resolution produces an error rather than an on-current.

With that bootstrap CS held on, the tuner performs a full RS sweep at
`FasFluxNumSteps` resolution. It then holds the refined RS on and sweeps CS at
`CsFluxNumSteps` resolution. Each sweep must resolve a response in every
enabled column. Disable columns that cannot supply
a usable response through `ColEnableMask`.

All candidates remain temporary. Candidates that share a physical output are
combined by median, producing one current per physical RS or CS line. This
aggregation can produce an unsuitable compromise or fall between periodic
minima, so the resulting physical pairs are measured again before programming.

### Final pair verification and programming

For each requested logical row, the tuner measures off/off, on/off, on/on, and
off/on using the final shared currents and unchanged off-current tables. In
every enabled column:

- The spread between the three off states must not exceed
  `FasIsolationTolerance` (SA-feedback uA).
- The on/on response must lie more than `FasMinimumResponse` below each off
  response, following the existing response-minimum convention.

If any row fails, the tuner retains the measurements and does not program any
candidate. These checks verify the measured contrast/isolation criterion for
the requested rows; they do not establish suitability for unmeasured rows that
share the same physical outputs, nor do they measure switching transients.

After all rows pass, the outputs are returned to `FasOff` and force currents
are restored. With `SetAfterFinish=True`, the tuner temporarily puts the row
drivers in TIMING mode while timing remains stopped. This suppresses the
normal `FasOn` RAM write-through, which would otherwise turn several RS and CS
lines on together during programming. Each selected physical entry is written
once, original modes are restored, and a final Stop checkpoint completes the
transaction. A Stop or programming failure rolls back touched entries,
including a partially failing write. Cleanup attempts all owned lines, forces,
and modes; transport failures are reported and can prevent full restoration.

### Example: logical rows 10–13 on an 8×10 map

After restarting the server with the extended software, use the existing
8×10 map, stop timing, establish usable `FasOff` currents, and complete SA
tuning. Then:

```python
session.group.RowReadoutOrder.set([10, 11, 12, 13])
result = session.fas_tune(SetAfterFinish=False)

process = session.group.FasTuneProcess
grids = process.FasDiscoveryOutput.get()
checks = process.FasValidationOutput.get()
```

The standard map resolves these to RS 0–3 and CS 11 on row board 0. The tune
produces four grids, eight refinement curves (RS then CS per logical row), and
four final pair checks. With the default grid size 9 and refinement sizes 21,
this takes 508 servo measurements; execution time depends strongly on servo
convergence and transport latency. Adjust both sweep ranges and the resolution
to the wafer before running. The defaults are provisional, not measured wafer
limits. `SetAfterFinish=True` repeats the acquisition and programs RS 0–3 and
the single shared CS 11 only after successful verification.

`FasTuneOutput` retains the one-dimensional result format and adds `select`
(`RS`/`CS`), `rowFasOn` (the per-row candidate), and the companion's board,
address, and held current. `fasOn` is assigned the aggregated physical candidate
after final pair verification. `PlotRow` indexes these curves, not logical row
numbers. `FasDiscoveryOutput` stores raw responses as
`[column, CS index, RS index]`; disabled or missing samples are NaN.
`PlotDiscoveryRow` selects the discovery heatmap, which displays the median
response above each column's minimum. `FasValidationOutput` stores final
four-state responses and pass/error details. Stop and errors preserve partial
diagnostics; starting a new process clears the previous outputs.

## Temporary physical-line actuation

`RowDacDriver2.ManualSet` provides temporary actuation without changing the
persistent FAS tables. It is one packed, write-only register at local offset
`0x18`:

| Bits | Purpose |
|---|---|
| `4:0` | Board-local physical line address |
| `21:8` | Temporary 14-bit DAC code |

Python exposes `driver.manual_set(address=address, current=current_uA)`. The path deliberately
has no acknowledgement or logical-row decoding and is not a separate PyRogue
command. The request remains pending until the row-driver FSM consumes it and
is cancelled if timing starts. Normal sequencing, activate/deactivate, and
table write-through retain their existing behavior.

Two-level tuning spaces temporary writes by `FasFluxSampleDelay`, including
companion selection and cleanup. This delay must be positive and appropriate
for the hardware or co-simulation speed. Stop interrupts a long settling wait
after at most a 50 ms slice; cleanup still spaces physical requests. There is
no hardware completion readback, so software-only tests cannot validate request
delivery or analog settling. Timing must stay stopped and other processes must
not manipulate the mapping, enabled set, or DAC outputs during a tune.

## Boundaries and extensions

Production defaults require cryogenic measurements. Automatic `FasOff`
selection, polarity-independent period/peak analysis, and operating margins
remain deferred. The two-level path assumes the same response polarity as the
one-level tuner and a bias that makes both switches observable. A coarse grid
can miss a narrow on region; increase its resolution or adjust its bounds when
no pair is found. Shared-setting verification can reject incompatible rows; it
does not search all possible combinations of periodic branches for a global
solution. Hardware/RTL co-simulation acceptance of this extension remains to be
performed under #99. Use that issue for current acceptance and follow-up scope.
