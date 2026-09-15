# PID cosim verification (integer + floating-point)

## Goal

Re-qualify the column-board PID DSP path after the accumulator-split restructure
and validate the new floating-point PI servo, using layered simulation — from
model-free bit-exact unit regression up to full-system closed-loop cosim.

Both paths are in scope, and **the integer path is treated as new code to be
re-qualified**, not assumed good: the restructure moved real logic, so "it was
the known-good integer PID" no longer holds without proof.

## Branch & worktree

Verification targets the `channelization` integration (Issue #82, Self-describing
data frames + channel-layout cleanup; PR #106), which now carries the FP-PID core
(Issue #70, Floating-point PID firmware — AdcDspFp + accumulator split), the
accumulator split, and the self-describing frame header. The FP-PID track
(formerly `fp-pid`) converged into `channelization`; see the Branch Merge Roadmap
wiki. Worktree: `warm-tdm-channelization`.

## Background — why re-qualification is needed

- **Integer `AdcDsp` was restructured.** The accumulation front-end (baseline
  subtract + sample sum) moved out into the new `AdcAccumulator`; `AdcDsp` now
  consumes `accumIn : AdcAccumResultType` + `accumValid` instead of the raw ADC
  stream. The AXI-Lite crossbar shrank 8→7 masters, every downstream RAM offset
  shifted, and `ROW_ADDR_BITS_G` default changed 8→7. The PID compute states look
  unchanged, but the accumulation numerics moved from an `sfixed` accumulator to a
  `signed(31:0)` accumulator + slice — that must be shown **bit-exact**.
- **Floating-point `AdcDspFp` is new.** PI-only (D dropped), single shared FpMac,
  ~34-cycle pipeline, software-configurable flux-quantum wrap; depends on the
  Xilinx FpMac / Int2Fp / Fp2Int IEEE-754 IP cores.
- **The detector/wafer sim model differs between branches**, so a *closed-loop*
  cross-branch comparison confounds "PID logic changed" with "model changed."
  Bit-exact checks therefore live at the unit level (model-free); the closed loop
  is a behavioral check only.

## Verification layers

### Layer 0 — static / build sanity  *(largely done)*
- VHDL↔PyRogue register cross-check across the offset shifts. Done by hand (the
  automated parser is blind to the crossbar + `AxiDualPortRam` + local-endpoint
  architecture); `RowPidStatus`/`RowPidStatusFp`/`AdcAccumulator` offsets all
  match VHDL. **PASS.**
- Device-tree import smoke in `warm-tdm-r615`. **PASS.**
- `software/tests/` pytest suite — **owed** (pytest not installed in
  `warm-tdm-r615`; resolve the env).

### Layer 1 — unit RTL simulation (cocotb, Issue #90)
The unit half of the story; deterministic and model-free. Issue #90's framework
already lives on `channelization`.
- **Integer `AdcDsp` bit-exact regression under GHDL** — the Tier-1
  re-qualification. Drive identical scripted stimulus and compare against a
  captured pre-split (ops-fixes-era) reference; plus the reconstructed PID checks
  (P-term response, anti-windup, software PID-state clear). Model-free, license-
  free, CI-able. This is the check the closed-loop cosim **cannot** provide.
- **`AdcDspFp` under VCS** (`WARM_TDM_SIM=vcs`; GHDL can't elaborate the FP IP) —
  deterministic PI arithmetic, flux-jump wrap at the configured quantum, ~34-cycle
  latency, dropCount behavior.

### Layer 2 — closed-loop cosim  *(centerpiece)*
Full system (`GroupTb` + `warmTdmServer --sim`) with a **wafer load**, where the
servo loop closes physically: `SaOut = f(TesBias, sq1Fb, saFb, rowSel, …)` through
the SQUID transfer functions, and TES bias opposes SQ1 feedback (the sign a
nulling servo needs).

Procedure:
1. Configure a known tune point; `setup_mux(enable_pid=True, enable_pid_debug=True)`.
2. `run_mux()` (StartRun); let the loop lock — the PID should hold the accumulated
   error (SaOut vs baseline) at ~zero by driving `sq1Fb`.
3. Capture and analyze the PID-debug stream per row visit (locked state).
4. `Group.TesBias.set(index=col, value=step)` to perturb SaOut.
5. Observe `sq1Fb` recover the error to zero; capture and analyze the transient.

Run once for the integer path (`USE_FLOAT_PID_G=false`) and once for the float
path (`true`).

Pass criteria: loop locks (error → ~0), recovers from the step with sensible
settling, no spurious flux-jump relocking, stable dropCount.

Gotchas (all confirmed):
- `GroupTb` currently hardcodes the float path (`USE_FLOAT_PID_C := true`);
  parameterize it (or flip) to cover the integer path too.
- **Frame format is resolved on `channelization`** by the Issue #82 tagged 16-byte
  header: the host stream reader dispatches `PID_FIXED` (80-byte body) vs
  `PID_FLOAT` (40-byte body), so both read cleanly — no bare-frame reader hack
  (this was the blocker on the pre-convergence `fp-pid`).
- Per-device wafer variation is on (fixed seed), so each column locks at a
  different operating point — compare each column's own trajectory.
- The SSA V–Φ is periodic and clamps at ±1 V: keep the step modest to stay on the
  locked branch, or use a large step deliberately to exercise flux-jump handling.
- `TesBias` broadcasts to all rows of a column, perturbing every enabled row.
- Cross-branch, this is a behavioral reference only (model differs); bit-exact
  belongs to Layer 1.

### Layer 3 — synthesis / timing / utilization
- Build under **Vivado 2024.1** (2025.1 has the hold-time bug); the FP IP needs
  2025.1 to *simulate* — confirm it also *synthesizes* clean under 2024.1 (an
  untested risk).
- Build `ColumnFpgaBoard325Coord10G` (`USE_FLOAT_PID_G=true`): timing closure +
  utilization (verify the LUT savings from dropping the D-term / FpAdd; assess the
  distributed-vs-block RAM opportunity for the PID state RAMs).
- Build a plain integer target to confirm the shared-RTL changes (accumulator
  split, timing rename) didn't regress non-FP builds.

## Tooling / environments
- GHDL — integer cocotb bench (no Vivado license needed).
- VCS X-2025.06 + Vivado 2025.1 sim libraries — FP cocotb bench and cosim
  (`WARM_TDM_SIM=vcs`; FP IP requires 2025.1 in simulation).
- Vivado 2024.1 — synthesis builds.
- conda `warm-tdm-r615` — cosim client / software (needs surf's Python on
  `PYTHONPATH`; pytest currently missing).
- surf ≥ `4acecf9` for cosim ADC reads; the branch is currently at `af07029b`.

## Affected modules / files
- RTL: `AdcDsp.vhd`, `AdcDspFp.vhd`, `AdcAccumulator.vhd`, `DataPath.vhd`,
  `WarmTdmPkg.vhd`, `TimingPkg.vhd`, `EventBuilder.vhd`, the frame-header package.
- Benches: `tests/warm_tdm/adc_dsp/test_AdcDsp.py`, `test_AdcDspFp.py`,
  `tests/common/regression_utils.py`.
- Cosim / host: `software/scripts/hwtest/verify_cosim_*.py`,
  `warm_tdm_api/operations/streamreader.py`, `warm_tdm/_DataFormats.py`,
  `_PidDebugger.py` / `_PidDebuggerFp.py`, `software/scripts/PidDebugFileReaderFp.py`.
- SW knobs: `Group.TesBias`, `setup_mux` / `run_mux`
  (`warm_tdm_api/operations/session/_setup.py`).

## Open risks & dependencies
- **FP IP under Vivado 2024.1 build** while simulation needs 2025.1 — untested;
  could block Layer 3.
- **Integer bit-exact baseline**: need a captured pre-split (ops-fixes-era) `AdcDsp`
  reference and a model-free stimulus definition to diff against.
- **Relock risk**: a large `TesBias` step may relock the servo on a different flux
  branch (periodic V–Φ) — bound the step for the settling measurement.
- **pytest env gap** blocks the software suite in Layer 0.

## Next steps
1. Elaborate `GroupTb` with `USE_FLOAT_PID_G` both true and false (Vivado 2025.1) —
   the next gate; catches parent-crossbar/port issues beyond the import check.
2. Run the integer `AdcDsp` GHDL bench; capture a pre-split reference and assert
   bit-exact equivalence.
3. Wire the cosim step-response test (extend `verify_cosim_readout.py`: enable PID +
   debug, set non-zero coefficients, apply a `TesBias` step, capture, analyze via
   the tagged-header reader).
4. Synthesis build under 2024.1 for timing closure + utilization.

## References
- Issue #70 — Floating-point PID firmware (AdcDspFp + accumulator split)
- Issue #82 — Self-describing data frames + channel-layout cleanup
- Issue #90 — RTL cocotb/GHDL regression framework (AdcDsp + AdcDspFp)
- PR #106 — channelization integration (base `pre-release`)
- [`docs/plans/fp-dsp-pid/`](../fp-dsp-pid/), [`docs/plans/pipelined-dsp-accumulator/`](../pipelined-dsp-accumulator/), [`docs/plans/channelization/`](../channelization/)
- Branch Merge Roadmap wiki
