# warm_tdm_jupyter refactor — implementation plan

> **Status: planning / not yet approved for execution.** Tasks use checkbox
> (`- [ ]`) syntax. When this is approved and we start implementing, use
> superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Reshape the PR #61 notebook-utility code into a reusable, well-named
part of the software stack: rename away from "jupyter", push reusable hardware
capabilities down onto `Group`/`pr.Process` nodes, factor out duplicated
analysis code, and fix the handful of correctness bugs — without rewriting the
analysis math.

> **Scope grew (2026-08-11 operations API review):** the original "single-system
> assumption is accepted" framing is superseded. Multi-Group scaling (10–100
> Groups) is now an explicit forward concern — see the "Operations API review →
> Scaling" section and Tasks 7–9. The single-Group assumption is now a *starting
> point to decouple from*, not a permanent constraint.

**Spec:** [SPEC.md](SPEC.md) · **Progress:** [PROGRESS.md](PROGRESS.md)

---

## Conventions & references (reconciled with repo guides)

This plan must follow the repo's own documented software conventions. Read
before executing:

- Root [AGENTS.md](../../../AGENTS.md) — project orientation + software
  conventions (device tree hierarchy `GroupRoot → Group → HardwareGroup →
  boards`, `pr.Process` for long-running algorithms, PyDM GUI).
- [software/SOFTWARE_GUIDE.md](../../../software/SOFTWARE_GUIDE.md) — the
  detailed software reference. Most relevant here:
  - **`GroupLinkVariable` pattern** (`_Group.py`) for cross-board array access
    with `tuneEnVar` gating. This is the idiomatic way to expose a per-channel
    quantity across all boards — a better fit than raw board loops for several
    G-items below (esp. G3 cryo resistance, and the PID/timing scalars in G1).
  - Tuning/long-running algorithms are `pr.Process` devices (start/stop/status).
  - Config via `GroupRoot.SaveConfig`/`LoadConfig` (confirms G8 stays as a thin
    session wrapper).
- [docs/RELEASE.md](../../../docs/RELEASE.md) — **branch flow: feature →
  `pre-release` → `main`.** The eventual PR target for this work is
  `pre-release`, not `main`.

**Naming:** new `pr.Device`/`pr.Process` modules use the `_Xxx.py`
underscore-prefix convention, exported via `warm_tdm_api/__init__.py` (as
`_TesBiasWaveform.py` already does). The `operations` subpackage modules (plain
`client.py`, `data.py`, `analysis.py`) keep plain names.

**Documentation gap to close (see Task 3):** neither AGENTS.md nor
SOFTWARE_GUIDE mentions `warm_tdm_jupyter`. AGENTS.md:42 lists `software/jupyter/`
(notebooks, a separate existing dir) as the "Analysis" location. The rename must
update both guides so the new package/home is documented.

---

## Capabilities to move to Group — graduation candidates

This is the list the user asked to start. **Important framing (from the original
author):** these functions were deliberately kept as client-side Python for
**runtime editability**, not by oversight. The intent was always to graduate
them into `Group` *as they mature*. So this is a **maturity-gated graduation
list**, not a batch move.

### Why client-side vs server-side matters (the real criterion)

- A `warm_tdm_api.operations` function runs **client-side** (notebook /
  `warmTdmClientCmd` process, driving the Group tree over ZMQ). Edit it and
  re-run in seconds. No server restart.
- A `Group` method/variable runs **server-side** (baked into `GroupRoot` at
  server start). Changing it requires a **server restart**, which drops tuning
  state → forces a re-tune. In the current system that is slow enough to be the
  dominant cost — hence the pressure to keep iterating code client-side.

**Graduation criterion:**
- **Move to `Group` now** if the capability *needs* server-side execution or
  server-owned state: continuous loops that must survive client disconnect
  (`pr.Process`), GUI buttons, config-serialized state. (`TesBiasWaveformProcess`
  is already in `Group` for exactly this reason — a continuous software-clocked
  loop.)
- **Keep in `operations` until mature** if it's just a sequence of register
  writes. It works fine client-side; the *only* gains from moving are GUI access
  + serialization + single source of truth — real, but they cost runtime
  editability. Graduate each once it has stopped changing.

> Deeper alternative the author raised (out of scope here, worth capturing): if
> re-tuning were as fast as MCE (or faster), a server restart would be cheap and
> the runtime-editability pressure would largely evaporate — allowing much more
> to live in `Group`. That is a larger firmware/software effort, tracked
> separately, not part of this refactor. See SPEC.md.

Legend for **Form**: `method` = plain `Group` method; `process` = `pr.Process`
(long-running / stoppable); `device` = `pr.Device` node with variables.
**Gate** column: `now` = meets the move-now criterion; `mature` = graduate once
stable; `n/a` = stays in `operations`.

