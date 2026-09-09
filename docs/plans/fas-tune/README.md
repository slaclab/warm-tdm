# Minimal FAS tune repair (historical)

This work is **implemented and under review in [PR #102](https://github.com/slaclab/warm-tdm/pull/102)**;
hardware acceptance is tracked on
**[Issue #99 (Repair FAS tuning and improve SA/SQ1 tuning controls)](https://github.com/slaclab/warm-tdm/issues/99)**.
The detailed PLAN with its blow-by-blow completion checklist was pruned once the
work landed — the code, the PR description, and Issue #99's integration/acceptance
checklist are now the sources of truth. This stub records the durable "why" so it
is not re-derived.

## What shipped (PR #102)

Restores the original one-level FAS tune with the smallest practical change: sweep
FAS current, close the SA feedback servo, find each enabled column's response
minimum, take the median, and optionally program `FasOn`. Also refactors the SQ1
tuning UI onto a shared process widget and hardens Stop/state-restoration.

- **`RowDacDriver2.ManualSet`** — a narrow, write-only path for temporary
  physical-line actuation during characterization, without editing the persistent
  FAS tables (see design note below).
- **`FasTuneProcess`** — active rows from `RowIndexOrderList` resolved through
  `RowMap`; one-level maps only (two-level rejected before any hardware write);
  configurable sweep range/points, interruptible settling, provisional SQ1 bias,
  `SetAfterFinish` gating, partial-result publication on Stop, and rollback of the
  Stop-vs-final-programming race. `FasOff` is never written.
- **Operations wrapper** — `Session.fas_tune()`.

## Key design decisions (the durable "why")

- **Why the old tune broke.** It wrote the removed logical `group.FasFluxOn`
  variable, and `FasTuneProcess` never defined the servo parameters `saFbServo()`
  requires. The repair replaces the logical write with physical
  `RowDacDriver2.manual_set()` calls and supplies the missing servo controls.
- **Minimal-repair scope.** Deliberately one-level only, manual-mode only (timing
  already stopped), and it leaves `FasOff` untouched — the goal is to get a
  working tune onto hardware whose recorded curves then show what more is needed.
- **`ManualSet` register layout** — one packed, write-only register at
  `RowDacDriver2` local offset `0x18`:

  | Bits | Purpose |
  |---|---|
  | `4:0` | Board-local physical line address |
  | `21:8` | Temporary 14-bit DAC code |

  Python exposes only `driver.manual_set(address, current_uA)`. Intentionally
  statusless: no acknowledgement, no logical-row decoding, no separate PyRogue
  command. It is retained until the row-driver FSM consumes it and is cancelled
  if timing starts. Normal timing, activate/deactivate, and table write-through
  behavior are unchanged.

## Deferred (reconsider only after the minimal tune runs on hardware)

Intentionally outside this first repair — automatic `FasOff` selection;
polarity-independent peak/period analysis; operating-margin calculations;
two-level RS/CS discovery or bootstrap; four-state isolation validation;
transactional commissioning across a full two-level topology; specialized FAS GUI
controls beyond the existing process + two plots; cleanup of unrelated legacy
Control-tab bindings and scripts; and production defaults before real hardware
data exists.
