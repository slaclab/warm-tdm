# Firmware Target Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the shared board RTL/pinouts into `common/warm_tdm/` so no target owns code another reaches into, then give every active target an explicit `160`/`325` part token and a consistent `Coord` ring token, archive the legacy `*Module*` targets, and prune stale `releases.yaml` entries — without touching the rogue software hierarchy.

**Architecture:** The board top entities (`ColumnFpgaBoard.vhd`, `RowFpgaBoard.vhd`, `ColumnFpgaBoardAwaXe.vhd`), the Column testbench, and the three pinout `.xdc` files move into the existing shared library `common/warm_tdm/`. RTL + TBs are auto-loaded into every target by `common/warm_tdm/ruckus.tcl`; each target names its own top via `set_property top` and loads only its own pinout `.xdc` by explicit path. After the move, every target `ruckus.tcl` is a uniform thin file with no `../` cross-references, so renaming/archiving targets is mechanical.

**Tech Stack:** Bash, `git mv`, Edit/Write for `ruckus.tcl` rewrites, SLAC ruckus build system, `sfs-lint` release linter, `build_release.sh --list`. Definitive correctness requires a Vivado 2024.1 build (out of scope for the coding steps; called out in final verification).

**Spec:** [docs/superpowers/specs/2026-07-20-target-cleanup-design.md](../../superpowers/specs/2026-07-20-target-cleanup-design.md)

---

## Reference tables

### Rename map
| Current dir | New dir | Top entity | Generics (beyond defaults) | Strategy |
|---|---|---|---|---|
| `ColumnFpgaBoard` | `ColumnFpgaBoard160` | `ColumnFpgaBoard` | (none — defaults) | — |
| `ColumnFpgaBoard0` | `ColumnFpgaBoard160Coord` | `ColumnFpgaBoard` | `RING_ADDR_0_G=true ETH_10G_G=false GEN_ADC_FILTER_G=false ROW_ADDR_BITS_G=5` | PostRoutePhysOpt |
| `ColumnFpgaBoard325Coordinator` | `ColumnFpgaBoard325Coord` | `ColumnFpgaBoard` | `RING_ADDR_0_G=true ETH_10G_G=false` | — |
| `ColumnFpgaBoard325Coordinator10G` | `ColumnFpgaBoard325Coord10G` | `ColumnFpgaBoard` | `RING_ADDR_0_G=true ETH_10G_G=true` | PostRoutePhysOpt |
| `ColumnFpgaBoardAwaXe` | `ColumnFpgaBoard325AwaXeCoord10G` | `ColumnFpgaBoardAwaXe` | `RING_ADDR_0_G=true ETH_10G_G=true` | — |
| `RowFpgaBoard` | `RowFpgaBoard160` | `RowFpgaBoard` | (none — defaults) | — |
| `RowFpgaBoard0` | `RowFpgaBoard160Coord` | `RowFpgaBoard` | `RING_ADDR_0_G=true` | — |
| `RowFpgaBoard325` | `RowFpgaBoard325` (unchanged) | `RowFpgaBoard` | (none — defaults) | — |

Each target loads pinout: Column* → `ColumnFpgaBoard.xdc`; AwaXe → `ColumnFpgaBoardAwaXe.xdc`; Row* → `RowFpgaBoard.xdc`.

### Shared-code move map (tracked files only)
| From | To |
|---|---|
| `targets/ColumnFpgaBoard/rtl/ColumnFpgaBoard.vhd` | `common/warm_tdm/rtl/ColumnFpgaBoard.vhd` |
| `targets/ColumnFpgaBoardAwaXe/rtl/ColumnFpgaBoardAwaXe.vhd` | `common/warm_tdm/rtl/ColumnFpgaBoardAwaXe.vhd` |
| `targets/RowFpgaBoard/rtl/RowFpgaBoard.vhd` | `common/warm_tdm/rtl/RowFpgaBoard.vhd` |
| `targets/ColumnFpgaBoard/sim/ColumnFpgaBoardTb.vhd` | `common/warm_tdm/sim/ColumnFpgaBoardTb.vhd` |
| `targets/ColumnFpgaBoard/xdc/ColumnFpgaBoard.xdc` | `common/warm_tdm/xdc/ColumnFpgaBoard.xdc` |
| `targets/ColumnFpgaBoardAwaXe/xdc/ColumnFpgaBoardAwaXe.xdc` | `common/warm_tdm/xdc/ColumnFpgaBoardAwaXe.xdc` |
| `targets/RowFpgaBoard/xdc/RowFpgaBoard.xdc` | `common/warm_tdm/xdc/RowFpgaBoard.xdc` |

