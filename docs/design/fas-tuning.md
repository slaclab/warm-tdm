# One-level FAS tuning

The repair integrated through [PR #102](https://github.com/slaclab/warm-tdm/pull/102)
restores one-level FAS characterization. Hardware acceptance and extensions are
owned by [#99](https://github.com/slaclab/warm-tdm/issues/99).
See the [software guide](../../software/SOFTWARE_GUIDE.md#fas-commissioning)
for the operations entry point.

## Algorithm and operating contract

With timing stopped, `FasTuneProcess` resolves each logical row in
`RowReadoutOrder` through `RowMap`, sweeps the physical row-select current,
and closes the SA feedback servo at each point. It finds the response minimum
for each enabled column and takes the median. `SetAfterFinish` controls whether
that result is programmed into the physical `FasOn.Current` table.

The process exposes sweep bounds, points, settling delay, servo settings, and
provisional SQ1 bias. It publishes samples collected before Stop, does not apply
incomplete results, and restores state on cancellation, including a Stop racing
with final programming. It leaves `FasOff` untouched. Two-level maps are rejected
before hardware writes.

The original routine wrote the removed logical `group.FasFluxOn` variable and
lacked the parameters required by `saFbServo()`. The repair uses physical-line
actuation and explicit servo controls. Keeping this first tune limited to one
selection level lets measured curves guide more complex commissioning.

## Temporary physical-line actuation

`RowDacDriver2.ManualSet` provides temporary actuation without changing the
persistent FAS tables. It is one packed, write-only register at local offset
`0x18`:

| Bits | Purpose |
|---|---|
| `4:0` | Board-local physical line address |
| `21:8` | Temporary 14-bit DAC code |

Python exposes `driver.manual_set(address, current_uA)`. The path deliberately
has no acknowledgement or logical-row decoding and is not a separate PyRogue
command. The request remains pending until the row-driver FSM consumes it and
is cancelled if timing starts. Normal sequencing, activate/deactivate, and
table write-through retain their existing behavior.

## Boundaries and extensions

Production defaults require cryogenic measurements. Automatic `FasOff`
selection, polarity-independent period/peak analysis, operating margins,
two-level RS/CS discovery and bootstrap, four-state isolation checks, and
transactional commissioning were deliberately deferred. Specialized FAS GUI
controls and unrelated legacy Control-tab cleanup were also outside the repair.
Use #99 for current acceptance and follow-up scope rather than treating these
design boundaries as a second checklist.
