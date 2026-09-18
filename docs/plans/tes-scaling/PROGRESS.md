# TES scaling → multi-flux-jump swing (cosim verification)

## Goal

Make a TES-bias DAC ramp swing the SQ1 servo across **multiple flux jumps** in
the GroupTb PyRogue↔VCS cosim, so the flux-jump path is exercised end-to-end
through the real RTL against the wafer model. Owning issue: #70 (closed-loop
PID/flux-jump acceptance).

## Key finding (2026-09-17) — supersedes the "weak coupling" note

Prior notes (`pid-cosim-verification/PROGRESS.md`, `cosim-tuning-settings.md`,
commit `18c797b`) claimed the synthetic TES→SQ1 coupling is **weak**
(`~0.024 µA_fb/µA_TES`, needing `TES_CURRENT_SCALE≈40000`), and that cranking the
scale broke lock via the TES-bias baseline offset → a clean flux-jump demo was
deferred pending "model surgery."

An open-loop GHDL probe against the **current, recalibrated** model
(`DetectorModuleSim`, SQ1 tune point sq1Fb=7 µA, row ON) measured instead:

| TES current | SQ1 phase | note |
|---|---|---|
| 0 µA  | −0.70 Φ0 | |
| 10 µA | +0.30 Φ0 | **1 Φ0 per 10 µA** |
| 20 µA | +1.30 Φ0 | |
| 30 µA | +2.30 Φ0 | SSA out swings cleanly 0.03–4.6 mV per period |

