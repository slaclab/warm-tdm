# Firmware Target Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every active target an explicit FPGA-part token (`160`/`325`), standardize the ring-coordinator token on `Coord`, archive the legacy `*Module*` targets under `targets/legacy/`, and prune stale `releases.yaml` entries — without touching the rogue software hierarchy.

**Architecture:** Directory renames + one dir move. The catch: `ColumnFpgaBoard` and `RowFpgaBoard` are the *canonical* dirs that physically hold the shared RTL/sim/xdc; the 325/Coord variants `loadSource` from them via relative `../` paths. Renaming these to `*160` requires updating those relative paths in the referencing `ruckus.tcl` files. RTL top-entity names (`set_property top {ColumnFpgaBoard}`) are NOT renamed — only directories.

**Tech Stack:** Bash, `git mv`, `sed`/Edit for `ruckus.tcl` path edits, SLAC ruckus build system, `sfs-lint` release linter, `build_release.sh --list`.

**Spec:** [docs/superpowers/specs/2026-07-20-target-cleanup-design.md](../../superpowers/specs/2026-07-20-target-cleanup-design.md)

---

## Rename map (reference)

| Current dir | New dir | Part |
|---|---|---|
| `ColumnFpgaBoard` | `ColumnFpgaBoard160` | 160T (canonical RTL dir) |
| `ColumnFpgaBoard0` | `ColumnFpgaBoard160Coord` | 160T |
| `ColumnFpgaBoard325Coordinator` | `ColumnFpgaBoard325Coord` | 325T |
| `ColumnFpgaBoard325Coordinator10G` | `ColumnFpgaBoard325Coord10G` | 325T |
| `ColumnFpgaBoardAwaXe` | `ColumnFpgaBoard325AwaXeCoord10G` | 325T |
| `RowFpgaBoard` | `RowFpgaBoard160` | 160T (canonical RTL dir) |
| `RowFpgaBoard0` | `RowFpgaBoard160Coord` | 160T |
| `RowFpgaBoard325` | `RowFpgaBoard325` (unchanged) | 325T |

## Move map (reference)

`ColumnModule`, `ColumnModule0`, `RowModule`, `RowModule0`, `RowModuleC00`
→ `firmware/targets/legacy/<same-name>`

## Cross-references to fix when the canonical dirs are renamed (reference)

These `ruckus.tcl` files reference `../ColumnFpgaBoard/` or `../RowFpgaBoard/`
(lines 25, 26, 28 in each) and must be repointed to the `*160` names:

- `ColumnFpgaBoard0` (→ `ColumnFpgaBoard160Coord`): `../ColumnFpgaBoard/` → `../ColumnFpgaBoard160/`
- `ColumnFpgaBoard325Coordinator` (→ `ColumnFpgaBoard325Coord`): `../ColumnFpgaBoard/` → `../ColumnFpgaBoard160/`
- `ColumnFpgaBoard325Coordinator10G` (→ `ColumnFpgaBoard325Coord10G`): `../ColumnFpgaBoard/` → `../ColumnFpgaBoard160/`
- `RowFpgaBoard0` (→ `RowFpgaBoard160Coord`): `../RowFpgaBoard/` → `../RowFpgaBoard160/`
- `RowFpgaBoard325`: `../RowFpgaBoard/` → `../RowFpgaBoard160/`

`ColumnFpgaBoardAwaXe` loads only its own `rtl/` — no cross-reference to fix.

## Untouched (reference)

`RowFpgaBoard325` (name), `ColumnAu25p`, Vesper/Boreas `~` backups, all RTL top-entity names, all generics.

---

## Task 1: Rename the Column targets

**Files:**
- Rename: `firmware/targets/ColumnFpgaBoard` → `ColumnFpgaBoard160`
- Rename: `firmware/targets/ColumnFpgaBoard0` → `ColumnFpgaBoard160Coord`
- Rename: `firmware/targets/ColumnFpgaBoard325Coordinator` → `ColumnFpgaBoard325Coord`
- Rename: `firmware/targets/ColumnFpgaBoard325Coordinator10G` → `ColumnFpgaBoard325Coord10G`
- Rename: `firmware/targets/ColumnFpgaBoardAwaXe` → `ColumnFpgaBoard325AwaXeCoord10G`

- [ ] **Step 1: Perform the Column renames with git mv**

