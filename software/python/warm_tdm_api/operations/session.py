##
## Session: the hardware handle for the operations layer.
##
## Replaces the former all-classmethod `Client` global singleton. A `Session`
## wraps a connected pyrogue client, discovers the boards from the device tree,
## and exposes every hardware-coupled operation (acquisition + setup helpers) as
## a method. Because it is an ordinary instance:
##   - tests can construct one around a fake/emulate client, no global state;
##   - two systems are simply two Session objects;
##   - a method never sees a half-initialized handle (boards are populated in
##     __init__), and missing pieces raise clear RuntimeErrors, not AttributeError.
##
## For notebook ergonomics a module-level *default* Session is kept: `connect()`
## / `use()` build one and cache it, and thin free-function shims (exported from
## the package, e.g. `ops.take_raw(0)`) delegate to it. Scripts/tests that want
## explicitness call methods on their own Session instead.

import os
import re
import time
import logging
import datetime

import numpy as np

log = logging.getLogger(__name__)

# Board node names look like 'ColumnBoard[3]' / 'RowBoard[1]'.
_BOARD_INDEX_RE = re.compile(r'\[(\d+)\]$')


class OutputDir:
    """Timestamped output directory for a data-taking session.

    Owns ``<base>/<YYYYMMDD>/<ctime0>/`` and is constructed independently of any
    client binding (unlike the old ``Client.set_client`` which created this as a
    side effect). Falls back to a local ``data`` dir then the home directory if
    the requested base is not writable.
    """

    DEFAULT_BASE = '/data/warm_tdm/'

    def __init__(self, base=DEFAULT_BASE):
        base = self._resolve_base(base)
        self.date = datetime.datetime.now().strftime('%Y%m%d')
        self.datedir = os.path.join(base, self.date)
        self.ctime0 = str(int(time.time()))
        self.sessiondir = os.path.join(self.datedir, self.ctime0)
        os.makedirs(self.sessiondir, exist_ok=True)
        log.info("Session output directory: %s", self.sessiondir)

    @staticmethod
    def _resolve_base(base):
        """Return the first writable base among: requested, ../data, home."""
        if os.path.isdir(base) and os.access(base, os.W_OK):
            return base
        log.warning("Output path '%s' does not exist or is not writable; "
                    "falling back.", base)

        fallback = os.path.join(os.path.dirname(os.getcwd()), 'data')
        if os.path.isdir(fallback) and os.access(fallback, os.W_OK):
            return fallback
        log.warning("Fallback path '%s' also unusable; defaulting to home.",
                    fallback)
        return os.path.expanduser('~')

    def __fspath__(self):
        return self.sessiondir

    def __repr__(self):
        return f"<OutputDir sessiondir='{self.sessiondir}'>"


