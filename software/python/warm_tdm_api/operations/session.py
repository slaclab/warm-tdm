##
## Session: the per-Group hardware handle for the operations layer.
##
## Replaces the former all-classmethod `Client` global singleton. A `Session`
## binds to ONE `Group` node of a connected pyrogue client's tree, discovers the
## boards under its HardwareGroup, and exposes every hardware-coupled operation
## (acquisition + setup helpers) as a method. Because it is an ordinary instance:
##   - tests can construct one around a fake/emulate Group, no global state;
##   - two Groups (or two systems) are simply two Session objects;
##   - a method never sees a half-initialized handle (boards are populated in
##     __init__), and missing pieces raise clear RuntimeErrors, not AttributeError.
##
## The client/server seam is unchanged: `warmTdmServer` owns the real GroupRoot
## and a ZmqServer; a `VirtualClient` mirrors that tree over ZMQ, and Session
## drives the mirror (`client.root.Group`). Binding to the *Group* node (not the
## client) is what makes the layer multi-Group-ready: a future `Instrument`
## holds one Session per Group -- N Sessions over one client (non-federated root
## with several Groups) or N clients (federated, a server per Group). See
## docs/plans/wtj-refactor/PLAN.md "Operations API review -> Scaling".
##
## Topology is derived from the bound Group (channels-per-board, board maps),
## never hardcoded, so a differently-shaped Group works without code changes.
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

from .channels import col_to_board_chan

log = logging.getLogger(__name__)

# Board node names look like 'ColumnBoard[3]' / 'RowBoard[1]'.
_BOARD_INDEX_RE = re.compile(r'\[(\d+)\]$')

