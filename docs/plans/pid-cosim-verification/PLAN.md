# Layered PID verification

[#90](https://github.com/slaclab/warm-tdm/issues/90) owns the reusable harness;
[#70](https://github.com/slaclab/warm-tdm/issues/70) owns the controller and
system/build/hardware acceptance. Framing acceptance remains on
[#82](https://github.com/slaclab/warm-tdm/issues/82). Implementation is consolidated
in [#106](https://github.com/slaclab/warm-tdm/pull/106). See the
[index](README.md) for current design records and historical investigations.

## Goal

Verify both PID paths after the accumulator split. Distinguish numerical unit
checks, generated-IP behavior, closed-loop system behavior and physical
performance; success in one does not establish the others.

## Layer 0: software, register and configuration integration

Cross-check production RTL/driver offsets and defaults, instantiate fixed and
FP trees, and exercise direct/VirtualClient controls, configuration save/restore
and enabled-column behavior. Repeat affected checks after interface changes.

At `fae7151`, the published CI fails because new pytest modules are imported by
unittest discovery without pytest installed. Merely installing pytest is not
enough to collect their module-level pytest functions; run pytest explicitly.
A separate helper subtest still loads removed `_ColumnModule.py`. Reconcile
legacy-support scope and all active driver cases rather than hiding failures.
The exact current blockers belong on #90/#106.

## Layer 1: deterministic RTL and arithmetic

Integer GHDL/cocotb benches cover controller properties, retained fractional
feedback, flux accounting and signed transport, and stalled DAC delivery.
The pre-split golden is immutable history. Later intentional numerical changes
use independent expectations, with a common-prefix historical comparison;
whole-path bit equivalence is not the acceptance criterion for changed behavior.

FP GHDL/cocotb benches now use explicit test-only arithmetic models. The
independent rational oracle checks model rounding/conversion. These tests run
without the generated Xilinx cores; they do not qualify vendor exceptional
values, denormals, scheduling or XPM transport.

Use [the native AdcDspFpTb target](../../../firmware/simulations/AdcDspFpTb/README.md)
for generated-IP execution. The cocotb/VCS VHDL runner is not a supported path.
Record the actual IP/tool versions for that run; do not treat older VCS-selector
notes or a modeled bench pass as generated-IP evidence.

Reproduction commands and reported local case counts are in
[FP_FIX_IMPLEMENTATION.md](FP_FIX_IMPLEMENTATION.md). The separate
[FP cleanup](FP_CLEANUP.md) compares output records and cycle timing against
`07a87d0` under its stated stimulus/configurations, not formal equivalence.

## Layer 2: full GroupTb closed loop

Use `USE_FLOAT_PID_G` to select each path and record the complete fixture:
source/submodule revisions, wafer variation seed, shaping/current scaling,
row/column map, gains, sample timing and initial DAC state. Earlier captures in
[PROGRESS.md](PROGRESS.md) predate some current corrections and are not inherited
by later revisions automatically.

For each path, establish the same supported visit schedule and a measured local
plant slope, lock, perturb TES bias, and capture step/reversal recovery. Check
residual/noise, fractional correction, flux wrapping, start/stop/reseed, masked
rows and all loss/error counters. Bound small steps to the locked branch; label
large-step relocking separately. Parameter/setup guidance is in
[cosim-tuning-settings.md](cosim-tuning-settings.md).

Closed-loop comparisons across different models, gains or operating points do
not establish an intrinsic fixed/FP performance difference. A simulated wafer
is not a calibrated physical detector.

## Layer 3: synthesis and timing

Build the affected target/generic matrix with **Vivado 2024.1**. Include an
integer configuration, FP configuration, supported row depths, debug/memory
options and the release targets listed by #70. Verify generated-core
compatibility with the build tool, timing closure, utilization, register map
and source/package selection. Report actual artifacts and checksums.

The modeled 52/55/57-clock FP delivery measurements are not real-system latency
bounds. Test the intended row schedule through the actual generated IP, XPM and
AXI paths and confirm no unexpected missed/discarded visits or delivery loss.

## Hardware acceptance and evidence

The live #70/#82 checklists define supported board/configuration coverage and
physical acceptance. Record fixed candidate revisions and artifacts; retain
failures and limitations. #42/#52 remain separate physical investigations even
when the same session supplies useful evidence. Hardware tests may follow
integration; prerequisite simulation and build checks may not be replaced by a
promise of later bench time.

[The original plan](https://github.com/slaclab/warm-tdm/blob/fae7151/docs/plans/pid-cosim-verification/PLAN.md)
preserves the earlier tools and proposed sequence. Its hardcoded-GroupTb,
GHDL-cannot-run-FP and pending-baseline claims are historical.
