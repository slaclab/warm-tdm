# SW Cleanup Progress

## 2026-05-22

- Completed Phase 1: Legacy removal and config simplification
- Deleted 10 legacy files (-3,451 lines net)
- Simplified GroupConfig, removed dead parameter chain
- Extracted variable helper classes to `_GroupVariables.py`
- Fixed broken sq1Ramp/tesRamp tuning diagnostics
- Removed dead FllEnable variable and GUI widget reference
- Commits: f917982, 58eef7c (branch: fp-pid)
