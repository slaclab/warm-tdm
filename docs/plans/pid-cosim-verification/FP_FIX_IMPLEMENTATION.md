# Floating-point fixes — implementation and validation

2026-09-16; implemented from `e2eafb5` on `channelization`.
This executes the approved [FP fix plan](FP_FIX_PLAN.md). Issue #70 remains the
feature/acceptance owner; this local record does not complete hardware acceptance.

## Behavior and implementation

The controller retains **unwrapped float32 F per row**, a separate integral S,
and the diagnostic signed int32 quotient J. It remains an incremental PI loop:
`F_candidate = F + P*E + I*S_old`, with individual binary32 FMAs. E is the row
window's error sum; sample normalization stays in the existing software gains.
There is no D term and no new split fractional-feedback/flux-offset architecture.

1. **Startup and masking.** Keep the seeded-DAC initialization in `f6f1e55`.
   Masked visits may calculate/debug a candidate and update error telemetry,
   but write neither F/S/J nor the DAC/readout. An initially masked row remains
   unseeded; an already seeded row resumes its held state. Manual DAC changes
   while masked require an explicit full clear/reseed before resuming.
2. **Clipping.** After local wrapped feedback is rounded to int32, clip to
   −8192..8191. Only if that integer command clips, reuse FpMac to save
   `F = float32(J*R + clipped_DAC)`, where R is the configured wrap period.
   Normal DAC rounding leaves fractional F untouched. Primary readout, saved
   RAM and the debug new-F field agree on the accepted value. This prevents
   feedback-state windup; the existing sign-based conditional update of S is
   retained and is not a guarantee of immediate recovery from arbitrary old S.
3. **Gain lifecycle.** Snapshot P/I/R/inverse for each accepted visit. An actual
   I-bit-pattern change queues an integral-only RAM sweep after that visit
   completes; preserve F/J. Same-value I writes do not reset. Both signed zeros
   canonicalize to +0 and disable/zero S. Raw writes and public setters share
   this policy. Incoming visits during the sweep are intentionally discarded
   and counted. Changing I can still change the next increment: this is not a
   promise of bumpless gain switching.
4. **Full clear and disabling.** StartRun, explicit ClearPidState and rising
   enable deliberately clear/reseed all rows, establishing a new unwrapped
   reference. Disabling prevents new visits but finishes the accepted visit and
   queued DAC writes. The driver no longer issues a full clear on disable or
   routine I writes. A full clear does not flush already queued DAC commands;
   disable and wait for both busy bits before a deliberate reconfiguration.
5. **Period configuration.** `_PidFpConfig.py` converts a current *difference*
   through `abs(currentPerLsb())`, preserving fractional DAC codes. The setter
   validates both float32 R and `float32(1/R)` before writing, uses the stored
   R to derive the inverse, and writes both zeros when wrapping is disabled.
   WrapMultiplier changes recompute the pair while preserving physical Q.
   Actual public writes require disabled PID, ControlBusy=0 and DacWriteBusy=0.
   Re-enable then deliberately reseeds. Raw-register clients must maintain the
   same coherent configuration contract themselves.
6. **Supported configuration envelope.** Gains and periods must be finite;
   N is a positive integer, Q is nonnegative, and positive R is at most 16380
   DAC codes (one-code headroom above the ideal centered upper endpoint).
   Tiny periods that could overflow the int32 quotient within any 14-bit seed
   plus ±256 physical quanta are rejected. This bound is not a proof that an
   arbitrarily large error/gain/transient is valid: internal results and int32
   conversions must stay finite/in range. NaN/Inf/denormal recovery is not added.
7. **Operational API.** `set_pid` accepts supported requested gains; FP allows
   omitted D or D=0 and rejects nonzero D before writes. Finite-gain and board
   validation precedes writes. Debug uses global-column board/channel mapping.
   `setup_mux` remains an explicit setup/reset operation, including ClearPids;
   routine `set_pid` does not establish a new feedback reference.
8. **DAC delivery.** Both AdcDsp and AdcDspFp latch/pop only one FIFO command
   when the AXI request/ack handshake is idle. The request remains stable until
   acknowledgement, then waits for acknowledgement release before the next pop.
   FP accounts for FIFO pointer latency when reporting outstanding writes.
   Overflow and AXI errors are counted; they do not roll back saved control
   state or automatically retry failed commands. Supported schedules must keep
   this path lossless.

