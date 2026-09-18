# TES scaling → multi-flux-jump swing (cosim verification)

## Goal

Make a TES-bias DAC ramp swing the SQ1 servo across **multiple flux jumps** in
the GroupTb PyRogue↔VCS cosim, so the flux-jump path is exercised end-to-end
through the real RTL against the wafer model. Owning issue: #70 (closed-loop
PID/flux-jump acceptance).

## Post-merge lock revalidation (2026-09-18)

After merging the big integer-PID changes (`558cad9` multi-flux wrapping +
19-bit count + 23 µA SQ1 period; `33599a9` PID refactor), the integer servo
initially did NOT lock with the carried-over profile (residual ~35000, feedback
railed) — because the profile's **P sign was negative**, wrong for the current
plant. Chasing it with `cosim_pid_lock.py`:

- **P must be POSITIVE.** Normalized P=+0.05 (raw +0.0025 at SampleCount=20)
  locks: row 0-3 settle to ~±260-360 counts, `FluxJumps=0`, monotonic descent.
  Negative P railed the feedback. Matches the doc note "descending slope stable
  P sign is POSITIVE".
- Higher rows (4-7) converge slower — need >10 s of settling; add I=+0.0004
  (raw +2e-5) to close the deadband.
- Updated `cosim_pid.example.json` + `verify_cosim_pid.py` DEFAULTS integer
  block to `p_raw=+0.0025, i_raw=+2e-5`.
- Two script fixes for the new RTL: `cosim_pid_lock.py` now (a) disables PID
  before setting `FluxQuantum` (multi-flux RTL rejects the change otherwise:
  "Disable PID and wait for ControlBusy"), and (b) sets `RowReadoutOrder` to all
  monitored rows (default [0] left rows 1..N reading stale 0).

### BUT: lock only holds WITHOUT `SetCosimTunePoints` — tune points are stale

Sharp contradiction found and reproduced:
- `cosim_pid_lock.py` P=+0.05, I=0 on the fixture left by an earlier harness run
  (Sq1Bias≈76.9 µA) → **locks**, rows 0-3 to ±260, FluxJumps=0.
- The turnkey harness (`--seed-tune-points`) and a manual repro that calls
  `SetCosimTunePoints()` first → **does NOT lock**, AccumError ≈ 33400 at the
  same P. windup=0 confirms it's not integrator windup (I=0 too).

Root cause: `SetCosimTunePoints` → `SetSimSq1TunePoint` seeds
`Sq1Fb=16.951, Sq1Bias=100, SaFb=64.8` — all **scaled/carried from the old 10 µA
fixture** (Sq1Fb = 7.37·23/10; the others unchanged). On the recalibrated 23 µA
sinusoid-blend plant these do NOT land on a lockable mid-slope operating point.
This is exactly the "gains/tune points retained from the old fixture, require
closed-loop revalidation on the rebuilt model" caveat the merge flagged.

**So the positive-P gain is correct, but the SEED operating point from
`SetCosimTunePoints` is wrong for the new plant.** Fixing it needs a real SA +
SQ1 tune sweep on the 23 µA model to re-fit `SetSimSaTunePoint` /
`SetSimSq1TunePoint` (SaBias, SaFb, Sq1Bias, Sq1Fb) — a multi-cycle slow-sim
effort. NOT yet done. (A PID-off `AccumError` vs `Sq1Fb` sweep to find the
zero-crossing failed — AccumError reads 0 with PID disabled, so the operating
point must be found with the debug/accumulator path active or via a proper
sq1Tune process run.)

### Status of the TES sweep goal

Still blocked on a clean lock at the seeded operating point. Once
`SetCosimTunePoints` seeds a lockable point on the 23 µA model, the merged
multi-flux-wrap RTL (multiple quanta/visit, 19-bit count) should let the TES
ramp walk `numFluxJumps` up cleanly — that capability is new and directly serves
this goal.

## SQ1 retune on the 23 µA period (2026-09-18) — deeper blocker found

Ran the actual tune processes (SetCosimTunePoints → SaOffset → SaTune →
Sq1Tune) against a fresh simv of the merged RTL.

- **SA side is fine.** SaOffset nulls (SaOutAdc≈0.002), SaTune fits
  SaFb≈9.13 µA (mid-slope, as expected).
