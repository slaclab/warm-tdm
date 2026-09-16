# Floating-point path: consolidated fix plan

Reviewed against `b37ff8c` on 2026-09-16; implementation started from `e2eafb5`.
The approved RTL/driver/API fixes are now implemented locally. See
[FP_FIX_IMPLEMENTATION.md](FP_FIX_IMPLEMENTATION.md) for the current behavior,
passing regressions, and remaining vendor/system/hardware acceptance. The
proposal text below records the reviewed baseline and its design rationale;
statements about the old behavior are historical, not the current RTL.
The historical assessments are [FP_REVIEW.md](FP_REVIEW.md) and
[FP_SEED_REVIEW.md](FP_SEED_REVIEW.md). The feature owner is issue #70, as linked
from [PLAN.md](PLAN.md); this note specifies proposed behavior and validation.

## Preserve the chosen architecture

Keep unwrapped float32 feedback as the primary per-row state, the incremental
PI law, the shared FpMac, and quotient-based multi-quantum wrapping. The stated
approximately +/-256 physical-quantum operating envelope does not establish a
need for bounded fractional feedback plus a separate accumulated flux offset.
Keep the existing FP signed 32-bit quotient/count; the integer controller's
user-selected nine-bit limit does not apply here.

Use these symbols below: F is unwrapped feedback, S is accumulated error, E is
the current row-window error sum, Q is a positive physical period in DAC-code
units, N is a positive integer WrapMultiplier, R=N*Q is the actual wrap period,
J is the signed wrap quotient, W is local fractional feedback and D is the
integer DAC command in controller coordinates. Ignoring finite rounding:

```text
F_candidate = F + P*E + I*S_old
J = nearest_even(F_candidate / R)       # enabled wrapping
W = F_candidate - J*R
D = nearest_even(W)                    # then enforce DAC limits
```

The implementation multiplies by a float32 reciprocal instead of dividing;
boundary tests must use the actual stored R and reciprocal. J counts periods
of R, so N*J is the corresponding number of physical quanta. It is not an
event counter starting at enable.

## Proposals and intended behavior

### 1. Startup seeding — retain the implemented fix, finish its qualification

`f6f1e55` marks full-feedback RAM unseeded on a full clear and converts the
captured signed DAC feedback through Int2Fp on the first visit. Keep this
approach. A masked visit must not commit a seed or remove the unseeded marker
(proposal 2). Subsequent enabled visits retain full feedback and its fraction.

An initial J=1 can be correct. F=377, R=538 gives W=-161 and J=1 while preserving
F. Replacing the primary F with W merely to show J=0 would shift the readout
reference by 538. Do not make that cosmetic change.

Acceptance: exact zero-gain seed preservation inside the wrap interval;
expected full-state preservation and equivalent DAC wrap outside it; both
polarities/signs, multiple rows, clear/start/enable paths and subsequent
fractional updates. Measure first-visit and steady-state latency separately.

### 2. Masked rows — hold control state

`AdcDspFp.RAM_WRITE_S` currently writes S, F and J even when the DAC write is
masked. Gate those three writes with the captured row-enable decision. Error
telemetry may still update; distinguish a computed candidate from applied
state in debug documentation. A masked uninitialized row must remain unseeded.

Recommended lifecycle: masking holds the previously applied control state;
unmasking resumes it. Manual changes to the DAC while masked require an
explicit reseed/reset policy, rather than silently treating the held state as
current. No automatic loss of fractional or unwrapped history on ordinary
mask/unmask transitions.

Acceptance: repeated nonzero masked errors change neither control RAM nor DAC;
enabled rows continue; unmasking releases no accumulated unapplied correction;
an initially masked row seeds from its first enabled visit's captured DAC.

### 3. Flux-period configuration — correct units and coherent updates

The FP driver still converts a period with `outCurrentToDac`, which converts
an absolute operating point and includes offset/clipping. With inverted
encoding, zero current returns raw code 8192, and the setter's XOR operations
turn that into **16383.0**. A local probe executed the production nested setter
with that amplifier result and observed R=16383 and reciprocal about 6.1039e-5.
This is a software counterexample, not a hardware run.