Run:
```bash
cd firmware/targets
git mv ColumnFpgaBoard ColumnFpgaBoard160
git mv ColumnFpgaBoard0 ColumnFpgaBoard160Coord
git mv ColumnFpgaBoard325Coordinator ColumnFpgaBoard325Coord
git mv ColumnFpgaBoard325Coordinator10G ColumnFpgaBoard325Coord10G
git mv ColumnFpgaBoardAwaXe ColumnFpgaBoard325AwaXeCoord10G
```

- [ ] **Step 2: Verify new dirs exist and old ones are gone**

Run:
```bash
cd firmware/targets
ls -d ColumnFpgaBoard160 ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G ColumnFpgaBoard325AwaXeCoord10G
ls -d ColumnFpgaBoard ColumnFpgaBoard0 ColumnFpgaBoard325Coordinator ColumnFpgaBoard325Coordinator10G ColumnFpgaBoardAwaXe 2>&1
```
Expected: first `ls` prints all five new dirs; second prints five "No such file or directory" errors.

- [ ] **Step 3: Repoint the Column variant ruckus.tcl paths to ColumnFpgaBoard160**

Three targets reference the old canonical `../ColumnFpgaBoard/`. Update them:
```bash
cd firmware/targets
for d in ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G; do
  sed -i 's#\.\./ColumnFpgaBoard/#../ColumnFpgaBoard160/#g' "$d/ruckus.tcl"
done
```

- [ ] **Step 4: Verify no Column variant still references the old canonical path, and entity names are intact**

Run:
```bash
cd firmware/targets
echo "--- stale ../ColumnFpgaBoard/ refs (expect none) ---"
grep -rn '\.\./ColumnFpgaBoard/' ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G || echo "clean"
echo "--- new ../ColumnFpgaBoard160/ refs (expect 3 lines each: rtl, sim, xdc) ---"
grep -rn '\.\./ColumnFpgaBoard160/' ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G
echo "--- top entity still ColumnFpgaBoard (must NOT change) ---"
grep -rn 'set_property top' ColumnFpgaBoard160Coord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G
```
Expected: "clean"; nine `../ColumnFpgaBoard160/` lines (3 per target); each `set_property top {ColumnFpgaBoard}` unchanged.

- [ ] **Step 5: Confirm the canonical ColumnFpgaBoard160 dir still holds the RTL**

Run:
```bash
cd firmware/targets
ls ColumnFpgaBoard160/rtl/*.vhd | head -1
grep -c 'DIR_PATH/rtl/' ColumnFpgaBoard160/ruckus.tcl
```
Expected: at least one `.vhd` file listed; grep count `>= 1` (the canonical dir loads its own `rtl/`, confirming the shared RTL moved with the rename).

- [ ] **Step 6: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Rename Column targets with explicit part + Coord tokens

ColumnFpgaBoard                   -> ColumnFpgaBoard160  (canonical RTL dir)
ColumnFpgaBoard0                  -> ColumnFpgaBoard160Coord
ColumnFpgaBoard325Coordinator     -> ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coordinator10G  -> ColumnFpgaBoard325Coord10G
ColumnFpgaBoardAwaXe              -> ColumnFpgaBoard325AwaXeCoord10G

Variant ruckus.tcl paths repointed to ../ColumnFpgaBoard160/. RTL top
entity names (set_property top {ColumnFpgaBoard}) left unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Rename the Row targets

**Files:**
- Rename: `firmware/targets/RowFpgaBoard` → `RowFpgaBoard160`
- Rename: `firmware/targets/RowFpgaBoard0` → `RowFpgaBoard160Coord`
- Modify: `firmware/targets/RowFpgaBoard325/ruckus.tcl` (repoint path only; not renamed)

- [ ] **Step 1: Perform the Row renames with git mv**

Run:
```bash
cd firmware/targets
git mv RowFpgaBoard RowFpgaBoard160
git mv RowFpgaBoard0 RowFpgaBoard160Coord
```

- [ ] **Step 2: Verify new dirs exist and old ones are gone**

Run:
```bash
cd firmware/targets
ls -d RowFpgaBoard160 RowFpgaBoard160Coord RowFpgaBoard325
ls -d RowFpgaBoard RowFpgaBoard0 2>&1
```
Expected: first `ls` prints the three dirs (`RowFpgaBoard325` unchanged); second prints two "No such file or directory" errors.