# The timing coordinator is always the first column board (RING_ADDR_0). This is
# a fixed hardware convention -- HardwareGroup itself assumes ColumnBoard[0] owns
# TimingTx (see _HardwareGroup.py). There is nothing to discover.
COORDINATOR_COL_BOARD = 0


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
    """A connected Warm-TDM hardware handle, bound to one Group.

    Binds to a ``Group`` device node (``root.Group`` today), discovers the
    column/row boards under its ``HardwareGroup``, and provides the acquisition
    and hardware-setup operations as methods.

    Binding to the *Group* (rather than the client's global ``root.Group``) is
    deliberate: it is the topology unit, and it is the seam a future multi-Group
    ``Instrument`` needs -- a Session per Group, one Group per Session. All
    per-Group state (board maps, channel count) is derived from the bound Group,
    not hardcoded, so a differently-shaped Group (more/fewer column boards, a
    different channels-per-board) works without code changes. See
    ``docs/plans/wtj-refactor/PLAN.md`` "Operations API review -> Scaling".

    Topology is read from the Group, never assumed:
      - ``chans_per_board`` = ``NumColumns // NumColumnBoards``;
      - per-board AFE sub-devices are enumerated from the tree (Column
        ``Channel[*]``, Row ``Amp[*]``), not looped over a fixed ``range()``.
    The one fixed convention kept as a literal is that the timing coordinator is
    ``ColumnBoard[0]`` (``COORDINATOR_COL_BOARD``) -- a hardware fact, not a
    discovery.

    Attributes:
        group: the bound ``Group`` device node.
        root: the pyrogue Root the Group belongs to (for Root-scoped ops:
            SaveConfig/LoadConfig, DataWriter).
        hwg: ``group.HardwareGroup``.
        cbs (dict): {index: ColumnBoard node}.
        rbs (dict): {index: RowBoard node}.
        rdds (dict): {index: RowDacDriver node} for each row board.
        chans_per_board (int): columns per column board, derived from the Group.
        output (OutputDir | None): where data files are written.
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

    # ---- board enumeration ---------------------------------------------

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

    # ---- hardware info / setup (ported from utils.py) -------------------
    #
    # Several methods below reach through fixed device-tree paths
    # (WarmTdmCore.WarmTdmCommon2.AxiVersion, ...WarmTdmConfig.LedEn,
    # WarmTdmCore.Timing.TimingTx.PwrSync*, DataPath.AdcDsp[col].PidEnable).
    # These are deliberately client-side *convenience shims pending graduation*:
    # each such capability's real home is an owning tree node (a board-device or
    # HardwareGroup accessor for build-info/LED/PwrSync; a Group channel var for
    # per-column PID). They are grouped here so the paths live in one file, and
    # are meant to be trimmed as the G-list capabilities graduate onto the tree
    # (see docs/plans/wtj-refactor/PLAN.md). Do NOT grow a path-resolution layer
    # around them -- push each to its node instead.

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
        """Disable status-blinking LEDs on all boards.

        Delegates to the Group ``LedEnable`` variable, which owns the broadcast
        (issue #83, G6). Kept as a thin ``operations`` convenience so existing
        call sites (``ops.disable_leds()``) don't change.
        """
        self.group.LedEnable.set(False)
        print("Disabled LEDs on all boards.")

    def set_cryo_resistance(self, Rcryo_Ohm):
        """Set cryostat roundtrip cable resistance on all boards' AFE amps.

        Broadcasts ``Rcryo_Ohm`` to every AFE ``CableR`` model node (column
        ``Channel[*].{SAAmp,SAFbAmp,SQ1BiasAmp,SQ1FbAmp,TesBiasAmp}``; row
        ``Amp[*]``).

        This now delegates to the Group ``CableResistance`` variable, which owns
        the broadcast (issue #83, G3). Kept as a thin ``operations`` convenience
        so notebook/script call sites (``ops.set_cryo_resistance(R)``) don't
        change.
        """
        self.group.CableResistance.set(Rcryo_Ohm)
        print(f"Set cryostat resistance to {Rcryo_Ohm} Ohm.")

    def set_ps_synch(self, sync_mode):
        """Set power-supply synchronization mode on all boards.

        ``sync_mode`` truthy => synchronized (PwrSyncA/B/C=OSC, PwrSyncEn on);
        falsy => unsynchronized (all LOW, PwrSyncEn off).

        Delegates to the Group ``PowerSupplySynchronized`` variable, which owns
        the broadcast (issue #83, G4). Kept as a thin ``operations`` convenience
        so existing call sites (``ops.set_ps_synch(1)``) don't change.
        """
        self.group.PowerSupplySynchronized.set(bool(sync_mode))
        print("Synchronized power supplies."
              if sync_mode else "Unsynchronized power supplies.")

    def check_ps_synch(self):
        """Print (and return) the power-supply synchronization state.

        Reads the Group ``PowerSupplySynchronized`` variable (issue #83, G4).
        """
        synched = bool(self.group.PowerSupplySynchronized.get())
        print(f"Power supplies are {'Synchronized' if synched else 'Unsynchronized'}.")
        return synched

    # Fast-DAC force-current drivers that ride the FastDacDriver override
    # one-shot (Issue #86): Group setter variable -> per-column-board driver
    # device (whose DacCurrentNow reads back the actual driven output).
    _FAST_DAC_FORCE = {
        'Sq1Fb':   ('Sq1FbForceCurrent',   'SQ1Fb'),
        'SaFb':    ('SaFbForceCurrent',    'SAFb'),
        'Sq1Bias': ('Sq1BiasForceCurrent', 'SQ1Bias'),
    }

    def _read_dac_now(self, dev_name):
        """{(board_idx, chan): DacCurrentNow (uA)} for one fast-DAC driver.

        ``DacCurrentNow`` is a LinkVariable computed from the *cached* DacRawNow
        (its ``linkedGet`` reads ``DacRawNow.value()``, not ``.get()``). With
        polling off (e.g. simulation, where the Root sets ``pollEn=False``) or
        between poll ticks that cache is stale, so a naive read reports an old
        value -- which silently defeats the verify loop. Force a fresh read of
        ``DacRawNow`` first so the returned current reflects the live DAC output.
        """
        out = {}
        for idx, cb in sorted(self.cbs.items()):
            dev = getattr(cb, dev_name, None)
            if dev is None or not hasattr(dev, 'DacCurrentNow'):
                continue
            for ch in range(self.chans_per_board):
                try:
                    if hasattr(dev, 'DacRawNow'):
                        dev.DacRawNow[ch].get()   # refresh dependency (live read)
                    out[(idx, ch)] = float(dev.DacCurrentNow[ch].get())
                except Exception:
                    break
        return out

    def _apply_force_verified(self, kind, target_uA, tol_uA=0.5, tries=5,
                              settle_sec=0.1):
        """Write a fast-DAC force current and confirm it reached the DAC output,
        re-issuing on a mismatch (bounded).

        Software coordination for the FastDacDriver override one-shot race
        (Issue #86): the override register is only serviced while the driver FSM
        is in IDLE, so a write issued during the post-EndRun drain can be
        dropped. Once the run is stopped the FSM parks in IDLE (``stageNextRow``
        is gated by ``running`` in the RTL), so a re-issued write is always
        serviced -- this converges, typically in one retry. Reading DacCurrentNow
        back also gives real confirmation the output moved (what Issue #32
        wanted), instead of a blind write.

        ``target_uA`` is a scalar (broadcast to every column) or a per-global-
        column sequence. Returns ``(converged, residual)`` where residual is
        ``{(board, chan): current}`` for channels still off target.
        """
        setter_name, dev_name = self._FAST_DAC_FORCE[kind]
        setter = getattr(self.group, setter_name)
        ncol = len(setter.get())
        target = (np.full(ncol, float(target_uA)) if np.isscalar(target_uA)
                  else np.asarray(target_uA, dtype=float))

        residual = {}
        for _ in range(max(1, tries)):
            setter.set(target.tolist())
            time.sleep(settle_sec)
            residual = {}
            for (idx, ch), val in self._read_dac_now(dev_name).items():
                col = idx * self.chans_per_board + ch
                tgt = target[col] if col < len(target) else 0.0
                if abs(val - tgt) > tol_uA:
                    residual[(idx, ch)] = val
            if not residual:
                return True, {}
        return False, residual

    def set_force(self, kind, current_uA, tol_uA=0.5, tries=5, settle_sec=0.1):
        """Set a fast-DAC force current and verify it reached the DAC, retrying.

        ``kind`` is one of ``Sq1Fb`` / ``SaFb`` / ``Sq1Bias``. Stop the run first
        -- the override is a stopped-state operation; during a MUX run the per-row
        RAM overwrites the DAC output every row. Retries close the override
        one-shot race (Issue #86). Returns ``(converged, residual)``.
        """
        if kind not in self._FAST_DAC_FORCE:
            raise ValueError(f"set_force kind must be one of "
                             f"{list(self._FAST_DAC_FORCE)}, got {kind!r}")
        ok, residual = self._apply_force_verified(
            kind, current_uA, tol_uA=tol_uA, tries=tries, settle_sec=settle_sec)
        if not ok:
            log.warning("set_force(%s, %s): %d channel(s) did not reach target "
                        "within %.2f uA after %d tries: %s", kind, current_uA,
                        len(residual), tol_uA, tries, residual)
        return ok, residual

    def stop_and_zero(self, settle_sec=2.0, poll_sec=0.05):
        """Return to a safe baseline: stop MUX, then zero the column outputs.

        Order matters. The force/override DAC path (Sq1FbForceCurrent etc. ->
        FastDacDriver override RAM) is only serviced while the driver FSM sits in
        its IDLE state, i.e. when the run has stopped -- and the override write is
        a single-cycle event. So this method:
          1. ends any active run and switches the coordinator to manual timing;
          2. waits for TimingTx.Running to drop (bounded by ``settle_sec``) so the
             DAC FSM is guaranteed idle;
          3. THEN zeros the fast-DAC force outputs with **read-back verification
             and bounded retry** (``_apply_force_verified``), so a write dropped
             at the stop boundary is re-issued until DacCurrentNow confirms ~0;
             the slow bias/offset outputs are zeroed with a single write.

        The verify-and-retry closes the override one-shot race (Issue #86) in
        software -- no RTL change -- and gives real confirmation the biases
        zeroed, which is what the "biases don't zero after MUX" report (Issue #32)
        actually needed. See G2 in docs/plans/wtj-refactor/PLAN.md.

        Not yet a hardware interlock:
          - Verification covers the fast DACs (SQ1Fb/SAFb/SQ1Bias) via their
            DacCurrentNow read-back; a warning is logged if any channel cannot be
            driven to ~0 within the retry budget.
          - Row DAC zeroing is still left commented (row-select / FAS DAC outputs
            untouched) pending a bench check.

        Args:
            settle_sec (float): max time to wait for Running to drop after EndRun
                (EndRun completes on the next row-boundary, so this is not
                instantaneous).
            poll_sec (float): poll interval while waiting for Running to drop.
        """
        cb0 = self.coordinator_cb
        tx = cb0.WarmTdmCore.Timing.TimingTx

        # 1. Stop the run and leave MUX mode. EndRun completes on the next
        #    row-boundary timeslot, so Running does not drop instantly.
        if tx.Running.get():
            tx.EndRun()
        tx.Mode.set(0)

        # 2. Wait for the run to actually stop, so the FastDacDriver FSM is idle
        #    and will service the override writes below.
        deadline = time.time() + settle_sec
        while tx.Running.get():
            if time.time() > deadline:
                log.warning("stop_and_zero: TimingTx.Running did not drop within "
                            "%.1f s; zeroing anyway (writes may not land).", settle_sec)
                break
            time.sleep(poll_sec)

        # 3a. Zero the fast-DAC force outputs WITH read-back verification + retry.
        #     These ride the FastDacDriver override one-shot (Issue #86): a single
        #     blind write issued at the stop boundary can be dropped. Re-issuing
        #     until DacCurrentNow confirms ~0 closes that race in software and
        #     confirms the biases actually zeroed.
        all_ok = True
        for kind in self._FAST_DAC_FORCE:
            ok, residual = self._apply_force_verified(kind, 0.0)
            if not ok:
                all_ok = False
                log.warning("stop_and_zero: %s did not verify to ~0 after retries; "
                            "residual (board,chan)->uA: %s", kind, residual)

        # 3b. Zero the remaining (slow) bias/offset outputs. These do not go
        #     through the override FSM, so a single write is sufficient.
        r = None
        try:
            for r in ['SaBiasCurrent', 'SaOffset', 'TesBias']:
                var = getattr(self.group, r)
                var.set(np.zeros_like(var.get()))
        except (AttributeError, TypeError) as e:
            log.error("Error zeroing %s: %s", r, e)

        # TODO: zero row DACs once the reorder is confirmed on the bench
        # for i, rdd in self.rdds.items():
        #     rdd.FasOn.Current.set(np.zeros_like(rdd.FasOn.Current.get()))
        #     rdd.FasOff.Current.set(np.zeros_like(rdd.FasOn.Current.get()))

        log.info("stop_and_zero: run stopped, manual timing; fast-DAC force "
                 "outputs zeroed and verified via DacCurrentNow (%s); slow "
                 "bias/offset outputs zeroed. Row DACs left untouched.",
                 "all channels ~0" if all_ok else "WITH RESIDUALS -- see warnings")

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
                        "is the controller.", list(self.cbs.keys()), COORDINATOR_COL_BOARD)
        if len(self.rbs) > 1:
            log.warning("Multiple row boards detected %s. Applying commands to all.",
                        list(self.rbs.keys()))

        cb = self.coordinator_cb

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

        board, chan = self.col_to_board_chan(col)
        cb = self.cbs[board]

        if outputdir is None:
            outputdir = self._require_output()

        wcr.SavedFilePath.set(outputdir)
        wcr.SaveData.set(True)

        cb.DataPath.WaveformCapture.AllChannels.set(False)
        cb.DataPath.WaveformCapture.SelectedChannel.set(chan)
        cb.DataPath.WaveformCapture.Decimation.set(decimation)
        wcr.PlotColumn.set(chan)
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
        cb0 = self.coordinator_cb
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

    # ---- tuning (start-and-block wrappers over the Group pr.Processes) ----

    # Named tuning processes and their output variable, so the wrappers can
    # return the result the algorithm produced. Every warm_tdm_api tuning
    # algorithm is a pr.Process on Group with the uniform Start/Stop/Running/
    # Progress/Message interface; run_process drives any of them by node name.
    _PROCESS_OUTPUT = {
        'SaOffsetProcess': 'SaOffsetOutput',
        'SaTuneProcess': 'SaTuneOutput',
        'Sq1TuneProcess': 'Sq1TuneOutput',
        'FasTuneProcess': 'FasTuneOutput',
    }

    def run_process(self, name, block=True, poll_sec=1.0, timeout_sec=None,
                    **params):
        """Configure, start, and (optionally) block on a Group ``pr.Process``.

        Replaces the hand-rolled ``proc.Start(); while proc.Running.get(): ...``
        idiom (see the old ``scripts/Jupyter.py``). Any of the Group tuning
        processes -- SaOffset, SaTune, Sq1Tune, FasTune, ... -- is driven by node
        name, since they all share the ``pr.Process`` interface.

        Args:
            name (str): the Group child process node, e.g. ``'SaTuneProcess'``.
            block (bool): if True, poll ``Running`` until the process finishes
                (or ``timeout_sec`` elapses) before returning; if False, Start
                and return immediately.
            poll_sec (float): poll interval while blocking.
            timeout_sec (float | None): max wall time to block; None = no limit.
            **params: process variable settings applied before Start, e.g.
                ``SaBiasNumSteps=5``. Unknown names raise AttributeError.

        Returns:
            The process's output value if it exposes a known output variable and
            we blocked to completion; otherwise None. (When ``block=False`` the
            result is not ready yet -- poll/collect via the process node.)

        Raises:
            AttributeError: no such process node, or an unknown param name.
            TimeoutError: the process was still running at ``timeout_sec``.
        """
        try:
            proc = getattr(self.group, name)
        except AttributeError:
            raise AttributeError(
                f"No process '{name}' on Group. Known tuning processes: "
                f"{sorted(self._PROCESS_OUTPUT)}.")

        for k, v in params.items():
            getattr(proc, k).set(v)  # AttributeError here = bad param name

        proc.Start()
        if not block:
            return None

        deadline = None if timeout_sec is None else time.time() + timeout_sec
        try:
            while proc.Running.get():
                if deadline is not None and time.time() > deadline:
                    raise TimeoutError(
                        f"{name} still running after {timeout_sec} s "
                        f"(last message: {proc.Message.get()!r}).")
                time.sleep(poll_sec)
        except KeyboardInterrupt:
            # Interrupting the wait should stop the process, not orphan it.
            proc.Stop()
            raise

        msg = proc.Message.get()
        if msg:
            print(f"{name}: {msg}")

        out_var = self._PROCESS_OUTPUT.get(name)
        if out_var is not None:
            return getattr(proc, out_var).get()
        return None

    def sa_offset(self, block=True, **params):
        """Run SaOffsetProcess (SA offset determination). See run_process."""
        return self.run_process('SaOffsetProcess', block=block, **params)

    def sa_tune(self, block=True, **params):
        """Run SaTuneProcess (SA amplifier tuning). See run_process.

        Example: ``sess.sa_tune(SaBiasLowOffset=.4, SaBiasHighOffset=.8,
        SaBiasNumSteps=5)``.
        """
        return self.run_process('SaTuneProcess', block=block, **params)

    def sq1_tune(self, block=True, **params):
        """Run Sq1TuneProcess (first-stage SQUID tuning). See run_process."""
        return self.run_process('Sq1TuneProcess', block=block, **params)


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


def use(client, path=OutputDir.DEFAULT_BASE, group='Group'):
    """Wrap a connected client's Group in a Session, cache it as the default.

    The client is a pyrogue client (e.g. ``VirtualClient`` over ZMQ to the
    ``warmTdmServer`` root); the Session binds to a Group node under it. The
    server owns the real tree -- ``client.root`` is the client-side mirror.

    Args:
        client: a connected pyrogue client (e.g. VirtualClient) with ``.root``.
        path: base directory for the session output dir (None to skip creating).
        group: which Group to bind -- a node name under ``client.root`` (default
            ``'Group'``) or an already-resolved Group node. (Multi-Group roots
            will expose several; today there is one.)
    """
    group_node = getattr(client.root, group) if isinstance(group, str) else group
    output = OutputDir(base=path) if path is not None else None
    return set_default_session(Session(group_node, output=output))


def connect(host='localhost', port=9099, path=OutputDir.DEFAULT_BASE,
            group='Group'):
    """Build a VirtualClient to (host, port), wrap its Group, cache as default."""
    import pyrogue.interfaces
    client = pyrogue.interfaces.VirtualClient(addr=host, port=port)
    return use(client, path=path, group=group)


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
status = _shim('status')
disable_leds = _shim('disable_leds')
set_cryo_resistance = _shim('set_cryo_resistance')
set_ps_synch = _shim('set_ps_synch')
check_ps_synch = _shim('check_ps_synch')
stop_and_zero = _shim('stop_and_zero')
save_config = _shim('save_config')
save_state = _shim('save_state')
load_config = _shim('load_config')
setup_mux = _shim('setup_mux')
apply_dead_masks = _shim('apply_dead_masks')
take_raw = _shim('take_raw')
multi_raw = _shim('multi_raw')
take_data = _shim('take_data')
run_process = _shim('run_process')
sa_offset = _shim('sa_offset')
sa_tune = _shim('sa_tune')
sq1_tune = _shim('sq1_tune')
new_session = _shim('new_session')
