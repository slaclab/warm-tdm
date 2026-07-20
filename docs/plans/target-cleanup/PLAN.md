# Firmware Target Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename ring-coordinator targets to a consistent `Coord` token, archive the legacy `*Module*` targets under `targets/legacy/`, and prune stale entries from `releases.yaml` — without touching the rogue software hierarchy.

**Architecture:** Pure mechanical rename/move. Target directory names appear in exactly three places — the dirs themselves, `firmware/targets/Makefile`, and `firmware/releases.yaml`. The four renamed variant targets `loadSource` their RTL *from* `ColumnFpgaBoard/`/`RowFpgaBoard/` (which are NOT renamed), so no intra-target `ruckus.tcl` path edits are needed. The legacy dirs move together, preserving their relative `../ColumnModule` / `../RowModule` load paths.

**Tech Stack:** Bash, `git mv`, SLAC ruckus build system, `sfs-lint` release linter. No compiled/test code — verification is via the linter and `build_release.sh --list`.

**Spec:** [docs/superpowers/specs/2026-07-20-target-cleanup-design.md](../../superpowers/specs/2026-07-20-target-cleanup-design.md)

---

## Rename map (reference)

| Current dir | New dir |
|---|---|
| `ColumnFpgaBoard0` | `ColumnFpgaBoardCoord` |
| `RowFpgaBoard0` | `RowFpgaBoardCoord` |
| `ColumnFpgaBoard325Coordinator` | `ColumnFpgaBoard325Coord` |
| `ColumnFpgaBoard325Coordinator10G` | `ColumnFpgaBoard325Coord10G` |

## Move map (reference)

`ColumnModule`, `ColumnModule0`, `RowModule`, `RowModule0`, `RowModuleC00`
→ `firmware/targets/legacy/<same-name>`

## Untouched (reference)

`ColumnFpgaBoard`, `RowFpgaBoard`, `RowFpgaBoard325`, `ColumnFpgaBoardAwaXe`, `ColumnAu25p`.

---

## Task 1: Rename the four coordinator target directories

**Files:**
- Rename: `firmware/targets/ColumnFpgaBoard0` → `firmware/targets/ColumnFpgaBoardCoord`
- Rename: `firmware/targets/RowFpgaBoard0` → `firmware/targets/RowFpgaBoardCoord`
- Rename: `firmware/targets/ColumnFpgaBoard325Coordinator` → `firmware/targets/ColumnFpgaBoard325Coord`
- Rename: `firmware/targets/ColumnFpgaBoard325Coordinator10G` → `firmware/targets/ColumnFpgaBoard325Coord10G`

- [ ] **Step 1: Perform the four renames with git mv**

Run from repo root:
```bash
cd firmware/targets
git mv ColumnFpgaBoard0 ColumnFpgaBoardCoord
git mv RowFpgaBoard0 RowFpgaBoardCoord
git mv ColumnFpgaBoard325Coordinator ColumnFpgaBoard325Coord
git mv ColumnFpgaBoard325Coordinator10G ColumnFpgaBoard325Coord10G
```

- [ ] **Step 2: Verify the renames landed and no old names remain as dirs**

Run:
```bash
cd firmware/targets
ls -d ColumnFpgaBoardCoord RowFpgaBoardCoord ColumnFpgaBoard325Coord ColumnFpgaBoard325Coord10G
ls -d ColumnFpgaBoard0 RowFpgaBoard0 ColumnFpgaBoard325Coordinator ColumnFpgaBoard325Coordinator10G 2>&1
```
Expected: first `ls` prints all four new dirs; second `ls` prints four "No such file or directory" errors.

- [ ] **Step 3: Confirm the renamed targets still reference the un-renamed base RTL dirs**

Run:
```bash
cd firmware/targets
grep -h 'DIR_PATH/\.\./' ColumnFpgaBoardCoord/ruckus.tcl RowFpgaBoardCoord/ruckus.tcl ColumnFpgaBoard325Coord/ruckus.tcl ColumnFpgaBoard325Coord10G/ruckus.tcl | grep -v '^#'
```
Expected: every path points to `../ColumnFpgaBoard/...` or `../RowFpgaBoard/...` (both dirs still exist — nothing to fix).

- [ ] **Step 4: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Rename coordinator targets to consistent Coord token

