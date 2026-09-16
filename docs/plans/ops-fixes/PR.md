# Operations fixes: enabled columns, board-local setup and safe-state cleanup

Draft replacement description for PR #107. Publish after the corrections are
committed, replacing the working-tree qualification with the tested revision
and its CI link.

Operations now keep the configured enabled columns consistent with the run:
`setup_mux` applies PID/debug enables and desired row masks across all column
boards, disabling PID/debug on deselected columns. PID gains use the
sample-count-normalized Group variables, and explicit debug changes address
the selected column's board.

`apply_dead_masks` writes each board-local row mask before updating the saved
`Group.RowEnableMasks` state. `stop_and_zero` addresses every column's fast and
slow outputs regardless of `ColEnableMask`, continues after individual write
failures and reports incomplete cleanup. Full-width mask values and these
paths work through direct and VirtualClient Sessions.

The branch also adopts `ColEnableMask` and logical-row naming throughout the
Python/RTL interface, aligns manual row commands with their drivers, and adds
optional SQ1 fitted-table application. A Stop during the final SQ1 row leaves
the tables unapplied; missing/nonfinite fits fail before table writes. The GUI,
operations guide and generated Group reference reflect the updated interface.

Refs #68, #83, #99. Remaining hardware acceptance stays on #68/#99; merging this
implementation does not close those issues.

## Validation

- Local working tree over `5549d4c`: 81 unit tests and 10 Rogue runtime tests
  pass, including production two-board memory-emulation checks through direct
  and VirtualClient Sessions. New regressions reproduce failures against the
  published source. See `docs/plans/ops-fixes/README.md` for configuration and
  runtime provenance.
- Python syntax, Qt UI XML and whitespace checks pass.
- All eight changed production VHDL files are token-equivalent to `pre-release`
  after the intended identifier renames. Register offsets and logic tokens are
  unchanged by those edits. This is not synthesis or GroupTb evidence.
- The production slow-zero smoke stubs fast-DAC completion only; it checks fresh
  emulated slow-DAC register readbacks. Physical outputs and real-SQUID tuning
  remain unverified by these tests.

## Before merging

- Publish the corrections and pass CI on that head; the old green run does not
  cover uncommitted changes.
- Complete the applicable firmware build/elaboration checks. The SURF update
  from `4acecf9` to `70191c1` also includes upstream DDR SPD/RoCE changes and is
  separate from the WarmTDM identifier-only comparison. No new Vivado 2024.1
  synthesis, GroupTb or hardware result is claimed here.
- Incorporate the corrected revision into dependent PR #106 through the normal
  merge workflow.