The XCI configuration remains unchanged. `FLUX_ROUND_S` and comments now name
nearest-even conversion correctly, following
[AMD PG060's rounding specification](https://docs.amd.com/api/khub/documents/ym1A7qsltTGP_saZFTrikQ/content).
Both quotient and DAC conversion round independently. J is recomputed from F
each visit and counts periods R=N*Q, so N*J gives physical quanta; it is not a
number of crossing events since enable.

## New FP diagnostics

| Offset | Field | Meaning |
|---|---|---|
| 0x34 bit 0 | ControlBusy | Calculation, full clear or queued/active integral clear |
| 0x34 bit 1 | DacWriteBusy | Launched/queued/in-flight DAC writes, including FIFO transit |
| 0x38 bit 0 | ResetCounters | Pulse to clear the four diagnostic counts |
| 0x80 | MissedVisitCount | Enabled visit arrives while calculation is busy |
| 0x84 | DiscardedVisitCount | Visit ignored because disabled or clearing |
| 0x88 | DacOverflowCount | Feedback FIFO could not accept a write |
| 0x8C | DacErrorCount | Completed DAC write returned non-OK AXI response |

The four counts are unsigned 32-bit wrapping counters, reset by hardware reset,
StartRun or ResetCounters. Masking is distinct from visit loss. The existing
debug dropCount now counts actual visits suppressed by debug pause instead of
idle paused clocks. FP debug stays v1, 56 bytes; no external stream format change.

## Validation performed locally

GHDL 6.0.0, cocotb 2.0.1, Python 3.13.2. No Vivado, VCS or PyRogue was available
on this Mac. Exact test inputs check real state RAMs, emitted DAC AXI writes,
debug bytes through the production parser, and primary output streams.

| Check | Result |
|---|---|
| FP controller: 9 cases × 8/inverted and 256/normal row configurations | 18 passed |
| Existing integer properties, historical stimulus, fractional and flux suites | 43 passed |
| Integer stalled-delivery regression, both configurations | 2 passed |
| Native VHDL acceptance bench using explicit test models | Passed |
| Arithmetic-model oracle: 262 FMA, 263 int→float, 266 float→int | 791 vectors passed |
| New period/driver-closure/API tests | 26 passed |
| Selected Python suites including those 26 | 111 tests and 38 subtests passed; one existing helper subtest failed |
| Whitespace check | `git diff --check` passed |

The known Python failure is
`BatchHelpersTests.test_all_fast_dacs_stages_all_channels_before_flushing_each_driver`
for ColumnModule: it tries to read the removed `_ColumnModule.py`. It is unrelated
to these changes and is not counted as passed. Closure tests exercise production
setter/API bodies with fake register I/O; actual PyRogue device construction,
dependency notification and configuration save/restore still need a tree smoke test.

**Delivery fail→pass:** a temporary source overlay containing baseline
`e2eafb5` AdcDsp reproduced only `[(0, 1)]` after queuing five distinct commands
behind a stalled slave. The fixed RTL produced
`[(0, 1), (1, 102), (2, 203), (3, 304), (4, 405)]`, exactly once in order.
No baseline source was copied over the working-tree RTL.

The test-only FP models use wide integer arithmetic with one nearest-even
rounding for each FMA. Independent exact-rational expectations check the models;
they are not copies of the controller recurrence. GHDL's bundled float_pkg
gave incorrect FMA/conversion results in an initial model, so it is not used.
Examples were `mac(-1,-1024,-1234)` and conversion of `0.50048828125`.
Normal finite model behavior does **not** qualify vendor exceptional values,
subnormal handling, generated-core scheduling or synthesis. Firmware source
loading never includes these models.

Observed input-to-DAC-sink latency with the models, shared 125 MHz clocks,
inferred RAM/FIFOs and no AXI stall: 55 clocks for seed, 52 for retained-state
normal conversion, 57 for retained-state clipping. The first clipped visit also
incurs seeding. These observations include transport to the bench sink and
are not a maximum real-system latency or a timing-closure claim.

## Reproduction and remaining acceptance

After `make rtl_import` and installing the repository test dependencies:

```bash
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp/test_AdcDspFp.py tests/warm_tdm/adc_dsp/test_AdcDspFp_native.py tests/warm_tdm/adc_dsp/test_fp_models.py -n 3 -q
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp/test_AdcDsp.py tests/warm_tdm/adc_dsp/test_AdcDsp_bitexact_compare.py tests/warm_tdm/adc_dsp/test_AdcDsp_fractional.py tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py tests/warm_tdm/adc_dsp/test_AdcDsp_delivery.py -n 4 -q
.venv/bin/python -m pytest software/tests/test_fp_pid_controls.py software/tests/test_pid_debug_formats.py software/tests/test_cosim_checks.py software/tests/test_operations_cleanup.py software/tests/test_supporting_helpers.py -q
```

The last command includes the known stale ColumnModule subtest above. The
native [AdcDspFpTb target](../../../firmware/simulations/AdcDspFpTb/README.md)
provides executable generated-IP assertions without cocotb/VCS VHDL support.
Its bench passed locally with models; its actual Vivado/VCS/XSIM run is pending.

Still required: generated-IP boundary checks and timing, PyRogue tree smoke,
fixed-visit closed-loop step/reversal captures with measured local plant slope,
noise/residual performance near zero and ±256 quanta, loss counters under the
intended schedule, XPM/system transport integration, Vivado **2024.1** timing
and utilization, and hardware lock/noise/bandwidth acceptance. No claim about
relative FP/integer/MCE performance follows from these unit regressions.
