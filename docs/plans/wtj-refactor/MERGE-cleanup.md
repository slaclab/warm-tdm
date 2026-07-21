# Merging the `cleanup` branch — analysis & plan

Date: 2026-07-21
Status: analysis complete, not yet executed

## Question

Can `origin/cleanup` merge into `wtj-refactor` easily? It carries software
refactors we want, but has **not been hardware-tested**, and is entangled with
firmware changes we are not ready to take.

## Short answer

**Not as a straight `git merge`.** A full merge pulls in 52 commits including a
large, untested firmware effort (floating-point PID / AdcDspFp rewrite,
accumulator split, resource-utilization generics) and collides head-on with the
target-cleanup reorg already in `wtj-refactor`. The conflicts are **entirely
firmware**; the software refactor itself merges cleanly. So the right move is to
**adopt the software refactor in isolation**, not merge the branch.

## Why a full merge is bad

- **Divergence.** merge-base is `ad715e3` ("Add agent helpers"), which predates
  `pre-release`. `origin/cleanup` does **not** contain `pre-release` and does
  **not** contain the target-cleanup reorg.
- **Conflicts are all firmware / target-reorg:**
  - `cleanup` still has the OLD target names (`ColumnFpgaBoard325Coordinator`,
    `...Coordinator10G`, `RowFpgaBoard325`); `wtj-refactor` renamed them to
    `...Coord` / `160`/`325` tokens. Result: modify/delete + rename/add-inside
    conflicts on target dirs and their `vivado/*.tcl` power-analysis scripts.
  - `AdcDsp.vhd`, `releases.yaml`, `.gitignore` content conflicts.
  - Both submodules (`surf`, `ruckus`) conflict ("commits don't follow
    merge-base"), plus 4 "Could not read <sha>" errors — `cleanup`'s submodule
    pointers reference objects not present locally.
- **Untested firmware would ride along.** The whole point (per user) is that
  `cleanup` is not hardware-validated. A branch merge drags the AdcDspFp rewrite
  and generics work into `wtj-refactor` whether we want it or not.

## What we actually want from `cleanup` (software only)

`git diff wtj-refactor...origin/cleanup -- software/` — the structural refactor:

| Change | Files | Notes |
|---|---|---|
| **`_Group.py` split** (−586 lines) | `_Group.py`, new `_GroupVariables.py`, new `_GroupConfig.py` | `GroupLinkVariable` moved out to `_GroupVariables.py`; config extracted to a `GroupConfig` dataclass-style object. **This is the same `GroupLinkVariable` pattern our G1/G3 plan targets** — adopting it first makes the Group-migration work land on the intended structure. |
| **`_Mapping.py` removed** (−79) | `_Mapping.py` deleted | Folded into the new config/variables split. |
| **`GroupConfig` simplification** | `_GroupConfig.py`, `_GroupRoot.py`, `_ArgParser.py` | Config carries `columnBoards`, `rowBoards`, `maxRows`, `host`. Processes now constructed as `SaTuneProcess(config=self.config)`. **IN SCOPE.** |
| **logging over print** | `_Tuning.py`, others | `Replace print calls with logging` (c94df81), `Add more logging` (54d4097). **IN SCOPE.** |
| **scipy dep** | `conda.yml` +1 | Same line our Task 1 already plans to add — harmless overlap. **IN SCOPE.** |
| **Unified launch script** (89c194f) | `warmTdmServer.py` (−112), deletes `gui.py` + `warmTdmGui.py`, `_ArgParser.py` | **IN SCOPE** (user, 2026-07-21). Folds the GUI into `warmTdmServer.py` behind a `--gui` flag via a new `WarmTdmArgparse`/`arg_dict` surface; standalone `gui.py`/`warmTdmGui.py` removed. Does **not** delete `testGroup.py` (my earlier note was wrong). See "Launch-script details" below. |
| ~~v1/retired register-driver deletions~~ | `firmware/python/warm_tdm/*` (f917982) | **DEFERRED** (user, 2026-07-21) — firmware-track, does not affect the software merge. |
| Dead `_FllEnable` var | `_Group`/related | `Remove dead FllEnable variable` (58eef7c). Software-only, keep IN SCOPE (independent of the firmware deletions above). |

## Launch-script details (89c194f, IN SCOPE)

What it actually does (verified):
- **`warmTdmServer.py`** becomes the single entry point: it builds `GroupRoot`
  from parsed args and, if `--gui` is passed, launches PyDM inline
  (`pyrogue.pydm.runPyDM(... display=warm_tdm_api.WarmTdmDisplay)`); otherwise
  `waitCntrlC()`. `--docs` triggers `genDocuments`.
- **Deletes** the standalone `gui.py` and `warmTdmGui.py` (their behavior now
  lives behind `--gui`). Does **not** touch `testGroup.py`.
- **`_ArgParser.py`** gains a `WarmTdmArgparse(argparse.ArgumentParser)` class +
  `arg_dict()` helper exposing: `--gui`, `--docs`, `--sim`, `--emulate`, `--ip`,
  `--pollEn`, `--initRead`, `--rowBoards`, `--maxRows`, `--columnBoards`,
  `--columnBoardType`, `--rowBoardType`, `--columnFrontEnd`, `--floatPid`, …

**Two coupling points to handle when porting:**
1. This shares `_ArgParser.py` edits with the in-scope `GroupConfig` commit
   (f917982), so porting is by **content** (path-scoped diff), not commit
   cherry-pick — both files' argument plumbing come in together, which is fine
   now that both are in scope.
2. The arg surface includes **`--floatPid`** (and `--maxRows`), which map to the
   deferred firmware FP path. Bring the *flags/plumbing* in, but their defaults
   must reflect **current** firmware: `floatPid` default off, `maxRows` pinned
   per the RTL (256 — see below). Do not let the launcher's defaults silently
   assume the FP firmware.

## Deferred (user, 2026-07-21) — not part of the software merge

- **v1/retired register-driver deletions** (f917982's `firmware/python/warm_tdm`
  removals + `__init__` rewrite) — firmware track, gated on `_AdcDspFp` hardware
  validation. This is a **subset** of commit f917982: take that commit's
  `software/` GroupConfig changes, leave its `firmware/python/warm_tdm/*`
  deletions and `__init__` rewrite for the firmware track.

## The critical coupling (why it can't be blindly adopted either)

`GroupConfig.maxRows` **maps directly to the firmware generic `ROW_ADDR_BITS_G`**
(the `cleanup` commit "Implement coherent row sizing generics" changes both
sides together; `_Group.py:96` sets a RAM sized to `config.maxRows`). So the
software refactor is *not* purely cosmetic — its row-sizing assumptions expect
the matching firmware. Adopting the software side while running **current**
(pre-FP) firmware needs `maxRows` pinned to a value the deployed firmware
supports, and needs hardware validation. This is the real reason "we can't just
go merge it yet."

Also: f917982 deletes 10 low-level PyRogue **register-map device drivers** from
`firmware/python/warm_tdm/` (the package that maps FPGA registers to Python).
These fall into two groups:

- **Superseded "v1" drivers** whose "v2" replacement is already the active one:
  `_WarmTdmCommon.py`→`_WarmTdmCommon2.py`, `_WarmTdmCore.py`→`_WarmTdmCore2.py`,
  `_SaBiasOffset.py`→`_SaBiasOffset2.py`, `_TesBias.py`→`_TesBias2.py`,
  `_RowDacDriver.py`→`_RowDacDriver2.py`.
- **Retired board-variant drivers:** `_Ad9106.py` (a 1970-line DAC-chip driver),
  `_ColumnModule.py`, `_RowModule.py`, `_RowModuleDacs.py`, `_RowSelect.py` —
  these correspond to the `*Module` targets the target-cleanup reorg already
  archived to `targets/legacy/`.

The commit's `firmware/python/warm_tdm/__init__.py` rewrite drops all of these
imports **and adds `_AdcAccumulator`/`_AdcDspFp`** — the untested floating-point
firmware drivers. So this file cannot be taken wholesale: it is bundled with the
firmware track. Whether a given v1 driver is truly unused also depends on which
board firmware is deployed (the v1/v2 split tracks a hardware revision). Deleting
these is a firmware-facing decision, not a software-only cleanup, and is scoped
out of the software-first adoption.

## Recommended approach: cherry-pick the software refactor, gated

Do **not** `git merge origin/cleanup`. Instead, land the software refactor as
its own reviewed step on a branch off `wtj-refactor`, decoupled from firmware:

1. **Branch** `wtj-cleanup-sw` off `wtj-refactor`.
2. **Port the software refactor by content, not by merge.** The cleanest
   mechanism is a path-scoped diff apply limited to the non-coupled software:
   ```bash
   # review first
   git diff wtj-refactor...origin/cleanup -- \
     software/python/warm_tdm_api/_Group.py \
     software/python/warm_tdm_api/_GroupVariables.py \
     software/python/warm_tdm_api/_GroupConfig.py \
     software/python/warm_tdm_api/_GroupRoot.py \
     software/python/warm_tdm_api/_Mapping.py \
     software/python/warm_tdm_api/_ArgParser.py \
     software/python/warm_tdm_api/_Tuning.py \
     software/scripts/warmTdmServer.py
   # plus the two script deletions from 89c194f:
   #   git rm software/scripts/gui.py software/scripts/warmTdmGui.py
   ```
   Apply the `_Group.py`/`_GroupVariables.py`/`_GroupConfig.py`/`_Mapping.py`
   split, the `_ArgParser`/`_Tuning`/logging changes, and the unified
   `warmTdmServer.py` + `gui.py`/`warmTdmGui.py` removal (launch-script
   consolidation, now in scope). **Hold back**:
   - the `firmware/python/warm_tdm` device-driver deletions (firmware-coupled),
   - anything that lowers `maxRows`/row-sizing below what current firmware runs,
   - `--floatPid`/`--maxRows` **defaults** that assume the FP firmware (bring the
     flags, default `floatPid` off and `maxRows` to the RTL value).
3. **Reconcile with wtj changes:**
   - Re-apply wtj's `TesBiasWaveformProcess` registration into the *new*
     `_Group.py` structure (verified it survives a textual merge, but the file
     is heavily rewritten — confirm by hand). Keep `_TesBiasWaveform.py` +
     its `__init__.py` import (cleanup does not have this file).
   - Fold our Task 1 `scipy` add into cleanup's identical `conda.yml` line
     (drop the duplicate).
4. **Pin `maxRows`** to match the firmware, derived directly from the RTL (see
   "maxRows value" below). Record it in `GroupConfig` defaults.
5. **Hardware validation gate (user step).** Import check + a live smoke test:
   `warmTdmServer.py` starts, Group builds, a tune/SaOffset runs, and — since the
   launcher is now in scope — `warmTdmServer.py --gui` brings up the PyDM display
   (replacing the deleted `gui.py`/`warmTdmGui.py`). Then feed back to
   `wtj-refactor`.
6. **Placement in the main plan.** This adoption is **PLAN.md Task 2** — right
   after the correctness fixes and before the rename (Task 3) and Group
   graduations (Task 5). Rationale: it creates the `_GroupVariables`/
   `_GroupConfig` structure that the rename rehomes around and the Group
   graduations target; doing it later would mean redoing that work on a
   throwaway structure.

## maxRows value (derived from the RTL)

`maxRows` is a row *count*, and it equals `2 ** ROW_ADDR_BITS_G` (cleanup's
`_Group.py` uses it as `range(maxRows)` for the RowMap RAM and exposes it as the
`NumRows` variable). `ROW_ADDR_BITS_G` is declared `integer range 3 to 8 := 8`
in `ColumnFpgaBoard.vhd:57`, `DataPath.vhd:45`, `AdcDsp.vhd:31`.

| Firmware target | `ROW_ADDR_BITS_G` | correct `maxRows` |
|---|---|---|
| default (all `325` targets inherit it) | 8 | **256** |
| `ColumnFpgaBoard160Coord` (only override) | 5 | **32** |

**Pin `GroupConfig.maxRows = 256`** to match the RTL default that every `325`
build uses; treat `160Coord` (→ 32) as the documented exception. Note cleanup's
shipped default of `maxRows=128` (2⁷) matches **neither** target — it is a stale
value and must not be adopted as-is.

## Firmware side (explicitly deferred)

The AdcDspFp floating-point PID rewrite, accumulator split, and row-sizing
generics in `cleanup` are a separate, larger effort with its own plans
(`docs/plans/` entries `Create plan for splitting accumulator`, the AdcDspFp
PLAN, etc.). They need their own hardware-validation track and a rebase onto the
post-target-cleanup firmware. **Out of scope for the software adoption above.**

## Open questions for the user

1. ~~What `maxRows` value?~~ **Resolved from RTL: pin 256** (RTL default; 32 for
   `160Coord`). See "maxRows value" above. Only open sub-question: which board
   is physically on the test bench — determines which of the two we validate
   against first.
2. ~~Unified launch-script consolidation in this pass?~~ **Resolved: IN SCOPE**
   (2026-07-21, reversed earlier deferral). Bring in the `warmTdmServer.py`
   consolidation + `gui.py`/`warmTdmGui.py` removal + `_ArgParser` surface;
   default `floatPid` off and `maxRows` to the RTL value. See "Launch-script
   details".
3. ~~v1/retired register-driver deletions now?~~ **Resolved: deferred**
   (2026-07-21) — firmware track, does not affect the software merge.

All merge-scoping questions are resolved. Remaining before execution is the
main-plan open decision on package name/home (PLAN.md) and the hardware-bench
choice (which board → validate maxRows 256 vs 32).
