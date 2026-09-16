# Floating-point PID

[#70](https://github.com/slaclab/warm-tdm/issues/70) owns implementation and
acceptance; [#106](https://github.com/slaclab/warm-tdm/pull/106) reviews the
consolidated branch. #87/#88 are historical, superseded reviews.

Read in this order:

1. [Current PI architecture](PLAN.md).
2. [Correctness/configuration/delivery implementation](../pid-cosim-verification/FP_FIX_IMPLEMENTATION.md), committed as `07a87d0`.
3. [Source-organization cleanup and comparison evidence](../pid-cosim-verification/FP_CLEANUP.md), committed as `fae7151`.
4. [Layered verification](../pid-cosim-verification/README.md), including the native generated-IP bench.

`FP_REVIEW`, `FP_SEED_REVIEW` and `FP_FIX_PLAN` in the verification directory
explain how the current implementation was reached; their open findings are
historical where the implementation record resolves them. The latest required
checks remain on #70/#90. Model-based passes do not establish generated-IP,
closed-loop, Vivado 2024.1 or hardware acceptance. `PROGRESS.md` and the demo
material preserve earlier design history; old cycle counts are not current
hardware guarantees.
