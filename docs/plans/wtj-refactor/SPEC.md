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

## Accepted constraints (explicitly OK, not to be "fixed")

- **Single live system / global `Client` per process.** Not being able to test
  without live hardware, and not being able to drive two systems from one
  process, are understood and acceptable limits. We are not adding multi-system
  support. The `Client` structure is still not great and we intend to reduce
  reliance on it, but removing the single-system assumption is out of scope.

## Scope

### 1. Rename / rehome the package (decision pending — see PLAN "Open decisions")

Drop the "jupyter" name. Candidate homes:
- `warm_tdm_api` subpackage (e.g. `warm_tdm_api.scripting` or `.notebook`)
- sibling package `warm_tdm_tools`

Keep it as **one cohesive procedural layer**. Do NOT smear its global-`Client`
procedural style into the `warm_tdm_api` `_Xxx.py` device modules — the two
paradigms should stay visibly distinct.

### 2. Migrate reusable hardware capabilities down into the rogue tree

Move capabilities that everyone should have (not just notebook users) onto
`Group` (as methods) or into small `pr.Process` / `pr.Device` nodes. See the
**"Capabilities to move to Group"** table in PLAN.md — this is the running list
the user asked to start.

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
