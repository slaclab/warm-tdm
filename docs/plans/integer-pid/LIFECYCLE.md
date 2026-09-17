# Integer PID masking and I-coefficient lifecycle

## Goal and decision

September 17, 2026 follow-up to the [path comparison](../pid-path-comparison/README.md):
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

Implemented in the working tree following `996aae6`:

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

## Validation

The initial focused run passed all 12 cocotb cases (six tests in each of two
configurations: 8 rows/inverted DAC and 256 rows/normal DAC). They cover masked
seeded/unseeded state, unmasking, I changes through positive/zero/negative
values, same-I writes, retained derivative history, in-flight coefficient
changes, nonzero flux counts and feedback fractions, and disabling/reseeding.
All 27 Python control tests passed, including the actual integer I-link
callback and cache-only writes with fake register I/O.

The final RTL, including the `axiP/I/D/FluxQuantum` rename, passed all **75
cocotb cases across 12 pytest configurations** in 377.43 seconds. This includes
the 12 new lifecycle cases, 45 existing integer arithmetic/fractional/flux/
historical/delivery cases, and 18 FP reference cases. No skips or failures.
`git diff --check` passed. The run log is temporarily at
`/private/tmp/warm-tdm-integer-lifecycle-regression.log`; this summary preserves
the validation result. Reproduce from the repo root:

```bash
make rtl_import
.venv/bin/python -m pytest -n 4 -q \
  tests/warm_tdm/adc_dsp/test_AdcDsp_lifecycle.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_fractional.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_bitexact_compare.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_delivery.py \
  tests/warm_tdm/adc_dsp/test_AdcDspFp.py
.venv/bin/python -m pytest -q software/tests/test_fp_pid_controls.py
```

FP tests use behavioral arithmetic cores, not generated vendor IP. Vivado
2024.1 timing/resources, full PyRogue-tree construction and hardware acceptance
remain separate checks. No files were staged or committed.