| # | Current location | Capability | Proposed form | Gate | Notes / dependencies |
|---|---|---|---|---|---|
| G1 | `utils.py:setup_mux` (`:400-465`) | Configure MUX readout timing + enable SQ1 PID for active columns | `method` on `Group` (or small `device` holding the timing params) | mature | Uses `ColTuneEnable`, `TimingTx`, `AdcDsp[col]`, row DAC `Mode`. Timing params (num_pts, sample window) are good candidates for `pr.LocalVariable`s so they're serialized; the per-column PID enable could be a `GroupLinkVariable` gated by `ColTuneEnable`/`tuneEnVar`. Has a `# TODO: multiple column boards` hardcode. Actively evolving → graduate once stable. |
| G2 | `utils.py:all_off` (`:304-341`) | Panic/clean-slate: zero all non-MUX outputs, end run, drop to manual timing | `method` on `Group` | mature | Already operates on `Group.<X>ForceCurrent` / `TesBias` etc. Blocked partly by a known firmware bug (row-DAC zeroing commented out) — carry that TODO across. Graduate once the firmware bug is resolved and the sequence is stable. |
| G3 | `utils.py:set_cryo_resistance` (`:75-113`) | Set roundtrip cable R on all column+row AFE amps | `GroupLinkVariable` (RW scalar fanned out) or `method` on `Group` | mature | Textbook `GroupLinkVariable` fan-out; would also be GUI-settable + serialized. Stable-ish → good early graduation candidate. |
| G4 | `utils.py:set_ps_synch` / `check_ps_synch` (`:116-188`) | Set / report power-supply sync state across boards | `method` pair on `Group`, or a `device` with a `RW` sync var + `RO` status | mature | `check` returns a summary; consider a `pr.LinkVariable` for the aggregate state so the GUI shows it. |
| G5 | `utils.py:print_hardware` (`:24-50`) | Print BuildStamp/DNA/GitHash/ImageName per board | `method` on `Group` (or `HardwareGroup`) | mature | Read-only convenience; low risk. Could also be a `RO` summary variable. |
| G6 | `utils.py:disable_leds` (`:53-72`) | Stop status-LED blinking on all boards | `method` on `Group` | mature | Trivial; pure register writes. |
| G7 | `client.py` board discovery (`:42-50`) | Enumerate ColumnBoard/RowBoard indices + RowDacDriver handles | Already native to `HardwareGroup` | n/a | The regex-over-`dir()` discovery duplicates `HardwareGroup.ColumnBoard.values()`. Prefer the tree directly; likely no new method. |
| G8 | `utils.py:save_config`/`save_state`/`load_config` (`:344-397`) | Timestamped config/state save + load | Leave as thin session helpers | n/a | Wrap existing `root.SaveConfig/SaveState/LoadConfig`; only added value is the timestamped path. Stays in `operations`. |
| G9 | `channels.py:make/read/write_dead_masks` + missing `apply_dead_masks` | Per-column dead-row (256-bit) mask → hardware | Format helpers stay in `operations`; fanned-out RW `GroupLinkVariable` over `AdcDsp[col].RowEnableMask` gated by `ColTuneEnable` | mature | **The hardware sink exists** — `AdcDsp[col].RowEnableMask` (RW 256-bit, `_AdcDsp.py:116`; applied per row-strobe `AdcDsp.vhd:631`) matches the `{col: 256-bit mask}` shape exactly. Near-term: add `Session.apply_dead_masks()` bridge. Graduate the fanned-out RW to `Group` as it stabilizes. |

Note: no G-item currently meets the **`now`** gate (none is a continuous loop /
GUI button / server-owned-state case). `TesBiasWaveformProcess` was the one such
case and is already in `Group`. So the near-term posture is: **the operations
subpackage keeps all of G1–G6 for now**, and they graduate individually as they
stabilize. The refactor's job is to give them a proper home and a clean
delegation seam, not to force them server-side prematurely.

**Not moving to Group** (stay in `operations` / analysis layer):
- Acquisition helpers `take_raw` / `multi_raw` / `take_data` (`data.py`) —
  orchestration + local-disk session policy, not a hardware capability. (But
  see Task 4: give `take_raw` a timeout.)
- All of `analysis.py` and `streamreader.py` — offline, no hardware, must not
  depend on `Client`.
- Dead-mask file I/O (`channels.py:make/write/read_dead_masks`) — file-format
  helpers. **But they DO have a real hardware sink (see review below): the
  `{col: 256-bit mask}` shape matches `AdcDsp[col].RowEnableMask`.** The format
  helpers stay in `operations`, but an `apply_dead_masks(session)` bridge that
  writes each column's mask to `AdcDsp[col].RowEnableMask` is a missing verb, and
  the fanned-out RW ("dead mask as a channel-indexed Group var") is a graduation
  candidate — see G9.

> When a G-item does graduate, keep a thin `operations` wrapper delegating to the
> new `Group` capability so notebook/production call sites don't break.

---

## Operations API review (2026-08-11) — layering, separation of concerns, scaling

A detached review of `warm_tdm_api.operations` (does the operator-facing API make
sense / is it intuitive / does it extend coherently / is separation of concerns
right?) surfaced findings that reshape the later tasks. Recorded here so they are
not re-derived.

### Verdict summary

