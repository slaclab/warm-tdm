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

### 1. Renames — make the FPGA part explicit and standardize the ring token on `Coord`

Every active target name must carry its FPGA part (`160` for XC7K160T, `325`
for XC7K325T) in the existing part slot — immediately after `FpgaBoard`, matching
the current `...FpgaBoard325...` targets. The ring-coordinator option is
standardized on the `Coord` token (the old trailing `0` and `Coordinator`
suffixes both meant `RING_ADDR_0_G=true`). Segment order is
`Function·FpgaBoard·Part·[FrontEnd]·[Coord]·[10G]`.

| Current target dir | New target dir | Part | Rationale |
|---|---|---|---|
| `ColumnFpgaBoard` | `ColumnFpgaBoard160` | 160T | add part token |
| `ColumnFpgaBoard0` | `ColumnFpgaBoard160Coord` | 160T | add part; `0` → `Coord` |
| `ColumnFpgaBoard325Coordinator` | `ColumnFpgaBoard325Coord` | 325T | `Coordinator` → `Coord` |
| `ColumnFpgaBoard325Coordinator10G` | `ColumnFpgaBoard325Coord10G` | 325T | `Coordinator` → `Coord` |
| `ColumnFpgaBoardAwaXe` | `ColumnFpgaBoard325AwaXeCoord10G` | 325T | add part; expose the Coord + 10G generics the target already sets |
| `RowFpgaBoard` | `RowFpgaBoard160` | 160T | add part token |
| `RowFpgaBoard0` | `RowFpgaBoard160Coord` | 160T | add part; `0` → `Coord` |
| `RowFpgaBoard325` | `RowFpgaBoard325` | 325T | already has part; unchanged |

Notes:
- `ColumnFpgaBoard160Coord` (formerly `ColumnFpgaBoard0`) keeps its extra generics
  `GEN_ADC_FILTER_G=false ROW_ADDR_BITS_G=5` unchanged — preserved as-is by this
  rename. This spec does not judge whether they are stale.
- **`ColumnFpgaBoard` and `RowFpgaBoard` are the canonical dirs that physically
  hold the shared RTL/sim/xdc.** The 325/Coord variants `loadSource` from them via
  `../ColumnFpgaBoard/rtl` etc. Renaming these two canonical dirs to `*160`
  therefore REQUIRES updating those relative paths in every referencing
  `ruckus.tcl` to `../ColumnFpgaBoard160/...` / `../RowFpgaBoard160/...`.
- The `set_property top {ColumnFpgaBoard}` / `{RowFpgaBoard}` lines name the
  **RTL top entity**, not the directory. These are NOT renamed — the entity names
  (and thus the rogue device classes) stay `ColumnFpgaBoard` / `RowFpgaBoard`.
- `ColumnFpgaBoard325AwaXe*` builds its own top entity `ColumnFpgaBoardAwaXe`
  from its own `rtl/`; it does not loadSource from a sibling, so only its own
  dir name and catalog entry change.

### 2. Archive legacy targets to `firmware/targets/legacy/`

Move (no rename) the following into `firmware/targets/legacy/`:

- `ColumnModule`
- `ColumnModule0`
- `RowModule`
- `RowModule0`
- `RowModuleC00`

They move together, so their relative `../ColumnModule` / `../RowModule`
`loadSource` paths continue to resolve within `legacy/`.

### 3. Update cross-references to the renamed canonical dirs

Because `ColumnFpgaBoard` → `ColumnFpgaBoard160` and `RowFpgaBoard` →
`RowFpgaBoard160`, every `ruckus.tcl` that `loadSource`/`loadConstraints` from
those dirs via a relative `../` path must be updated:

- `../ColumnFpgaBoard/{rtl,sim,xdc}` → `../ColumnFpgaBoard160/{rtl,sim,xdc}` in
  the Column 325 Coord and 325 Coord10G targets.
- `../RowFpgaBoard/{rtl,sim,xdc}` → `../RowFpgaBoard160/{rtl,sim,xdc}` in the
  Row Coord and Row 325 targets.

The `set_property top {ColumnFpgaBoard}` / `{RowFpgaBoard}` lines are the RTL
entity name and are left unchanged.

### 4. releases.yaml updates

- Rename all seven affected catalog keys and their `ImageDir` paths to match the
  renamed dirs (see table in §1). `RowFpgaBoard325` is unchanged.
- Update the four entries in the `warmTdm` release `Targets` list:
  - `ColumnFpgaBoard325Coordinator` → `ColumnFpgaBoard325Coord`
  - `ColumnFpgaBoard325Coordinator10G` → `ColumnFpgaBoard325Coord10G`
  - `RowFpgaBoard` → `RowFpgaBoard160`
  - `RowFpgaBoard325` → unchanged
- Remove the legacy `ColumnModule` and `ColumnModule0` entries from the
  `Targets` catalog entirely (they are legacy, in no release, and should not be
  advertised). The Row `*Module*` targets were never in the catalog.

### 5. Aggregate Makefile

`firmware/targets/Makefile` hardcodes the target list and uses each name as a
build path. Update `TARGETS` to the eight renamed active target names and drop
the archived Module targets.

## Explicitly out of scope / untouched

- `RowFpgaBoard325` name — already carries its part, unchanged.
- `ColumnAu25p` — **kept** for now. This was an Artix UltraScale+ AU25P *chip*
  exploration build; no board was ever built around it. (It has no
  Makefile/ruckus.tcl, only stray Vivado logs + an `images/` dir.) Left in place
  per decision; not renamed, not deleted.
- Vesper/Boreas `~` backup files in `firmware/python/warm_tdm/` — left as-is.
- No `Dev`/`Bicep` board-prefix scheme.
- No changes to rogue software (`firmware/python`, `software/`), RTL top entity
  names, or generics (beyond the preserved `ColumnFpgaBoard160Coord` set).
- BICEP: no targets created. The new BICEP board revision is future work with no
  RTL/target here yet.

## Impact & risk

- **Low–moderate.** `git mv` of seven active dirs + move of five legacy dirs +
  path edits in four referencing `ruckus.tcl` files + edits to `releases.yaml`
  and the aggregate `Makefile`. The one real hazard is the relative-path updates
  when the canonical `*FpgaBoard` dirs are renamed — enumerated in §3 and
  verified by a build-config check, not left implicit.
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
