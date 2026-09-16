# Integer PID: retained fractional SQ1 feedback

## Purpose and scope

Proposal from the September 16, 2026 controller review, based on Warm TDM
`ef81760`. Retain fractional feedback between visits to each row so repeated
sub-DAC-code corrections can eventually move the DAC. The change is proposed;
production RTL and its acceptance tests have not been implemented.

Use a per-row signed rounding remainder alongside the captured applied DAC.
Together these represent the retained fractional SQ1 feedback. Keep the existing
incremental PID equation, sample-window accumulation, coefficient normalization,
and integer flux-jump policy. This does not change the error integral SumAccum
or introduce another integration stage.

The FP controller deliberately retains unwrapped floating-point feedback. Its
design is separate and remains intact; see [FP_REVIEW.md](FP_REVIEW.md) for the
recorded rationale and the user's expected 256-jump operating envelope. MCE
compatibility is not a requirement for either controller.

Related feature context: [Issue #70](https://github.com/slaclab/warm-tdm/issues/70)
and the [RTL regression framework, Issue #90](https://github.com/slaclab/warm-tdm/issues/90).
This document supplies design guidance; implementation and acceptance tracking
belong on the owning issue under [the workflow policy](../../WORKFLOW.md).

## Current behavior and evidence

In `firmware/common/warm_tdm/rtl/AdcDsp.vhd`:

- `pidResult` has 23 fractional bits and is saved in the per-row PidResults RAM
  at lines 760-761. Its RAM output, `pidRamOut`, is not consumed by the controller.
- PREP_PID_S reloads `sq1Fb` from the captured 14-bit DAC at line 687.
- SQ1FB_ADJUST_S adds the correction and resizes it to
  `sq1Fb : sfixed(13 downto 0)` at line 769. The fraction is rounded away.
- `sq1FbFull : sfixed(31 downto 0)` also has no fractional bits and does not
  provide per-row feedback state for the next update.

A GHDL diagnostic on the current accumulator plus integer DSP fed each actual
DAC write back as the next visit's applied value, with I=D=0:

| Per-visit stimulus | Visits | Observed result |
| --- | ---: | --- |
| E=1, raw P=0.25 | 8 | PidResults stores 0.25 each visit; DAC stays unchanged |
| E=2, raw P=0.5 | 3 | DAC advances by one controller code each visit |

The first case encoded P as `1 << 21` in Q1.23 and read the fractional result
from PidResults RAM at 0x3000/0x3004. With the wrapper's inverted DAC encoding,
controller zero was DAC 8191; fractional-case writes all remained 8191, while
the whole-code control produced 8190, 8189, 8188. This confirms a fractional
correction record exists but fractional feedback does not accumulate.

The diagnostic passed under GHDL 6.0.0 / cocotb 2.0.1. Scratch files were
`/private/tmp/warm-tdm-pid-review/fractional_feedback_probe.py`,
`fractional_feedback.json`, and `fractional_feedback.log`; these are temporary,
not durable test assets. The stimulus and expectations above must become
checked-in regression coverage during implementation. This evidence establishes
the current behavior, not validation of the proposed change.

## Proposed arithmetic

For visit n to one row, let:

- `u[n]` be the signed controller-coordinate value decoded from that row's
  captured applied DAC. ADC-window feedback capture remains at firstSample.
- `R[n]` be the saved fractional remainder for that row, initially zero.
- `E[n]` be its accumulated window error and `S[n-1]` its previous error sum.
- `delta[n]` be the current implementation's PID correction, with its existing
  coefficient arithmetic and limits:

```text
delta[n] = P*E[n] + I*S[n-1] + D*(E[n-1] - E[n])
```

Compute the actuator update in this order:

```text
candidate = u[n] + R[n] + delta[n]
limited   = clamp(candidate, -8192, 8191)
q         = roundNearestEven(limited)
R[n+1]    = limited - q

# Existing integer threshold/count wrap, including its current limits:
nextDAC   = existingIntegerFluxWrap(q)
```

Keep candidate arithmetic wide until the explicit DAC clamp. A working type
with at least `RESULT_HIGH_C+1 downto RESULT_LOW_C` accommodates the current PID
result plus the DAC and remainder without premature overflow. Preserve the
existing 23 fractional bits throughout this calculation.

For an unclipped, unwrapped update, `q + R[n+1] = u[n] + R[n] + delta[n]`.
On the next visit, the applied integer DAC plus the saved remainder reconstructs
that fractional feedback state. The remainder stores the previous command's
rounding error; adding the previous complete pidResult would incorrectly repeat
its whole-code correction.

Example with +0.25 per visit, zero initial feedback and no clipping/wrapping:

| Visit | Candidate | Integer DAC coordinate | New remainder |
| ---: | ---: | ---: | ---: |
| 1 | 0.25 | 0 | +0.25 |
| 2 | 0.50 | 0 | +0.50 |
| 3 | 0.75 | 1 | -0.25 |
| 4 | 1.00 | 1 | 0 |

Apply rounding to the complete candidate. Rounding only the correction before
adding an integer DAC can differ at half-code ties because nearest-even depends
on the parity of the resulting integer code. Negative remainders are necessary.

## Per-row state and lifecycle

Proposed storage is `sfixed(0 downto -23)`: 24 bits per row, covering both
half-code endpoints. The remainder is bounded to [-0.5, +0.5]. With
`2**ROW_ADDR_BITS_G` entries this is 3,072 stored bits at 128 rows or 6,144 bits
at 256 rows per DSP, before physical RAM mapping and control overhead. No new
multiplier is required.

Read the remainder alongside the existing per-row state using the same logical
row address and established RAM-latency wait. Simply widening the transient
`sq1Fb` register is insufficient because PREP_PID_S reloads it from an integer
DAC each visit.

Proposed lifecycle rules:

| Event | Remainder behavior |
| --- | --- |
| Accepted enabled-row update | Use that row's old remainder and save its new remainder with the update |
| Masked-row visit | Hold its remainder; do not accumulate an unapplied correction |
| Global PID disabled | No remainder updates |
| StartRun, explicit ClearPidState, rising PID enable | Clear all row remainders with the existing state-clear sweep |
| Raw I-coefficient change | Follow the integer RTL's existing clear-state trigger |
| Normal P-only operation, I already zero | Retain the remainder; it is independent of SumAccum |
| Manual DAC reseeding | Clear PID state before resuming control, including after a masked interval |

Reset must leave the new state initialized before any enabled visit is accepted;
reuse the existing clear lifecycle rather than assuming block RAM clears with
the transient registers. With R=0, the first update adopts the current applied
DAC, preserving the integer controller's tuned starting point. Mask/unmask
without a DAC change can resume the held remainder. Live manual reseeding
without a clear is outside this proposed contract.

## Saturation, anti-windup and flux wrapping

Preserve the current ordering: limit/round to the signed DAC range, then apply
the existing threshold-based flux correction. Changing that ordering or adding
multi-quantum wrapping is a separate design change.

Derive the remainder from `limited - q`, not from the unclipped candidate.
Otherwise a large discarded overrange correction could become hidden windup
instead of a bounded rounding remainder. At a clamped integer rail the new
remainder is zero, while in-range fractional values retain their remainder.

Use the remainder-inclusive, unclipped candidate in the existing I-term
anti-windup comparison. Keep its directional integration rule and signed
18-bit SumAccum behavior. The proposed change does not widen that integral.

For a normal representable integer-quantum wrap by j*Q:

```text
nextDAC + R[n+1] = limited - j*Q
```

Thus the wrap leaves the remainder unchanged. Retain the existing flux-count
update. Exercise odd and even quantum values and half-code ties; rounding is
defined before wrapping. If a wrap operation itself saturates, discard the
remainder for that clipped output rather than assuming an exact integer shift.

This state scheme assumes the DAC write reaches the intended row before its
next sampled visit, as the existing controller does. It does not repair FIFO
overflow, failed writes, or missed visits. Tests must monitor actual DAC writes
and feed those values into subsequent visits, not assume every computed command
was applied.

## Implementation boundaries

| Area | Proposed change |
| --- | --- |
| `AdcDsp.vhd` state declarations / RAM | Add per-row remainder storage, its transient value and write controls |
| Clear sweep / PREP_PID_S | Clear and load the new state without reducing the current row-address setup time |
| PID_D_S / SQ1FB_ADJUST_S | Include remainder in the anti-windup candidate; clamp, round and extract the new remainder |
| FLUX_JUMP_S / update commit | Preserve the remainder through normal wraps; commit only for enabled updates |
| Integer cocotb tests | Add independent expected results for fractional carry and lifecycle/boundary cases |

Keep PidResults as the current fractional PID correction for software/debug
compatibility. Keep the DAC output and existing integer readout formats intact;
they need not expose the new fraction to benefit from retained state internally.
Start with an internal remainder RAM. If host readback is needed, allocate an
explicit field/window without moving existing register offsets or silently
repurposing a diagnostic. Select the RAM primitive and pipeline placement during
implementation; synthesis must establish actual resources and timing.

## Verification approach

The integer GHDL framework already executes the relevant accumulator/DSP RTL.
It can be extended for this change without first repairing the FP simulator
harness or establishing a lock in the wafer model. Use independently calculated
fixed-point expectations rather than a golden regenerated from the new RTL.

| Case | Required observation |
| --- | --- |
| Repeated +/-0.25 and smaller corrections | Feedback advances after enough visits; retained state equals the accumulated correction within specified arithmetic limits |
| Half-code boundaries and odd/even starting DACs | Nearest-even behavior, both signs, no bias from discarding negative remainders |
| Alternating rows with distinct DAC seeds/corrections | Each row retains its own fraction without predecessor coupling |
| Clear, enable, reset, I changes | No stale remainder; a nonzero DAC seed remains the starting point |
| Mask/unmask | Masked visits do not accumulate unapplied fractional feedback |
| Positive/negative flux wraps | Existing jump-count behavior and correct remainder carry, including half ties and odd/even Q |
| Clipping and error reversal | Remainder remains bounded; discarded overrange command is not later released |
| Whole-code updates with zero remainder | Existing actuator behavior is preserved |
| Large accumulated errors | Existing final-sum saturation and feedback-capture regressions remain covered |

The frozen pre-split golden remains evidence for the old algorithm. Fractional
carry deliberately changes some DAC sequences, so the historical 11-write
compare may need to be split into unchanged-behavior checks and explicit new
expectations. Do not overwrite the old golden and call that proof of the change.

After unit checks, use Vivado 2024.1 to assess the additional RAM/arithmetic and
the shortest supported row schedule. Closed-loop residual/noise improvements
remain an eventual system/hardware measurement; the existing diagnostic proves
the numerical loss, not its contribution to the observed cosim lock symptoms.

## Next implementation decisions

The recurrence, remainder precision, ordering and lifecycle above are the
proposed defaults. Implementation still needs to select the RAM primitive and
whether readback is useful, settle write-cycle placement against the existing
FSM, and make the new GHDL cases durable. Keep issue acceptance records separate
from this design note. No FPGA behavior has changed as part of this writeup.
