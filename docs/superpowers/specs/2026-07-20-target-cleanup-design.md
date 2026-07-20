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
- The `set_property top {ColumnFpgaBoard}` / `{RowFpgaBoard}` lines name the
  **RTL top entity**, not the directory. These are NOT renamed — the entity names
  (and thus the rogue device classes) stay `ColumnFpgaBoard` / `RowFpgaBoard` /
  `ColumnFpgaBoardAwaXe`.
- Once the shared board code moves into `common/warm_tdm/` (§2), no target
  contains RTL, and no target references another via a relative `../` path — so
  each rename above is an isolated `git mv` of a now-thin target dir plus a
  catalog edit. This is what makes the rename safe.

### 2. Move shared board code into `common/warm_tdm/` (the real fix)

**Problem being fixed:** Today `ColumnFpgaBoard/` and `RowFpgaBoard/` are
*canonical* target dirs that physically hold the board top entity, its testbench,
and its pinout `.xdc`. Every other variant reaches into them via
`loadSource "$::DIR_PATH/../ColumnFpgaBoard/rtl"`. That makes one target's *name*
load-bearing in its siblings' build scripts: it cannot be renamed, moved, or
deleted without editing every referrer, and it forces exactly the fragile path
edits this rename would otherwise require.

**Fix:** move the board tops (and the Column testbench) into the existing shared
RTL library `common/warm_tdm/`, so every target — including the plain 160 one —
becomes a thin, uniform `Makefile + ruckus.tcl` that selects a top entity and
generics. No target is canonical; there are no `../` cross-references.

Files to move (tracked files only; untracked `~` editor backups are not moved):

| From | To |
|---|---|
| `targets/ColumnFpgaBoard/rtl/ColumnFpgaBoard.vhd` | `common/warm_tdm/rtl/ColumnFpgaBoard.vhd` |
| `targets/ColumnFpgaBoardAwaXe/rtl/ColumnFpgaBoardAwaXe.vhd` | `common/warm_tdm/rtl/ColumnFpgaBoardAwaXe.vhd` |
| `targets/RowFpgaBoard/rtl/RowFpgaBoard.vhd` | `common/warm_tdm/rtl/RowFpgaBoard.vhd` |
| `targets/ColumnFpgaBoard/sim/ColumnFpgaBoardTb.vhd` | `common/warm_tdm/sim/ColumnFpgaBoardTb.vhd` |
| `targets/ColumnFpgaBoard/xdc/ColumnFpgaBoard.xdc` | `common/warm_tdm/xdc/ColumnFpgaBoard.xdc` |
| `targets/ColumnFpgaBoardAwaXe/xdc/ColumnFpgaBoardAwaXe.xdc` | `common/warm_tdm/xdc/ColumnFpgaBoardAwaXe.xdc` |
| `targets/RowFpgaBoard/xdc/RowFpgaBoard.xdc` | `common/warm_tdm/xdc/RowFpgaBoard.xdc` |

How loading works after the move — two distinct mechanisms, deliberately:

- **RTL + testbenches: auto-loaded, shared.** `common/warm_tdm/ruckus.tcl`
  already does `loadSource -dir rtl` and `loadSource -sim_only -dir sim` — so
  every target that does `loadRuckusTcl .../common/warm_tdm` gets all board tops
  in its fileset. Having multiple board tops in the fileset is harmless: only the
  entity named by `set_property top` is synthesized; the rest are elaborated
  away. (This is exactly how surf loads its entire library into every project.)
- **Pinout `.xdc`: explicit per target, NOT auto-loaded.** The `loadConstraints
  -dir xdc` line in `common/warm_tdm/ruckus.tcl` is (and must stay) commented
  out — otherwise every target would pull in *both* the Column and Row pinouts
  and conflict. Each target instead loads only its own pinout by exact path,
  right next to the `WarmTdmCore2.xdc` it already loads that way:
  `loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoard.xdc`.

Resulting per-target `ruckus.tcl` shape (uniform across all eight targets):
```tcl
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl
loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm           ;# board tops + TBs + shared RTL
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoard.xdc  ;# this target's pinout
set_property top {ColumnFpgaBoard} [get_filesets sources_1]
set_property generic "... RING_ADDR_0_G=true ETH_10G_G=false" [current_fileset]
```

Consequences accepted:
- Every target compiles-in all three board top entities. Unused ones are
  elaborated away — no bitstream impact, negligible parse cost.
- `targets/ColumnFpgaBoardAwaXe/sim/ColumnFpgaBoardTb.vhd` is a *divergent* copy
  of the Column TB that shares the same entity name but is **not loaded** (its
  `loadSource -sim_only` line is commented out). To avoid an entity-name
  collision in the shared `sim/`, it is NOT moved; it stays as dead code in the
  AwaXe target dir and is noted as a leftover, not migrated.
- AGENTS.md currently says "board pinout in `targets/*/xdc/`". That convention
  line is updated to reflect pinouts now living in `common/warm_tdm/xdc/`.

### 3. Archive legacy targets to `firmware/targets/legacy/`

Move (no rename) the following into `firmware/targets/legacy/`:

- `ColumnModule`
- `ColumnModule0`
- `RowModule`
- `RowModule0`
- `RowModuleC00`

They move together, so their relative `../ColumnModule` / `../RowModule`
`loadSource` paths continue to resolve within `legacy/`. (These legacy targets
are not migrated to the `common/`-hosted pattern of §2 — they keep their own
canonical-dir arrangement, isolated under `legacy/`.)

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

- **Moderate.** The substantive step is §2 (moving board tops + pinouts into
  `common/warm_tdm/` and rewriting every target `ruckus.tcl` to the uniform
  thin shape). The renames (§1), archive (§3), yaml (§4), and Makefile (§5) are
  then mechanical.
- **The one real hazard is a build regression from the §2 move**, not a path
  string: if the common `xdc` `-dir` auto-load were enabled, or a target loaded
  the wrong pinout, a build would fail place-and-route. Mitigated by loading
  each pinout explicitly by path and by the verification below. This risk is
  only fully closed by an actual Vivado build (see Verification step 4).
- Because no target references another via `../` after §2, the renames
  themselves carry essentially no cross-reference risk.
- Existing build artifacts inside the renamed dirs' `images/` carry the old name
  in their filenames. These are regenerated on the clean release rebuild, so
  stale-named artifacts are a non-issue; they may be pruned opportunistically.
- The `sfs-check-release` linter should report 0 errors after the change
  (release target list must still resolve to catalog entries that have real
  dirs with Makefile + ruckus.tcl).

## Verification

1. `git mv` history is preserved for the renamed/moved files and dirs.
2. Every target `ruckus.tcl` loads exactly one board pinout `.xdc` (its own) by
   explicit path, and the `common/warm_tdm/ruckus.tcl` `xdc -dir` auto-load
   stays disabled.
3. `firmware/targets/build_release.sh --list` resolves the `warmTdm` release to
   the renamed targets without error.
4. `sfs-lint release .` → 0 errors.
5. A clean rebuild of the four release targets (Vivado 2024.1) produces images
   under the new dir names — this is the definitive check that the §2 source
   reorganization did not break synthesis/constraints.