- [ ] **Step 3: Repoint the Row variant ruckus.tcl paths to RowFpgaBoard160**

Both `RowFpgaBoard160Coord` and `RowFpgaBoard325` reference `../RowFpgaBoard/`:
```bash
cd firmware/targets
for d in RowFpgaBoard160Coord RowFpgaBoard325; do
  sed -i 's#\.\./RowFpgaBoard/#../RowFpgaBoard160/#g' "$d/ruckus.tcl"
done
```

- [ ] **Step 4: Verify no stale refs remain and entity names intact**

Run:
```bash
cd firmware/targets
echo "--- stale ../RowFpgaBoard/ refs (expect none) ---"
grep -rn '\.\./RowFpgaBoard/' RowFpgaBoard160Coord RowFpgaBoard325 || echo "clean"
echo "--- new ../RowFpgaBoard160/ refs (expect 3 lines each) ---"
grep -rn '\.\./RowFpgaBoard160/' RowFpgaBoard160Coord RowFpgaBoard325
echo "--- top entity still RowFpgaBoard (must NOT change) ---"
grep -rn 'set_property top' RowFpgaBoard160Coord RowFpgaBoard325
```
Expected: "clean"; six `../RowFpgaBoard160/` lines; `set_property top {RowFpgaBoard}` unchanged in both.

- [ ] **Step 5: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Rename Row targets with explicit part + Coord tokens

RowFpgaBoard   -> RowFpgaBoard160  (canonical RTL dir)
RowFpgaBoard0  -> RowFpgaBoard160Coord
RowFpgaBoard325 unchanged; its ruckus.tcl path repointed to
../RowFpgaBoard160/. RTL top entity name (RowFpgaBoard) left unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Archive the legacy Module targets

**Files:**
- Create: `firmware/targets/legacy/`
- Move: `firmware/targets/{ColumnModule,ColumnModule0,RowModule,RowModule0,RowModuleC00}` → `firmware/targets/legacy/<same-name>`

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

