# Muxed-run bring-up: configuration layers, ordering, and tune-point restore

System-level model of what has to be configured to bring a Group into a
multiplexed (servoed) readout run, how those settings depend on each other, and
how we intend to save/restore them — in particular the "tune point." Written to
inform the `operations` bring-up + config/tune-point helpers (see
`docs/plans/wtj-refactor/PLAN.md`); reconstructed by reading the bench notebooks
(`software/scripts/2026*/`), `setup_mux`/the predecessor `lock_and_stream`, the
tuning `pr.Process`es, and `_Group.py` together.

> Status (2026-08-12): **design discussion, agreed to settle before building.**
> Two open questions are called out below (artifact slicing; the `Tuned` validity
> flags). No helper is implemented yet.

## The three configuration layers

Bringing up a muxed run touches three distinct kinds of state. Separating them is
the key to reasoning about ordering and save/restore:

### A. Enabled set (topology / frame of reference)
*Which* columns and rows participate. Everything else is indexed against this.
- `Group.ColTuneEnable` — which columns are active.
- `Group.RowIndexOrderList` / `RowMap` — which logical rows are read out and how
  they map to physical row-selects (see [row-mapping.md](row-mapping.md)).

A is the **anchor**: it is established first in every real workflow, and both B
and C are meaningful only relative to it.

### B. Tune point (servo setpoints)
The DAC values a tune produces — the working point.
- `SaBiasCurrent`, `SaOffset`, `SaFbForceCurrent`, `SaFbCurrent`
- `Sq1BiasForceCurrent`, `Sq1FbForceCurrent`, `Sq1FbCurrent`
- `TesBias`
- (row-select FAS on/off currents on `RowDacDriver`)

B **depends on A**: a tune point is only valid for the exact (cols, rows) it was
solved against. This dependency is what forces a consistency gate on restore.
Note the Voltage/Current twins (`SaBiasVoltage` vs `SaBiasCurrent`, …) are
alternate views of the *same* DAC — a tune point should record one domain
(Current) to avoid double-representation and restore fights.

### C. Run settings (how to run the readout)
The timing/servo-engine configuration for the muxed run.
- `TimingTx`: `RowPeriodCycles`, `SampleStartTime`/`SampleEndTime`, `Mode`
  (hardware-MUX vs software-stepped), power-sync.
- Per-column `AdcDsp[col].PidEnable` (+ `PidDebugEnable`).
- Per-column `AdcDsp[col].RowEnableMask` (which rows the servo acts on).

C **depends on A** (PID enables and row masks are expressed over the enabled set)
but is largely **independent of B** (the servo engine starts from whatever DAC
values are present; you can configure the run before or after the setpoints
exist).

## Ordering: what is fixed and what is free

The dependency graph — not a single mandated order — is:

```
        A  (enabled set: ColTuneEnable, RowMap/order)
       / \
      B   C
 (tune pt) (run settings: timing, PID enable, row masks)
```

- **A must precede both B and C.** Tuning is performed against the enabled set;
  row masks / PID enables are expressed over it.
- **B and C are siblings** — either order is valid depending on workflow:
  - *Fresh tune* (the bench notebooks): A → **B** (tune in stages: SaOffset →
    SaTune → set FAS → Sq1Tune) → **C** (set num_pts/sample window/Mode, enable
    PID) → run.
  - *Restore a working point*: A → **C** (configure the run) → **B** (drop in a
    saved tune point) → run. Equally valid because A is fixed first.

This is why "at what point does the tune point get loaded relative to the run
settings?" has no single answer — B and C don't depend on each other. The
invariant that *does* hold: **A is the anchor, established first, and the tune
point must be validated against the A it was solved against**, regardless of the
B/C order.

Observed bench sequence (`2026May14-...bamodI1`, representative):
static analog gains → set `ColTuneEnable` → `RowMap1x32()` + `RowIndexOrderList`
→ zero setpoints → SaOffset → SaTune → set FAS currents → Sq1Tune → *then*
num_pts/sample window/Mode/PID-enable → take data.

## The consistency gate (the reason this design matters)

Blindly applying a saved tune point when a different enabled set is active drives
DACs to values solved for a *different* configuration — worse than not loading.
So `load_tune_point` must **gate**:

1. A saved tune point records the **A it belongs to** (`ColTuneEnable` + row
   map/order at save time), as provenance embedded in the artifact.