- **Full 2-row SQ1 sweep (24×3×2=144 pts) TIMED OUT at 1500 s** in VCS — too
  many points. A reduced row-0 / fixed-bias / 15-pt sweep finishes in ~114 s.
- **The SQ1 tune cannot find a lock point because the measured SQ1 V–Φ is not a
  proper periodic curve on this fixture.** Dumped `Sq1TuneOutput[0][0]` curve at
  bias 76.87 µA (note: requested 100, but the force-current path applied 76.87):

  ```
   Sq1Fb:  -17..-2.4  -> SaOut flat +9.11   (no modulation)
   Sq1Fb:  0          -> +12.24
   Sq1Fb:  +7.3       -> +14.84
   Sq1Fb:  +9.7       -> +23.69
   Sq1Fb:  +12..+17   -> +34.9 .. +41.0     (monotonic ramp, no turnover)
  ```

  This is a one-sided ramp, not a sinusoidal V–Φ — there is no steep mid-slope
  null to lock to. The fit is unstable across runs (xOut came back 14.571, then
  9.719, then 9.714). Closed-loop tests at the fitted points do NOT lock at
  either P sign (AccumError ~24000-71000, feedback rails).

- **Likely root cause = row-select / SQ1-bias operating point, not PID gains.**
  `SetCosimTunePoints` drives FAS-on = 163 µA, but the row-FAS period is 300 µA,
  so 163 µA sits at ~0.54 Φ0 — the max-resistance extremum with weak (~15%)
  gating (already flagged in `cosim-tuning-settings.md` "Row-FAS set point does
  NOT agree with the model"). A weakly/incorrectly selected row won't route SQ1
  modulation into the readout, which matches the flat/ramp curve. Sq1Bias=76.87
  (vs the intended 100) may also leave the SQ1 below the modulation regime.

### Next steps (plant setup, NOT gain tuning)

1. Fix the FAS on/off currents to the 300 µA-period extrema (0 or 300 µA for
   min-R, 150 µA for max-R) — decide which extreme is "on" (run `fas_tune` or
   confirm switch topology), so the selected row actually gates its SQ1.
2. Re-check Sq1Bias: sweep it (the 40-140 µA range) to find where the SQ1
   actually modulates, before fixing the Fb sweep.
3. Only then re-fit Sq1Fb and re-test closed-loop lock + P sign.
4. `SetCosimTunePoints` / `SetSimSq1TunePoint` in
   `software/python/warm_tdm_api/_Group.py` need updating with the results.

This is a wafer-model/tune-fixture problem at the new period, beyond a gain
retune. The two infra fixes (server crash, sim eth bridge) and the positive-P
finding stand; the TES flux-jump sweep remains blocked on a real SQ1 lock.

## FAS row-select characterized on the model (2026-09-18) — GHDL probes

Rather than more slow cosim cycles, probed the wafer model directly with fast
throwaway GHDL testbenches on `DetectorModuleSim` (WaferModelTb path, seconds
per run; TBs since removed). Findings, all at Sq1Bias=100 µA:

**Row-FAS "ON" point is 150 µA, not 0/300.** SQ1 modulation depth (ssaV
peak-to-peak over a full Sq1Fb sweep) vs FAS-select current:

| FAS current | SQ1 modulation p-p |
|---|---|
| 0 µA   | 0.003 mV (row OFF — SQ1 invisible) |
| 50 µA  | 0.33 mV |
| **150 µA** | **4.61 mV (row fully ON, max)** |
| 250 µA | 0.33 mV |
| 300 µA | 0.003 mV (row OFF) |

So `SetCosimTunePoints`'s **FAS-on = 163 µA is actually correct** (≈150, the
half-period of the 300 µA row-FAS). The `cosim-tuning-settings.md` claim that
163 µA is a "bad" point and that 0/300 are the clean extrema is **BACKWARDS**:
0/300 µA is where the row is OFF (SQ1 shunted/invisible); 150 µA is ON.

**Clean SQ1 V–Φ at FAS=150, Sq1Bias=100** (23 µA period, ssaV):
peaks ≈4.99 mV at Sq1Fb≈+0.5 and +23; minima ≈0.37 mV at ≈−11.5 and +11;
steep mid-slopes (lock candidates) at Sq1Fb ≈ **+5 µA** (falling) and ≈+18
(rising). So the real mid-slope lock point is Sq1Fb≈5, NOT the scaled 16.951 in
`SetSimSq1TunePoint`.

