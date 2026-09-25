# Integer PID masking and I-coefficient lifecycle

## Operating contract

September 17, 2026 follow-up to the [path comparison](../../reference/pid-path-comparison.md):
align the integer controller with the FP lifecycle requested by the user.
Issue #70 remains the acceptance owner.

- A masked visit must preserve integral history, retained fractional feedback,
  its validity and flux count; emit neither DAC command nor primary readout.
  Error telemetry continues to update, as in FP. In integer PID this also keeps
  the derivative's previous-error sample current during masked visits.
- An actual I-coefficient change clears only integral history across all rows.
  Preserve feedback/validity, flux count, error history and diagnostics.
  Same-value writes must not clear anything.
- Finish an accepted visit using its captured coefficients before the integral
  sweep. The sweep blocks new visits. Full clear, StartRun and rising enable
  retain their explicit full-reset/reseed behavior.
- Remove the integer Python I setter's unconditional full-clear command.

Clearing S on an I change avoids reinterpreting accumulated error with a new
gain or sign. Keeping feedback preserves the operating point, fractional
remainder and unwrapped reference. This does not promise fully bumpless gain
changes: subsequent correction increments naturally change with the new gain.

## Implementation

The implementation uses these boundaries:

- `AdcDsp.vhd` gates SumAccum RAM commits with the accepted row mask, matching
  its feedback/count commits. Error/PID-result diagnostics still update.
- AXI configuration fields are named `axiP`, `axiI`, `axiD` and
  `axiFluxQuantum`, distinct from `activeP/I/D/Quantum`. Capturing these at
  acceptance prevents a visit from mixing configurations.
- An actual I change sets `clearSumPending`; once the current visit finishes,
  a separate sweep zeros only SumAccum RAM. Additional changes during a sweep
  remain pending and cause another sweep before accepting visits. Full clears
  take priority. There is no new state in the ordinary computation path.
- `ControlBusy` is read-only at `0x34[0]`, including computation, pending clear
  and either clear sweep. It does not indicate DAC-queue completion. As in FP,
  inputs arriving during a sweep are discarded; stop row sequencing for
  lossless reconfiguration. This change does not add integer loss counters.
- Disabling prevents new visits while letting an accepted visit finish, so it
  cannot strand a pending I sweep. `_AdcDsp.py` leaves enable/I state clearing
  to hardware instead of issuing unconditional full clears. Rising enable
  still clears/reseeds, while repeated enable writes do not.

## Verification

The lifecycle bench checks masked seeded/unseeded rows, positive/zero/negative
I changes, same-value writes, fractional feedback/count preservation,
derivative history, in-flight writes and disable/reseed. See the
[regression guide](../../../tests/README.md) for commands and
[#70](https://github.com/slaclab/warm-tdm/issues/70) for revision-specific
results and outstanding system/build/hardware acceptance.
