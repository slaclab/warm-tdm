# PID cosim verification — Progress

## 2026-09-15 (later) — GroupTb PID-path parameterized; both paths elaborate (Layer 2 gate)

### Done
- **`GroupTb` parameterized for both PID datapaths.** Promoted the hardcoded
  `USE_FLOAT_PID_C := true` to a `USE_FLOAT_PID_G` generic on the `GroupTb`
  entity (default `true`, preserving prior behavior); `ruckus.tcl` sets it on the
  `sim_1` fileset from the `USE_FLOAT_PID` env var, so `make vcs` builds the float
  path and `USE_FLOAT_PID=0 make vcs` builds the integer path — no VHDL edit
  between runs. Mirrors the target `ruckus.tcl` `set_property generic` convention.
  Files: `firmware/simulations/GroupTb/tb/GroupTb.vhd`,
  `firmware/simulations/GroupTb/ruckus.tcl` (uncommitted, pending review).
- **Elaboration gate: PASS (both paths), Vivado 2025.1 + VCS X-2025.06.**
  - Float: `make vcs` export OK; VCS elab command carries
    `-gv USE_FLOAT_PID_G="true"`. Identical to the prior hardcoded default (already
    known-good in cosim), so covered by equivalence.
  - Integer: `USE_FLOAT_PID=0 make vcs` export OK (`-gv USE_FLOAT_PID_G="false"`);
    full `sim_vcs_mx.sh` compile/elaborate/link of `GroupTb` succeeded ("All of 30
    modules done", "Verdi KDB elaboration done", "Ready to simulate", exit 0).
    This exercises the `GEN_FIXED_PID` `DataPath` branch through the full `GroupTb`
    for the first time — the parent-crossbar/port check the plan wanted. The
    `FLT_FMA` static-elaboration assertion *warnings* are benign (FP IP compiled in
    but unused on the integer datapath).

### Also done — Layer 1 integer bench restored to green (commit 6728d92)
Running the integer `AdcDsp` GHDL bench surfaced three surf-update/rename drifts
that had rotted the Issue #90 framework; all fixed:
- `tests/common/regression_utils.py` (warm-tdm shim) lacked `sample_after_tpd`,
  which updated surf `tests/axi/utils.py` now imports via `tests.common.
  regression_utils` — added the timing-sampling trio mirroring surf.
- Both DSP cocotb wrappers still assigned `accumIn.rowIndex`; the logical-row
  rename made it `logicalRow`. Fixed (external `ACCUM_ROW_INDEX` port unchanged).
- surf RAM refactor: `TrueDualPortRam`/`DualPortRam`/`SimpleDualPortRam` now
  pull in `TrueDualPortRamInferred`/`SimpleDualPortRamInferred`; added both to
  the benches' surf allowlists. `make rtl_import` re-run also clears stale
  `base/ram/inferred -> base/ram/rtl` symlink moves in `build/SRC_VHDL`.
Result: `pytest tests/warm_tdm/adc_dsp/test_AdcDsp.py` → 1 passed (5 PID
property checks under GHDL). FP bench collects cleanly (run gated to VCS).

### Next (unchanged priority)
- Layer 1 **bit-exact golden diff** (still owed): drive identical scripted
  stimulus and compare against a captured pre-split (ops-fixes-era) reference.
  Design fork to settle first (see below).
- Layer 2: wire and run the closed-loop cosim step-response, now runnable for
  both PID paths via the new generic (`warmTdmServer --sim`, TesBias step).

### Decision + feasibility (2026-09-15) — whole-path captured golden
Chosen approach (user): **whole-path, captured golden** — resurrect the
pre-split `AdcDsp` once, drive scripted raw-ADC stimulus, capture output vectors
to a checked-in golden; CI drives the new `AdcAccumulator`+`AdcDsp` on identical
stimulus and asserts bit-exact vs golden. Truly model-free (plan's intent).

**Feasibility PROVEN.** Reference commit `5645f7e` ("Clean up delayed timing
paths…", the immediate pre-split, post-PID-clear-fixes state). Its `AdcDsp` +
contemporaneous `TimingPkg`/`WarmTdmPkg`/`FixedPkg` (no `FrameHeaderPkg` yet)
elaborate clean under GHDL 1.0 + *current* surf via `ghdl -i`/`-m`. Only
snapshot-local change needed: add `use ieee.std_logic_unsigned.all;` (old file
left `numeric_std` commented; the original build resolved the `slv`
`pidStateRamAddr + 1` counter increment via the synopsys package — unsigned
semantics, faithful). Spike lived in gitignored `build/presplit_spike/`.

**Design for the two benches (to build):**
- Snapshot the 4 old files into a committed dir (e.g.
  `tests/warm_tdm/adc_dsp/golden_refs/presplit_rtl/`), compiled into a `warm_tdm`
  GHDL lib (so old `AdcDsp`'s `library warm_tdm` refs resolve) — separate pytest
  run / sim_build from the current-RTL bench, so no lib clash.
- Shared deterministic stimulus (raw ADC AXI stream + `LocalTimingType` +
  `sq1FbDac` + AXI-Lite coef/baseline config). Both old `AdcDsp` and new
  `AdcAccumulator` take the SAME raw-ADC+timing interface, so the driver is shared.
- Observable = the `mAxil` SQ1-FB-DAC RAM write master transactions (addr,data) —
  the true PID output, present identically on both old and new `AdcDsp`. Capture
  bench writes golden JSON; compare bench diffs bit-exact.
- Intricate part = replicating the old sample/row-strobe accumulation protocol
  exactly; study old `AdcDsp` adcAxisMaster+timing consumption before writing the
  driver.

### (superseded) Open design question — bit-exact reference capture
The property bench proves PID *behavior*; the plan's Tier-1 claim is *bit-exact*
equivalence of the accumulation-numerics move (old `sfixed` accum inside AdcDsp
-> new `signed(31:0)` accum in AdcAccumulator + PID in AdcDsp). Interfaces differ
across the split (old AdcDsp consumed the raw ADC stream; new AdcDsp consumes
`accumIn : AdcAccumResultType`), so the comparison strategy is not yet fixed:
whole-path (old AdcDsp vs new AdcAccumulator+AdcDsp on identical raw-ADC
stimulus) vs decomposed (AdcAccumulator accum vs old accum; PID stage golden).
Also undecided: which pre-split commit is the reference, and whether the golden
is captured to data files or the old RTL runs live in the bench.

## 2026-09-15 — plan established; Layer 0 largely done

### Done
- **Register cross-check (Layer 0): PASS.** VHDL crossbar/local-register offsets
  vs PyRogue `RemoteVariable` offsets verified by hand for `AdcDsp` (7-master
  crossbar: local 0x00–0x60 + RAMs 0x1000/0x2000/0x3000/0x6000), `AdcDspFp`
  (5-master: PI-only coefs + RAMs 0x1000/0x2000/0x3000/0x4000), and
  `AdcAccumulator` (baseline RAM at 0x000). The accumulator-split offset shifts
  are consistent on both sides, and the baseline RAM is confirmed moved out of
  `AdcDsp` into `AdcAccumulator`. The `sfs-check-registers` parser could not do
  this (blind to the crossbar + `AxiDualPortRam` + local-endpoint pattern; it
  reported 0 VHDL registers and false "python-only" findings).
- **Import smoke (Layer 0): PASS.** `warm_tdm`, `warm_tdm_api`, `.operations`,
  `.tuning`, `.session` import in `warm-tdm-r615`; `AdcDsp`/`AdcDspFp`/
  `AdcAccumulator` device classes load (surf Python on `PYTHONPATH`).
- **Synthesis fix (unblocks Layer 3 elaboration):** added the missing
  `use warm_tdm.WarmTdmPkg.all` to `WarmTdmCommon2.vhd` (commit `f46837a`). Its
  `config : out WarmTdmConfigType` port referenced a `WarmTdmPkg` type with only
  `library warm_tdm;` in scope, failing `ColumnFpgaBoard` synthesis at
  `WarmTdmCommon2.vhd:75`. Pre-existing on `channelization` (present at `bc0ebdb`),
  surfaced on the first `ColumnFpgaBoard` synthesis. Audited: all other
  `WarmTdmConfigType` users already had the use clause.

### Confirmed for the plan
- The sim closes the servo loop physically with a wafer load (SaOut couples to
  TesBias and sq1Fb through the SQUID transfer functions), so the closed-loop
  step-response test (Layer 2) is realizable.
- The 40-vs-80-byte PID-debug frame mismatch that blocked the pre-convergence
  `fp-pid` is resolved on `channelization` by the Issue #82 tagged-header reader
  dispatch.

### Not yet done
- Layer 0: `software/tests/` pytest (pytest missing from `warm-tdm-r615`).
- Layer 1: integer `AdcDsp` GHDL bit-exact regression vs a captured pre-split
  reference; `AdcDspFp` bench under VCS.
- Layer 2: wire and run the closed-loop cosim step-response (integer + float).
- Layer 3: Vivado 2024.1 synthesis of `ColumnFpgaBoard325Coord10G` (timing +
  utilization); confirm the FP IP synthesizes under 2024.1.

### Next
Elaborate `GroupTb` with `USE_FLOAT_PID_G` both true and false (Vivado 2025.1) —
the next gate. Re-run `ColumnFpgaBoard` synthesis to confirm `f46837a` clears the
reported error and to surface any next first-synthesis issue.