### Legacy archive map
`ColumnModule`, `ColumnModule0`, `RowModule`, `RowModule0`, `RowModuleC00` → `firmware/targets/legacy/<same-name>` (unchanged internally).

### Deleted
- `targets/ColumnFpgaBoardAwaXe/sim/ColumnFpgaBoardTb.vhd` — stale unused near-copy of the Column TB (never loaded, never a sim top, `AWAXE_G=false`, instantiates the generic `ColumnFpgaBoardModel`; does not test AwaXe). Deleted in Task 2 (git history preserves it).

### Not moved / untouched
- `ColumnAu25p`, Vesper/Boreas `~` backups, RTL top-entity names, generics.

---

## Task 1: Move shared board code into `common/warm_tdm/`

**Files:**
- Move: seven tracked files per the "Shared-code move map" above.
- Modify: `firmware/common/warm_tdm/ruckus.tcl` (confirm xdc `-dir` stays disabled).

- [ ] **Step 1: git mv the RTL, testbench, and pinout files into common/**

Run from repo root:
```bash
cd firmware
git mv targets/ColumnFpgaBoard/rtl/ColumnFpgaBoard.vhd            common/warm_tdm/rtl/ColumnFpgaBoard.vhd
git mv targets/ColumnFpgaBoardAwaXe/rtl/ColumnFpgaBoardAwaXe.vhd  common/warm_tdm/rtl/ColumnFpgaBoardAwaXe.vhd
git mv targets/RowFpgaBoard/rtl/RowFpgaBoard.vhd                  common/warm_tdm/rtl/RowFpgaBoard.vhd
git mv targets/ColumnFpgaBoard/sim/ColumnFpgaBoardTb.vhd         common/warm_tdm/sim/ColumnFpgaBoardTb.vhd
git mv targets/ColumnFpgaBoard/xdc/ColumnFpgaBoard.xdc          common/warm_tdm/xdc/ColumnFpgaBoard.xdc
git mv targets/ColumnFpgaBoardAwaXe/xdc/ColumnFpgaBoardAwaXe.xdc common/warm_tdm/xdc/ColumnFpgaBoardAwaXe.xdc
git mv targets/RowFpgaBoard/xdc/RowFpgaBoard.xdc                common/warm_tdm/xdc/RowFpgaBoard.xdc
```

- [ ] **Step 2: Verify the files landed in common/ and left the target dirs**

Run:
```bash
cd firmware
ls common/warm_tdm/rtl/ColumnFpgaBoard.vhd common/warm_tdm/rtl/ColumnFpgaBoardAwaXe.vhd common/warm_tdm/rtl/RowFpgaBoard.vhd
ls common/warm_tdm/sim/ColumnFpgaBoardTb.vhd
ls common/warm_tdm/xdc/ColumnFpgaBoard.xdc common/warm_tdm/xdc/ColumnFpgaBoardAwaXe.xdc common/warm_tdm/xdc/RowFpgaBoard.xdc
```
Expected: all seven paths listed, no errors.

- [ ] **Step 3: Confirm the common ruckus.tcl auto-loads rtl+sim but NOT xdc -dir**

`common/warm_tdm/ruckus.tcl` already loads `rtl` and `sim` by `-dir` and has the
`loadConstraints -dir "$::DIR_PATH/xdc"` line commented out. Verify this is
still true (it is critical: an enabled xdc `-dir` would load every board pinout
into every target and conflict).

Run:
```bash
cd firmware
grep -nE 'loadSource.*-dir.*rtl|loadSource.*-dir.*sim' common/warm_tdm/ruckus.tcl
grep -nE 'loadConstraints.*-dir.*xdc' common/warm_tdm/ruckus.tcl
```
Expected: the two `loadSource ... -dir ... rtl`/`sim` lines are present and NOT
commented; the `loadConstraints -dir ... xdc` line is present but commented
(begins with `#`). If it is NOT commented, comment it out now and note it in the
commit.

- [ ] **Step 4: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware
git commit -m "Move board tops, TB, and pinouts into common/warm_tdm/

Relocate ColumnFpgaBoard/RowFpgaBoard/ColumnFpgaBoardAwaXe top entities, the
Column testbench, and the three board pinout .xdc files into the shared
common/warm_tdm/ library. RTL+sim are auto-loaded into every target; pinouts
stay explicit per-target (common xdc -dir load remains disabled). This ends
the canonical-dir pattern where variants reached into a sibling via ../.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Rewrite + rename the Column targets

Each Column target `ruckus.tcl` is rewritten to the uniform thin shape (no `../`
paths; explicit `set_property top`; explicit pinout by path) and the dir is
renamed. **Setting the top explicitly is now mandatory** — with all three board
tops in the shared fileset, Vivado can no longer auto-detect a single top.

**Files:**
- Delete: `targets/ColumnFpgaBoardAwaXe/sim/ColumnFpgaBoardTb.vhd` (stale unused TB).
- Modify then rename five Column target `ruckus.tcl` + dirs per the Rename map.

- [ ] **Step 1: Delete the stale AwaXe testbench**

This must happen before the AwaXe dir is renamed. It is unused dead code that
would otherwise collide with the shared Column TB entity name.

Run:
```bash
cd firmware/targets
git rm ColumnFpgaBoardAwaXe/sim/ColumnFpgaBoardTb.vhd
```
Expected: the file is staged for deletion. (If the `sim/` dir is now empty of
tracked files, that is fine — git does not track empty dirs.)

- [ ] **Step 2: Rename the five Column dirs**

Run:
```bash
cd firmware/targets
git mv ColumnFpgaBoard ColumnFpgaBoard160
git mv ColumnFpgaBoard0 ColumnFpgaBoard160Coord
git mv ColumnFpgaBoard325Coordinator ColumnFpgaBoard325Coord
git mv ColumnFpgaBoard325Coordinator10G ColumnFpgaBoard325Coord10G
git mv ColumnFpgaBoardAwaXe ColumnFpgaBoard325AwaXeCoord10G
```

- [ ] **Step 3: Write the thin ruckus.tcl for `ColumnFpgaBoard160`**

Overwrite `firmware/targets/ColumnFpgaBoard160/ruckus.tcl` with exactly:
```tcl
##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoard.xdc

set_property top {ColumnFpgaBoard} [get_filesets {sources_1}]
```

- [ ] **Step 4: Write the thin ruckus.tcl for `ColumnFpgaBoard160Coord`**

Same as Step 3 but append the generics + strategy lines after `set_property top`:
```tcl
set_property top {ColumnFpgaBoard} [get_filesets {sources_1}]
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=false GEN_ADC_FILTER_G=false ROW_ADDR_BITS_G=5" [current_fileset]
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
```
(Header + `loadRuckusTcl` + `loadConstraints` block identical to Step 3.)

- [ ] **Step 5: Write the thin ruckus.tcl for `ColumnFpgaBoard325Coord`**

Same header/loads/top as Step 3, plus:
```tcl
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=false" [current_fileset]
```

- [ ] **Step 6: Write the thin ruckus.tcl for `ColumnFpgaBoard325Coord10G`**

Same header/loads/top as Step 3, plus:
```tcl
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=true" [current_fileset]
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
```

- [ ] **Step 7: Write the thin ruckus.tcl for `ColumnFpgaBoard325AwaXeCoord10G`**

This target's top is the AwaXe entity and its pinout is the AwaXe `.xdc`.
Overwrite `firmware/targets/ColumnFpgaBoard325AwaXeCoord10G/ruckus.tcl` with the
Step-3 header + loads, but the last four lines are:
```tcl
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoardAwaXe.xdc

set_property top {ColumnFpgaBoardAwaXe} [get_filesets {sources_1}]
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=true" [current_fileset]
```

- [ ] **Step 8: Verify all five Column targets are thin, top-explicit, and pinout-correct**

Run:
```bash
cd firmware/targets
for d in ColumnFpgaBoard160 ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G ColumnFpgaBoard325AwaXeCoord10G; do
  echo "--- $d ---"
  echo "  ../ refs (expect 0): $(grep -c '\.\./' $d/ruckus.tcl)"
  echo "  set_property top: $(grep 'set_property top' $d/ruckus.tcl)"
  echo "  pinout: $(grep -o 'xdc/[A-Za-z0-9]*\.xdc' $d/ruckus.tcl | grep -v WarmTdmCore2)"
done
```
Expected: every target shows `../ refs (expect 0): 0`; the four standard Column
targets show top `{ColumnFpgaBoard}` and pinout `xdc/ColumnFpgaBoard.xdc`; the
AwaXe target shows top `{ColumnFpgaBoardAwaXe}` and pinout
`xdc/ColumnFpgaBoardAwaXe.xdc`.

- [ ] **Step 9: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Rename Column targets and rewrite ruckus.tcl to thin common-sourced form

ColumnFpgaBoard                   -> ColumnFpgaBoard160
ColumnFpgaBoard0                  -> ColumnFpgaBoard160Coord
ColumnFpgaBoard325Coordinator     -> ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coordinator10G  -> ColumnFpgaBoard325Coord10G
ColumnFpgaBoardAwaXe              -> ColumnFpgaBoard325AwaXeCoord10G

Each ruckus.tcl now sources RTL/TB from common/warm_tdm, sets its top
explicitly (required now that all board tops share one fileset), and loads
its own pinout .xdc by path. No ../ cross-references remain. Also deletes the
AwaXe target's stale unused ColumnFpgaBoardTb.vhd (never loaded, AWAXE_G=false).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Rewrite + rename the Row targets

**Files:**
- Modify then rename Row target `ruckus.tcl` + dirs. `RowFpgaBoard325` is
  rewritten thin but not renamed.

- [ ] **Step 1: Rename the two Row dirs (RowFpgaBoard325 keeps its name)**

Run:
```bash
cd firmware/targets
git mv RowFpgaBoard RowFpgaBoard160
git mv RowFpgaBoard0 RowFpgaBoard160Coord
```

- [ ] **Step 2: Write the thin ruckus.tcl for `RowFpgaBoard160`**

Overwrite `firmware/targets/RowFpgaBoard160/ruckus.tcl` with:
```tcl
##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/RowFpgaBoard.xdc

set_property top {RowFpgaBoard} [get_filesets {sources_1}]
```
Note: the old `RowFpgaBoard` set a *sim* top (`RowFpgaBoardTb`) and no sources
top. The sim top is dropped (the TB now lives in common and is not the build
top); the sources top is set explicitly as above.

- [ ] **Step 3: Write the thin ruckus.tcl for `RowFpgaBoard160Coord`**

Same as Step 2 plus (normalizing the old `${testGeneric}` comma form to the
standard space-joined inherit form):
```tcl
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true" [current_fileset]
```

- [ ] **Step 4: Rewrite `RowFpgaBoard325/ruckus.tcl` thin (no rename)**

Overwrite `firmware/targets/RowFpgaBoard325/ruckus.tcl` with exactly the Step 2
content (identical: same top `{RowFpgaBoard}`, same `RowFpgaBoard.xdc` pinout,
default generics — the old target's generic override was commented out, so it
built with defaults).

- [ ] **Step 5: Verify all three Row targets are thin, top-explicit, pinout-correct**

Run:
```bash
cd firmware/targets
for d in RowFpgaBoard160 RowFpgaBoard160Coord RowFpgaBoard325; do
  echo "--- $d ---"
  echo "  ../ refs (expect 0): $(grep -c '\.\./' $d/ruckus.tcl)"
  echo "  sources top: $(grep 'set_property top' $d/ruckus.tcl)"
  echo "  pinout: $(grep -o 'xdc/[A-Za-z0-9]*\.xdc' $d/ruckus.tcl | grep -v WarmTdmCore2)"
done
```
Expected: each shows `0` `../` refs, top `{RowFpgaBoard}`, pinout
`xdc/RowFpgaBoard.xdc`; none shows a `sim_1` top.

- [ ] **Step 6: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Rename Row targets and rewrite ruckus.tcl to thin common-sourced form

RowFpgaBoard   -> RowFpgaBoard160
RowFpgaBoard0  -> RowFpgaBoard160Coord
RowFpgaBoard325 rewritten thin (name unchanged). Each sources RTL/TB from
common/warm_tdm, sets top {RowFpgaBoard} explicitly, and loads RowFpgaBoard.xdc
by path. The obsolete sim_1 top and ../ references are gone.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Archive the legacy Module targets

**Files:**
- Create: `firmware/targets/legacy/`
- Move: five `*Module*` dirs.

- [ ] **Step 1: Create legacy dir and move all five Module targets**

Run:
```bash
cd firmware/targets
mkdir -p legacy
git mv ColumnModule   legacy/ColumnModule
git mv ColumnModule0  legacy/ColumnModule0
git mv RowModule      legacy/RowModule
git mv RowModule0     legacy/RowModule0
git mv RowModuleC00   legacy/RowModuleC00
```

- [ ] **Step 2: Verify moves and that legacy `0` variants' relative paths still resolve**

Run:
```bash
cd firmware/targets
ls -d legacy/ColumnModule legacy/ColumnModule0 legacy/RowModule legacy/RowModule0 legacy/RowModuleC00
test -d legacy/ColumnModule0/../ColumnModule && echo "ColumnModule0 base OK"
test -d legacy/RowModule0/../RowModule && echo "RowModule0 base OK"
```
Expected: five dirs listed; both "base OK" lines print.

- [ ] **Step 3: Confirm no active target references a moved dir**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
grep -rn 'ColumnModule\|RowModule' firmware/targets --include=ruckus.tcl | grep -v '/legacy/'
```
Expected: no output.

- [ ] **Step 4: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Archive legacy Module targets under targets/legacy/

Move ColumnModule, ColumnModule0, RowModule, RowModule0, RowModuleC00 into
firmware/targets/legacy/. Legacy WarmTdmCore v1, unmaintained. They keep their
own canonical-dir arrangement, isolated under legacy/.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Update the aggregate targets Makefile

**Files:**
- Modify: `firmware/targets/Makefile`

- [ ] **Step 1: Replace the TARGETS list**

Replace the existing `TARGETS := \ ...` block with the list below; leave the
rest of the file unchanged.
```makefile
TARGETS := \
	ColumnFpgaBoard160 \
	ColumnFpgaBoard160Coord \
	ColumnFpgaBoard325Coord \
	ColumnFpgaBoard325Coord10G \
	ColumnFpgaBoard325AwaXeCoord10G \
	RowFpgaBoard160 \
	RowFpgaBoard160Coord \
	RowFpgaBoard325
```

- [ ] **Step 2: Verify `make list` prints exactly the eight active targets and all exist**

Run:
```bash
cd firmware/targets
make list
for t in $(make list); do test -f "$t/Makefile" && echo "OK $t" || echo "MISSING $t"; done
```
Expected: the eight names above, then eight `OK` lines, no `MISSING`.

- [ ] **Step 3: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add firmware/targets/Makefile
git commit -m "Update aggregate targets Makefile for renamed/archived targets

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Update releases.yaml

**Files:**
- Modify: `firmware/releases.yaml`

- [ ] **Step 1: Rename the catalog keys and their ImageDir paths**

Apply to each key line and the `ImageDir:` line beneath it:
```
  ColumnFpgaBoard:                  ->  ColumnFpgaBoard160:
    targets/ColumnFpgaBoard/images  ->    targets/ColumnFpgaBoard160/images
  ColumnFpgaBoard0:                 ->  ColumnFpgaBoard160Coord:
    targets/ColumnFpgaBoard0/images ->    targets/ColumnFpgaBoard160Coord/images
  ColumnFpgaBoard325Coordinator:    ->  ColumnFpgaBoard325Coord:
    targets/ColumnFpgaBoard325Coordinator/images -> targets/ColumnFpgaBoard325Coord/images
  ColumnFpgaBoard325Coordinator10G: ->  ColumnFpgaBoard325Coord10G:
    targets/ColumnFpgaBoard325Coordinator10G/images -> targets/ColumnFpgaBoard325Coord10G/images
  ColumnFpgaBoardAwaXe:             ->  ColumnFpgaBoard325AwaXeCoord10G:
    targets/ColumnFpgaBoardAwaXe/images -> targets/ColumnFpgaBoard325AwaXeCoord10G/images
  RowFpgaBoard:                     ->  RowFpgaBoard160:
    targets/RowFpgaBoard/images     ->    targets/RowFpgaBoard160/images
  RowFpgaBoard0:                    ->  RowFpgaBoard160Coord:
    targets/RowFpgaBoard0/images    ->    targets/RowFpgaBoard160Coord/images
```
`RowFpgaBoard325` and its ImageDir are unchanged.

- [ ] **Step 2: Remove the legacy ColumnModule catalog entries**

Delete these two blocks entirely from the `Targets:` catalog:
```yaml
  ColumnModule:
    ImageDir: targets/ColumnModule/images
    Extensions:
      - mcs
      - mcs.gz

  ColumnModule0:
    ImageDir: targets/ColumnModule0/images
    Extensions:
      - mcs
      - mcs.gz
```

- [ ] **Step 3: Update the warmTdm release Targets list**

```yaml
      - ColumnFpgaBoard325Coordinator      ->  - ColumnFpgaBoard325Coord
      - ColumnFpgaBoard325Coordinator10G   ->  - ColumnFpgaBoard325Coord10G
      - RowFpgaBoard                       ->  - RowFpgaBoard160
      - RowFpgaBoard325                    ->  (unchanged)
```

- [ ] **Step 4: Verify YAML parses and every release target resolves to a real dir**

Run from repo root:
```bash
firmware/targets/build_release.sh -r warmTdm --list
```
Expected:
```
ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coord10G
RowFpgaBoard160
RowFpgaBoard325
```

- [ ] **Step 5: Verify no stale old names remain**

Run:
```bash
grep -nE 'ColumnFpgaBoard0|RowFpgaBoard0|325Coordinator|FpgaBoardAwaXe|ColumnModule|ColumnFpgaBoard:|RowFpgaBoard:' firmware/releases.yaml
```
Expected: no output.

- [ ] **Step 6: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add firmware/releases.yaml
git commit -m "Update releases.yaml for renamed and archived targets

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Update the AGENTS.md xdc convention note

**Files:**
- Modify: `AGENTS.md` (line ~121)

- [ ] **Step 1: Update the XDC-split convention line**

Replace:
```
- **XDC split**: Common timing constraints in `common/warm_tdm/xdc/`, board pinout in `targets/*/xdc/`
```
with:
```
- **XDC split**: Common timing constraints AND board pinouts live in `common/warm_tdm/xdc/`; each target loads its own pinout by explicit `loadConstraints -path` (the common `xdc` `-dir` auto-load stays disabled so a target pulls in only its own pinout)
```