class Session:
    """A connected Warm-TDM hardware handle.

    Wraps a pyrogue client (typically a ``pyrogue.interfaces.VirtualClient``),
    discovers the column/row boards from the device tree, and provides the
    acquisition and hardware-setup operations as methods.

    Attributes:
        client: the wrapped pyrogue client (has ``.root``).
        hwg: ``client.root.Group.HardwareGroup``.
        cbs (dict): {index: ColumnBoard node}.
        rbs (dict): {index: RowBoard node}.
        rdds (dict): {index: RowDacDriver node} for each row board.
        coordinator_col (int): index of the column board that owns timing
            (default 0); used where a single controller board is assumed.
        output (OutputDir | None): where data files are written.
    """

    def __init__(self, client, output=None, coordinator_col=0):
        self.client = client
        self.hwg = client.root.Group.HardwareGroup
        self.cbs = self._discover(self.hwg.ColumnBoard)
        self.rbs = self._discover(self.hwg.RowBoard)
        self.rdds = {k: rb.RowDacDriver for k, rb in self.rbs.items()}
        self.coordinator_col = coordinator_col
        self.output = output

    @staticmethod
    def _discover(board_node):
        """Map a tree board-container node to {index: board}.

        Uses the tree node directly (``.values()``) and recovers the index from
        each board's ``name`` (e.g. 'ColumnBoard[3]' -> 3), which is sparse-safe
        and does not depend on scanning ``dir()`` of the parent.
        """
        boards = {}
        for board in board_node.values():
            m = _BOARD_INDEX_RE.search(board.name)
            if m:
                boards[int(m.group(1))] = board
        return boards

    @property
    def root(self):
        return self.client.root

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

    # ---- board enumeration ---------------------------------------------

    def boards(self):
        """Return {'Column N'/'Row N': board} for all connected boards."""
        boards = {}
        boards.update({f"Column {i}": b for i, b in self.cbs.items()})
        boards.update({f"Row {i}": b for i, b in self.rbs.items()})
        return boards

    # ---- hardware info / setup (ported from utils.py) -------------------

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

    def disable_leds(self):
        """Disable status-blinking LEDs on all boards."""
        boards = self.boards()
        if not boards:
            print("No column or row boards found.")
            return

        for board_name, board in sorted(boards.items()):
            try:
                board_type, board_index = board_name.split(" ")
                board.WarmTdmCore.WarmTdmCommon2.WarmTdmConfig.LedEn.set(False)
                print(f"Disabled LEDs for {board_type} Board {board_index}.")
            except (AttributeError, TypeError) as e:
                log.error("Error disabling LEDs for %s: %s", board_name, e)

    def set_cryo_resistance(self, Rcryo_Ohm):
        """Set cryostat roundtrip cable resistance on all boards' AFE amps.

        Column boards: sets CableR on SAFbAmp/SQ1BiasAmp/SQ1FbAmp/TesBiasAmp and
        R_CABLE on SAAmp, for all 8 channels. Row boards: CableR on Amp[0..31].
        """
        boards = self.boards()
        if not boards:
            print("No column or row boards found.")
            return

        for board_name, board in sorted(boards.items()):
            try:
                board_type, board_index = board_name.split(" ")
                if board_type == "Column":
                    for ch in range(8):
                        afe_ch = getattr(board.AnalogFrontEnd, f'Channel[{ch}]')
                        afe_ch.SAFbAmp.CableR.set(Rcryo_Ohm)
                        afe_ch.SQ1BiasAmp.CableR.set(Rcryo_Ohm)
                        afe_ch.SQ1FbAmp.CableR.set(Rcryo_Ohm)
                        afe_ch.TesBiasAmp.CableR.set(Rcryo_Ohm)
                        afe_ch.SAAmp.R_CABLE.set(Rcryo_Ohm)
                    print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm for Column Board {board_index}.")
                elif board_type == "Row":
                    for rs in range(32):
                        getattr(board.AnalogFrontEnd, f'Amp[{rs}]').CableR.set(Rcryo_Ohm)
                    print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm for Row Board {board_index}.")
            except (AttributeError, TypeError) as e:
                log.error("Error setting cryostat resistance for %s: %s", board_name, e)

    def set_ps_synch(self, sync_mode):
        """Set power-supply synchronization mode on all boards.

        Synchronized (sync_mode=1): PwrSyncA/B/C=2, PwrSyncEn=1.
        Unsynchronized (sync_mode=0): PwrSyncA/B/C=0, PwrSyncEn=0.
        """
        boards = self.boards()
        if not boards:
            print("No column or row boards found.")
            return

        for board_name, board in sorted(boards.items()):
            try:
                board_type, board_index = board_name.split(" ")
                tx = board.WarmTdmCore.Timing.TimingTx
                if sync_mode == 0:
                    tx.PwrSyncA.set(0)
                    tx.PwrSyncB.set(0)
                    tx.PwrSyncC.set(0)
                    tx.PwrSyncEn.set(0)
                    print(f"Unsynchronized power supplies for {board_type} Board {board_index}.")
                elif sync_mode == 1:
                    tx.PwrSyncA.set(2)
                    tx.PwrSyncB.set(2)
                    tx.PwrSyncC.set(2)
                    tx.PwrSyncEn.set(1)
                    print(f"Synchronized power supplies for {board_type} Board {board_index}.")
                else:
                    log.warning("Invalid sync_mode value: %s", sync_mode)
            except (AttributeError, TypeError) as e:
                log.error("Error setting power supply synchronization for %s: %s", board_name, e)

    def check_ps_synch(self):
        """Print the power-supply synchronization state across all boards."""
        boards = self.boards()
        if not boards:
            print("No column or row boards found.")
            return

        sync_state = set()
        for board_name, board in sorted(boards.items()):
            try:
                tx = board.WarmTdmCore.Timing.TimingTx
                if (tx.PwrSyncA.get() == 2 and tx.PwrSyncB.get() == 2
                        and tx.PwrSyncC.get() == 2 and tx.PwrSyncEn.get() == 1):
                    sync_state.add("Synchronized")
                else:
                    sync_state.add("Unsynchronized")
            except (AttributeError, TypeError) as e:
                log.error("Error checking power supply synchronization for %s: %s", board_name, e)

        if len(sync_state) == 1:
            print(f"Power supplies are {sync_state.pop()}.")
        else:
            print("Power supplies are in a mixed state (some synchronized, some unsynchronized).")

    def all_off(self):
        """Zero all signal outputs and stop multiplexing (clean-slate reset).

        Zeros all non-multiplexed column outputs (SQ1/SA/TES bias + feedback),
        ends any active run, and switches the coordinator board to manual timing.

        Note: a firmware bug currently prevents zeroing biases after dropping out
        of multiplexing; row-DAC zeroing is left commented pending resolution.
        """
        r = None
        try:
            for r in ['Sq1FbForceCurrent', 'Sq1BiasForceCurrent', 'SaFbForceCurrent',
                      'SaBiasCurrent', 'SaOffset', 'TesBias']:
                var = getattr(self.root.Group, r)
                var.set(np.zeros_like(var.get()))
        except (AttributeError, TypeError) as e:
            log.error("Error zeroing %s: %s", r, e)

        # End the run if active; dropping out of MUX should zero multiplexed
        # outputs. The coordinator column board owns timing.
        cb0 = self.cbs[self.coordinator_col]
        if cb0.WarmTdmCore.Timing.TimingTx.Running.get():
            cb0.WarmTdmCore.Timing.TimingTx.EndRun()

        # Switch to manual (non-MUX) timing mode
        cb0.WarmTdmCore.Timing.TimingTx.Mode.set(0)

        # TODO: zero row DACs once firmware bug is resolved
        # for i, rdd in self.rdds.items():
        #     rdd.FasOn.Current.set(np.zeros_like(rdd.FasOn.Current.get()))
        #     rdd.FasOff.Current.set(np.zeros_like(rdd.FasOn.Current.get()))

    def save_config(self):
        """Save writable config to ``<sessiondir>/config_<ctime>.yml``."""
        ctime = int(time.time())
        filename = os.path.join(self._require_output(), f'config_{ctime}.yml')
        self.root.SaveConfig(filename)
        print(f'Saved config to {filename}')
        return filename

    def save_state(self):
        """Save full system state (incl. RO) to ``<sessiondir>/state_<ctime>.yml``."""
        ctime = int(time.time())
        filename = os.path.join(self._require_output(), f'state_{ctime}.yml')
        self.root.SaveState(filename)
        print(f'Saved state to {filename}')
        return filename

    def load_config(self, filename):
        """Load a hardware configuration YAML saved by save_config()."""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Configuration file '{filename}' not found.")
        self.root.LoadConfig(filename)
        print(f"Loaded configuration from {filename}")

    def setup_mux(self, num_pts=2048, sample_end_offset=100, sample_num=250,
                  strobe=False, enable_pid=True, enable_pid_debug=False):
        """Configure hardware for multiplexed readout and enable PID servos.

        Sets the row period + sample window on the coordinator board, puts all
        row DAC drivers into timing mode, and enables SQ1 PID for every column
        flagged active in ColTuneEnable. The sample window sits near the end of
        each row period: start = num_pts - sample_end_offset - sample_num,
        end = num_pts - sample_end_offset.
        """
        if not self.cbs:
            log.error("No column boards detected. Cannot setup multiplexing.")
            return
        if not self.rbs:
            log.error("No row boards detected. Cannot setup multiplexing.")
            return
        if len(self.cbs) > 1:
            log.warning("Multiple column boards detected %s. Assuming ColumnBoard[%d] "
                        "is the controller.", list(self.cbs.keys()), self.coordinator_col)
        if len(self.rbs) > 1:
            log.warning("Multiple row boards detected %s. Applying commands to all.",
                        list(self.rbs.keys()))

        cb = self.cbs[self.coordinator_col]

        # Mode 1 = hardware MUX (free-running), Mode 0 = software-stepped
        cb.WarmTdmCore.Timing.TimingTx.Mode.set(0 if strobe else 1)

        num_pts = int(num_pts)
        cb.WarmTdmCore.Timing.TimingTx.RowPeriodCycles.set(num_pts)
        cb.WarmTdmCore.Timing.TimingTx.SampleStartTime.set(num_pts - sample_end_offset - sample_num)
        cb.WarmTdmCore.Timing.TimingTx.SampleEndTime.set(num_pts - sample_end_offset)

        # Put all row DAC drivers in timing mode so they switch rows during MUX
        for rb_idx, rdd in self.rdds.items():
            rdd.Mode.set(0)
            if len(self.rdds) > 1:
                print(f"Set RowBoard[{rb_idx}] to timing mode.")

        # TODO: expand to support multiple column boards.
        # Enable PID for all columns flagged active in ColTuneEnable.
        col_list = self.root.Group.ColTuneEnable.get()
        for col, enabled in enumerate(col_list):
            if enabled:
                print(f"Enabling PID for column {col}")
                cb.DataPath.AdcDsp[col].ClearPids()
                cb.DataPath.AdcDsp[col].PidEnable.set(enable_pid)
                cb.DataPath.AdcDsp[col].PidDebugEnable.set(enable_pid_debug)

    # ---- acquisition (ported from data.py) ------------------------------

    def take_raw(self, col, outputdir=None, synch=False, decimation=0,
                 check_delay_sec=0.1, timeout_sec=30.0):
        """Capture a raw waveform for a single column; return the saved path.

        Args:
            col (int): global column index.
            outputdir (str, optional): where to save; defaults to the session dir.
            synch (bool): synchronized vs asynchronous capture trigger.
            decimation (int): decimation factor (0 = none).
            check_delay_sec (float): poll interval while waiting for the file.
            timeout_sec (float): max wait before raising TimeoutError.

        Raises:
            TimeoutError: if no new waveform file appears within timeout_sec.
        """
        wcr = self.hwg.WaveformCaptureReceiver
        last_raw0 = wcr.LastSavedFileName.get()

        cb = self.cbs[col // 8]

        if outputdir is None:
            outputdir = self._require_output()

        wcr.SavedFilePath.set(outputdir)
        wcr.SaveData.set(True)

        cb.DataPath.WaveformCapture.AllChannels.set(False)
        cb.DataPath.WaveformCapture.SelectedChannel.set(col % 8)
        cb.DataPath.WaveformCapture.Decimation.set(decimation)
        wcr.PlotColumn.set(col % 8)
        wcr.PlotWaveform.set(True)

        if synch:
            cb.WarmTdmCore.Timing.TimingTx.WaveformCapture()
        else:
            cb.DataPath.WaveformCapture.CaptureWaveform()

        # Wait for the waveform to be saved to disk (bounded by timeout_sec).
        last_raw = None
        deadline = time.time() + timeout_sec
        try:
            while True:
                if last_raw is not None:
                    if last_raw != last_raw0 and os.path.getsize(last_raw) > 0:
                        break
                if time.time() > deadline:
                    raise TimeoutError(
                        f"take_raw: no new waveform file for column {col} within "
                        f"{timeout_sec} s (last seen: {last_raw!r}).")
                time.sleep(check_delay_sec)
                last_raw = wcr.LastSavedFileName.get()
        finally:
            # Always disable waveform capture, even if we timed out.
            wcr.SaveData.set(False)

        return last_raw

    def multi_raw(self, col, nraw, synch=False, decimation=0):
        """Capture nraw waveforms for one column into a raw_<ctime>/ dir.

        Returns the path to a text index file listing the saved waveform paths.
        """
        ctime = int(time.time())
        save_dir = os.path.join(self._require_output(), f'raw_{ctime}')
        os.makedirs(save_dir, exist_ok=True)

        # Enable msec timestamping for high-cadence acquisition, then restore.
        ms_ts = self.hwg.WaveformCaptureReceiver.MillisecondTimestamp
        previous_ms_ts = ms_ts.get()
        ms_ts.set(True)

        wfs = []
        try:
            for _ in range(nraw):
                wfs.append(self.take_raw(col=col, outputdir=save_dir, synch=synch,
                                         decimation=decimation))
        finally:
            ms_ts.set(previous_ms_ts)

        idxfp = os.path.join(save_dir, f'raw_{ctime}.txt')
        with open(idxfp, 'w') as f:
            for wf in wfs:
                f.write(f"{wf}\n")

        print(f"{nraw} waveforms indexed to {idxfp} for column {col}.")
        return idxfp

    def take_data(self, acq_time_sec, start_delay_sec=1.0):
        """Open the DataWriter, acquire for acq_time_sec, then close.

        Starts the run if not already running (and stops it again afterward,
        leaving the system in the state it was found). The DataWriter is always
        closed and the run state restored, even if acquisition is interrupted.
        """
        cb0 = self.cbs[self.coordinator_col]
        tx = cb0.WarmTdmCore.Timing.TimingTx

        was_running = tx.Running.get()
        if not was_running:
            tx.StartRun()
            time.sleep(start_delay_sec)

        r = self.root
        r.DataWriter.AutoName()
        r.DataWriter.DataFile.set(
            os.path.join(os.path.abspath(self._require_output()),
                         r.DataWriter.DataFile.get()))
        data_filename = r.DataWriter.DataFile.get()

        try:
            print(f'Open file {data_filename}')
            r.DataWriter.Open()
            print(f'Acquire data for {acq_time_sec} sec ...')
            time.sleep(acq_time_sec)
        finally:
            # Always close the file and restore run state, even on interrupt.
            print(f'Close file {data_filename}')
            r.DataWriter.Close()
            if not was_running:
                # The user had the run stopped; return the system to that state.
                tx.EndRun()

        return data_filename


# ---- module-level convenience (cached default Session) ------------------

_default_session = None


def set_default_session(session):
    """Set the process-wide default Session used by the free-function shims."""
    global _default_session
    _default_session = session
    return session


def get_default_session():
    """Return the default Session, or raise an actionable error if unset."""
    if _default_session is None:
        raise RuntimeError(
            "No default Session. Call ops.connect(host, port) (or ops.use(client)) "
            "first, or call methods on an explicit Session instance.")
    return _default_session


def use(client, path=OutputDir.DEFAULT_BASE, coordinator_col=0):
    """Wrap an already-connected client in a Session, cache it as the default.

    Args:
        client: a connected pyrogue client (e.g. VirtualClient) with ``.root``.
        path: base directory for the session output dir (None to skip creating).
        coordinator_col: index of the timing controller column board.
    """
    output = OutputDir(base=path) if path is not None else None
    return set_default_session(Session(client, output=output,
                                       coordinator_col=coordinator_col))


def connect(host='localhost', port=9099, path=OutputDir.DEFAULT_BASE,
            coordinator_col=0):
    """Build a VirtualClient to (host, port), wrap it, cache as default Session."""
    import pyrogue.interfaces
    client = pyrogue.interfaces.VirtualClient(addr=host, port=port)
    return use(client, path=path, coordinator_col=coordinator_col)


# Free-function shims: delegate to the default Session so notebooks can call
# ops.take_raw(0) etc. without a `session.` prefix. Scripts/tests should prefer
# calling the methods on an explicit Session.
def _shim(name):
    def wrapper(*args, **kwargs):
        return getattr(get_default_session(), name)(*args, **kwargs)
    wrapper.__name__ = name
    wrapper.__doc__ = (f"Delegates to the default Session's {name}(). "
                       f"See Session.{name}. Requires ops.connect()/ops.use() first.")
    return wrapper


print_hardware = _shim('print_hardware')
disable_leds = _shim('disable_leds')
set_cryo_resistance = _shim('set_cryo_resistance')
set_ps_synch = _shim('set_ps_synch')
check_ps_synch = _shim('check_ps_synch')
all_off = _shim('all_off')
save_config = _shim('save_config')
save_state = _shim('save_state')
load_config = _shim('load_config')
setup_mux = _shim('setup_mux')
take_raw = _shim('take_raw')
multi_raw = _shim('multi_raw')
take_data = _shim('take_data')
new_session = _shim('new_session')
