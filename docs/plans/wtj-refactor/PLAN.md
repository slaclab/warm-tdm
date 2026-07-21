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
`_TesBiasWaveform.py` already does). The convenience-layer modules (plain
`client.py`, `data.py`, `analysis.py`) are a subpackage and keep plain names.

**Documentation gap to close (see Task 3):** neither AGENTS.md nor
SOFTWARE_GUIDE mentions `warm_tdm_jupyter`. AGENTS.md:42 lists `software/jupyter/`
(notebooks, a separate existing dir) as the "Analysis" location. The rename must
update both guides so the new package/home is documented.

---

## Capabilities to move to Group (the running list)

This is the list the user asked to start. Each row is a candidate to become a
`Group` method (or a small `pr.Process`/`pr.Device` node) so it becomes
GUI-usable and config-serializable, not just importable in a notebook.

Legend for **Form**: `method` = plain `Group` method; `process` = `pr.Process`
(long-running / stoppable); `device` = `pr.Device` node with variables.

| # | Current location | Capability | Proposed form | Notes / dependencies |
|---|---|---|---|---|
| G1 | `utils.py:setup_mux` (`:400-465`) | Configure MUX readout timing + enable SQ1 PID for active columns | `method` on `Group` (or small `device` holding the timing params) | Uses `ColTuneEnable`, `TimingTx`, `AdcDsp[col]`, row DAC `Mode`. Timing params (num_pts, sample window) are good candidates for `pr.LocalVariable`s so they're serialized; the per-column PID enable could be a `GroupLinkVariable` gated by `ColTuneEnable`/`tuneEnVar` rather than a manual loop. Has a `# TODO: multiple column boards` hardcode to resolve. |
| G2 | `utils.py:all_off` (`:304-341`) | Panic/clean-slate: zero all non-MUX outputs, end run, drop to manual timing | `method` on `Group` | Already operates on `Group.<X>ForceCurrent` / `TesBias` etc. Blocked partly by a known firmware bug (row-DAC zeroing commented out) — carry that TODO across. |
| G3 | `utils.py:set_cryo_resistance` (`:75-113`) | Set roundtrip cable R on all column+row AFE amps | `GroupLinkVariable` (RW scalar fanned out) or `method` on `Group` | Iterates all boards + channels writing the same value to many `CableR`/`R_CABLE` vars — the textbook `GroupLinkVariable` fan-out case, which would also make it GUI-settable + serialized. Strong fit. |
| G4 | `utils.py:set_ps_synch` / `check_ps_synch` (`:116-188`) | Set / report power-supply sync state across boards | `method` pair on `Group`, or a `device` with a `RW` sync var + `RO` status | `check` returns a summary; consider a `pr.LinkVariable` for the aggregate state so the GUI shows it. |
| G5 | `utils.py:print_hardware` (`:24-50`) | Print BuildStamp/DNA/GitHash/ImageName per board | `method` on `Group` (or `HardwareGroup`) | Read-only convenience; low risk. Could also be a `RO` summary variable. |
| G6 | `utils.py:disable_leds` (`:53-72`) | Stop status-LED blinking on all boards | `method` on `Group` | Trivial; pure register writes. |
| G7 | `client.py` board discovery (`:42-50`) | Enumerate ColumnBoard/RowBoard indices + RowDacDriver handles | Already native to `HardwareGroup` | The regex-over-`dir()` discovery duplicates what `HardwareGroup.ColumnBoard.values()` already provides. Prefer using the tree directly; may not need a new method at all. |
| G8 | `utils.py:save_config`/`save_state`/`load_config` (`:344-397`) | Timestamped config/state save + load | Leave as thin session helpers | These wrap existing `root.SaveConfig/SaveState/LoadConfig`; the only added value is the timestamped path. Keep in the convenience layer, not `Group`. |

**Not moving to Group** (stay in the convenience / analysis layer):
- Acquisition helpers `take_raw` / `multi_raw` / `take_data` (`data.py`) —
  orchestration + local-disk session policy, not a hardware capability. (But
  see Task 4: give `take_raw` a timeout.)
- All of `analysis.py` and `streamreader.py` — offline, no hardware, must not
  depend on `Client`.
- Dead-mask file I/O (`utils.py:make/write/read_dead_masks`) — file-format
  helpers; keep in convenience layer.

> Fill in the "Proposed form" decisions with the user before executing G1–G6.
> G2 and G1 are the highest-value (panic-off and MUX setup are the things every
> user wants) and the best proof-of-concept candidates.

---

## Open decisions (resolve before execution)

1. **Package home + name.** `warm_tdm_api.scripting` vs `.notebook` vs a
   sibling `warm_tdm_tools`. Affects imports in existing notebooks.
2. **Migration cadence.** Do G1–G6 as one pass, or land a proof-of-concept
   (G2 `all_off` + G1 `setup_mux`) first, validate on hardware, then continue?
3. **Constants home** (Task 5): a `constants.py` in the package vs deriving
   `fs`/`sq1fb_to_pA` from the rogue tree.

---

## Tasks

### Task 0 (done): Review + scaffold
- [x] Review PR #61, capture findings and decisions in SPEC.md.
- [x] Create `wtj-refactor` branch off `wtj`.
- [x] Scaffold this plan set.

### Task 1: Correctness fixes (low-risk, do first)
- [ ] Fix README install command to match repo-root `install.sh`.
- [ ] Add `scipy` to `conda.yml`.
- [ ] Add a timeout to the `take_raw` capture-wait loop (`data.py:140-147`).
- [ ] Remove dead `import pandas as pd` (`streamreader.py:33`).
- [ ] Replace `_TesBiasWaveform.py` hardcoded `num_generators = 8` with the
      dynamic count from `_ensureWaveformGenerators`.

### Task 2: Proof-of-concept Group migration (validates architecture)
- [ ] Implement G2 (`all_off`) and G1 (`setup_mux`) as `Group` methods/nodes.
- [ ] Have the convenience-layer functions delegate to the new `Group`
      capability (keep the notebook entry points working).
- [ ] Validate on hardware (user step).

### Task 3: Package rename / rehome
- [ ] Apply the decided name/home from "Open decisions".
- [ ] Update `__init__` imports, add `__all__`, drop `import *` sprawl.
- [ ] Remove import-time `addLibraryPath` side effects from `streamreader.py`.
- [ ] Update existing notebooks / docs that import `warm_tdm_jupyter`.
- [ ] **Document the package** in root `AGENTS.md` and `software/SOFTWARE_GUIDE.md`
      (both currently omit it; AGENTS.md:42 only lists `software/jupyter/`
      notebooks). Add the new name/home to the package-structure sections.

### Task 4: Remaining Group migrations
- [ ] G3–G6 per the table, delegating convenience wrappers as in Task 2.

### Task 5: Analysis + convenience structural cleanup
- [ ] Extract pure `compute_asd` / `channel_timeseries` helpers shared by
      `plot_stream_data` and `analyze_pair`.
- [ ] Move `sq1fb_to_pA` / `fs` calibration constants out of default args.
- [ ] Bound / rethink `StreamData._instances` unbounded registry.

### Task 6: Verification
- [ ] `warm_tdm_api` and the renamed package import cleanly.
- [ ] Notebook entry points still work against live hardware (user step).
- [ ] New `Group` capabilities visible/serializable (SaveConfig round-trip).
- [ ] PR targets `pre-release` (not `main`), per docs/RELEASE.md branch flow.
