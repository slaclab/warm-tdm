## Session core: the bound-Group handle, topology discovery, and read-only
## reporting (board enumeration, status, hardware-version print).
##
## This module owns ALL Session instance state -- __init__ populates self.group,
## self.root, self.hwg, self.cbs, self.rbs, self.rdds, self.chans_per_board and
## self.output, and every other mixin only *reads* those attributes. Keeping the
## shape in one place is what makes the mixin split honest (mixins never invent
## new self.* attributes).

import logging
import re

from ..channels import col_to_board_chan
from ._output import OutputDir

log = logging.getLogger(__name__)

# Board node names look like 'ColumnBoard[3]' / 'RowBoard[1]'.
_BOARD_INDEX_RE = re.compile(r'\[(\d+)\]$')

# The timing coordinator is always the first column board (RING_ADDR_0). This is
# a fixed hardware convention -- HardwareGroup itself assumes ColumnBoard[0] owns
# TimingTx (see _HardwareGroup.py). There is nothing to discover.
COORDINATOR_COL_BOARD = 0


class TopologyCore:
    """Session state + topology discovery + read-only reporting.

    The base of the ``Session`` mixin stack. Owns ``__init__`` and every instance
    attribute; the concern mixins (acquisition, tuning, force-DAC, hardware setup,
    config) are mounted on top and rely on the attributes defined here
    (``self.group``, ``self.root``, ``self.hwg``, ``self.cbs``, ``self.rbs``,
    ``self.rdds``, ``self.chans_per_board``, ``self.output``).
    """

    def __init__(self, group, output=None):
        self.group = group
        # Every attached pyrogue Node exposes .root (the Root it belongs to).
        # Group-scoped access goes through self.group; Root-scoped operations
        # (SaveConfig, DataWriter, ...) go through self.root.
        self.root = group.root
        self.hwg = group.HardwareGroup
        self.cbs = self._discover(getattr(self.hwg, 'ColumnBoard', None))
        self.rbs = self._discover(getattr(self.hwg, 'RowBoard', None))
        self.rdds = {k: rb.RowDacDriver for k, rb in self.rbs.items()}
        self.chans_per_board = self._derive_chans_per_board()
        self.output = output

    def _derive_chans_per_board(self):
        """Columns per column board = NumColumns / NumColumnBoards (from the tree).

        Falls back to the shared default (8) if the Group lacks the count vars or
        reports zero boards, so a partially-built tree never divides by zero.
        """
        try:
            n_cols = int(self.group.NumColumns.get())
            n_boards = int(self.group.NumColumnBoards.get())
            if n_boards > 0 and n_cols > 0:
                return n_cols // n_boards
        except (AttributeError, TypeError, ZeroDivisionError) as e:
            log.warning("Could not derive channels-per-board from Group (%s); "
                        "defaulting to 8.", e)
        return 8

    def col_to_board_chan(self, col):
        """Map a global column index to (board_index, channel) for this Group."""
        return col_to_board_chan(col, self.chans_per_board)

    @staticmethod
    def _discover(board_node):
        """Map a tree board-container node to {index: board}.

        Uses the tree node directly (``.values()``) and recovers the index from
        each board's ``name`` (e.g. 'ColumnBoard[3]' -> 3), which is sparse-safe
        and does not depend on scanning ``dir()`` of the parent.

        ``board_node`` may be ``None`` when the tree was built without that board
        type (e.g. a column-only bench with ``rowBoards=0`` has no ``RowBoard``
        container); returns an empty dict in that case.
        """
        boards = {}
        if board_node is None:
            return boards
        for board in board_node.values():
            m = _BOARD_INDEX_RE.search(board.name)
            if m:
                boards[int(m.group(1))] = board
        return boards

    @property
    def coordinator_cb(self):
        """The column board that owns timing (always ``ColumnBoard[0]``)."""
        return self.cbs[COORDINATOR_COL_BOARD]

    # ---- session output -------------------------------------------------

    def new_session(self, base=OutputDir.DEFAULT_BASE):
        """Start a fresh timestamped output directory for this session."""
        self.output = OutputDir(base=base)
        return self.output

    def _require_output(self):
        """Return the session dir, raising an actionable error if unset."""
        if self.output is None:
            raise RuntimeError(
                "No output directory set for this Session. Call "
                "session.new_session(path) (or ops.connect(..., path=...)) "
                "before taking or saving data.")
        return self.output.sessiondir

    # ---- board enumeration + read-only reporting -----------------------

    def boards(self):
        """Return {'Column N'/'Row N': board} for all connected boards."""
        boards = {}
        boards.update({f"Column {i}": b for i, b in self.cbs.items()})
        boards.update({f"Row {i}": b for i, b in self.rbs.items()})
        return boards

    def status(self):
        """Print a one-shot summary of the instrument state, and return it.

        The "where am I?" answer for an interactive prompt: board counts, timing
        run/MUX mode, tune-enabled columns, and the output dir. Read-only; safe
        to call any time.

        Returns:
            dict: the same fields that are printed (for scripting).
        """
        st = {
            'columns': sorted(self.cbs),
            'rows': sorted(self.rbs),
            'chans_per_board': self.chans_per_board,
            'output_dir': (self.output.sessiondir if self.output else None),
        }
        try:
            tx = self.coordinator_cb.WarmTdmCore.Timing.TimingTx
            st['running'] = bool(tx.Running.get())
            # Mode: 1 = hardware MUX (free-running), 0 = software-stepped/manual.
            st['mux_mode'] = 'MUX' if tx.Mode.get() == 1 else 'manual'
        except (AttributeError, TypeError, KeyError) as e:
            log.error("Could not read timing state: %s", e)
            st['running'] = st['mux_mode'] = None
        try:
            col_en = self.group.ColTuneEnable.get()
            st['tune_enabled_cols'] = [c for c, en in enumerate(col_en) if en]
        except (AttributeError, TypeError) as e:
            log.error("Could not read ColTuneEnable: %s", e)
            st['tune_enabled_cols'] = None

        print("+" * 60)
        print("Session status")
        print("+" * 60)
        print(f"  Column boards      : {st['columns']}")
        print(f"  Row boards         : {st['rows']}")
        print(f"  Channels/board     : {st['chans_per_board']}")
        print(f"  Timing run state   : {'RUNNING' if st['running'] else 'stopped'}")
        print(f"  Timing mode        : {st['mux_mode']}")
        print(f"  Tune-enabled cols  : {st['tune_enabled_cols']}")
        print(f"  Output dir         : {st['output_dir']}")
        print("+" * 60)
        return st

    def print_hardware(self):
        """Print firmware/hardware version info for all connected boards."""
        boards = self.boards()
        if not boards:
            print("No column or row boards found.")
            return

        print("+" * 80)
        print("Hardware Information")
        print("+" * 80)
        for board_name, board in sorted(boards.items()):
            try:
                board_type, board_index = board_name.split(" ")
                av = board.WarmTdmCore.WarmTdmCommon2.AxiVersion
                print(f"{board_type} Board {board_index}:")
                print(f"  BuildStamp       : {av.BuildStamp.get()}")
                print(f"  DeviceDna        : {hex(av.DeviceDna.get())}")
                print(f"  Git hash         : {hex(av.GitHash.get())}")
                print(f"  Image Name       : {av.ImageName.get()}")
                print("---")
            except (AttributeError, TypeError) as e:
                log.error("Error retrieving information for %s: %s", board_name, e)
        print("+" * 80)
