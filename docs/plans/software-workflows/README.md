# Software entry points and measurement notebooks

## Goal

Separate supported operator tools, bench/cosim verification, reusable notebook
templates and historical measurement records. A copied, executed notebook belongs
with its data outside Git and can be reopened without creating another run.

## Decisions

- Keep the server, local/remote GUI and PROM tools; replace the stale interactive
  client bootstrap and consolidate the three file readers.
- Keep all bench/cosim checks and tests. Move bench tools to `software/hwtest/`;
  share verification routines with the interactive notebooks.
- Maintain output-free templates under `software/notebooks/`, with percent-format
  Python as the source and a deterministic notebook generation/check command.
- Store new measurement runs outside the checkout (or in ignored `runs/`). Each
  contains an executed notebook, provenance, configuration, data and figures.
  Creating a run is offline; reconnecting attaches to its exact directory.
- Preserve existing historical notebook bytes under `docs/reference/measurements/`.
  Keep the unused native extension as an explicitly unmaintained example.
- Keep the existing `warm_tdm_api` package layout. No firmware behavior changes,
  staging, commits, or issue publication are part of this work.

## Current state

Implemented locally. The [software index](../../../software/README.md) maps every
moved/retired entry point; [notebook runs](../../notebook-runs.md) documents the
supported workflow and its compatibility boundary. `new_run.py` creates records
offline; `ops.connect(run_dir=...)` reuses existing data/config directories with
no fallback. The lightweight `warm_tdm_run` package is included by the release
selector without importing Rogue. Checkout notebook tools remain checkout tools.

Seven maintained templates now share their batch verification implementations
or operations helpers. Percent-format Python is authoritative; a deterministic
standard-library converter generates the output-free notebooks and checks them
in CI. Copies remain independent. The hardware template consistently uses its
earlier notebook's 8×10 example, with explicit fixture settings. Gain sweeps use
actual logical-row indices, restore P, detect opposing per-row flux excursions,
and apply a chosen candidate only to the measured column. Completed candidates
survive interruption; capture/health/analysis steps remain available.

All six historical notebooks (four measurements plus the old template and
latency exploration) were moved byte-for-byte with outputs intact. The native
extension is labeled unmaintained under `software/examples/cpp_extension/`.
Release script paths, notebook ignore rules, imports and active documentation
links were updated. The root conda file was already the only tracked environment
definition when implementation started.

Affected areas: `software/scripts`, `software/hwtest`, `software/cosim`,
`software/notebooks`, operations session/output helpers, tests,
`firmware/releases.yaml`, documentation and notebook ignore rules.

## Evidence and next step

Local validation on 2026-09-23:

- `python -m pytest software/tests -q`: **256 passed, 83 subtests passed**.
- Notebook consistency, active Python syntax, packaged script existence,
  relative documentation links, ignore rules and `git diff --check` passed.
- An offline CLI smoke created a run outside the checkout, with source
  provenance and editable cosim profiles. Tests cover reconnection/relocation,
  missing storage, failed checks, portable bootstrap, interrupted sweeps and
  distinct acquisition filenames.
- The actual ruckus release selector includes `warm_tdm_run` as a package;
  importing a copied installed layout succeeds without Rogue and does not
  attribute an unrelated checkout's revision to the installed code.
- Original and relocated historical notebook bytes match exactly.

No owning issue/PR has been assigned. Next: review the working-tree changes,
then exercise a copied notebook with a real Rogue server on the shared
filesystem: capture, save settings/outputs, restart the kernel, reconnect into
the same record, and capture again without overwriting earlier data. Exercise
the moved bench scripts and batch-backed cosim notebooks on their respective
fixtures, and smoke-test packaged launchers in a release environment. These
runtime/bench checks were not performed locally (Rogue/VCS/hardware unavailable).
Record acceptance on its owning issue when assigned; unit tests are not physical
acceptance. Nothing has been staged or committed.