2. On load, compare recorded-A against the currently-active A.
3. On mismatch: refuse by default; allow an explicit `force=` override; ideally
   report *what* differs (which cols/rows).

Because A precedes B and C in all workflows, this gate is well-defined no matter
which order B and C were loaded in.

## OPEN QUESTION 1 — artifact slicing

How to slice the save/restore artifacts so the ordering freedom is expressible
while A stays the anchor. Not decided.

- **(i) Three artifacts** — separate save/load for A (enabled set), B (tune
  point), C (run settings). Maximum freedom; A explicitly its own restorable
  thing; most helpers. The tune point (B) still embeds A-provenance for the gate.
- **(ii) Two artifacts** — bundle A+C as "run config" (the how-to-run), keep B
  (tune point) separate with A-provenance. Fewer pieces; serves both "configure
  run, then load tune" and "tune, then configure run." Risk: A living in the
  run-config artifact must still be comparable to the A a tune point recorded.

Leaning unresolved. (i) is cleaner conceptually (A is genuinely its own layer);
(ii) is fewer moving parts for the operator. Revisit with the helper design.

## OPEN QUESTION 2 — per-thing `Tuned` validity flags

Should each tunable unit carry a "do I currently hold a valid tune?" flag, beyond
just having DAC values present? This answers: which cols/rows are actually tuned
now; what went stale after a bias change or re-enable; on load, does the incoming
tune point cover everything currently enabled. Not decided — needs its own design.

Sub-questions:
- **Granularity.** Tuning is staged and 2-D: SA/SaOffset are per-**column**;
  Sq1 is per-**(column,row)**; FAS is per-row-select. A single boolean cannot
  express this — likely need at least `SaTuned[col]` and `Sq1Tuned[col,row]`
  (and maybe `FasTuned[...]`), i.e. indexed by A.
- **Who sets/clears.** Tune processes set the flag on convergence
  (`SetAfterFinish`); changing a bias, re-enabling a row, or editing A should
  *invalidate* the affected flags. This is real instrument state, so probably
  `pr.LocalVariable`s on `Group` (server-side, serialized, GUI-visible) — which
  makes it a **new state model**, not just a save/restore helper.
- **Relationship to the gate.** With `Tuned` flags, `load_tune_point`'s gate
  strengthens from "same enabled set" to "the tune point supplies a valid tune
  for every currently-enabled (col,row)."

Because `Tuned` is new server-side state that the tune processes, GUI, and load
logic all touch, its granularity is expensive to change later — design before
building. The consistency gate on A gives most of the safety immediately and
informs what `Tuned` must express.

## Implications for the `operations` bring-up API (once the above is settled)

- A richer bring-up verb (beyond today's `setup_mux`, which covers only the
  C-layer timing + PID enable) that also drives the A-layer and the hand-written
  configure steps (FAS currents, per-column bias/offset) the notebooks still do
  by hand.
- `save_tune_point` / `load_tune_point` (B) with embedded A-provenance + the gate.
- `save/load` for run settings (C) — or the A+C bundle, per open question 1 —
  built on Rogue's `saveYaml`/`loadYaml` `incGroups`/`excGroups` filtering (tag
  the layer's variables with a group, e.g. `'TunePoint'`, and filter on it;
  Rogue-native, no YAML surgery, GUI/SaveConfig-consistent).
- Keep the existing `save_state` (everything incl. RO) and `save_config` (all
  RW+WO) — the operator already uses and understands those; the new helpers are
  *narrower*, layer-scoped snapshots, not replacements.

## Reference

| Layer | Key variables | Where set today |
|---|---|---|
| A enabled set | `ColTuneEnable`, `RowIndexOrderList`, `RowMap` | notebook, first |
| B tune point | `Sa/Sq1 *Current/*ForceCurrent`, `SaOffset`, `TesBias`, FAS currents | tune `pr.Process`es (`SetAfterFinish`) |
| C run settings | `TimingTx.{RowPeriodCycles,Sample*,Mode}`, `AdcDsp[col].{PidEnable,RowEnableMask}` | `setup_mux` (partial) + notebook |

Rogue save/restore mechanism: `Root.saveYaml`/`loadYaml`/`treeYaml` all accept
`modes` + `incGroups`/`excGroups`. `SaveConfig` = RW+WO excl. `NoConfig`;
`SaveState` = RW+RO+WO excl. `NoState`. A group tag (`'TunePoint'`, etc.) plus
`incGroups` is the clean selector for a layer-scoped snapshot.
