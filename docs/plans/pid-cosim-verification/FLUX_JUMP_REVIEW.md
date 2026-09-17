# Integer flux-jump review — September 16, 2026

## Scope and result

Reviewed the working-tree `AdcDsp` path after retained fractional feedback and
AXI RAM/debug exposure. The wrap direction and fractional arithmetic are correct
for a positive quantum, within the single-wrap and net-count limits below.
The review found and corrected counting, telemetry and signed-readout defects.
**Superseded limits:** the later [multi-wrap implementation](../integer-pid/MULTI_FLUX.md)
expands J to 19 signed bits, recovers multiple wraps before clipping, and
moves integral admission to the post-wrap command. The single-wrap/nine-bit
limits below describe the earlier revision and its evidence.

At that earlier revision, the user chose to retain the **signed nine-bit net count,
−256 through +255**, rather than widen it. AdcDspFp is unchanged.

The primary files are `AdcDsp.vhd`, `WarmTdmPkg.vhd`, `FrameHeaderPkg.vhd`,
`_AdcDsp.py`, `_DataFormats.py`, `_PidDebugger.py`, and the actual-output test
`tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py`.

## Arithmetic contract

Let F be saved local feedback, J the saved net wrap count, Q a positive integer
quantum, and Δ the PID correction. Before clipping or count saturation:

```
C = F + Δ
w = +1 if C > 7862, −1 if C < −7862, otherwise 0
F_next = C − w*Q
J_next = J + w
F_next + J_next*Q = F + J*Q + Δ
```

Thus the count sign compensates exactly for the local feedback shift. Both DAC
polarities use this same controller coordinate system; offset-binary inversion
is applied at the DAC boundary. Strict full-precision threshold comparisons are
intentional: exactly ±7862 does not wrap; crossing it by one fractional LSB does.
For Q in 1..8191, a threshold crossing cannot wrap past the opposite threshold.

After wrapping, F_next is clamped to [−8192, 8191] and saved with all 23 fractional
bits. The DAC receives nearest-even rounding. The integer readout is
`round(F_next) + J_next*Q`; it does not expose the retained fraction. Its difference
from the unclipped full-precision signal is at most half a DAC code, provided
neither the DAC nor the count has saturated. Odd-Q half ties can change rounding parity but do
not lose fractional state. The debug stream carries F_next before rounding.

## Defects confirmed and corrected

| Defect | Evidence on the pre-review candidate | Correction |
| --- | --- | --- |
| Masked visits advanced the saved count without applying a DAC wrap | F=7862, J=7, Q=2000, masked +0.25 correction left F unchanged but wrote J=8 | Gate count-RAM write with `rowEnabled`, matching the full-feedback/DAC commit |
| Q=0 consumed count range without shifting feedback | Zero-gain visits at F=8000 incremented J from 0 to 1 | Zero quantum disables both wrapping and count changes |
| Nine-bit count was truncated to eight bits in telemetry | J=128 read back correctly from raw RAM but decoded as −128 in debug | Sign-extend all nine bits to int32 in debug v3; use nine-bit Python register fields |
| Internal 24-bit FIFO transport discarded the readout sign-extension byte | Unwrapped −21862 emerged as 16755354 in `tData(31:0)` | Carry all 32 integer bits through the DSP and Biquad input FIFOs |
| FluxQuantum conversion used an absolute DAC operating point for a difference | The inverted-amplifier zero-current conversion encoded raw `0x3fff` (signed −1) | Convert the quantum magnitude using `abs(currentPerLsb())`; zero encodes exactly zero, and negative/unrepresentable periods are rejected |

The readout issue is observable at the actual DSP FIFO output. `BiquadFilter`
passes `tData(31:0)` directly to Int2Fp, and the checked-in Int2Fp XCI selects
Int32 input. The shared integer stream configuration is now four bytes, so both
FIFOs preserve the signed word. This does not change the external readout frame
layout or floating-point PID stream configuration.

Debug format v3 is still 96 bytes. Relative to v2, body word 7 now carries the
complete signed net count in bits 31:0, with zeros in bits 63:32. The host
retains v1 (88-byte) and v2 (96-byte) decoders; their original eight-bit count
field cannot recover the ninth bit that those frames never transmitted.
The new fractional-feedback word remains at frame byte 64.

For masked visits the debug frame continues to show the *computed* feedback
and count. Neither is committed to RAM, and no DAC command/readout sample is
issued. Clearing and initialization continue to use the existing row-RAM sweep.

## Retained limits and operating requirements

