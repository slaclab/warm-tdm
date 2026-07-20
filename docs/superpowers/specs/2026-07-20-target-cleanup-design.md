# Firmware target cleanup — design

Date: 2026-07-20
Status: approved for planning

## Goal

Reduce inconsistency and cruft in the `firmware/targets/` set before cutting a
release, **without** a wholesale renaming scheme and **without** touching the
rogue software hierarchy. This is contained hygiene, not a redesign.

A broader `Dev/Bicep`-style naming scheme was explored and rejected: it did not
read well, and — although verified not to affect the rogue software — it was
more churn than warranted right now. This spec captures only the changes we
agreed to.

## Background (verified facts)

- **Target directory names do not appear in the rogue software.** No references
  to `ColumnFpgaBoard325Coordinator`, `ColumnFpgaBoard0`, `RowFpgaBoard325`, or
  `ColumnFpgaBoardAwaXe` exist under `firmware/python`, `software/python`, or
  `software/scripts`. The rogue device classes (`ColumnFpgaBoard`,
  `RowFpgaBoard`, `ColumnAwaXeFpgaBoard`, …) are named after the top-level RTL
  entities, not the build targets. Renaming a target therefore cannot break the
  rogue hierarchy.
- **No sibling `ruckus.tcl` references the dirs being renamed.** The variant
  targets `loadSource` *from* `ColumnFpgaBoard/` and `RowFpgaBoard/` (which are
  NOT renamed), so renaming the variant dirs breaks no internal path.
- **The only config file that names these targets is `firmware/releases.yaml`.**
- The trailing `0` suffix and the `Coordinator` suffix encode the *same* build
  option: `RING_ADDR_0_G=true` (ring node-0 / drives the stack's ethernet).
  This duplication is the main inconsistency being removed.

## Scope

### 1. Renames — standardize the ring-coordinator token on `Coord`

| Current target dir | New target dir | Rationale |
|---|---|---|
| `ColumnFpgaBoard0` | `ColumnFpgaBoardCoord` | `0` meant ring-coordinator; make it explicit and consistent. |
| `RowFpgaBoard0` | `RowFpgaBoardCoord` | same |
| `ColumnFpgaBoard325Coordinator` | `ColumnFpgaBoard325Coord` | `Coordinator` → `Coord` |
| `ColumnFpgaBoard325Coordinator10G` | `ColumnFpgaBoard325Coord10G` | `Coordinator` → `Coord` |

Notes:
- `ColumnFpgaBoardCoord` (formerly `ColumnFpgaBoard0`) keeps its extra generics
  `GEN_ADC_FILTER_G=false ROW_ADDR_BITS_G=5` unchanged — they are preserved
  as-is by this rename. This spec does not judge whether they are stale.
- Each renamed dir's `ruckus.tcl` continues to `loadSource` from
  `../ColumnFpgaBoard/rtl` or `../RowFpgaBoard/rtl` — those paths are unchanged
  and keep working.

### 2. Archive legacy targets to `firmware/targets/legacy/`

Move (no rename) the following into `firmware/targets/legacy/`:

- `ColumnModule`
- `ColumnModule0`
- `RowModule`
- `RowModule0`
- `RowModuleC00`

They move together, so their relative `../ColumnModule` / `../RowModule`
`loadSource` paths continue to resolve within `legacy/`.

### 3. releases.yaml updates

- Rename the four catalog keys and their `ImageDir` paths to match the renamed
  dirs (see table in §1).
- Update the two renamed entries in the `warmTdm` release `Targets` list:
  - `ColumnFpgaBoard325Coordinator` → `ColumnFpgaBoard325Coord`
  - `ColumnFpgaBoard325Coordinator10G` → `ColumnFpgaBoard325Coord10G`
- Remove the legacy `ColumnModule` and `ColumnModule0` entries from the
  `Targets` catalog entirely (they are legacy, in no release, and should not be
  advertised). The Row `*Module*` targets were never in the catalog.

## Explicitly out of scope / untouched

- `ColumnFpgaBoard`, `RowFpgaBoard`, `RowFpgaBoard325`, `ColumnFpgaBoardAwaXe` —
  names unchanged.
- `ColumnAu25p` — **kept** for now. This was an Artix UltraScale+ AU25P *chip*
  exploration build; no board was ever built around it. (It has no
  Makefile/ruckus.tcl, only stray Vivado logs + an `images/` dir.) Left in place
  per decision; not renamed, not deleted.
- Vesper/Boreas `~` backup files in `firmware/python/warm_tdm/` — left as-is.
- No `Dev`/`Bicep` board-prefix scheme. No FPGA-part tokens beyond the existing
  `325`.
- No changes to rogue software (`firmware/python`, `software/`), RTL entities,
  or generics (beyond the preserved `ColumnFpgaBoardCoord` set).
- BICEP: no targets created. The new BICEP board revision is future work with no
  RTL/target here yet.

## Impact & risk

- **Low.** The rename is a `git mv` of four dirs + a move of five legacy dirs +
  a handful of edits to one YAML file. No cross-target `ruckus.tcl` path
  updates are needed.
- Existing build artifacts inside the renamed dirs' `images/` carry the old name
  in their filenames. These are regenerated on the clean release rebuild, so
  stale-named artifacts are a non-issue; they may be pruned opportunistically.
- The `sfs-check-release` linter should report 0 errors after the change
  (release target list must still resolve to catalog entries that have real
  dirs with Makefile + ruckus.tcl).

## Verification

1. `git mv` history is preserved for the renamed/moved dirs.
2. `firmware/targets/build_release.sh --list` resolves the `warmTdm` release to
   the renamed targets without error.
3. `sfs-lint release .` → 0 errors.
4. A clean rebuild of the four release targets (Vivado 2024.1) produces images
   under the new dir names.
