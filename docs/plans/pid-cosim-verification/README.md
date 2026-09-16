# PID verification: start here

This directory contains reusable verification guidance and dated investigation
records. It accumulated several implementation efforts; their entry points are
now [integer PID](../integer-pid/README.md), [FP PID](../fp-dsp-pid/README.md),
[frame formats](../channelization/PLAN.md), and
[resource integration](../resource-integration/README.md).

[#90](https://github.com/slaclab/warm-tdm/issues/90) owns the harness;
[#70](https://github.com/slaclab/warm-tdm/issues/70) owns controller/build/hardware
acceptance; [#82](https://github.com/slaclab/warm-tdm/issues/82) owns frame/file
acceptance. [#106](https://github.com/slaclab/warm-tdm/pull/106) is the integration
review. Their live checklists supersede old "next steps" in dated reports.

| Need | Read |
|---|---|
| Verification layers, tools and remaining gates | [PLAN.md](PLAN.md) |
| Current FP behavior and local regressions (`07a87d0`) | [FP_FIX_IMPLEMENTATION.md](FP_FIX_IMPLEMENTATION.md) |
| FP refactor comparison (`fae7151`) | [FP_CLEANUP.md](FP_CLEANUP.md) |
| Integer retained-state numerical contract | [INTEGER_FRACTIONAL_FEEDBACK.md](INTEGER_FRACTIONAL_FEEDBACK.md) |
| Integer wrap/count/transport corrections | [FLUX_JUMP_REVIEW.md](FLUX_JUMP_REVIEW.md) |
| Vendor-IP execution | [AdcDspFpTb README](../../../firmware/simulations/AdcDspFpTb/README.md) |
| Fixture/gain setup for historical captures | [cosim-tuning-settings.md](cosim-tuning-settings.md) |
| Rationale and chronology | [PROGRESS.md](PROGRESS.md), [REVIEW.md](REVIEW.md), [FP_REVIEW.md](FP_REVIEW.md), [FP_SEED_REVIEW.md](FP_SEED_REVIEW.md), [FP_FIX_PLAN.md](FP_FIX_PLAN.md), [MCE_COMPARISON.md](MCE_COMPARISON.md) |

Reported passes apply to the revision/configuration named in each record.
GHDL arithmetic models, generated vendor IP, full GroupTb, synthesis/timing and
physical hardware establish different things. Preserve that distinction when
moving evidence into issues. No current record proves relative FP/integer/MCE
hardware performance.
