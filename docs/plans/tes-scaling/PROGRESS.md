# TES scaling and flux-jump capture

## Current handoff

The September 18 integer GroupTb session reported a steady-state verify pass
and a repeatable fine TES ramp with changing flux counts. The remaining
problem is that the general `steady,flux` harness still reports net zero on
its capture cadence while `cosim_pid_lock.py` observes jumps. The cause is
unconfirmed; this remains controller/test work on
[#70](https://github.com/slaclab/warm-tdm/issues/70), not physical acceptance.

The original session sequence is preserved in the
[source-pinned record](https://github.com/slaclab/warm-tdm/blob/d0bedaae8b65e648d6cec101c39564f5bcbb2b9a/docs/plans/tes-scaling/PROGRESS.md).
It includes earlier unsuccessful operating points and interpretations that
later measurements superseded. Do not use those earlier “blocked” sections
or gain signs as the current handoff.

## Reproduction and operating point

Use [GroupTb setup](../../../firmware/simulations/GroupTb/README_cosim.md)
and [the client harness](../../../software/cosim/README_cosim.md).
The recorded session used the integer path, 23 uA nominal quantum, coherent
per-row Sq1Bias=50 uA / Sq1Fb=2 uA / SaFb=9 uA before the SA null, raw
P=-0.0025 and I=0. Those values are fixture-specific; gain sign changes with
the operating slope. The earlier clipped approximately 77 uA bias point
supported a different sign and is not an interchangeable setup.

`cosim_pid_lock.py` carries the coherent `--seed-tune-points` / `--seed-tune`
sequence and `--tes-steps` register-read ramp. The reported repeatable demo
used `--tes-steps 12 --tes-step-uA 4`: FluxJumps changed 0 to 11 over 48 uA,
with retained feedback bounded. An earlier fine-ramp table recorded 1 to 104
over 80 uA. These are separate reported captures, not a calibrated conversion
between TES current and flux count. The original notes do not pin a complete
source/image/configuration tuple for every capture.

The steady verify result reported mean residual 577 below its threshold of
800 and FluxJumps=0. This establishes the reported synthetic integer check
only; it does not establish FP equivalence, physical lock or noise/bandwidth.
Do not issue an extra ClearPids while reproducing a seeded operating state
without accounting for the reset/reseed behavior.

## Remaining discriminating check

`check_flux_jump` now reads the per-row FluxJumps register and reports net
change across the ramp. Its zero result can still differ from the immediate
register-read demo. The suspected difference is settle/acquisition cadence,
not a confirmed counter defect.

1. Use one fixed source/submodule/configuration and the same initialized row,
   bias, gain, quantum and TES starting point for both scripts.
2. Record counters and retained feedback immediately before/after each step
   and again after each settle/capture; record whether timing restarts or any
   setup/clear is repeated. Read Sq1Fb_DBG as a scalar and the per-row
   Sq1FbFull/FluxJumps arrays with the intended row index.
3. Compare register deltas with decoded debug timestamps and loss counters.
   Separate a net count change over an interval from a count of all crossings.
4. Attribute the discrepancy before treating the general harness as a
   flux-jump acceptance gate. Preserve the resulting source/image IDs and
   captures on #70.

Keep the [SQ1 static/muxed-state investigation](../pid-cosim-verification/SQ1_RETUNE.md)
for the independent applied-current, SA-offset and servo-convergence limits.
Run/build commands belong in the maintained harness READMEs, not this handoff.
