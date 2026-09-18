# Operations merge preparation

Prepare [PR #107](https://github.com/slaclab/warm-tdm/pull/107) for integration
into `pre-release`. Hardware acceptance remains on
[#68](https://github.com/slaclab/warm-tdm/issues/68), with Group graduation on
[#83](https://github.com/slaclab/warm-tdm/issues/83) and tuning on
[#99](https://github.com/slaclab/warm-tdm/issues/99).

## Baseline and decisions

- September 16, 2026: `ops-fixes` at `5549d4c11ba0691ed206ac5a0a6072d30c110f8d`;
  `pre-release` at `1045236eecac9719092883b78dee6e850c63698b` is its ancestor.
- The published head passes CI but contains the two defects recorded in its
  description. The prepared three-file correction from
  `/private/tmp/warm-tdm-ops107-fix` has been copied into this checkout for review.
  That earlier worktree is preserved.
- No staging, commits, publication or merging is authorized by this task.
  Keep the final corrections unstaged for the maintainer.
- `RowEnableMasks` stores desired configuration. `apply_dead_masks` must write
  each board-local register before updating that desired state.
- Safe-state writes must bypass column gating for fast and slow outputs and
  keep attempting remaining outputs after an individual failure.
- MUX PID/debug/row-mask setup and explicit PID debug changes must translate
  global column indices into board-local channels.

## Changes prepared

- `_setup.py`: write dead masks to board-local registers before caching them;
  route MUX PID/debug/masks and `set_pid(debug=...)` across column boards.
- `_forcedac.py`: use unmasked board-local slow-output leaves for zeroing;
  keep attempting remaining outputs and report failures.
- `tuning/_sq1.py`: do not apply fitted tables when Stop occurs inside the final
  row sweep; reject nonfinite fits before any table write.
- Update the synthetic Rogue smoke fixture for board-local force setters.
  Add production-tree direct/VirtualClient setup coverage, unit regressions for
  multi-board mapping and SQ1 application, and the prepared dead-mask/zero tests.
- Repair the legacy `.ui` mask controls, document the desired-state contract
  and multi-board behavior, and refresh the generated Group API reference.
  `_Group.py` changes only comments and a description.

## Validation — September 16, 2026

All results below are on the **uncommitted working tree** over the baseline
above. No published revision or existing CI run includes these corrections.

| Check | Result and scope |
|---|---|
| `python -m unittest discover -s software/tests -v` | 81 tests pass |
| `python software/tests/rogue_operations_smoke.py` | 8 tests pass: real Rogue threads, localhost ZMQ, file I/O, synthetic instrument and FastDacDriver memory reads |
| `python software/tests/rogue_ops_setup_smoke.py` | 2 tests pass, each through direct and VirtualClient Sessions on a production two-column-board, one-row-board MemEmulate tree |
| Regression sensitivity | Six selected new cases fail against published production source `5549d4c`: dead-mask writes, disabled-column slow zeroing, multi-board setup/debug, final-row Stop and nonfinite fits |
| Python syntax / UI | 104 Python files parse; edited Qt UI parses as XML |
| RTL source comparison | All eight changed production VHDL files have identical tokens after `rowIndex` → `logicalRow`, `rowIndexNext` → `nextLogicalRow`, `rowIndex8` → `logicalRow8`, ignoring comments/whitespace; no stale field uses found in production or simulation sources |
| Whitespace | `git diff --check` passes |

The production smoke uses ColumnFpgaBoard/FpgaBoardColumnFeb and
RowFpgaBoard/FpgaBoardRowFeb, two column boards, one row board, `maxRows=8`,
`numRowSelects=8`, `numChipSelects=0`, `pollEn=False`, `initRead=False`.
It verifies full-width 256-bit masks, gains and disabled PID/debug state across
both column boards. Slow-zero assertions read the actual emulated slow-DAC
registers after seeding nonzero outputs. Only fast-DAC completion is stubbed in
that test, since MemEmulate does not execute the FPGA FSM. This is not a physical
output measurement or a new GroupTb result.

Runtime: `/private/tmp/ops-fixes-runtime/bin/python`, an isolated venv over
`/Users/bareese/miniforge3/envs/rogue_build`: Python 3.12.13, locally modified
Rogue `v6.10.1-5-g8688d012b-dirty`, NumPy 2.4.2, SciPy 1.18.1, simple-pid 2.0.1,
SymPy 1.14.0, PyQt5 5.15.11 / Qt 5.15.19. No compatibility claim for other Rogue
versions. The system Python lacks NumPy; the base Rogue environment lacks
SciPy/simple-pid/SymPy and a complete QtDesigner import. Dependencies were added
only to the temporary venv. Runtime tests require localhost socket access.

Set `PYTHONPATH=software/python:firmware/python:firmware/submodules/surf/python`
and, for headless execution, `QT_QPA_PLATFORM=offscreen` and a writable
`MPLCONFIGDIR`. Local diagnostic logs are `/private/tmp/ops-fixes-unit.log`,
`ops-fixes-rogue.log`, `ops-fixes-setup-smoke.log` and `ops-fixes-before.log`
(all under `/private/tmp`). These are temporary diagnostics, not durable
hardware acceptance evidence. Maintained test scripts reproduce the checks.

The generated Group page comes from the same emulated board classes with one
column board, one row board, 32 row selects and default `maxRows=256`.
Before calling `root.genDocuments`, mark underscore-prefixed Group variables
`NoDoc` to omit GUI aliases; include `DocApi`/`TopApi` and exclude
`NoDoc`/`Enable`/`Hardware`. Copy only `GroupRoot_Group.rst` into the repository.
The local generator is `/private/tmp/ops-fixes-gendocs.py`. Other pre-existing
generated pages were not refreshed.

## Handoff and remaining prerequisites

1. Maintainer reviews/stages/commits/pushes the prepared changes to `ops-fixes`.
   The prior `channelization` checkout left simulation outputs and bytecode
   caches under `tests/`; `.gitignore` now excludes `tests/sim_build/` and local
   `.venv/` directories. The artifacts remain on disk; new test sources remain
   visible to Git.
2. Require CI on the new published head. The old passing run at `5549d4c` does
   not establish these corrections. [PR description draft](PR.md) captures the
   final scope and the present validation limits; update its revision when
   publishing evidence.
3. Complete applicable firmware integration checks with Vivado 2024.1 / GroupTb
   before declaring those prerequisites satisfied. Neither toolchain was run
   here. Local `firmware/build` contains only older testbench/cache directories.
   The identifier comparison is not synthesis/elaboration evidence.
4. The existing SURF pin `70191c1e11726cb5ba46725249acdc1f2daf76b2` is preserved.
   Relative to `pre-release`'s `4acecf9`, it adds upstream DDR SPD and RoCE work,
   including an ethernet build-loader change. The source-only WarmTDM rename
   comparison does not cover that dependency update. Ruckus remains
   `d9b775a8f0538fedb8134e809a976e5287c2cbb7`.
5. Merge into `pre-release` only when the applicable checks pass; keep #68/#99
   hardware acceptance open. Then bring the fixes into PR #106 with the normal
   merge workflow. Do not imply that existing channelization ancestry already
   contains these uncommitted changes.

Nothing was staged, committed, pushed or merged; no PR or issue was edited.
Remove this handoff after integration, retaining enduring usage guidance in
`docs/operations-api.md` and acceptance on the owning issues.
