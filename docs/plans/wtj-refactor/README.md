# warm_tdm_jupyter → warm_tdm_api.operations refactor (historical)

This refactor is **complete and shipped in [PR #78](https://github.com/slaclab/warm-tdm/pull/78)**
(closes #68, supersedes #61). The detailed plan/progress/spec docs that once
lived here were pruned once the work landed — the code, the PR description, and
the design docs below are now the sources of truth. This stub records what was
done and where the forward-looking pieces went, so the reasoning isn't re-derived.

## What shipped (PR #78)

`warm_tdm_api.operations` — the client-side operational layer for running a Group:
- **Injectable per-Group `Session`** (replaced the `Client` global singleton);
  binds to a `Group` node, derives topology from the tree (no hardcoded
  `//8`/`range(8)`), coordinator = `ColumnBoard[0]`.
- **Operator arc** verbs: tuning wrappers (`run_process`/`sa_tune`/`sq1_tune`/
  `sa_offset`), `stop_and_zero` (was `all_off`), `status()`, explicit
  `StreamData`/path input to the analysis functions.
- **Config-derived unit conversions**: `fs`/`sq1fb_to_pA` from each file's Rogue
  config channel + `CurrentPerLsb`; defensive config read (slaclab/rogue#1282).
- **PID-debug stream** as data model #3 (`PidDebugData`, `plot_pid_debug`,
  canonical `PidDebug` format in `warm_tdm._DataFormats`).
- **Clarity renames**: `calibration.py`→`unit_conversions.py`,
  `formats.py`→`channels.py`.
- **Workflow template**: `software/jupyter/operations_template.{py,ipynb}`.
- Adopted the PR #67 software-cleanup foundation (Group split, unified launcher,
  `maxRows`/`rowAddrBits` separation) and the package rename (history preserved).

## Key design decisions (the durable "why")

- **Client-side vs. server-side (the graduation criterion).** These helpers are
  deliberately client-side for **runtime editability** — a `Group` method needs a
  server restart, which drops tuning state and forces a slow re-tune. Move a
  capability onto `Group` only when it *needs* server-side execution/state
  (continuous loop, GUI button, serialized config); otherwise keep it in
  `operations` and graduate as it stabilizes. See issue #83.
- **`Session` binds to a Group, not the client** — the topology is the Group, and
  this is the seam a multi-Group `Instrument` needs. See issue #80.
- **`warm_tdm_api` vs `warm_tdm` is about the node, not the package** — both
  packages contribute nodes to one runtime tree; capability placement is a
  node-ownership question (the graduation list), not a package-move.
- **Merge, not rebase** for integration (this branch's history was an exception —
  bench notebooks were dropped via a deliberate one-off history rewrite).

## Forward-looking work (promoted to issues)

| Issue | Work | Design authority |
|---|---|---|
| [#80](https://github.com/slaclab/warm-tdm/issues/80) | Multi-Group `Instrument` + federated-vs-not scaling decision | `docs/design/muxed-run-bringup.md` |
| [#81](https://github.com/slaclab/warm-tdm/issues/81) | Bring-up helpers + tune-point save/restore (2 open Qs) | `docs/design/muxed-run-bringup.md` |
| [#82](https://github.com/slaclab/warm-tdm/issues/82) | Self-describing frames + channel-layout cleanup (firmware-track) | `firmware/common/DataChannelization.md` |
| [#83](https://github.com/slaclab/warm-tdm/issues/83) | Graduate operations helpers onto `Group` (G1–G9) | this file (criterion above) |
| [#56](https://github.com/slaclab/warm-tdm/issues/56) | Curate bench notebooks into the repo (policy + strip-outputs) | — |

## Canonical docs

- `firmware/common/DataChannelization.md` — end-to-end data path / channel scheme.
- `docs/design/muxed-run-bringup.md` — muxed-run config layers, ordering,
  tune-point restore.
- `docs/design/row-mapping.md` — logical/physical row addressing.
- `software/SOFTWARE_GUIDE.md` — the operations package + data streaming overview.