ColumnFpgaBoard0        -> ColumnFpgaBoardCoord
RowFpgaBoard0          -> RowFpgaBoardCoord
ColumnFpgaBoard325Coordinator     -> ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coordinator10G  -> ColumnFpgaBoard325Coord10G

The trailing '0' and 'Coordinator' suffixes both meant RING_ADDR_0_G=true
(ring node-0 / stack ethernet driver). Standardize on 'Coord'. These dirs
loadSource their RTL from the un-renamed ColumnFpgaBoard/RowFpgaBoard dirs,
so no ruckus.tcl path edits are needed.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Archive the legacy Module targets

**Files:**
- Create: `firmware/targets/legacy/` (new directory)
- Move: `firmware/targets/{ColumnModule,ColumnModule0,RowModule,RowModule0,RowModuleC00}` → `firmware/targets/legacy/<same-name>`

- [ ] **Step 1: Create the legacy dir and move all five Module targets**

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

- [ ] **Step 2: Verify the moves and that relative RTL load paths still resolve**

The `0` variants load from `../ColumnModule` / `../RowModule`. Since all five moved into the same `legacy/` dir, `legacy/ColumnModule0/../ColumnModule` still resolves.

Run:
```bash
cd firmware/targets
ls -d legacy/ColumnModule legacy/ColumnModule0 legacy/RowModule legacy/RowModule0 legacy/RowModuleC00
# Confirm the sibling RTL dir each '0' variant references now exists next to it:
test -d legacy/ColumnModule0/../ColumnModule && echo "ColumnModule0 base OK"
test -d legacy/RowModule0/../RowModule && echo "RowModule0 base OK"
```
Expected: all five dirs listed; both "base OK" lines print.

- [ ] **Step 3: Confirm no non-legacy target references a moved dir**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
grep -rn 'ColumnModule\|RowModule' firmware/targets --include=ruckus.tcl | grep -v '/legacy/'
```
Expected: no output (only files inside `legacy/` reference these names).

- [ ] **Step 4: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add -A firmware/targets
git commit -m "Archive legacy Module targets under targets/legacy/

Move ColumnModule, ColumnModule0, RowModule, RowModule0, RowModuleC00
into firmware/targets/legacy/. These use the legacy WarmTdmCore v1 and are
no longer maintained. They move together so their relative ../ load paths
still resolve.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Update the aggregate targets Makefile

**Files:**
- Modify: `firmware/targets/Makefile`

The `TARGETS` list hardcodes every target name and the rule `$(TARGETS): cd $@ && $(MAKE)` uses each name as a path. Renamed targets need new names; legacy targets, if kept in the list, would need a `legacy/` path prefix — but per spec they are archived and dropped from release builds, so remove them from this aggregate list entirely.

- [ ] **Step 1: Replace the TARGETS list**

Replace the existing `TARGETS := \ ... ` block (the 14-entry list) with the active-only list below. Keep the rest of the file (`.PHONY`, `all`, `list`, `$(TARGETS)` rule, `clean`) unchanged.

```makefile
TARGETS := \
	ColumnFpgaBoard \
	ColumnFpgaBoardCoord \
	ColumnFpgaBoard325Coord \
	ColumnFpgaBoard325Coord10G \
	ColumnFpgaBoardAwaXe \
	RowFpgaBoard \
	RowFpgaBoardCoord \
	RowFpgaBoard325
```

Note: `ColumnAu25p` is intentionally NOT in this list — it has no Makefile/ruckus.tcl (it never built here) and was excluded from the aggregate before this change as well.

- [ ] **Step 2: Verify the Makefile lists exactly the eight active targets**

Run:
```bash
cd firmware/targets
make list
```
Expected output (order as listed):
```
ColumnFpgaBoard
ColumnFpgaBoardCoord
ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coord10G
ColumnFpgaBoardAwaXe
RowFpgaBoard
RowFpgaBoardCoord
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

Point TARGETS at the renamed Coord targets and drop the archived legacy
Module targets from the aggregate build list.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Update releases.yaml

**Files:**
- Modify: `firmware/releases.yaml`

Three edits: rename the four catalog keys + their `ImageDir` paths, update the two renamed entries in the `warmTdm` release `Targets` list, and remove the legacy `ColumnModule` / `ColumnModule0` catalog entries.

- [ ] **Step 1: Rename the four catalog keys and their ImageDir paths**

In the `Targets:` catalog, apply these substitutions to both the key line and the `ImageDir:` line under it:

```
  ColumnFpgaBoard0:                     ->  ColumnFpgaBoardCoord:
    ImageDir: targets/ColumnFpgaBoard0/images
                                        ->  ImageDir: targets/ColumnFpgaBoardCoord/images

  ColumnFpgaBoard325Coordinator:        ->  ColumnFpgaBoard325Coord:
    ImageDir: targets/ColumnFpgaBoard325Coordinator/images
                                        ->  ImageDir: targets/ColumnFpgaBoard325Coord/images

  ColumnFpgaBoard325Coordinator10G:     ->  ColumnFpgaBoard325Coord10G:
    ImageDir: targets/ColumnFpgaBoard325Coordinator10G/images
                                        ->  ImageDir: targets/ColumnFpgaBoard325Coord10G/images

  RowFpgaBoard0:                        ->  RowFpgaBoardCoord:
    ImageDir: targets/RowFpgaBoard0/images
                                        ->  ImageDir: targets/RowFpgaBoardCoord/images
```

- [ ] **Step 2: Remove the legacy ColumnModule catalog entries**

Delete these two blocks (key + `ImageDir` + `Extensions` list) from the `Targets:` catalog entirely:
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
(The Row `*Module*` targets were never in the catalog — nothing to remove there.)

- [ ] **Step 3: Update the warmTdm release Targets list**

In `Releases: warmTdm: Targets:`, rename the two coordinator entries:
```yaml
      - ColumnFpgaBoard325Coordinator      ->  - ColumnFpgaBoard325Coord
      - ColumnFpgaBoard325Coordinator10G   ->  - ColumnFpgaBoard325Coord10G
```
(`RowFpgaBoard` and `RowFpgaBoard325` in that list are unchanged.)

- [ ] **Step 4: Verify the YAML parses and every release target resolves to a real dir**

Run from repo root:
```bash
firmware/targets/build_release.sh -r warmTdm --list
```
Expected output:
```
ColumnFpgaBoard325Coord
ColumnFpgaBoard325Coord10G
RowFpgaBoard
RowFpgaBoard325
```
(The script fails loudly if any release target is missing from the catalog.)

- [ ] **Step 5: Verify no stale old names remain in releases.yaml**

Run:
```bash
grep -nE 'ColumnFpgaBoard0|RowFpgaBoard0|325Coordinator|ColumnModule' firmware/releases.yaml
```
Expected: no output.

- [ ] **Step 6: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add firmware/releases.yaml
git commit -m "Update releases.yaml for renamed and archived targets

Rename the four coordinator catalog keys + ImageDir paths to the Coord
scheme, update the warmTdm release target list, and drop the archived
ColumnModule / ColumnModule0 catalog entries.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the release linter — expect 0 errors**

Run from repo root:
```bash
python3 $HOME/.claude/slac-fpga-skills/bin/sfs-lint release . 2>&1 | grep -E '"severity": "Error"' || echo "NO ERRORS"
```
Expected: `NO ERRORS` (the 4 intentional `_*.py` re-export warnings and the packaging/config Info items may remain — those predate this work).

- [ ] **Step 2: Confirm the git tree is clean and history preserved renames as moves**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
git status --porcelain
git log --oneline -5
```
Expected: empty `git status` (all committed); the last 4 commits are Tasks 1–4.

- [ ] **Step 3: Sanity-check a renamed target's dir contents survived the move**

Run:
```bash
cd firmware/targets
ls ColumnFpgaBoard325Coord10G
grep -c 'ETH_10G_G=true' ColumnFpgaBoard325Coord10G/ruckus.tcl
```
Expected: `Makefile`, `ruckus.tcl`, `images/` present; grep count `1` (the 10G generic is intact).

---

## Notes / non-blocking follow-ups (do NOT action in this plan)

- `firmware/common/warm_tdm/ip/{FpMac,Int2Fp}/*.xci` contain stale Vivado
  `gen_directory` / `OUTPUTDIR` paths mentioning `ColumnFpgaBoard325Coordinator10G_project.gen`.
  These are managed-IP output-path artifacts, regenerated by Vivado on build;
  they do not affect the rename and are left as-is.
- Old-named `.mcs` images still live inside the renamed dirs' `images/` folders.
  They are regenerated under the new dir name on the clean release rebuild;
  optional to prune.
- `ColumnAu25p` (AU25P chip exploration, no board) is kept per the spec.