Recommended driver contract:

- Compute Q from `current / abs(currentPerLsb())`. FP can preserve a fractional
  code period; do not unnecessarily copy the integer driver's rounding or
  8191-period cap.
- Require finite nonnegative requested current, a valid nonzero conversion
  slope, and a positive integer N. Validate the effective float32 period and
  reciprocal. Reject positive values that cannot form a usable represented
  period/reciprocal.
- Zero disables wrapping: write both R and reciprocal as zero; the firmware
  contract is J=0, W=F. Do not leave a stale reciprocal.
- A write to either physical quantum or N must recompute the pair. Derive the
  reciprocal from the period actually represented in float32. Reads must not
  reinterpret an unchanged hardware period using a newly changed local N.
- Apply the pair while processing is quiescent, with in-flight calculations and
  writes drained. Do not rely on two separately visible AXI writes being
  atomic. An atomic staged-register implementation is optional if live updates
  become a requirement.
- Validate that approximately +/-R/2 fits inside the DAC range with the chosen
  margin. The asymmetric rails (-8192/+8191), rounding ties and reciprocal
  error need boundary tests. R=16000 can fit centered wrapping; the integer
  path's positive signed 14-bit period limit should not be imposed blindly.

Changing the physical period or using a full clear establishes a new acquisition
reference unless preservation is explicitly implemented. Stopped reconfiguration
and deliberate reseeding are the initial supported workflow.

### 4. Saturation — keep retained feedback consistent with the limited command

The current DAC path clips D, but RAM and primary output retain F_candidate.
This permits feedback windup even with I=0, especially with wrapping disabled.
Limiting future S updates alone cannot correct that state discrepancy.

Recommended mathematical behavior on **actual clipping**:

```text
F_next = D_clipped + J*R
```

For disabled wrapping, J=0. Otherwise preserve the valid unwrapped offset.
When there is no clipping, keep the original fractional F_candidate; copying
the rounded DAC into feedback on every visit would recreate the integer
deadband. Commit the same accepted F to RAM and primary readout, and keep J
consistent. Retain/refine the integral anti-windup rule alongside this change.

Implementation should reuse the existing conversion/FMA resources where
practical; it may require extra cycles on the clipped path. Qualify that path's
latency. No cycle or resource estimate is an acceptance result.

Acceptance: repeated forcing of both rails and error reversal with P-only and
PI, wrapping disabled, and valid wraps that must not trigger clipping recovery
or lose unwrapped signal. Back-calculation removes F windup; it does not by
itself prove that all previously accumulated I action unwinds promptly.

### 5. I-gain changes — separate integral reset from full feedback reseeding

Today the public I setter invokes ClearPidState on every write, even the same
value. A raw I write does not. Positive-zero I holds old S; negative zero does
not match the RTL's exact positive-zero test. These are different lifecycle
contracts for nominally the same operation.

Full clearing now seeds from the *wrapped* DAC. For F=377, R=538 and D=-161,
an I-setting-triggered full clear makes the next F approximately -161, losing
538 from the previous readout reference as well as any sub-code fraction.
This is appropriate for an explicit full reset but undesirable as an
undocumented effect of routine live gain adjustment.

Recommended policy, requiring a deliberate implementation change: an actual
I-coefficient change clears only integral history and preserves F/J; I=+0 or
-0 disables/zeros S; writing the same coefficient has no reset side effect.
Reserve the existing full clear for deliberate new-reference/reseed operations.
Apply the policy consistently to raw writes and public APIs. Handle changes at
a defined calculation boundary so an in-flight result cannot undo the reset.
Changing I can still alter the subsequent control increment; this proposal
does not promise a completely bumpless transfer of integral action.

### 6. Operational API — allow PI-only set_pid

`Session.set_pid` must validate only the gains requested and supported by the
tree. Recommended compatibility behavior: P/I and debug-only calls work;
omitted D and D=0 are accepted on FP; a nonzero D request raises an explicit
unsupported-gain error **before any writes**. Keep sample-count normalization.
Use global-column-to-board/channel mapping for the debug-enable write as well
as the gain arrays; the current debug path assumes the coordinator board.

