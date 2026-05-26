# Python Software Cleanup

## Scope

Remove legacy code paths, simplify configuration structures, and fix broken
tuning functions in the `warm_tdm` and `warm_tdm_api` Python packages.

Goals:
- Only support ColumnFpgaBoard, ColumnAwaXeFpgaBoard (AwaXe), and RowFpgaBoard
- Remove dead `numRowSelects`/`numChipSelects` parameter chain (RowMap is dynamic now)
- Simplify GroupConfig (remove PhysicalMap/columnMap/rowMap indirection)
- Fix broken diagnostic tuning functions
- Reduce debug print noise

## Completed Work

### Phase 1: Legacy removal and config simplification (commits f917982, 58eef7c)

| Change | Files |
|--------|-------|
| Delete legacy board classes | `_ColumnModule.py`, `_RowModule.py`, `_WarmTdmCore.py`, `_WarmTdmCommon.py`, `_RowDacDriver.py`, `_SaBiasOffset.py`, `_TesBias.py`, `_Ad9106.py`, `_RowSelect.py`, `_RowModuleDacs.py` |
| Remove legacy front-ends | `ColumnBoardC00*`, `RowBoardC01*` from `_FrontEnds.py` |
| Remove legacy amplifiers | `ColumnBoardC00SaAmp`, `FEAmplifier3` from `_Amplifiers.py` |
| Remove dead params | `numRowSelects`/`numChipSelects` from ArgParser → GroupRoot → Group → HardwareGroup → RowFpgaBoard |
| Simplify GroupConfig | Now just `columnBoards`, `rowBoards`, `maxRows`, `host`. Renamed `_Mapping.py` → `_GroupConfig.py` |
| Replace columnMap indirection | `col_iter()` on Group; inline `board // 8`, `chan % 8` in variable classes |
| Extract variable classes | `GroupLinkVariable`, `GroupArrayLinkVariable`, `FastDacVariable` → `_GroupVariables.py` |
| Remove ~150 lines commented code | `_Group.py` cleaned of dead RowTuneEnable, FasFlux, ForceVoltage, etc. |
| Fix tuning diagnostics | `sq1Ramp`, `sq1RampRow`, `tesRamp`, `tesRampRow` — use `ActivateRowIndex`/`DeactivateRowIndex` directly |
| Remove dead FllEnable | Variable and GUI reference removed |

## Remaining Work

### Phase 2: Print noise and debug cleanup

1. **`_Tuning.py` print statements** — 20 active `print()` calls for debug output during tuning sweeps. Replace with `logging` module or remove entirely.
2. **`_Tuning.py` commented-out prints** — 15 `#print(...)` lines. Delete.
3. **`_HardwareGroup.py` DataDebug** — Prints every received frame. Remove class or gate behind a flag.
4. **`_HardwareGroup.py` startup print** — `print(f'Starting HardwareGroup...')` on line 62. Remove.

### Phase 3: Broken FAS tuning

5. **`fasSweep`/`fasTune`** in `_Tuning.py` reference `group.FasFluxOn` which doesn't exist. Options:
   - Implement `FasFluxOn`/`FasFluxOff` as link variables to `RowDacDriver2.FasOn`/`FasOff`
   - Or remove the functions if FAS tuning will be redesigned

### Phase 4: RTL dead generics

6. **`RowFpgaBoard.vhd` lines 54-55** — `NUM_ROW_SELECTS_G` and `NUM_CHIP_SELECTS_G` declared but never used in architecture body. Remove.

### Phase 5: Widget references

7. **`_control_tab.py` line 55** — References `RowTuneIndex` which no longer exists in Group.