- [ ] **Step 2: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add AGENTS.md
git commit -m "Update AGENTS.md: board pinouts now live in common/warm_tdm/xdc/

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the release linter — expect 0 errors**

Run from repo root:
```bash
python3 $HOME/.claude/slac-fpga-skills/bin/sfs-lint release . 2>&1 | grep -E '"severity": "Error"' || echo "NO ERRORS"
```
Expected: `NO ERRORS` (pre-existing `_*.py` re-export warnings and packaging Info items may remain).

- [ ] **Step 2: Confirm no target references shared code via `../` and each has exactly one pinout**

Run from repo root:
```bash
cd firmware/targets
echo "--- ../ refs among active targets (expect none) ---"
grep -rn '\.\./' ColumnFpgaBoard160 ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G ColumnFpgaBoard325AwaXeCoord10G RowFpgaBoard160 RowFpgaBoard160Coord RowFpgaBoard325 --include=ruckus.tcl || echo "clean"
echo "--- each active target loads exactly one board pinout (expect '1' eight times) ---"
for d in ColumnFpgaBoard160 ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G ColumnFpgaBoard325AwaXeCoord10G RowFpgaBoard160 RowFpgaBoard160Coord RowFpgaBoard325; do
  echo "$d: $(grep -o 'xdc/[A-Za-z0-9]*\.xdc' $d/ruckus.tcl | grep -v WarmTdmCore2 | wc -l)"
done
```
Expected: `clean`; each of the eight targets prints `1`.