The plumbing is sound (injectable `Session`, config-derived calibration, bounded
registry) and the layer extends cleanly (method + shim + `__all__`; the
`_resolve_*` override→derive→fallback ladder is reusable). The gaps are in
**operator-facing surface** and **scaling**, not the internals.

**Intuitiveness / completeness gaps (agreed):**
- **Tuning is absent from `operations`.** The middle of the operator arc
  (`SaOffset → SaTune → Sq1Tune → FasTune`) has no `ops.*` presence; today it is
  hand-rolled `group.SaTuneProcess.Start(); while Running.get(): ...` (see
  `scripts/Jupyter.py`). Add thin start-and-block wrappers (per-process, or one
  `run_process(name, **params)` that returns the result payload). Highest
  intuitiveness payoff. Client-side orchestration of existing tree Processes — no
  graduation needed.
- **`all_off` is misnamed** — a firmware bug means it does NOT fully zero biases
  after MUX (row-DAC zeroing is commented out). Naming a best-effort safe-state
  `all_off` is a footgun for the person reaching for it. Rename (`safe_reset` /
  `stop_and_zero`), log what it cannot do. Also missing a one-shot
  `status()`/`summary()` verb.
- **Dead-mask helpers are NOT orphaned** (correction to first-pass review): their
  `{col: 256-bit mask}` output matches `AdcDsp[col].RowEnableMask`
  (`firmware/python/warm_tdm/_AdcDsp.py:116`, RW 256-bit; applied per row-strobe
  in `AdcDsp.vhd:631`). The consumer exists and the representation already lines
  up — only the `apply_dead_masks` bridge was never written. See G9.
- **Two data models, deliberately** (`StreamData`/`data[col][row]` channel-9
  `.dat` vs. the `.npy` raw-ADC path in `get_mean_raw_asd`). Keeping both is fine
  **as long as each function is explicit about which stream it operates on** (user
  direction). Action is documentation/naming clarity, not unification.
- **`stream_data_id` is implicit global state.** `plot_stream_data(crstring,
  stream_data_id=-1)` takes an *integer index into a module-global deque of the
  last 128 loaded files* (`-1` = most-recently-loaded-anywhere-in-process), not a
  `StreamData` or a path. Fine for a single notebook; surprising for scripted /
  batch / two-analysis use. Minor: also accept an explicit `StreamData`/path as
  first-class, keep `-1` as sugar.

### Separation of concerns — the core structural finding

`Session` currently fuses three roles: (1) a connection handle [keep], (2) a
**hardcoded topology model** (`col//8`, `col%8`, `range(8)`, `range(32)`,
`coordinator_col`), (3) the operation verbs (reaching through deep tree paths like
`board.WarmTdmCore.WarmTdmCommon2.AxiVersion`). Roles (2) and (3) are the smells.

**Principle: Session should orchestrate over `Group`/`HardwareGroup`
abstractions, not re-implement the topology.** The tree is the single source of
topology truth. Session's legitimately-client-side job is *sequencing* (setup
order, acquisition try/finally bracketing, safe-state ordering) — that is why
these stay client-side per the graduation criterion (runtime editability). But
sequencing does not require owning the topology.

- **Smell A — topology constants.** `col//8` etc. duplicate what `Group` already
  exposes: `NumColumns`, `NumColumnBoards`, `NumRowBoards`, `MaxRows`
  (`_Group.py:104-127`). `calibration._col_to_board_chan` hardcodes the *same*
  `//8` independently → already duplicated within `operations`. **Fix: derive
  channels-per-board = `NumColumns // NumColumnBoards` from the bound `Group`;
  share one `col→(board,chan)` mapper between `session` and `calibration`.** No
  new tree API needed — `Group` already knows the shape. **Coordinator is always
  index 0** (user); drop `coordinator_col` as a discovery concept — a literal
  `ColumnBoard[0]` (matching `HardwareGroup`'s own assumption at
  `_HardwareGroup.py:207`), at most a one-line assert. (Retracts an earlier
  "coordinator handle / discovery" idea — unnecessary.)

- **Smell B — scattered deep paths.** A firmware rename breaks each method
  separately because each re-spells the path. **Do NOT solve this with a new
  path-resolution adapter layer in `operations`** (a fourth thing to maintain).
  Instead, each deep path graduates to its **owning node** — which is the G-list
  work already planned. Node-ownership table:

  | Path Session uses today | Owner node | Package | Level |
  |---|---|---|---|
  | `WarmTdmCore.WarmTdmCommon2.AxiVersion.*` (build info) | board device / `HardwareGroup` summary | `warm_tdm` | driver (trim later) |
  | `AnalogFrontEnd.Channel[ch].*Amp.CableR` fan-out | `Group.CableResistance` GroupLinkVariable (**G3**) | `warm_tdm_api` | Group var |
  | `AdcDsp[col].PidEnable` / `RowEnableMask` per-col | `Group` channel var gated by `ColTuneEnable` (**G1/G9**) | `warm_tdm_api` | Group var |
  | `TimingTx.PwrSync*` / `Mode` / `RowPeriodCycles` | `HardwareGroup` (owns the coordinator=`[0]` convention) | `warm_tdm` | HardwareGroup |

  **So #3 collapses into the existing G-list + one small principle: deep per-board
  reaches are *convenience shims pending graduation* — label them as such in
  `operations` so nobody mistakes them for the intended access pattern, and trim
  as they graduate.** No standalone adapter.