**Why earlier tunes saw flat/ramp curves:** they ran at LOW Sq1Bias — FasTune
default Sq1Bias=40 µA and the SQ1 sweep landed near 40-77 µA, where modulation
is weak. At Sq1Bias=100 the model modulates cleanly (4.6 mV).

## Still NOT locking in cosim — SA-offset/per-row-setpoint interaction

Closed-loop test with the model-derived point (SetCosimTunePoints, then override
Sq1Fb=5, FAS=163, Sq1Bias=100) STILL does not lock: AccumError ≈35000 constant
at both P signs, FluxJumps=0. The static SA null reads fine (SaOutAdc≈0.002 V)
but the muxed-run error is large and constant.

Suspected cause: `SetSimSq1TunePoint` writes a large per-row **SaFb=64.8 µA**
into the readout table, and the single global SA-offset DAC can only null one
operating point — so during the muxed readout the SA sees a large fixed SQ1
voltage that shows as constant AccumError. The model has signal (GHDL proves
it); the cosim readout/servo setpoint path is where it's lost. Next: check the
per-row SaFb table vs SA-offset null, and whether AccumError is measured against
the right baseline for the seeded point (the GHDL V–Φ says a real null exists at
Sq1Fb≈5). This is the current edge.

### Concrete recommended tune points (from the model, for _Group.py)
- FAS-on: 150 µA (163 is fine); FAS-off: 0 µA.
- Sq1Bias: 100 µA requested → clips to ~77 µA (SQ1-bias fast-DAC max); 77 is the
  actual operating bias and locks fine.
- Sq1Fb lock: ≈5 µA (falling mid-slope), NOT 16.951.
- SaBias: 55 µA; SaFb: the SA-tune fit (~9 µA), NOT 64.8.

## Lock ACHIEVED (2026-09-18), but harness path still flaky

**`_Group.py` `SetSimSq1TunePoint` updated:** Sq1Fb 16.951→5.0, SaFb 64.8→9.0
(Sq1Bias stays 100, clips to 77). Comment records the closed-loop rationale.

**Reproducible manual lock:** the recipe that reliably converges (to ±20-280
AccumError, P=+0.05, I=0, FluxJumps=0):
1. `SetCosimTunePoints()` (RowMap + FAS=163 + SA/SQ1 seed)
2. `sa_offset()` (reference null)
3. write the coherent operating point to the row tables:
   Sq1Bias=100(→77), Sq1Fb=5, SaFb=9 for each readout row
4. **`sa_offset()` AGAIN** — after the tables are applied
5. setup_mux(sample_num=20) + set_pid(P=+0.05,I=0) + run_mux

**Decisive A/B (run_ab2.py):** with the operating-point tables applied,
- readout with the offset taken BEFORE the tables → **rails ~80000 (no lock)**
- readout with an extra `sa_offset()` AFTER the tables → **LOCKS (±200)**

So the cosim helpers' extra pre-readout `sa_offset()` is **necessary, not
harmful** — but it MUST run AFTER the final per-row SaFb/Sq1 values are in the
tables, because those per-row currents shift the SA operating point and the
earlier offset no longer nulls it. (This differs from the hardware workflow,
where the SQ1-tune servo already nulls at each fitted point so no extra offset
is needed. In cosim we apply static tables, so we must re-null once after.)