- [ ] **Step 2: Verify moves and that relative RTL load paths still resolve within legacy/**

The `0` variants load from `../ColumnModule` / `../RowModule`; since all moved into the same `legacy/` dir, those paths still resolve.

Run:
```bash
cd firmware/targets
ls -d legacy/ColumnModule legacy/ColumnModule0 legacy/RowModule legacy/RowModule0 legacy/RowModuleC00
test -d legacy/ColumnModule0/../ColumnModule && echo "ColumnModule0 base OK"
test -d legacy/RowModule0/../RowModule && echo "RowModule0 base OK"
```
Expected: all five dirs listed; both "base OK" lines print.

- [ ] **Step 3: Confirm no active (non-legacy) target references a moved dir**

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
firmware/targets/legacy/. Legacy WarmTdmCore v1, no longer maintained. They
move together so relative ../ load paths still resolve.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Update the aggregate targets Makefile

**Files:**
- Modify: `firmware/targets/Makefile`

- [ ] **Step 1: Replace the TARGETS list**

Replace the existing `TARGETS := \ ...` block with the list below. Leave the rest of the file (`SUBTARGET`, `.PHONY`, `all`, `list`, the `$(TARGETS)` rule, `clean`) unchanged.

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

- [ ] **Step 2: Verify `make list` prints exactly the eight active targets**

Run:
```bash
cd firmware/targets
make list
```
Expected:
```
ColumnFpgaBoard160
ColumnFpgaBoard160Coord
ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coord10G
ColumnFpgaBoard325AwaXeCoord10G
RowFpgaBoard160
RowFpgaBoard160Coord
RowFpgaBoard325
```

- [ ] **Step 3: Verify every listed target is a real dir with a Makefile**

Run:
```bash
cd firmware/targets
for t in $(make list); do test -f "$t/Makefile" && echo "OK $t" || echo "MISSING $t"; done
```
Expected: eight `OK` lines, no `MISSING`.

- [ ] **Step 4: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add firmware/targets/Makefile
git commit -m "Update aggregate targets Makefile for renamed/archived targets

Point TARGETS at the renamed part+Coord target names and drop the archived
legacy Module targets.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Update releases.yaml

**Files:**
- Modify: `firmware/releases.yaml`

- [ ] **Step 1: Rename the catalog keys and their ImageDir paths**

In the `Targets:` catalog, apply these substitutions to each key line and the `ImageDir:` line beneath it:

```
  ColumnFpgaBoard:                  ->  ColumnFpgaBoard160:
    targets/ColumnFpgaBoard/images  ->    targets/ColumnFpgaBoard160/images

  ColumnFpgaBoard0:                 ->  ColumnFpgaBoard160Coord:
    targets/ColumnFpgaBoard0/images ->    targets/ColumnFpgaBoard160Coord/images

  ColumnFpgaBoard325Coordinator:            ->  ColumnFpgaBoard325Coord:
    targets/ColumnFpgaBoard325Coordinator/images ->  targets/ColumnFpgaBoard325Coord/images

  ColumnFpgaBoard325Coordinator10G:            ->  ColumnFpgaBoard325Coord10G:
    targets/ColumnFpgaBoard325Coordinator10G/images -> targets/ColumnFpgaBoard325Coord10G/images

  ColumnFpgaBoardAwaXe:                 ->  ColumnFpgaBoard325AwaXeCoord10G:
    targets/ColumnFpgaBoardAwaXe/images ->    targets/ColumnFpgaBoard325AwaXeCoord10G/images

  RowFpgaBoard:                  ->  RowFpgaBoard160:
    targets/RowFpgaBoard/images  ->    targets/RowFpgaBoard160/images

  RowFpgaBoard0:                 ->  RowFpgaBoard160Coord:
    targets/RowFpgaBoard0/images ->    targets/RowFpgaBoard160Coord/images
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

In `Releases: warmTdm: Targets:`:
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

- [ ] **Step 5: Verify no stale old names remain in releases.yaml**

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

Rename all seven affected catalog keys + ImageDir paths to the part+Coord
scheme, update the warmTdm release target list, and drop the archived
ColumnModule / ColumnModule0 catalog entries.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the release linter — expect 0 errors**

Run from repo root:
```bash
python3 $HOME/.claude/slac-fpga-skills/bin/sfs-lint release . 2>&1 | grep -E '"severity": "Error"' || echo "NO ERRORS"
```
Expected: `NO ERRORS` (the 4 intentional `_*.py` re-export warnings and packaging/config Info items may remain — they predate this work).

- [ ] **Step 2: Confirm no old target dir names survive anywhere in the target tree or build config**

Run from repo root:
```bash
grep -rn 'ColumnFpgaBoard0\|RowFpgaBoard0\|325Coordinator\|ColumnFpgaBoardAwaXe' \
  firmware/targets firmware/releases.yaml \
  --include=ruckus.tcl --include=Makefile --include='*.yaml' 2>/dev/null || echo "no stale names"
# Bare canonical names should now only appear as RTL entity refs (set_property top), not as paths:
grep -rn '\.\./ColumnFpgaBoard/\|\.\./RowFpgaBoard/' firmware/targets --include=ruckus.tcl || echo "no stale canonical paths"
```
Expected: `no stale names` and `no stale canonical paths`.

- [ ] **Step 3: Confirm git tree is clean and history preserved renames as moves**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
git status --porcelain
git log --oneline -6
```
Expected: empty `git status`; last 5 commits are Tasks 1–5.

- [ ] **Step 4: Sanity-check the renamed AwaXe target survived intact**

Run:
```bash
cd firmware/targets
ls ColumnFpgaBoard325AwaXeCoord10G
grep -c 'ETH_10G_G=true' ColumnFpgaBoard325AwaXeCoord10G/ruckus.tcl
```
Expected: `Makefile`, `ruckus.tcl`, `rtl/`, `images/` present; grep count `1`.

---

## Notes / non-blocking follow-ups (do NOT action in this plan)

- `firmware/common/warm_tdm/ip/{FpMac,Int2Fp}/*.xci` contain stale Vivado
  `gen_directory` / `OUTPUTDIR` paths mentioning
  `ColumnFpgaBoard325Coordinator10G_project.gen`. Managed-IP output-path
  artifacts, regenerated by Vivado on build; left as-is.
- Old-named `.mcs` images inside the renamed dirs' `images/` folders are
  regenerated under the new dir name on the clean release rebuild; optional to
  prune.
- `ColumnAu25p` (AU25P chip exploration, no board) is kept per the spec.
- The extra generics on `ColumnFpgaBoard160Coord`
  (`GEN_ADC_FILTER_G=false ROW_ADDR_BITS_G=5`) are preserved, not judged.