### Layering model (corrected) — where warm_tdm_api earns its keep

The three-package model is roughly right, with one correction: **cross-board
aggregation is NOT exclusive to `warm_tdm_api`.** The aggregation point is
`HardwareGroup`, which lives in `firmware/python/warm_tdm` and already builds
board-spanning `LinkVariable`s (`_HardwareGroup.py:225`) and composite devices
(`WaveformCaptureReceiver`). `warm_tdm` as a whole is not a pure register map: 290
`RemoteVariable` **plus 135 `LinkVariable` + 81 `LocalVariable`**.

Real distinction:
- **`warm_tdm`** = everything describing *one hardware system's tree* — register
  maps **and** the board-spanning structure (`HardwareGroup`) + per-device
  conveniences.
- **`warm_tdm_api`** = the `Group` **operator abstraction** (`GroupLinkVariable`
  channel-indexed fan-out with `tuneEnVar` gating) + tuning `pr.Process`es + GUI.
  "Operator concepts" (channels, tune-enable, tuning) vs. "hardware concepts"
  (boards, chips, registers).
- **`operations`** = client-side session / sequencing / analysis.

**On "does `warm_tdm_api` need to be a separate package from `warm_tdm`":** the
split is defensible but the fault line is drawn imperfectly, which is why it feels
questionable. Do NOT try to back out the package split (sunk cost, and it does
carry a real conceptual seam). **Stop treating "which package" as the meaningful
question — the meaningful unit is "which *node* owns this capability."**
`GroupRoot → Group → HardwareGroup → boards` is one runtime object graph; the
package a node's class lives in follows from the node. This is exactly what the
G-list already does (node-placement). Keep packages; let the node be the unit.

### Scaling: single-Group today → 10–100 Groups deployed (NEW, unsupported)

Critical context (user): all testing to date is **one Group = 1 row + 1 column
board**; BICEP3 ≈ 1 row + 4 column; **real deployments are 10–100 Groups**, and
**nothing in the stack supports multi-Group today.** The tree bakes in a single
Group: `GroupRoot` instantiates one `Group` with `groupId=0` hardcoded
(`_GroupRoot.py:55-61`); `Session` wraps `client.root.Group` (singular,
`session.py:94`); `DataWriter` is a `GroupRoot`-level shared resource
(`_GroupRoot.py:43`).

**Two-object model we converged on** (do not fuse these into one `Session`):
- **`Session`** = handle to **one Group's Root** (one server, one connection, one
  DataWriter). All current `session.py` verbs are per-Group and stay here. This is
  the object every bench uses today; the only change is it binds to *a* Root/Group
  rather than *the* global `root.Group`.
- **`Instrument`** (a.k.a. `Array`/`GroupSet`) = a **client-side federation
  coordinator** holding N `Session`s. Its job is precisely the operator's
  whole-instrument needs: **run tuning across all Groups** and **aggregate
  analysis across all Groups**. The 1-Group bench is just an `Instrument` with one
  `Session` (or the bare `Session`) — no federation tax for the common case.

```
Instrument                         # federation coordinator (client-side, operations)
 ├── Session(root_0) → Group 0      # per-Group ops handle (one server each)
 ├── Session(root_1) → Group 1
 └── ... Session(root_N)
```

This cleanly answers "where does cross-group live": in `Instrument`, client-side.
Per-Group trees never learn other Groups exist → federated servers stay
independent, per-file channel-255 config dumps stay sane-sized, tuning `Process`es
stay per-Group and `Instrument.tune_all()` orchestrates them (orchestration is
what the client layer is for).

**Topology-API home = `Group`** (user): `operations` should interact with `Group`
to the extent it can, and `Group` already carries the per-group counts. `Group`
owns per-group topology; `GroupRoot` owns the group registry + genuinely shared
resources.

### The open architectural decision: federated vs. non-federated

**Undecided (user lean: federated, but genuinely uncertain).** This is the single
question that gates the deployment design.

- **Non-federated (one Root holds `Group[0..K]`):** gives a single
  Instrument-level `LoadConfig`/`SaveConfig` and one endpoint a future
  supervisory/EPICS/site-DAQ layer could connect to. **Main risk (user's central
  worry): tree size — a 10–100-Group PyRogue tree may collapse under its own
  weight; we have never scaled a PyRogue tree that large.** Also inflates the
  channel-255 whole-tree config dump per data file and concentrates poll/register
  load in one process.
- **Federated (many Roots, one per Group/crate; `Instrument` federates
  client-side):** matches how we test today (one Group per bench), scales
  process/poll load horizontally, keeps each Group's data file self-describing at
  sane size. **Cost:** additional federation logic/structure; **no single
  server-side object represents "the whole instrument"** — if a non-Python
  supervisory control layer over the whole array is ever required, that pushes
  back toward non-federated. (This supervisory-layer question is *the* deciding
  factor if it turns out to matter.)