So on today's model coupling is **~1:1 in flux (1 Φ0 / 10 µA of TES current) at
`TES_CURRENT_SCALE=1`** — ~40000× stronger than the old note. `sq1PhaseCycles =
tesCurrent / currentPerPhi0Amp` with `currentPerPhi0Amp=10 µA`,
`tesCouplingScale=1.0` ([WaferSimPkg.vhd:817](../../../firmware/common/warm_tdm/sim/WaferSimPkg.vhd#L817)).
The old measurement predates the SSA Rn→120 Ω / sense-path recalibration
(`c442382`, `601dd2e`) and sinusoid blend.

Implication: a modest TES ramp (~150–250 µA, well within the ±1250 µA DAC range)
should already walk feedback to the ±7862 rail through several flux jumps with
`TES_CURRENT_SCALE=1` and **no** baseline-offset surgery.

## Decision

User: **verify in cosim first** before changing anything. The open-loop probe
contradicts the recorded closed-loop finding in `18c797b`; a real closed-loop
VCS run settles it.

## Plan

1. Clean VCS build with **known generics**: `TES_CURRENT_SCALE=1`, integer PID
   (`USE_FLOAT_PID=0`, matches the measured tune point), `VARIATION_SEED=0`,
   `LOAD_G=WAFER` (32 rows). — the existing Sep-16 `simv` has unknown generics.
2. Start `warmTdmServer --sim`; seed the integer tune point (sq1Fb=7 µA,
   P=−0.0006, I=−2e-5, FluxQuantum=10 µA) per `cosim-tuning-settings.md`.
3. Ramp `Group.TesBias` from the operating point in steps; capture PID-debug
   and confirm `FluxJumps` increments by several while lock is retained.
4. If confirmed: correct the stale docs, and decide whether to raise the
   `flux_step_uA`/scale defaults in `verify_cosim_pid.py::check_flux_jump`.

## Status

- [x] Open-loop coupling measured (GHDL probe, throwaway, removed)
- [x] VCS rebuild — `simv` compiled with confirmed generics
  `USE_FLOAT_PID_G=false VARIATION_SEED_G=0 TES_CURRENT_SCALE_G=1`
  (verified in `.../behav/sim_vcs_mx.sh` line 493 `-gv` args).
- [x] simv launched — col-board bridges 10000/20000 open.
- [ ] **BLOCKED: server won't start** (see below). Closed-loop TES ramp not yet run.
- [ ] TES ramp → multiple FluxJumps observed, lock retained
- [ ] Docs corrected / defaults updated

## Server construction crash — FIXED (2026-09-17)

`warmTdmServer.py` was crashing on startup — **both `--sim` and `--emulate`** —
with `AttributeError: 'NoneType' object has no attribute 'root'` at
`_HardwareGroup.py:134`/`:219`:

```python
self.ColumnBoard[index].WarmTdmCore.ComCore.EthCore.enable.set(index == 0)
```

Introduced by commit `316b112` ("Gate Ethernet to coordinator targets"). The
`.set()` ran INSIDE `HardwareGroup.__init__`, before the tree is attached to a
root; `pyrogue`'s `EnableVariable.set` ignores `write=False` and always calls
`self.parent.root.updateGroup()`, so it can't be set pre-connection.

**Fix:** mirror the RTL (EthCore generated only for ring address 0) by NOT
instantiating the EthCore subtree at all on non-coordinators. Added
`ethPresent` (default True) threaded HardwareGroup → board classes
(`_ColumnFpgaBoard`, `_RowFpgaBoard`, `_ColumnAwaXeFpgaBoard`) → `WarmTdmCore` →
`ComCore`, which now does `if ethPresent: self.add(EthCore(...))`. HardwareGroup
passes `ethPresent=(index==0)` / `(boardIndex==0)` and the dead `.enable.set()`
lines are gone.

**Verified:** server constructs + serves ZMQ on 9099 under both `--emulate` and
`--sim`; a real SRP read through the simv bridge returns `SampleCount=128`; the
col board has an `EthCore` node and the row board does not (matches RTL). 72/74
software tests pass (the 2 failures are pre-existing `No module named pytest`
import errors, unrelated).

## Row-board SRP bridge in sim — FIXED (2026-09-17)

`316b112` gated the RTL Ethernet block to ring addr 0, which in sim also removed
the row board's Rogue TCP bridges (11000/21000) — but in sim EthCore is NOT a
GigEth PHY, it's a lightweight `RogueTcpStreamWrap` SRP/data bridge
(`EthCore.vhd` SIM_GEN). Removing it left the row board unreachable (the sim
server's `TcpClient(11000)` hung), and simulating the PGP GTX ring instead would
be far slower (deliberately avoided; the ring is stubbed in sim).

**Fix (option A, user-chosen):** in `PgpEthCore.vhd`, generate EthCore when
`GEN_ETH_C = RING_ADDR_0_G or SIMULATION_G` (new constant; `GEN_ETH`/`NO_ETH`
both use it). This restores the pre-`316b112` sim topology — every simulated
board gets its own Rogue TCP bridge, no GTX ring — while real-hardware
non-coordinators still omit the Ethernet PHY. Python `_HardwareGroup.py` mirrors
it: `ethPresent=(index==0 or simulation)`.

**Verified:** rebuilt simv opens all four bridges (10000/11000/20000/21000);
row-board register read/write round-trips (`ScratchPad` 0x0 → write 0xDEADBEEF →
reads back 0xDEADBEEF); `verify_cosim_pid.py --behaviors steady,flux` runs the
full 8×20 µA TES ramp to completion.

## Result: infra fixed, but servo does not lock (separate issue)

With both fixes in, the flux exercise runs end-to-end but the **integer servo
does not lock** at the profile operating point: steady-state
`mean_residual ≈ 38180` (threshold 800), per-row `feedback_mean ≈ 8407` (railed
near the +8191 DAC clip), `peak_abs_error ≈ 40940`, `flux_jump_delta = 0` at
every ramp step. So the TES ramp does not (yet) produce controlled flux jumps —
not because coupling is too weak (the open-loop probe shows 1 Φ0/10 µA), but
because the loop is not holding lock to begin with.

This is the known finicky closed-loop-lock problem
(`docs/plans/pid-cosim-verification/`), NOT an infrastructure bug. The profile
(`cosim_pid.example.json`: raw P=−6e-4, I=−2e-5, sq1Fb=7 µA, FluxQuantum=10 µA)
was tuned on an earlier model revision; the plant has since changed (SSA
recalibration, sinusoid blend). Next step is to re-establish lock — verify the
seeded operating point sits mid-slope, re-tune P/I against the current plant
slope (see cosim-tuning-settings.md), confirm sign — THEN ramp TesBias and watch
`numFluxJumps` step. The 1:1 coupling means only ~a few tens of µA per Φ0 once
locked.

## Files changed (server-crash + sim-bridge fixes)

- `firmware/common/warm_tdm/rtl/PgpEthCore.vhd` — `GEN_ETH_C` sim gate.
- `firmware/python/warm_tdm/_ComCore.py` — `ethPresent` gates EthCore subtree.
- `firmware/python/warm_tdm/_WarmTdmCore.py`, `_ColumnFpgaBoard.py`,
  `_RowFpgaBoard.py`, `_ColumnAwaXeFpgaBoard.py` — thread `ethPresent`.
- `firmware/python/warm_tdm/_HardwareGroup.py` — pass
  `ethPresent=(index==0 or simulation)`; removed the crashing `.enable.set()`.
- `software/scripts/hwtest/README_cosim.md` — document the PID/flux suite.

NOTE: these are uncommitted. The RTL change needs Vivado 2024.1 synth/timing +
hardware acceptance for the coordinator-ethernet workstream before it's real.

## Once unblocked

Re-run the turnkey suite (simv from this build is fine; correct generics):

```bash
conda activate warm-tdm-r615
python software/scripts/hwtest/run_cosim_pid_suite.py \
  --paths integer --no-build --mode measure \
  --behaviors steady,flux --rows 8 --output /tmp/wtj-tes-scaling --keep-up
```

Expect `flux_jump_delta` to increment by several across the default 6×20 µA
(=120 µA) TES ramp if the ~1:1 coupling holds closed-loop. If confirmed, correct
the stale `pid-cosim-verification` docs + commit `18c797b` message, and decide
whether to bump `check_flux_jump`'s ramp defaults.

## How to run (turnkey)

The user's `software/scripts/hwtest/run_cosim_pid_suite.py` orchestrates
build→simv→server→readiness→harness→teardown. To reuse an already-compiled
`simv` (correct generics), pass `--no-build`. The flux exercise ramps
`--flux-steps × --flux-step-uA` (defaults 6 × 20 µA = 120 µA TES →
~12 Φ0 at the measured 1:1 coupling). `--mode measure` reports without
hard-failing; `check_flux_jump` records per-step `flux_jump_delta` from the
PID-debug `numFluxJumps` series.

```bash
conda activate warm-tdm-r615
python software/scripts/hwtest/run_cosim_pid_suite.py \
  --paths integer --no-build --mode measure \
  --behaviors steady,flux --rows 8 --col 0 --output /tmp/wtj-tes-scaling --keep-up
```

## Toolchain / commands

- SIM Vivado **2025.1** + VCS X-2025.06 (2024.1 fails FP IP).
- Conda env `warm-tdm-r615`.
- Read-only-project error → `rm -rf firmware/build/GroupTb` then `make vcs`.
- See `firmware/simulations/GroupTb/README_cosim.md`,
  `software/scripts/hwtest/README_cosim.md`.