- [ ] **Step 3: Confirm the common xdc `-dir` auto-load is still disabled**

Run:
```bash
grep -nE 'loadConstraints.*-dir.*xdc' firmware/common/warm_tdm/ruckus.tcl
```
Expected: the matching line begins with `#` (commented). If it prints an
uncommented line, that is a defect — fix before proceeding.

- [ ] **Step 4: Confirm git tree clean and history preserved moves as renames**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
git status --porcelain
git log --oneline -8
```
Expected: empty status; the last 7 commits are Tasks 1–7.

- [ ] **Step 5 (out of coding scope — flag for the user): Vivado build check**

The definitive proof that the §2 source move didn't break synthesis/constraints
is a real build. This requires Vivado 2024.1 (see spec) and is the user's clean
release rebuild step. Note in PROGRESS.md that this remains to be run; do not
attempt it as part of plan execution.

---

## Notes / non-blocking follow-ups (do NOT action in this plan)

- `firmware/common/warm_tdm/ip/{FpMac,Int2Fp}/*.xci` contain stale Vivado
  `gen_directory` paths mentioning `ColumnFpgaBoard325Coordinator10G_project.gen`
  — managed-IP output-path artifacts, regenerated on build; left as-is.
- Old-named `.mcs` images inside the renamed dirs' `images/` folders are
  regenerated under the new dir name on the clean rebuild; optional to prune.
- `ColumnAu25p` (AU25P chip exploration, no board) kept per the spec.
- The `~` editor-backup files throughout the target dirs are untracked and
  outside this plan's scope.
