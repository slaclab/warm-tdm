## Multiplexed-readout configuration: MUX/PID setup and per-column dead-row masks.
##
## Reaches through fixed device-tree paths (TimingTx row-period/sample-window,
## RowDacDriver.Mode, DataPath.AdcDsp[col].PidEnable / RowEnableMask). Relies on
## TopologyCore state (self.cbs, self.rbs, self.rdds, self.group,
## self.coordinator_cb, self.col_to_board_chan). Mounted on Session.

import logging

from ._core import COORDINATOR_COL_BOARD

log = logging.getLogger(__name__)


class SetupMixin:
    """Configure MUX/PID readout and apply per-column dead-row masks."""

    def setup_mux(self, num_pts=2048, sample_end_offset=100, sample_num=250,
                  strobe=False, enable_pid=True, enable_pid_debug=False):
        """Configure hardware for multiplexed readout and enable PID servos.

        Sets the row period + sample window on the coordinator board, puts all
        row DAC drivers into timing mode, and enables SQ1 PID for every column
        flagged active in ColTuneEnable. The sample window sits near the end of
        each row period: start = num_pts - sample_end_offset - sample_num,
        end = num_pts - sample_end_offset. Existing Group-level normalized PID
        gains are preserved, so the hardware P/I/D coefficients are rescaled
        inversely with ``sample_num``.
        """
        if not self.cbs:
            log.error("No column boards detected. Cannot setup multiplexing.")
            return
        if not self.rbs:
            log.error("No row boards detected. Cannot setup multiplexing.")
            return
        if len(self.cbs) > 1:
            log.warning("Multiple column boards detected %s. Assuming ColumnBoard[%d] "
                        "is the controller.", list(self.cbs.keys()), COORDINATOR_COL_BOARD)
        if len(self.rbs) > 1:
            log.warning("Multiple row boards detected %s. Applying commands to all.",
                        list(self.rbs.keys()))

        cb = self.coordinator_cb

        # Preserve the gains on the mean row-window error while changing the
        # number of accumulated samples.  The underlying fixed-point AdcDsp
        # coefficients operate on an error sum and must therefore scale as 1/N.
        normalized_pid_gains = None
        if all(hasattr(self.group, name)
               for name in ('PidP_Gain', 'PidI_Gain', 'PidD_Gain')):
            normalized_pid_gains = {
                name: list(getattr(self.group, name).get(read=True))
                for name in ('PidP_Gain', 'PidI_Gain', 'PidD_Gain')}

        # Mode 1 = hardware MUX (free-running), Mode 0 = software-stepped
        cb.WarmTdmCore.Timing.TimingTx.Mode.set(0 if strobe else 1)

        num_pts = int(num_pts)
        cb.WarmTdmCore.Timing.TimingTx.RowPeriodCycles.set(num_pts)
        cb.WarmTdmCore.Timing.TimingTx.SampleStartTime.set(num_pts - sample_end_offset - sample_num)
        cb.WarmTdmCore.Timing.TimingTx.SampleEndTime.set(num_pts - sample_end_offset)

        if normalized_pid_gains is not None:
            for name, gains in normalized_pid_gains.items():
                getattr(self.group, name).set(gains)

        # Put all row DAC drivers in timing mode so they switch rows during MUX
        for rb_idx, rdd in self.rdds.items():
            rdd.Mode.set(0)
            if len(self.rdds) > 1:
                print(f"Set RowBoard[{rb_idx}] to timing mode.")

        # TODO: expand to support multiple column boards.
        # Enable PID for all columns flagged active in ColTuneEnable.
        col_list = self.group.ColTuneEnable.get()
        for col, enabled in enumerate(col_list):
            if enabled:
                print(f"Enabling PID for column {col}")
                cb.DataPath.AdcDsp[col].ClearPids()
                cb.DataPath.AdcDsp[col].PidEnable.set(enable_pid)
                cb.DataPath.AdcDsp[col].PidDebugEnable.set(enable_pid_debug)

    def apply_dead_masks(self, dead_masks):
        """Write per-column dead-row masks to the ``AdcDsp[col].RowEnableMask``
        hardware registers (issue #83, G9).

        This is the missing bridge from the pure ``make_dead_masks`` /
        ``read_dead_masks`` helpers (which only build ``{col: mask}`` dicts and
        read/write mask files) to hardware: each mask is a 256-bit integer where
        bit ``row`` = 1 means the row is active, 0 means dead. The servo acts only
        on rows whose bit is set.

        ``col`` keys are **global** column indices; they are mapped to the owning
        column board and its board-local ``AdcDsp`` channel via the tree-derived
        ``chans_per_board``. Columns whose board is not present are skipped with a
        warning. Written values are read-back verified by the transaction.

        Args:
            dead_masks (dict): ``{col: mask}`` as returned by
                ``make_dead_masks``/``read_dead_masks``.
        """
        if not self.cbs:
            log.error("No column boards detected. Cannot apply dead masks.")
            return

        for col, mask in sorted(dead_masks.items()):
            board_idx, chan = self.col_to_board_chan(col)
            cb = self.cbs.get(board_idx)
            if cb is None:
                log.warning("Column %d maps to absent column board %d; "
                            "skipping dead mask.", col, board_idx)
                continue
            cb.DataPath.AdcDsp[chan].RowEnableMask.set(mask)
            print(f"Applied dead mask for column {col} "
                  f"(ColumnBoard[{board_idx}].AdcDsp[{chan}]).")
