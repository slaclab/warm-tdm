# Warm-TDM RTL Regression Plan

## Objective
- Build a checked-in cocotb regression flow for `warm-tdm` RTL.
- Keep executable test logic in Python so new benches share one workflow.
- Make verification progress resumable through checked-in `_meta` files.

## Chosen Methodology
- Python-only executable tests: `pytest + cocotb + GHDL`.
- Use a repo-local virtualenv and call tools through `./.venv/bin/...`, matching the local VS Code task pattern used in `~/surf/.vscode/tasks.json`.
- Keep VHDL limited to thin cocotb-facing wrappers and required simulation models.
- Reuse the existing models under `firmware/common/warm_tdm/sim/` as support assets, not as the primary bench style.
- Prefer narrow, deterministic first benches over large integration shells.

## Scope
- Phase 1 focuses on simulator-friendly `firmware/common/warm_tdm/rtl/` modules.
- Full board- or wafer-level simulation remains a later integration tier.
- IP-backed modules under `firmware/common/warm_tdm/ip/` are deferred unless a stable open-source simulation path exists.

## Coverage Model
- `functional_python`
  Python-authored cocotb regression for a simulator-friendly RTL unit.
- `wrapper_required`
  Functional cocotb regression exists, but needs a checked-in VHDL wrapper.
- `integration_sim`
  Uses multiple RTL blocks and existing warm-tdm simulation models for a realistic subsystem check.
- `deferred_ip_backed`
  Intentionally deferred because the current phase would depend on vendor IP or a fragile mixed simulation flow.

## Initial Rollout
- First pilot: `AdcDsp`.
- Second wave: `TimingDelay`, `TimingTx`/`TimingRx`, and `WaveformCapture`.
- Third wave: `DataPath` and `EventBuilder`.
- Later integration wave: board- and wafer-level benches using existing models from `firmware/common/warm_tdm/sim/`.

## AdcDsp Bench Strategy
- The first `AdcDsp` cocotb bench drives `LocalTimingType` directly through a thin wrapper.
- That direct-drive bench is the authoritative regression for PID behavior, including:
  - `I_Coef = 0` not accumulating,
  - clear-on-`StartRun` / `PidEnable` / `I_Coef`,
  - anti-windup behavior.
- A follow-on `integration_sim` bench should connect `AdcDsp` to the real timing subsystem.
- Do not block the PID bench on the full serialized timing path unless the `Timing` loopback proves stable under the chosen simulator flow.

## Environment And Runtime Policy
- Bootstrap the regression environment with `scripts/setup_regression_env.sh`.
- The bootstrap script creates `./.venv`, installs repo and regression Python requirements, and creates or links a repo-local `ruckus/` checkout for the GHDL flow.
- Imported HDL sources are expected under `build/SRC_VHDL/`.
- Phase-1 benches use the repo-root GHDL import surface rather than a firmware target build tree.

## Acceptance Criteria For Phase 1
- `docs/_meta/` contains plan, handoff, inventory, and progress files.
- The repo has a shared `tests/common/regression_utils.py`.
- The first checked-in cocotb bench for `AdcDsp` exists with a matching checked-in wrapper.
- A fresh session can recover the current verification state from `_meta` docs alone.

## Deferred Decisions
- Whether the full `Timing` serialized loopback is stable enough for default CI coverage.
- Whether the long-term import flow should use a dedicated simulation target instead of a firmware target import tree.
- Whether a graph-driven rollout is worth adding once the first subsystem benches land.
