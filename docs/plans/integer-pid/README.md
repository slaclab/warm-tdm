# Integer PID and accumulator requalification

[#70](https://github.com/slaclab/warm-tdm/issues/70) owns the accumulator split
and the correctness of both resulting DSP paths. Integer changes are part of
[#106](https://github.com/slaclab/warm-tdm/pull/106), not a frozen reference that
can be assumed unchanged. [#90](https://github.com/slaclab/warm-tdm/issues/90)
owns the maintained harness; [#82](https://github.com/slaclab/warm-tdm/issues/82)
owns the frame contract.

| Subject | Authoritative design/evidence record |
|---|---|
| Accumulator split rationale | [Original design](../pipelined-dsp-accumulator/PLAN.md) |
| State-read, feedback-lag and accumulator-range corrections | [Dated investigation log](../pid-cosim-verification/PROGRESS.md) |
| Retained fractional feedback, seeding, masking and rounding | [Integer fractional feedback](../pid-cosim-verification/INTEGER_FRACTIONAL_FEEDBACK.md) |
| Masked integral hold and I changes that preserve feedback/count | [Lifecycle alignment](LIFECYCLE.md) |
| Flux accounting, signed nine-bit limit, v3 debug transport | [Flux-jump review](../pid-cosim-verification/FLUX_JUMP_REVIEW.md) |
| Shared FIFO/AXI delivery correction | [Implementation, section 8](../pid-cosim-verification/FP_FIX_IMPLEMENTATION.md) |
| Reproduction and system/build gates | [Verification plan](../pid-cosim-verification/PLAN.md) |

The frozen pre-split golden remains historical evidence. Retained fractional
feedback intentionally changes later visits; the comparison checks the common
prefix and independently calculated later expectations. Do not claim whole-path
bit equivalence after an intentional numerical change or replace the golden to
obtain it. Closed-loop performance and hardware acceptance remain separate.