Acceptance: integer P/I/D and FP P/I, omitted/zero/nonzero D, debug-only calls,
selected columns and multiple boards. Reapplying gains through setup_mux must
obey the selected I-change policy rather than silently resetting the reference.

### 7. Conversion semantics — document and test nearest-even

The XCI selects Float_to_fixed to Int32. [AMD PG060, Rounding Modes, printed
pages 5–6](https://docs.amd.com/api/khub/documents/ym1A7qsltTGP_saZFTrikQ/content)
specifies nearest-even, including float-to-fixed conversion. Keep that behavior
and centered wrapping unless a separate requirement selects truncation. Correct
the truncation comments/state naming and old architecture notes.

Use the generated IP to test both signs at and around half-integers, quotient
boundaries over multiple quanta, and final DAC rounding independently. Test
stored float32 R/reciprocal combinations, not an ideal real-valued division.
This review rechecked the documentation; it did not simulate the converter.

### 8. Delivery and diagnostics — qualify the actual actuator path

Add distinct counters/status for accumulation visits missed while busy,
DAC FIFO overflow and failed DAC writes. Define intentional clear/disable
discards separately. Existing dropCount covers debug suppression and cannot
establish that the control path processed every visit.

Source inspection also identifies a concrete handshake problem:
`AdcDspFp.axilComb` pops the FIFO and replaces `req` whenever fifoValid is high,
even while AxiLiteMaster is executing a previous request. A second queued write
during a stalled transaction can be consumed without subsequently being issued.
The corresponding integer code has the same pattern. This finding was not
covered by the previous FP review and has not been reproduced in RTL here.

Latch/pop exactly one request when the master handshake is available; hold it
through completion and release the request/acknowledgement before consuming
another. Counters alone do not fix this. Verify with a deliberately stalled
AXI slave and a burst of distinct row/value writes, checking exactly-once
delivery, ordering and error reporting. Include FIFO-full behavior. If a
control write is lost, expose the fault rather than claiming saved state was
applied. The supported operating schedule must keep the queues lossless.

Measure input-to-DAC latency including seed, clipping recovery, RAM clear,
debug activity and downstream backpressure. Require completion before the
affected row next needs that feedback; do not rely on the old ~34-cycle sketch.

### 9. Test harness and performance qualification

Repair the FP source allowlist (missing FrameHeaderPkg), vendor runner, and DAC
stimulus encoding. Replace nonzero-only assertions with exact state/correction
checks. See FP_SEED_REVIEW for the current raw-zero/+8191 seed problem. A small
behavioral FP model can exercise FSM/control logic, but cannot qualify generated
IP rounding, exceptions or latency by itself.

Measure local plant slope at the actual wrapped DAC operating point, then
capture step-up/step-back recovery at fixed visit counts. The reported opposite
P signs have no demonstrated intrinsic RTL explanation. Compare equal sample
counts, raw gains, polarity, wrap settings and plant points. A low error at
P=0 is not disturbance rejection.

Check small corrections and residual/noise near zero and +/-256 physical
quanta. Keep the architecture unless those measurements fail the required
performance budget. Finish Vivado 2024.1 timing/resource checks and hardware
acceptance separately from simulation.

## Suggested sequence and scope boundaries

1. Restore a useful FP regression harness and reconcile the separately merged
   integer test's obsolete reseeding assumption (7/8 passed in the prior review).
2. Qualify startup and fix masked state, period configuration and set_pid.
3. Implement clipping feedback tracking and the agreed I-change lifecycle.
4. Fix/verify stalled DAC-write handling, add loss diagnostics and qualify
   every supported execution path against row timing.
5. Run controlled cosim comparisons, precision-envelope checks, synthesis and
   hardware acceptance.

No proposed change to the PI recurrence, addition of D, MCE emulation, or split
feedback/flux-state architecture is justified by these findings. A redesign of
the NaN seed marker is also not required for the ordinary finite operating
envelope; exceptional-value handling should be specified if it becomes a
supported requirement rather than assuming NaN can never occur.
