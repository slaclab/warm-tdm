# Two-level FAS tuning

## Goal and scope

Extend `FasTuneProcess` to operate directly on two-level `RowMap` entries,
including logical rows 10–13 of the standard 8×10 map (RS 0–3, shared CS 11).
Keep one-level tuning available. Existing FAS commissioning and hardware
acceptance are owned by [#99](https://github.com/slaclab/warm-tdm/issues/99).

The user explicitly requested discovery when both RS and CS on-currents are
unknown. The implemented two-level path scans an RS×CS grid per active logical row,
refines each axis, aggregates candidates by shared physical output, and measures
the resulting pairs before programming. The user's follow-up clarified that
topology must come entirely from `RowMap`; the proposed FAS mode selector and
partial-sweep branches have been removed. No duplicate Group flag is needed.

## Status and decisions

- Implemented locally; no staging or commits. Two-level maps dispatch from
  `fasTune` to `_fas_two_level.py`; flat maps retain the existing sweep.
- Each run redetects the topology from active `RowMap` entries. The same
  `session.fas_tune()` or GUI Start action handles either configuration.
- Preserve logical row indices and the original map/readout order; these also
  index the SA feedback seed table.
- Resolve and validate physical RS/CS pairs before writes. Account for all
  mapped lines when isolating the selected pair, including inactive rows and
  companion lines on another row board.
- Keep persistent programming deferred until every requested sweep completes;
  preserve Stop, partial-result publication, rollback, and force/mode cleanup.
- Include the swept level and companion context in results and plots.
- Publish discovery grids and final four-state measurements. Reject missing
  response on either axis and incompatible shared settings before programming.
- Preserve the existing response-minimum convention; response polarity and
  configured off-current validity remain explicit commissioning assumptions.
- Row-driver TIMING mode suppresses FasOn write-through during programming
  while timing is stopped, so committing several table entries cannot turn
  multiple row/chip paths on simultaneously. Stop racing the final mode
  restoration rolls back touched table entries.

## Files and validation

Implementation: `software/python/warm_tdm_api/tuning/_fas_two_level.py`,
dispatch in `tuning/_fas.py`, strict optional servo convergence in
`tuning/_common.py`, and controls/results/plots in `_FasTune.py` and the FAS
GUI tab. Usage/design guidance is in
[the FAS design record](../../design/fas-tuning.md),
`software/SOFTWARE_GUIDE.md`, and the operations API.

`software/tests/test_fas_two_level.py` exercises real tuning functions with
fake hardware and synthetic measured-response callbacks. All 27 focused tests
passed using Python 3.11 with NumPy, SciPy, Matplotlib/Agg, pytest and simple-pid.
Coverage includes the 8×10 subset with unknown on-currents, redetection after
changing the same process's map from one level to two and back, cross-board
companions, inactive-line isolation, multiple enabled
columns with different offsets, shared RS across chips, shared-CS conflicts,
off-state leakage rejection, Stop during acquisition/verification/programming/final
mode restore, partial hardware-write failures, cleanup errors, strict servo
timeout/non-finite rejection, and complete/partial/empty plot rendering.

The final full software suite passed **99 tests**, including all 27 FAS tests,
using `python -m unittest discover -s software/tests -v`. Changed Python files
parse with Python 3.8 grammar, and whitespace checks passed. The test environment
was the existing `rogue-build` Python 3.11 environment, with the locally
available pure-Python `simple_pid` package supplied through a temporary
`PYTHONPATH`; Matplotlib used Agg and temporary cache directories. All
measurements in these tests are synthetic: there is no RTL, real Rogue
transport, or cryogenic acceptance evidence for this extension yet.

## Remaining acceptance

The implementation and usage notes are ready for review. Before bench use,
restart the server with these changes and establish appropriate sweep ranges,
off currents, SQ1 bias, settling delay, response polarity, and response/isolation
thresholds. Start with `SetAfterFinish=False`. The four requested rows produce
four grids, eight refinement curves, and four verification records.

Remaining acceptance under #99 includes the real request/settling path in
two-level RTL co-simulation, then cryogenic response and physical isolation.
The software preserves the existing no-acknowledgement ManualSet interface.
A coarse grid can miss a narrow on region; shared-current medians can fail
verification even when another combination of periodic branches would work.
Discovery does not determine off currents or validate inactive logical rows.
