# Minimal FAS Tune Repair Plan

**Status:** Implemented; firmware build and hardware test remain

**Branch:** `fix-fas-tune`

## Goal

Restore the original one-level FAS tune with the smallest practical changes.
The process sweeps FAS current, closes the SA feedback servo, finds the response
minimum for each enabled column, takes the median, and optionally programs
`FasOn`.

The old implementation failed because it wrote the removed logical
`group.FasFluxOn` variable and because `FasTuneProcess` did not define the servo
parameters required by `saFbServo()`.

## Supported behavior

- Use active logical rows from `RowIndexOrderList`, not `MaxRows`.
- Resolve every active row through `RowMap` to `(rsBoard, rsAddr)`.
- Support one-level row selection only. Reject any active mapping containing a
  chip-select field before changing hardware state.
- Require timing to already be stopped. Manual tuning does not stop or start a
  MUX run.
- Put only participating `RowDacDriver2` instances into manual mode for the
  operation, then restore their original modes in `finally`.
- Sweep the physical line with `driver.manual_set(address=..., current=...)`.
- Wait `FasFluxSampleDelay` after each write, then call the existing
  `saFbServo()` and record all column responses.
- Use only `ColTuneEnable` columns when calculating the selected current.
- Select each row's response minimum and combine enabled columns with a median,
  matching the original algorithm.
- If logical rows share a physical line, combine their row candidates with a
  second median and program that physical line once.
- When `SetAfterFinish` is enabled, program `FasOn.Current` only after all
  active-row sweeps complete. Otherwise publish the candidates without changing
  the table.
- Leave `FasOff.Current` unchanged.
- On Stop, publish collected curves and leave `FasOn` unchanged.
- Make settling waits interruptible so `Stop()` does not wait for a complete
  user-configured sample delay.
- Report a stopped process as `Stopped`, not `Done`, and do not force progress
  to 100 percent.
- Recheck Stop before and during final `FasOn` programming; roll back any
  entries already written if Stop arrives in that interval.
- Apply a configurable provisional SQ1 bias to enabled columns and zero their
  SQ1 feedback so the FAS state is observable before the final SQ1 tune.
- Seed the SA feedback force-current path from the tuned per-row SA feedback
  table before each FAS row sweep; timing is stopped, so the table does not
  drive the DAC directly.
- Restore SA feedback, SQ1 bias/feedback, row-driver modes, and temporarily
  driven row outputs on every exit path.
- If a batched `FasOn` programming operation fails, restore the original values.

## Minimal firmware support

`RowDacDriver2` provides one packed, write-only `ManualSetRaw` register at local
offset `0x18`:

| Bits | Purpose |
|---|---|
| `4:0` | Board-local physical line address |
| `21:8` | Temporary 14-bit DAC code |

The Python driver exposes only the current-valued helper:

```python
driver.manual_set(address=physical_address, current=current_uA)
```

There is no status register, acknowledgement, logical-row decoding, or separate
`ManualSet()` PyRogue command. Normal timing, activate/deactivate, and table
write-through behavior remain unchanged.

## Implementation

### Firmware

- [x] Add the packed `ManualSetRaw` write.
- [x] Retain an accepted request until the row-driver FSM consumes it.
- [x] Restrict it to stopped manual mode and cancel it if timing starts.
- [x] Add `RowDacDriver2.manual_set(address, current)` using the existing
  per-line amplifier conversion.
- [ ] Compile an affected row target with Vivado 2024.1.
- [ ] Bench-check temporary actuation and confirm `FasOn`/`FasOff` are unchanged.

### Software

- [x] Add the missing servo controls to `FasTuneProcess`.
- [x] Add a configurable current range, point count, FAS settling delay, and
  post-write ADC discard-read counts that advance cosim before sampling.
- [x] Apply a configurable bootstrap SQ1 bias to enabled columns and restore
  the previous SQ1 bias/feedback force currents on exit.
- [x] Replace the missing logical `FasFluxOn` access with physical
  `RowDacDriver2.manual_set()` calls.
- [x] Iterate active rows and validate their one-level `RowMap` entries.
- [x] Preserve the existing curve/minimum/median algorithm.
- [x] Program physical `FasOn.Current` entries only after complete acquisition.
- [x] Add `SetAfterFinish` so acquisition can publish candidates without
  programming `FasOn`.
- [x] Preserve partial plots on Stop without applying settings.
- [x] Make `Stop()` responsive during settling and SA-servo loops.
- [x] Prevent the PyRogue process wrapper from relabeling Stop as `Done`.
- [x] Close the Stop-versus-final-programming race with rollback.
- [x] Restore temporary modes and SA/SQ1 force currents on exit.
- [x] Keep `Session.fas_tune()` as the operations-layer convenience wrapper.
- [x] Enable the `FasTuneProcess` logger at DEBUG for every run and trace
  configuration, topology resolution, raw/quantized manual requests, every
  servo iteration, acquired responses, selection, programming, Stop/rollback,
  result publication, and cleanup.
- [ ] Run the process against GroupTb or hardware with a one-level map.

### Local verification

- [x] Compile-check the changed Python modules.
- [x] Construct `FasTuneProcess` under PyRogue.
- [x] Exercise one-level sweep/programming, shared-line handling, disabled
  columns, Stop behavior, state restoration, and two-level rejection with a
  focused fake-hardware smoke test.
- [x] Verify a real PyRogue `Process.Stop()` joins the worker, leaves
  `Running=False`, reports `Stopped`, and does not force progress to completion.
- [x] Construct the PyDM FAS tab headlessly and verify that its Process widget
  exposes every sweep/servo control, drives the standard `Start`/`Stop`
  channels, and connects both result plots.
- [x] Verify the legacy client `.ui` uses the same process and plot paths and
  that partial results published by Stop remain valid plot inputs.
- [ ] Build an affected target with Vivado 2024.1; Vivado is not available in
  the current environment.

## Acceptance checks

- The process starts without missing-variable exceptions.
- A stopped, one-level configuration produces one sweep per active logical row.
- Each sweep addresses the `rsBoard` and `rsAddr` from `RowMap`.
- Disabled columns do not influence the median.
- Shared physical lines are programmed once with their combined median.
- With `SetAfterFinish` disabled, fitted candidates are published and every
  `FasOn` entry remains unchanged.
- Stop before acquisition completes leaves every `FasOn` entry unchanged.
- `Stop()` waits for cleanup, returns with `Running=False`, and leaves the
  process message as `Stopped` rather than `Done`.
- `FasOff` is never written.
- A two-level map fails before any manual DAC write.
- Row-driver modes and SA feedback, SQ1 bias, and SQ1 feedback force currents
  are restored after success, Stop, or exception.

## Deferred work

The following are intentionally outside this first repair:

- automatic `FasOff` selection;
- polarity-independent peak or period analysis;
- operating-margin calculations;
- two-level RS/CS discovery or bootstrap;
- four-state isolation validation;
- transactional commissioning across a complete two-level topology;
- specialized FAS GUI controls beyond the existing Process and two plots; and
- cleanup of unrelated legacy Control-tab bindings and scripts; and
- production defaults before real hardware data exists.

These should be reconsidered only after the minimal one-level tune runs on the
intended hardware and its recorded curves show what additional behavior is
actually needed.