**Decision method (user):** don't pick on paper. **First implement "#3"
(topology-from-`Group`, `Session` binds to an injected Group/Root, fan-out
graduations), then build a NON-federated `Instrument` and see how it behaves —
specifically whether the tree scales.** The non-federated attempt is the
experiment that informs the choice; if the tree collapses, federated wins.

---

## Open decisions

1. ~~Package home + name.~~ **RESOLVED (2026-07-21): `warm_tdm_api.operations`.**
   A subpackage of `warm_tdm_api` (not a sibling — the layer is API-coupled and
   production-bound, not throwaway). Name rationale: it is the **client-side
   operational layer** for running the system (acquisition + setup + analysis),
   deliberately runtime-editable, and expected to reach production. Rejected:
   `scripting`/`workflows` (too generic, don't convey the operational role),
   `notebook` (re-narrows to the venue we're shedding), `lab`/`bench` (imply
   experimental/throwaway — but this code is production-bound).
2. **Migration cadence.** Given the graduation criterion above, near-term there
   is nothing to force server-side. Cadence question is really "which mature
   G-items (e.g. G3) do we graduate first, if any, vs. just rehome everything
   into `operations` and graduate later?" Default: rehome first, graduate later.
3. ~~**Constants home**~~ **RESOLVED (2026-08-11):** derive `fs`/`sq1fb_to_pA`
   from each data file's Rogue config channel (255), not a `constants.py`. See
   Task 4.
4. **Federated vs. non-federated multi-Group model** (see "Operations API review
   → Scaling" above). **OPEN.** User lean: federated; central worry: PyRogue tree
   size in the non-federated case. **Decision method: implement Task 7 (#3) first,
   then build a non-federated `Instrument` (Task 8) as the experiment; let tree
   scaling behavior decide.** The tie-breaker if it surfaces: whether a non-Python
   supervisory/EPICS control layer over the whole array is ever required (→ favors
   non-federated single-endpoint).

---

## Tasks

### Task 0 (done): Review + scaffold
- [x] Review PR #61, capture findings and decisions in SPEC.md.
- [x] Create `wtj-refactor` branch off `wtj`.
- [x] Scaffold this plan set.

### Task 1: Correctness fixes (low-risk, do first) — DONE
- [x] Fix README install command to match repo-root `install.sh`. (0a8f16f)
- [x] Add `scipy` to `conda.yml`. (5d097db) Note: the Task 2 cleanup adoption
      adds the same line after `numpy` — placed identically here, dedup on merge.
- [x] Add a timeout to the `take_raw` capture-wait loop. (78a1946) Added
      `timeout_sec=30.0`, raises `TimeoutError`, `SaveData` disable moved to
      `finally`.
- [x] Remove dead `import pandas as pd` (`streamreader.py`). (2f079de)
- [x] Replace `_TesBiasWaveform.py` hardcoded `num_generators = 8` with the
      dynamic count `process._waveformGeneratorCount`. (fd5d97a)

### Task 2: Adopt the `cleanup` software refactor — DONE (merged 0491e7b) — full plan in [MERGE-cleanup.md](MERGE-cleanup.md)
This is the structural foundation the later tasks build on: it splits `_Group.py`
into `_GroupVariables.py` (the `GroupLinkVariable` home the Group migrations in
Task 5 target) + `_GroupConfig.py`, adopts the unified launch script, and pins
`maxRows`.
- [x] Branch `wtj-cleanup-sw` off `wtj-refactor`; ported by content (Option A).
- [x] In scope: `_Group.py`/`_GroupVariables.py`/`_GroupConfig.py`/`_Mapping.py`
      split, `_ArgParser`/`_Tuning`/logging, unified `warmTdmServer.py`
      (+ `gui.py`/`warmTdmGui.py`/`testGroup.py` removal), `scipy` (Task 1), dead
      `_FllEnable` widget.
- [x] Held back: all `firmware/python/warm_tdm` (0 files changed), `_AdcDspFp`,
      `PidDebugFileReaderFp.py`. Firmware seam adapted: kept
      `HardwareGroup(num_row_selects/num_chip_selects)`; `--floatPid`
      accepted-but-ignored w/ warning; `maxRows` software-side only.
- [x] Pinned `GroupConfig.maxRows = 256` (RTL default; 32 for `160Coord`).
- [x] Re-applied wtj's `TesBiasWaveformProcess` registration into new `_Group.py`;
      kept `_TesBiasWaveform.py` + `__init__` import.
- [x] Validated: emulate-mode lifecycle + GroupTb(VCS)+`--sim` cosim against real
      RTL register maps. Merged `wtj-cleanup-sw` → `wtj-refactor` (0491e7b).
- [ ] **Analog bench (deferred, user step):** real tune/SaOffset converging on
      SQUIDs + `--gui`, on the integrated branch. Not blocking further tasks.

### Task 3: Package rename / rehome → `warm_tdm_api.operations` — DONE (7b5946f, f5e22f6)
- [x] Move `software/python/warm_tdm_jupyter/` → `software/python/warm_tdm_api/operations/` (git mv, history preserved).
- [x] Replace `import *` sprawl with explicit re-exports + `__all__` (28 names);
      internal helpers no longer leak.
- [x] Remove import-time `addLibraryPath` side effects from `streamreader.py`.
- [x] No tracked importers of `warm_tdm_jupyter` existed (notebooks not in repo);
      nothing external to update. `warm_tdm_api/__init__` intentionally does NOT
      auto-import `operations` (keeps matplotlib/scipy off the server path) — use
      `import warm_tdm_api.operations`.
- [x] Documented in root `AGENTS.md` (layout + Software Conventions) and
      `software/SOFTWARE_GUIDE.md` (package-structure section).
- [x] Import-checked in `warm-tdm-env`: `warm_tdm_api` imports without loading
      `operations`; `import warm_tdm_api.operations` resolves all 28 exports.

### Task 4: Analysis + `operations` structural cleanup — DONE (2026-08-11)
- [x] Extract pure `compute_asd` / `channel_timeseries` helpers shared by
      `plot_stream_data` and `analyze_pair`. (in `analysis.py`)
- [x] Move `sq1fb_to_pA` / `fs` calibration constants out of default args.
      **Open decision 3 RESOLVED (2026-08-11): derive from the data file's Rogue
      config channel** (user decision: "enable config capture first"). Both
      constants are computable from the tree state, and that state is embedded in
      each `.dat` at capture time, so derivation is *offline* (no live `Client`).

      **Investigation findings (2026-08-11), verified in emulate mode:**
      - The `GroupRoot.DataWriter` (`_GroupRoot.py:40-46`) already has a config
        stream wired to **channel 255** via `pyrogue.interfaces.stream.Variable`;
        `StreamWriter._open()`/`_close()` auto-dump the full tree YAML there. A
        `.dat` opened through `DataWriter.Open()/Close()` **does** contain channel
        255 — confirmed it carries every `ColumnBoard[i].AnalogFrontEnd.Channel[c]
        .SQ1FbAmp.{ShuntR,FbR,InputR,IOUTFS,...}` and
        `...DataPath.WaveformCapture.Decimation`, keyed by full tree path.
      - **Why existing files lack it — two gaps, both real:**
        1. **Read side:** `streamreader.py:36` calls `FileReader(files=[filename])`
           *without* `configChan=255`, so channel-255 records are silently skipped
           (the `configChan=255` version is commented out at `:35`). Even when
           passed, `FileReader._updateConfig` hits a framework bug on this pyrogue
           version: `yaml.load(...)` without a `Loader` raises under PyYAML 6.
           Workaround: parse channel 255 ourselves with `yaml.SafeLoader`.
        2. **Write side:** the `operations.take_raw` path does NOT use
           `GroupRoot.DataWriter`. It saves via `WaveformCaptureReceiver`
           (`_WaveformCapture.py:436-452`) as **`.npy`** (`np.save`), no config.
           The channel-9 `.dat` files that analysis reads come from `DataWriter`
           (readout streams linked at `_HardwareGroup.py:154`) — a separate path.
      - **`sq1fb_to_pA`** = per-DAC-LSB output-current slope of the SQ1FB amp,
        modeled by `FastDacAmplifierSE/Diff.dacToOutCurrent` (`_Amplifiers.py`)
        from `IOUTFS`/`Gain`/`LoadR`/`rout()`:
        `(dacToOutCurrent(1)-dacToOutCurrent(0)) * 1e6` (µA→pA), for the right
        `ColumnBoard[i]...Channel[c].SQ1FbAmp`.
        **Streamed-value provenance verified end-to-end (2026-08-11) through the
        RTL** — the channel-9 `DataSample.value` float32 IS the flux-unwrapped
        SQ1FB *DAC code*, so the per-LSB slope is the correct conversion:
        1. `AdcDsp.vhd` `SQ1FB_ADJUST_S` (:766) `sq1Fb := sq1Fb + pidResult` — PID
           delta applied; `sq1Fb` now = the real DAC code driving the SQ1FB DAC RAM.
        2. `DATA_STREAM_FLUX_JUMP_0_S` (:786) reloads `pidResult := sq1Fb`, then
           `_1_S` (:792) adds `fluxQuantum*numFluxJumps` → flux-unwrapped DAC code.
           (The name `pidResult` is misleading here — at stream time it holds the
           SQ1FB DAC value, NOT the PID delta.)
        3. `DATA_STREAM_S` (:799, outputMode "00") packs it as an integer slv.
        4. `BiquadFilter.vhd` `Int2Fp` IP (:268) converts int→IEEE float32; default
           coeff `b0=1.0` (:136) = unity DC gain, no fractional rescale.
        5. `EventBuilder`→channel 9→`DataSample.from_numpy` views 4 bytes as
           float32. So value == DAC code as a real number.
        The ~15x gap between the emulate default (`FastDacAmplifierDiff`,
        ShuntR=7680/FbR=402 → ~18566 pA/LSB) and the notebook literal 1224.23 is a
        **front-end-config difference** (1224.23 = a different SQ1FbAmp) — which is
        exactly why this must be tree-derived per front-end, not hardcoded.
      - **Home for the derived value — IMPLEMENTED (2026-08-11):** added
        `CurrentPerLsb` RO LinkVariable on `FastDacAmplifierSE` (inherited by
        `Diff` and every FastDacAmplifier in the design), units **`µA/LSB`**,
        `linkedGet=currentPerLsb()` = `dacToOutCurrent(1)-dacToOutCurrent(0)`.
        Generic (no SQ1 name; other FastDacAmplifiers exist) and in the µA
        convention used by `MaxCurrent`/`MinCurrent`. Offline analysis reads it
        straight from the config channel and applies the µA→pA (×1e6) itself.
      - **`fs` — IMPLEMENTED:** direct read of `TimingTx.DaqReadoutRate` (Hz), a
        LinkVariable that already folds in row period / active row count /
        row-sequences-per-readout. No client-side derivation needed.
      - **Config decode is broken in ALL released rogue** (verified 6.6.2 / 6.12.0
        / 6.15.0, the last on py3.13):
        - 6.6.2: `_FileReader` bare `yaml.load()` → PyYAML-6 Loader TypeError
          (fixed in rogue v6.9.0, commit `582133155`).
        - 6.12.0 + 6.15.0: root-caused to **rogue `_DataWriter.py:131`** — the
          built-in `DataWriter.Bandwidth` LocalVariable has `disp='{:,.3f}'`, and
          config serialization writes the *disp-formatted* string as a `!!float`
          scalar (`!!float '256,939.708'`). The comma thousands-separators are
          not round-trippable; one bad leaf aborts the whole `configDict` decode.
          Filed upstream: **slaclab/rogue#1282**. Still open at rogue HEAD.
      - **Decision: defensive read, no rogue-version dependency.** Neither
        upgrading nor waiting on the upstream fix is required.
      - **IMPLEMENTED (2026-08-11):** (a) `streamreader.py` collects channel-255
        payloads and parses **defensively** — `_desep_commas()` strips commas from
        quoted `!!float` scalars, then `pyrogue.yamlToData`; returns `{}` on any
        failure (never breaks readout). Config exposed as `StreamData.config`.
        (b) `operations/calibration.py`: `derive_fs` (reads `DaqReadoutRate`),
        `derive_sq1fb_to_pA` (`CurrentPerLsb`×1e6, per-column), plus `resolve_*`
        wrappers returning `(value, wasDerived)` with documented-literal fallback
        (`DEFAULT_FS`/`DEFAULT_SQ1FB_TO_PA`). (c) `analysis.py`: `plot_stream_data`
        /`analyze_pair` now default `fs`/`sq1fb_to_pA` to `None` → resolve from the
        file's config (per-column for sq1fb), explicit override still honored,
        literal fallback + note when no config. Validated in `warm-tdm-r615`
        (py3.13/rogue 6.15.0): derived value matches the live tree, fallback works
        on config-less input, full plot/analyze flow runs.
- [x] Bound / rethink `StreamData._instances` unbounded registry. **DONE:** now a
      `deque(maxlen=128)` (configurable via `set_max_instances`); `.index` is a
      stable monotonic id (survives eviction) and `get_by_index` searches by it;
      new `get_by_position` preserves the `stream_data_id`/`-1`-is-most-recent
      contract used by the analysis functions.

### Task 5: Group graduations (as capabilities mature — deprioritized)
Per the graduation criterion, nothing here meets the "move now" gate today, so
this is not urgent. Graduate individual G-items into `Group` once they stabilize,
targeting the `_GroupVariables`/`_GroupConfig` structure adopted in Task 2. Each
graduation keeps a thin `operations` wrapper delegating to the new `Group`
capability so call sites don't break.
- [ ] Graduate G3 (`set_cryo_resistance`) as a `GroupLinkVariable` — likely the
      first, being the most stable + textbook fan-out.
- [ ] Graduate G1/G2/G4–G6 individually as each stops changing (see G-table).

### Task 6: Verification
- [ ] `warm_tdm_api` and `warm_tdm_api.operations` import cleanly.
- [ ] Notebook / operations entry points still work against live hardware (user step).
- [ ] Any graduated `Group` capabilities visible/serializable (SaveConfig round-trip).
- [ ] PR targets `pre-release` (not `main`), per docs/RELEASE.md branch flow.

---

## Follow-on tasks from the 2026-08-11 operations API review

These come out of the review section above. Task 7 is the prerequisite for the
scaling decision; Task 8 is the experiment that decides federated vs. not; Task 9
is operator-surface polish that can proceed independently.

### Task 7: Decouple `Session` from tree topology (#3) — DONE (2026-08-11)
Make `Session` orchestrate over `Group` instead of re-implementing topology.
- [x] Derive channels-per-board from the bound `Group`
      (`NumColumns // NumColumnBoards`, `_derive_chans_per_board`, default-8
      fallback); removed hardcoded `//8` / `%8`. Shared `col_to_board_chan` mapper
      added to `formats.py`, used by `Session.col_to_board_chan` **and**
      `calibration._col_to_board_chan` (duplication killed).
- [x] Replaced `range(8)`/`range(32)` AFE loops with `Session._afe_amps()` which
      enumerates the actual `Channel[*]`/`Amp[*]` nodes from the tree (front-end
      classes differ in count). Validated: 8 col channels, 32 row amps in emulate.
- [x] Dropped `coordinator_col` entirely — `COORDINATOR_COL_BOARD = 0` constant +
      `Session.coordinator_cb` property (coordinator is always `ColumnBoard[0]`).
- [x] `Session` now binds to an injected **Group node** (`Session(group)`), not
      the global `root.Group`. `self.root = group.root` for Root-scoped ops;
      Group-scoped access goes through `self.group` (no more `self.root.Group`).
      `use(client, group='Group')` / `connect(..., group='Group')` resolve the
      Group node under the client and support a future multi-Group root.
- [x] Labeled the residual deep per-board reaches (AxiVersion, `LedEn`,
      `PwrSync*`, `AdcDsp[col].PidEnable`) as *convenience shims pending
      graduation* in a block comment — no path-resolution adapter built.
- [x] Validated in `warm-tdm-r615` emulate: direct `Session(root.Group)` +
      VirtualClient/ZMQ `ops.use(client)` seam; topology derivation,
      `set_cryo_resistance` (enumerated AFE writes), `print_hardware`,
      `check_ps_synch`, shims all work.
- [ ] **Deferred to Task 5/G-list (not this task):** graduate G3
      `CableResistance` as a `GroupLinkVariable` and add the G9 `apply_dead_masks`
      bridge. Task 7 kept `set_cryo_resistance` client-side but routed it through
      `_afe_amps` so the eventual graduation is a clean lift.

### Task 8: Multi-Group `Instrument` experiment — DECIDES federated vs. not
Depends on Task 7. Build the non-federated attempt first as the scaling probe.
- [ ] Introduce `operations.Instrument` (a.k.a. `Array`/`GroupSet`): holds N
      `Session`s, exposes `tune_all()` (fan-out over existing per-Group tuning
      `pr.Process`es) and cross-group analysis aggregation. 1-Group case = one
      `Session`, no federation tax.
- [ ] Prototype the **non-federated** tree: `GroupRoot` holds `Group[0..K]`
      (remove the hardcoded single `groupId=0`). Measure PyRogue tree behavior at
      representative group counts (10, then toward 100): build/poll load, memory,
      channel-255 config-dump size per data file, client responsiveness.
- [ ] **Decision gate:** if the tree scales acceptably → non-federated (keeps a
      single Instrument-level `LoadConfig`/endpoint). If it collapses → federated
      (many Roots, `Instrument` federates client-side). Record the result and the
      supervisory-control tie-breaker in Open decision 4.

### Task 9: Operator-facing surface polish — DONE (2026-08-12)
- [x] Tuning wrappers (generic + named, per user): `Session.run_process(name,
      block=True, poll_sec, timeout_sec, **params)` sets params, `Start()`s,
      polls `Running` (with `timeout_sec` + KeyboardInterrupt→Stop), prints the
      final `Message`, and returns the process output var (`_PROCESS_OUTPUT`
      map). Thin `sa_offset`/`sa_tune`/`sq1_tune` delegate to it. Closes the
      operator arc (connect → setup → **tune** → take data → analyze).
- [x] Renamed `all_off` → `stop_and_zero`; honest docstring + a `log.warning`
      that it is best-effort (biases may not zero after MUX; row DACs untouched
      — the G2 firmware bug). Not a hardware interlock.
- [x] Added `Session.status()` — one-shot state summary (board counts,
      run/MUX mode, tune-enabled cols, output dir); prints and returns a dict.
- [x] `plot_stream_data`/`analyze_pair` `stream_data_id` now accepts a
      `StreamData` instance or a file path (first-class) as well as the int
      position (`-1` = most recent) via `_resolve_stream_data`.
- [x] Documented the two data models in `analysis.py` module docstring (channel-9
      `.dat` `StreamData` vs. `.npy` raw-ADC `get_mean_raw_asd`) + a DATA MODEL
      note on `get_mean_raw_asd`. Both kept — not unified.
- [x] New shims (`status`, `stop_and_zero`, `run_process`, `sa_offset`,
      `sa_tune`, `sq1_tune`) registered; `all_off` shim removed. 47 exports.
- [x] Validated in `warm-tdm-r615` emulate: `status()` output, `stop_and_zero()`
      (2s + warning), `run_process` bad-name/bad-param → AttributeError,
      node/output-var mapping, and the analysis resolver (StreamData passthrough /
      int position / bad path → FileNotFoundError). A *converging* tune needs the
      analog bench (not emulate); the wrapper plumbing around it is verified.