- **Net count −256..255.** This is signed net excursion, not the lifetime number
  of forward/backward events. At +255 a further positive wrap still moves the
  DAC but J saturates; reconstructed feedback loses one Q. The corresponding
  negative case occurs beyond −256. This limitation is explicitly retained at
  the user's request, and tested as a limitation rather than a successful
  lossless wrap. There is no new overflow alarm or automatic recovery.
- **One quantum per visit.** For example, 8500.25 with Q=2000 recovers to 6500.25.
  But 12000 with Q=2000 becomes 10000 and clips to 8191; it does not perform a
  second wrap. At the positive/negative thresholds, the correction margin
  before DAC clipping is approximately Q+329 / Q+330 codes. Physical tracking
  requires adequate settling and slew headroom; arithmetic tests do not prove
  analog lock through a jump.
- **Positive Q, 1..8191 DAC codes.** Q=0 disables wrapping. Negative signed raw
  encodings retain the old arithmetic for compatibility with low-level tests,
  but move feedback outward and are unsupported operating configurations. The
  Python driver rejects them. An integer quantum also must be calibrated to the
  physical periodicity; retaining feedback fractions does not improve Q's
  one-code resolution.
- **Configure Q while quiescent, then clear/reseed before resuming.** Changing
  Q with a nonzero count changes reconstructed feedback by `J * change_in_Q`.
  Mid-visit writes are not an atomic update of wrapping and reconstruction.
- **Pre-wrap I anti-windup is unchanged.** It can hold SumAccum when the
  pre-wrap candidate exceeds a DAC rail even if the subsequent flux wrap
  recovers an in-range command. A test demonstrates 8500.25 → 6500.25 with
  SumAccum held. A future performance change could base admission on actual
  post-wrap clipping; this review does not retune that policy.

The one guard bit in `sfixed(14 downto -23)` is sufficient under this contract.
Commands outside that working range cannot be brought into the DAC range by
one positive signed 14-bit quantum, so the intermediate saturation cannot
change the final clamped result.

## Multiple-quanta follow-up (discussed, not implemented)

If one wrap leaves F outside the threshold but inside the DAC range, a later
visit can wrap again even with zero new error. If it leaves F outside the DAC
range, the immediate clamp discards the excess; later visits cannot recover
that discarded correction. For C=11000, Q=2000 and initial J=0, the current
path produces F=8191 and J=1 (reconstructed 10191). Two wraps before clipping
would produce F=7000 and J=2, preserving 11000.

Supporting multiple quanta per visit would require preserving the candidate
through all required wraps and adjusting J for each one before the final DAC
conversion. Only the final physical DAC write is needed. A repeated-wrap FSM
would reuse a simple add/subtract path but add cycles per quantum; its worst-case
latency must fit the row schedule. It would also require reassessing the working
width: the current 38-bit guard-range saturation is justified only by the
single-wrap contract. This remains a follow-up, not part of the saved change.

## Verification

Reproduce from the repository root after `make rtl_import`:

```bash
.venv/bin/python -m pytest -n 4 \
  tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_fractional.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_bitexact_compare.py
.venv/bin/python -m pytest \
  software/tests/test_pid_debug_formats.py \
  software/tests/test_cosim_checks.py \
  software/tests/test_supporting_helpers.py::IntegerFluxQuantumTests
```

Eight flux cases run with 8 rows/inverted DAC and 256 rows/normal DAC. They
exercise the actual DAC writes, retained state, count RAM, debug FIFO/production
decoder, and reconstructed integer FIFO output. Coverage includes both signs,
Q=1/2000/2001/8191, threshold crossings/reversals, independent rows, masks,
Q=0, count sign boundaries and extrema, signed conversion input, recoverable
overrange commands, clipping and the retained pre-wrap anti-windup policy.

The final run passed all **40 GHDL/cocotb cases** with no skips (six pytest
configurations), including the existing arithmetic/lifecycle/historical cases.
All **37 targeted Python tests** passed, including 25 subtests; results are also
recorded in PROGRESS.md. The targeted Python tests cover all three
integer debug versions, FP compatibility and quantum conversion for either
amplifier polarity. Full PyRogue tree construction is unavailable locally.

A broader run of `test_supporting_helpers.py` has an unrelated existing failure:
its `ColumnModule` subtest references the removed `_ColumnModule.py`. That is
not a flux regression and was not changed as part of this review.

Vivado 2024.1 synthesis/timing and physical flux-wrap/closed-loop acceptance
remain outstanding. Reusable procedure and constraints live here; hardware
acceptance remains on the owning issue under [WORKFLOW.md](../../WORKFLOW.md).