**Still flaky:** `verify_cosim_pid.py --seed-tune-points` intermittently does
NOT lock (resid ~70000, windup 0, error a fixed constant P can't reduce) even
though its order is SetCosimTunePoints → seed Sq1Fb → sa_offset → run. The
manual recipe locks; the harness sometimes doesn't, from the same operating
point. Difference not fully closed — suspected residual SA-offset/state
dependence (the SA-offset DAC and per-row feedback RAM carry between runs; a
warm vs fresh fixture changes the result). apply_lock re-seeds only Sq1Fb, not
Sq1Bias/SaFb, so it leans entirely on SetCosimTunePoints having written a
coherent point THEN its own sa_offset. Needs: make apply_lock write the full
coherent per-row point (Sq1Bias/Sq1Fb/SaFb) explicitly, then sa_offset, and/or
clear PID/feedback RAM (ClearPids) at entry for determinism.

### Profile/DEFAULTS state
- `cosim_pid.example.json` + `verify_cosim_pid.py` DEFAULTS: integer
  sq1fb_uA=5.0, p_raw=+0.0025, **i_raw=0.0** (I=+2e-5 wound the 19-bit count to
  the 131071 rail — P-only is the verified lock).

## ROOT CAUSE of flakiness: Sq1Bias was 100, should be 50 (2026-09-18)

User caught it: `SetSimSq1TunePoint` seeded **Sq1Bias=100 µA**, but the measured
cosim fit is **50 µA** (`cosim-tuning-settings.md:58`: "FittedSq1Bias = 50 µA
... `SetSimSq1TunePoint` currently seeds ... Sq1Bias=100 ... from the old ideal
model; update ... once the SQ1 lock is confirmed" — that update never happened).
The 100 traces to `caf32d5` where the function was first added as
`TmpSetSq1TunePoint`; every later commit carried it forward untouched. Worse,
**100 µA exceeds the SQ1-bias fast-DAC range**, so it clipped to an arbitrary
~77 µA — the operating bias was never a controlled tune point, which is exactly
why the lock was erratic and state-dependent.

Fixes applied:
- `_Group.py SetSimSq1TunePoint`: **Sq1Bias 100→50**, Sq1Fb 16.951→**2.0**
  (re-derived: at Sq1Bias=50 the model V-Phi is sharper; steepest mid-slope is
  ~+2 µA on the falling flank, per a fresh GHDL DetectorModuleSim probe), SaFb
  64.8→**9.0**. Unlike Sq1Fb (scales with the 10→23 µA period), Sq1 *bias* is an
  operating current and does not scale — 50 carries straight over.
- `verify_cosim_pid.py apply_lock` HARDENED: now writes the COMPLETE coherent
  per-row point (Sq1Bias=50, Sq1Fb, SaFb=9) into the readout tables BEFORE the
  SA null, then `sa_offset()` — instead of seeding only Sq1Fb. New profile keys
  `sq1bias_uA`/`safb_uA` (DEFAULTS 50/9). The per-row SaFb sets the SA operating
  point, so the offset must be taken after all three are applied (the A/B
  finding above).

Result (harness, measure mode, 4 rows, P=+0.05, I=0):
- Sq1Bias=100 (old): resid **~89000, no lock**.
- Sq1Bias=50 + coherent seed: resid **~9700** at short settle, **~2274 and still
  descending** at longer settle (25 s) — all rows converging together, feedback
  ~7887 (not railed), windup 0. **The servo now LOCKS/converges.**

Remaining gap to the 800 threshold is P-only convergence speed / deadband;
close it with a small I (now safer — 19-bit count) or larger P, then the TES
flux-jump sweep is unblocked. This is the current edge.

## LOCK VERIFIED + flux-jump characterized (2026-09-18)

**Gain sign: NEGATIVE P is correct at the fixed Sq1Bias=50 point** (opposite the
earlier clipped-77 result — operating point, not just gain, set the sign). Gain
sweep (re-seed each trial; do NOT `ClearPids` — it wipes the seeded sq1Fb and
drops the servo to the V-Phi extremum, ungovernable):
- P=-0.05 (raw -0.0025), I=0 → monotonic converge to **370** (best).
- P=+0.05, I=0 → converges slower to ~1300.
- P=+0.05, I=+2e-4 → ~880.

**`verify_cosim_pid.py --mode verify` steady PASSES:** residual **577 < 800**,
FluxJumps=0, at P=-0.0025 / Sq1Bias=50 / Sq1Fb=2 / SaFb=9, long settle. The
integer servo genuinely locks on the 23 µA plant. Profile + DEFAULTS set to
p_raw=-0.0025.

**TES flux-jump sweep: servo stays locked, but does NOT wrap (FluxJumps=0).**
Stepping TesBias from the locked point (probed to +1200 µA, DAC max ~±1250):
- AccumError stays BOUNDED and OSCILLATES with TesBias (e.g. -13360, -13180,
  -1600, +2540, -8080, -13540 at +200..+1200 µA) — i.e. the readout traverses
  the SQ1 V-Phi periodically, dipping to ~0 near nulls.
- FluxJumps stays 0 throughout; the servo never railed sq1Fb.

Interpretation: with P-only at this modest gain the loop shows the periodic
*error* as TES flux moves it, but does NOT drive the sq1Fb feedback across the
±7862 wrap threshold — so no flux jumps. The AccumError swing (±14000) exceeds
7862 in error units, but the wrap triggers on the FEEDBACK (sq1Fb) crossing, not
the accumulated error. To actually produce flux jumps the servo must TRACK the
TES-induced flux into the DAC rail: needs higher loop gain (so feedback follows
and wraps) and/or a finer/slower TES ramp so the servo stays locked while its
feedback walks to ±7862. (Note `Sq1Fb_DBG` is 0-dim per-visit — index it as a
scalar, not [:n], to read the feedback value next time.)

### GOAL ACHIEVED (2026-09-18): TES ramp drives multiple flux jumps

The "no flux jumps" conclusion above was an **artifact of the flux-jump CHECK**,
not the servo. `verify_cosim_pid`'s `check_flux_jump` used 20 µA steps and
measured `flux_jump_delta` as the net count change WITHIN one short capture
window (and reported a heuristic `locked=False`); it missed the jumps. Reading
the raw `FluxJumps` register directly during a fine ramp shows them plainly.

Fine ramp (single row, P=-0.0025, I=0, FluxQuantum=23 µA, TesBias +4 µA/step):

```
 TesBias   Sq1FbFull   Sq1Fb_DBG   FluxJumps
  base      6834        7159          1
  +4        6897        7408          6
  +8        7162        7508         11
  +12       7480        7802         16
  +20       7750        7094         27
  +40       7686        6744         53
  +80       7297        7650        104
```

`FluxJumps` climbs **monotonically 1 → 104** across an 80 µA TES ramp (~5 jumps
per 4 µA step). `Sq1FbFull`/`Sq1Fb_DBG` stay BOUNDED (~6700-8000 codes, hugging
the ±7862 wrap threshold) instead of railing — textbook multi-flux-wrap: the
feedback tracks the TES-induced flux, wraps at the threshold, increments the
count, and keeps the retained feedback in range. End-to-end through the real
RTL against the wafer model. **This is the original goal met.**

**User was right that P does NOT gate flux jumps.** A locked P-only loop is an
integrator (sq1Fb += P·error); at DC it drives error→0 and sq1Fb parks where it
cancels the applied flux — independent of P. Flux jumps occur because the TES
flux walks that feedback across ±7862; P only sets convergence speed/deadband.
The earlier "raise P" idea was wrong; the fix was reading the counter correctly
and using fine steps.

### Follow-up (DONE + caveat, 2026-09-18)
- **`cosim_pid_lock.py` now captures the full validated procedure** (committed):
  `--seed-tune-points` (SetCosimTunePoints), `--seed-tune` writes the COHERENT
  per-row point (Sq1Bias=50/Sq1Fb=2/SaFb=9) before the SA null, negative-P
  default, and a `--tes-steps` TES flux-jump ramp that reads the FluxJumps
  register. VALIDATED live: `--tes-steps 12 --tes-step-uA 4` drove FluxJumps
  0→11 across a 48 µA ramp, Sq1FbFull bounded. This is the repeatable demo.
- **`check_flux_jump` rewritten** to read the `FluxJumps` register directly
  (`_flux_jump_counts`) and report `total_flux_jumps` = net wrap over the ramp,
  instead of the per-window `flux_jump_delta`.
- **CAVEAT — the harness still reports net=0** in a `steady,flux` run even though
  `cosim_pid_lock.py` shows clear jumps on the same sim/point. Suspect the
  harness's `capture_data` cadence (long `--settle`, a fresh `take_data` per
  step) lets the servo fully re-null between steps so the net register delta per
  step is ~0, and the ramp base already sits settled. The register read is
  correct; the harness step/settle interaction needs a separate look (compare
  the immediate-read cadence cosim_pid_lock uses). For a trustworthy flux-jump
  demo TODAY, use `cosim_pid_lock.py --tes-steps ...`, not the harness flux check.
- Read Sq1Fb_DBG as a SCALAR, Sq1FbFull/FluxJumps
per-row via .flat[0].

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
