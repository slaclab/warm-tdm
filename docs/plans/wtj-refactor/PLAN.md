# warm_tdm_jupyter refactor — implementation plan

> **Status: planning / not yet approved for execution.** Tasks use checkbox
> (`- [ ]`) syntax. When this is approved and we start implementing, use
> superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Reshape the PR #61 notebook-utility code into a reusable, well-named
part of the software stack: rename away from "jupyter", push reusable hardware
capabilities down onto `Group`/`pr.Process` nodes, factor out duplicated
analysis code, and fix the handful of correctness bugs — without rewriting the
analysis math or removing the accepted single-system assumption.

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
- Dead-mask file I/O (`utils.py:make/write/read_dead_masks`) — file-format
  helpers.

> When a G-item does graduate, keep a thin `operations` wrapper delegating to the
> new `Group` capability so notebook/production call sites don't break.

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
3. **Constants home** (Task 5): a `constants.py` in the package vs deriving
   `fs`/`sq1fb_to_pA` from the rogue tree.

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

### Task 2: Adopt the `cleanup` software refactor — full plan in [MERGE-cleanup.md](MERGE-cleanup.md)
This is the structural foundation the later tasks build on: it splits `_Group.py`
into `_GroupVariables.py` (the `GroupLinkVariable` home the Group migrations in
Task 5 target) + `_GroupConfig.py`, adopts the unified launch script, and pins
`maxRows`. **Do this before the rename and the Group migrations** — migrating
onto the pre-split structure would mean redoing that work.
- [ ] Branch `wtj-cleanup-sw` off `wtj-refactor`; port the software refactor by
      content (path-scoped diff), NOT a branch merge. See MERGE-cleanup.md for
      the exact file list and hold-backs.
- [ ] In scope: `_Group.py`/`_GroupVariables.py`/`_GroupConfig.py`/`_Mapping.py`
      split, `_ArgParser`/`_Tuning`/logging, unified `warmTdmServer.py`
      (+ `gui.py`/`warmTdmGui.py` removal), `scipy`, dead `_FllEnable`.
- [ ] Hold back: `firmware/python/warm_tdm` v1/retired driver deletions;
      `--floatPid`/`--maxRows` defaults must reflect current (pre-FP) firmware.
- [ ] Pin `GroupConfig.maxRows = 256` (RTL default; 32 for `160Coord`).
- [ ] Re-apply wtj's `TesBiasWaveformProcess` registration into the new
      `_Group.py`; keep `_TesBiasWaveform.py` + its `__init__` import.
- [ ] **Hardware validation gate (user step):** `warmTdmServer.py` starts, Group
      builds, a tune/SaOffset runs, `--gui` brings up PyDM. Then merge
      `wtj-cleanup-sw` back into `wtj-refactor`.

### Task 3: Package rename / rehome → `warm_tdm_api.operations`
- [ ] Move `software/python/warm_tdm_jupyter/` → `software/python/warm_tdm_api/operations/`.
- [ ] Update `__init__` imports, add `__all__`, drop `import *` sprawl.
- [ ] Remove import-time `addLibraryPath` side effects from `streamreader.py`.
- [ ] Update existing notebooks / docs that import `warm_tdm_jupyter` →
      `warm_tdm_api.operations`.
- [ ] **Document the package** in root `AGENTS.md` and `software/SOFTWARE_GUIDE.md`
      (both currently omit it; AGENTS.md:42 only lists `software/jupyter/`
      notebooks). Add `warm_tdm_api.operations` to the package-structure sections.

### Task 4: Analysis + `operations` structural cleanup
- [ ] Extract pure `compute_asd` / `channel_timeseries` helpers shared by
      `plot_stream_data` and `analyze_pair`.
- [ ] Move `sq1fb_to_pA` / `fs` calibration constants out of default args
      (see open decision 3: `constants.py` vs derive from tree).
- [ ] Bound / rethink `StreamData._instances` unbounded registry.

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
