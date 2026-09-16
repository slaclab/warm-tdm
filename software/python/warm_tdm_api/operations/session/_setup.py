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
                  strobe=False, enable_pid=True, enable_pid_debug=False,
                  run_now=False):
        """Configure hardware for multiplexed readout and enable PID servos.

        Sets the row period + sample window on the coordinator board, puts all
        row DAC drivers into timing mode, and enables SQ1 PID for every column
        flagged active in ColEnableMask. The sample window sits near the end of
        each row period: start = num_pts - sample_end_offset - sample_num,
        end = num_pts - sample_end_offset. Existing Group-level normalized PID
        gains are preserved, so the hardware P/I/D coefficients are rescaled
        inversely with ``sample_num``. ``set_pid`` sets those same normalized
        gains, so call it after ``setup_mux`` to give a specific gain the final
        say for the configured window.

        Configuration and run-start are separate: this only configures. Call
        ``run_mux()`` to start the free-running readout, or pass
        ``run_now=True`` to start it here once configuration succeeds.
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
        # number of accumulated samples.  The underlying AdcDsp coefficients
        # operate on an error sum and must therefore scale as 1/N.  The
        # floating-point PI DSP exposes only P/I gains (no D), so preserve
        # whichever gains the group actually publishes.
        _pid_gain_names = [name for name in ('PidP_Gain', 'PidI_Gain', 'PidD_Gain')
                           if hasattr(self.group, name)]
        normalized_pid_gains = None
        if _pid_gain_names:
            normalized_pid_gains = {
                name: list(getattr(self.group, name).get(read=True))
                for name in _pid_gain_names}

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
        # Make the run's PID enable-set exactly track ColEnableMask: iterate ALL
        # columns, enabling PID (+clear, +debug) on the selected ones and
        # explicitly disabling (+clear) the de-selected ones. A previously
        # enabled, now-deselected column must not keep servoing.
        col_enabled = self.col_enable_bools()
        for col, enabled in enumerate(col_enabled):
            dsp = cb.DataPath.AdcDsp[col]
            dsp.ClearPids()
            dsp.PidEnable.set(bool(enable_pid) and bool(enabled))
            dsp.PidDebugEnable.set(bool(enable_pid_debug) and bool(enabled))
            print(f"{'Enabling' if enabled else 'Disabling'} PID for column {col}")

        # Apply the per-column dead-row masks as part of MUX setup so the run's
        # active-row set matches the configured Group.RowEnableMasks.
        if hasattr(self.group, 'RowEnableMasks'):
            masks = self.group.RowEnableMasks.get(read=True)
            for col, enabled in enumerate(col_enabled):
                if enabled:
                    cb.DataPath.AdcDsp[col].RowEnableMask.set(int(masks[col]))

        if run_now:
            self.run_mux()

    def run_mux(self):
        """Start the free-running multiplexed readout on the coordinator.

        Setup and run-start are separated: configure with ``setup_mux`` (which
        does not start a run unless ``run_now=True``), then call this to begin
        the MUX. ``take_data`` captures within an already-running MUX without
        stopping it, so setup_mux -> run_mux -> take_data leaves the run going;
        ``stop_and_zero`` (or ``TimingTx.EndRun``) ends it.

        No-op with a warning if a run is already active, so it is safe to call
        after ``setup_mux(run_now=True)``.
        """
        tx = self.coordinator_cb.WarmTdmCore.Timing.TimingTx
        if tx.Running.get():
            log.warning("run_mux: a run is already active; leaving it running.")
            return
        tx.StartRun()
        print("MUX run started.")

    def set_pid(self, p=None, i=None, d=None, cols=None, debug=None):
        """Set the sample-count-normalized per-column PID gains.

        Writes the Group-level normalized gains ``PidP_Gain``/``PidI_Gain``/
        ``PidD_Gain`` -- the same quantity ``setup_mux`` snapshots and re-applies
        across a sample-window change. These present the flux-lock-loop gain on
        the *mean* row-window error, so the value is independent of ``sample_num``:
        each write divides by the coordinator's current ``TimingTx.SampleCount``
        before storing the fixed-point ``AdcDsp`` coefficient (see
        ``PidGainVariable``). Only the gains passed (not ``None``) are written.
        ``cols`` selects global column indices (default: columns enabled in
        ``ColEnableMask``); ``debug`` optionally sets each selected column's
        ``PidDebugEnable``.

        Call after ``setup_mux`` to give these gains the final say, since
        ``setup_mux`` re-applies the pre-existing normalized gains for the
        configured window.
        """
        for name in ('PidP_Gain', 'PidI_Gain', 'PidD_Gain'):
            if not hasattr(self.group, name):
                log.error("Group is missing %s; cannot set normalized PID gains. "
                          "This tree predates the sample-count-aware PID API.", name)
                return

        cb = self.coordinator_cb
        if cols is None:
            cols = [c for c, en in enumerate(self.col_enable_bools()) if en]
        gain_vars = (('P', p, self.group.PidP_Gain),
                     ('I', i, self.group.PidI_Gain),
                     ('D', d, self.group.PidD_Gain))
        for col in cols:
            for _label, value, gain_var in gain_vars:
                if value is not None:
                    gain_var.set(value=float(value), index=col)
            if debug is not None:
                cb.DataPath.AdcDsp[col].PidDebugEnable.set(bool(debug))
            print(f"Set PID for column {col}: " + ", ".join(
                f"{k}={v}" for k, v in
                (('P', p), ('I', i), ('D', d), ('debug', debug)) if v is not None))

    def apply_dead_masks(self, dead_masks):
        """Write per-column dead-row masks through ``Group.RowEnableMasks``
        (issue #83, G9).

        This is the bridge from the pure ``make_dead_masks`` / ``read_dead_masks``
        helpers (which only build ``{col: mask}`` dicts and read/write mask files)
        to the graduated Group variable: each mask is a 256-bit integer where bit
        ``row`` = 1 means the row is active, 0 means dead. The servo acts only on
        rows whose bit is set. Writing ``Group.RowEnableMasks`` stores the desired
        state and drives the corresponding ``AdcDsp[col].RowEnableMask`` register;
        ``setup_mux`` re-applies it as part of MUX setup.

        ``col`` keys are **global** column indices; columns whose board is not
        present are skipped with a warning.

        Args:
            dead_masks (dict): ``{col: mask}`` as returned by
                ``make_dead_masks``/``read_dead_masks``.
        """
        if not self.cbs:
            log.error("No column boards detected. Cannot apply dead masks.")
            return
        if not hasattr(self.group, 'RowEnableMasks'):
            log.error("Group has no RowEnableMasks variable; cannot apply dead masks.")
            return

        for col, mask in sorted(dead_masks.items()):
            board_idx, _chan = self.col_to_board_chan(col)
            if self.cbs.get(board_idx) is None:
                log.warning("Column %d maps to absent column board %d; "
                            "skipping dead mask.", col, board_idx)
                continue
            self.group.RowEnableMasks.set(value=int(mask), index=col)
            print(f"Applied dead mask for column {col}.")

    def read_hardware_dead_masks(self):
        """Read the live per-column ``AdcDsp[col].RowEnableMask`` registers back
        into a ``{col: mask}`` dict.

        The read-side companion to ``apply_dead_masks``: pairs with
        ``channels.write_dead_masks`` to round-trip the hardware masks to a file.
        Columns on absent boards are skipped. Global column indices key the dict.
        """
        masks = {}
        for col in range(int(self.group.NumColumns.get())):
            board_idx, chan = self.col_to_board_chan(col)
            cb = self.cbs.get(board_idx)
            if cb is None:
                continue
            masks[col] = int(cb.DataPath.AdcDsp[chan].RowEnableMask.get(read=True))
        return masks
