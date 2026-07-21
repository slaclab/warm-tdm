# warm_tdm_jupyter refactor — design

Date: 2026-07-21
Status: in planning

## Goal

Take the notebook-utility code introduced by PR #61 (branch `wtj`, package
`software/python/warm_tdm_jupyter/`) and reshape it into a well-structured,
reusable part of the warm-tdm software stack — **without** rewriting the
analysis math or changing observable behavior for the notebook users who
already depend on it.

Two things drive this effort:

1. The package is named/scoped as "jupyter" but almost none of it is
   Jupyter-specific. It is a general procedural convenience layer over the
   rogue tree plus offline analysis/plotting.
2. Genuinely reusable hardware capabilities (MUX setup, panic-off, cryo
   resistance, PS sync) are trapped in this convenience layer and only
   available to notebook users, when they should be first-class capabilities
   available to everyone (GUI, config scripts, notebooks).

## Background (verified facts)

- The package lives at `software/python/warm_tdm_jupyter/`, a **peer of
  `warm_tdm_api`** on the same import path — not under a separate `jupyter/`
  area as the PR description states.
- Module-by-module, the only genuine Jupyter dependency is
  `client.py:new_session()` importing `jupyter_client.session` to capture a
  session id (`client.py:80-82`). That id (`jupyter_session_id`) is **never
  read anywhere downstream**. Everything else — board discovery, session
  directories, acquisition, hardware config, analysis, plotting — is generic
  Python over the rogue tree and matplotlib.
- `warm_tdm_api` is a **pyrogue-tree package**: every capability is a
  `pr.Device` / `pr.Process` node hung off `Group`, reachable from the GUI and
  serializable via SaveConfig/SaveState. The new code is a **procedural layer**
  that drives that tree through a module-global singleton `Client`.
- PR #61 already demonstrates the correct integration pattern for one piece:
  `TesBiasWaveformProcess` entered `warm_tdm_api` as a `pr.Process`, registered
  in `_Group.py:832` and `__init__.py:11`. The procedural helpers did not get
  that treatment.
- `Group` already holds `self.HardwareGroup` and can iterate boards directly
  via `self.HardwareGroup.ColumnBoard.values()` / `.RowBoard.values()`
  (`_Group.py:356`, `:463`), and already exposes `ColTuneEnable`, `TesBias`,
  the `*ForceCurrent` arrays, etc. So the hardware capabilities in `utils.py`
  can be expressed as `Group` methods with no new plumbing.
- The repo's own `software/SOFTWARE_GUIDE.md` documents the **`GroupLinkVariable`
  pattern** for cross-board array access (RW scalar or array fanned out to a
  `dependencies=[...]` list across boards, gated by `tuneEnVar`). This is the
  idiomatic path for the per-channel/per-board register fan-outs in `utils.py`
  (e.g. `set_cryo_resistance`) and is preferable to raw board loops because it
  is also GUI-settable and config-serialized.
- Branch flow (`docs/RELEASE.md`): feature → `pre-release` → `main`. This work
  merges to `pre-release`.
- Neither `AGENTS.md` nor `SOFTWARE_GUIDE.md` currently mentions the new
  package; `AGENTS.md:42` only lists the separate `software/jupyter/` notebook
  dir. Documenting the renamed package is part of the rename task.

## Accepted constraints (explicitly OK, not to be "fixed")

- **Single live system / global `Client` per process.** Not being able to test
  without live hardware, and not being able to drive two systems from one
  process, are understood and acceptable limits. We are not adding multi-system
  support. The `Client` structure is still not great and we intend to reduce
  reliance on it, but removing the single-system assumption is out of scope.

## Scope

### 1. Rename / rehome the package → `warm_tdm_api.operations` (RESOLVED)

Drop the "jupyter" name. The package becomes the **`operations` subpackage of
`warm_tdm_api`** — the client-side operational layer for running the system
(acquisition + setup + analysis), deliberately runtime-editable and
production-bound. A subpackage (not a sibling) because it is API-coupled.

Keep it as **one cohesive layer**. Do NOT smear its global-`Client` procedural
style into the `warm_tdm_api` `_Xxx.py` device modules — the two paradigms stay
visibly distinct. (Name rationale + rejected alternatives: PLAN "Open decisions".)

### 2. Graduate reusable hardware capabilities into the rogue tree — as they mature

**Key rationale (from the original author):** these functions were kept
client-side on purpose, for **runtime editability**. A `Group` method runs
server-side, so changing it needs a server restart, which drops tuning state and
forces a slow re-tune. So capabilities graduate into `Group` **individually, as
they stabilize**, not in a batch. The exception is anything that *needs*
server-side execution (continuous loops, GUI, serialized state) — e.g.
`TesBiasWaveformProcess`, already correctly in `Group`.

The deeper fix the author noted: if re-tuning were as fast as MCE, restarts would
be cheap and this pressure would largely disappear, enabling broader migration.
That is a separate, larger effort — out of scope here.

See the **"Capabilities to move to Group — graduation candidates"** table in
PLAN.md (with the client/server graduation criterion) — the running list the
user asked to start.

### 3. Structural / quality cleanup of the remaining convenience + analysis code

- Factor duplicated ASD/time-domain computation out of `plot_stream_data` /
  `analyze_pair` into pure, testable helpers.
- Move calibration constants (`sq1fb_to_pA`, `fs`) out of function-default
  arguments into a config/constants location (or derive from the tree).
- Bound / rethink the `StreamData._instances` global registry.

### 4. Correctness fixes (do regardless of the larger restructuring)

- README install command says `bash scripts/install.sh` but the file is at
  repo-root `install.sh` — the command fails as written.
- `scipy` is imported by `analysis.py` but missing from `conda.yml`.
- `take_raw` polling loop (`data.py:140-147`) has no timeout — can hang forever.
- Remove dead `import pandas as pd` (`streamreader.py:33`).
- `_TesBiasWaveform.py` hardcodes `num_generators = 8` (`:146,:155`) despite
  having dynamic generator-sizing logic — use the dynamic count.

## Out of scope

- Rewriting the analysis math (Welch/ASD, noise-model fit, SQ1 curve plotting).
- Removing the single-system / global-`Client` assumption (see constraints).
- Any firmware/RTL change. The `all_off` firmware bug noted in `utils.py` is
  tracked there, not here.
