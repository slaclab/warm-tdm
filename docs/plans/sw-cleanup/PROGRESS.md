# SW Cleanup Progress

## 2026-05-26

- Unified launch scripts: consolidated `warmTdmGui.py` + old `warmTdmServer.py` + `gui.py` into single `warmTdmServer.py` with `--gui` flag
- `warmTdmServer.py` now uses `WarmTdmArgparse` + `arg_dict()` + `GroupRoot` (removed dependency on legacy `WarmTdmRoot`)
- Cleaned up `_ArgParser.py`: added `--gui`, fixed broken `type=bool` args (`--pollEn`, `--initRead`), added help strings, set standard defaults
- Removed `.ipynb_checkpoints/` from scripts directory
- Updated `releases.yaml`, `AGENTS.md`, `SOFTWARE_GUIDE.md`
- Branch: cleanup

## 2026-05-22

- Completed Phase 1: Legacy removal and config simplification
- Deleted 10 legacy files (-3,451 lines net)
- Simplified GroupConfig, removed dead parameter chain
- Extracted variable helper classes to `_GroupVariables.py`
- Fixed broken sq1Ramp/tesRamp tuning diagnostics
- Removed dead FllEnable variable and GUI widget reference
- Commits: f917982, 58eef7c (branch: fp-pid)
