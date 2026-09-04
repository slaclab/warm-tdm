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
##
## The Session implementation is split by concern across this package: _core
## (state + topology + reporting) is the base; _acquisition, _tuning, _forcedac,
## _setup, _config, and _hwsetup are mixins mounted on top. The split is a pure
## source reorganization -- Session's public surface (and the `ops.*` shims) is
## unchanged. All instance state lives in TopologyCore.__init__; mixins only read
## self.*, never add attributes.

from ._output import OutputDir
from ._core import TopologyCore, COORDINATOR_COL_BOARD
from ._acquisition import AcquisitionMixin
from ._tuning import TuningMixin
from ._forcedac import ForceDacMixin
from ._setup import SetupMixin
from ._config import ConfigMixin
from ._hwsetup import HwSetupMixin


class Session(TopologyCore, AcquisitionMixin, TuningMixin, ForceDacMixin,
              SetupMixin, ConfigMixin, HwSetupMixin):
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

    The methods are organized into mixins by concern (see the package modules):
    acquisition (``take_raw``/``multi_raw``/``take_data``), tuning
    (``run_process``/``sa_tune``/...), fast-DAC force + ``stop_and_zero``,
    MUX/dead-mask setup, config save/load, and transitional Group-broadcast
    shims. This is source organization only; the object is one flat ``Session``.

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
# calling the methods on an explicit Session. The names are generated from one
# list (below) rather than hand-written, so a new shimmed method is a one-line
# addition here and in the package __all__.
def _shim(name):
    def wrapper(*args, **kwargs):
        return getattr(get_default_session(), name)(*args, **kwargs)
    wrapper.__name__ = name
    wrapper.__doc__ = (f"Delegates to the default Session's {name}(). "
                       f"See Session.{name}. Requires ops.connect()/ops.use() first.")
    return wrapper


# Session methods exposed as default-Session-delegating free functions.
_SHIM_NAMES = (
    # hardware info / setup
    'print_hardware', 'status', 'disable_leds', 'set_cryo_resistance',
    'set_ps_synch', 'check_ps_synch', 'stop_and_zero', 'save_config',
    'save_state', 'load_config', 'setup_mux', 'apply_dead_masks',
    'new_session',
    # acquisition
    'take_raw', 'multi_raw', 'take_data',
    # tuning
    'run_process', 'sa_offset', 'sa_tune', 'sq1_tune', 'fas_tune',
)

for _name in _SHIM_NAMES:
    globals()[_name] = _shim(_name)
del _name

__all__ = [
    'Session', 'OutputDir', 'COORDINATOR_COL_BOARD',
    'connect', 'use', 'set_default_session', 'get_default_session',
    *_SHIM_NAMES,
]
