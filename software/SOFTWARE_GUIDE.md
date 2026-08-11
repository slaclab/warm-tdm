# Software Deep-Dive Guide

Supplementary reference for AI agents working on warm-tdm software. For the project overview, see the root [`AGENTS.md`](../AGENTS.md).

## Package Structure

Two Python packages work together:

| Package | Location | Scope |
|---------|----------|-------|
| `warm_tdm` | `firmware/python/warm_tdm/` | Low-level PyRogue device drivers mapping FPGA registers |
| `warm_tdm_api` | `software/python/warm_tdm_api/` | High-level control, tuning, data, GUI |

`warm_tdm_api` also contains the `operations` subpackage
(`software/python/warm_tdm_api/operations/`): the **client-side operational
layer** for running the system from a notebook, script, or production tooling —
session/board management (`Session`), data acquisition (`take_raw`, `take_data`),
hardware setup helpers (`setup_mux`, `all_off`, `set_cryo_resistance`), stream
reading (`StreamReader`), pure format helpers (`formats.py`), and offline
analysis/plotting (`plot_stream_data`, `analyze_pair`). It drives the rogue tree
remotely and is deliberately kept distinct from the pyrogue-tree device modules
(`_Group`, `_SaTune`, …). It is **not** auto-imported by `warm_tdm_api` (so the
server import path stays free of matplotlib/scipy); import it explicitly:
```python
import warm_tdm_api.operations as ops

# Hardware-coupled ops live on a Session. Establish a default for notebook use:
sess = ops.connect(host='localhost', port=9099)   # or ops.use(existing_client)
sess.setup_mux()
sess.take_raw(0)
# ...or via the convenience shims that delegate to the default Session:
ops.take_raw(0)
```
The `Session` is an ordinary object (not a global singleton) bound to **one
`Group`**: tests and multi-system code construct their own
`ops.Session(client.root.Group)` and call methods on it directly, while
`connect()`/`use()` cache a process-wide default for the free-function shims.
Binding to the Group (not the client) is deliberate — it is the topology unit,
and it is what makes the layer multi-Group-ready (a future `Instrument` holds one
Session per Group). Per-Group topology (channels-per-board, board maps) is
**derived from the bound Group**, not hardcoded; the timing coordinator is always
`ColumnBoard[0]`. The client/server seam is unchanged: `warmTdmServer` owns the
real `GroupRoot`+ZmqServer, and `Session` drives the `VirtualClient` mirror over
ZMQ. Reusable hardware capabilities here are candidates to graduate into `Group`
as they mature (see `docs/plans/wtj-refactor`). This subpackage was formerly the
standalone `warm_tdm_jupyter` package.

Both are loaded via `pyrogue.addLibraryPath()` in scripts:
```python
pyrogue.addLibraryPath(f'../python/')            # warm_tdm_api
pyrogue.addLibraryPath(f'../../firmware/python/') # warm_tdm
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')
```

## Device Tree Hierarchy

```
GroupRoot (pyrogue.Root)
└── Group (pr.Device)
    ├── HardwareGroup (pr.Device)
    │   ├── SrpRssi (UdpRssiPack, port 8192)
    │   ├── DataRssi (UdpRssiPack, port 8193)
    │   ├── ColumnBoard[0..N] (warm_tdm.ColumnFpgaBoard or variant)
    │   │   ├── WarmTdmCore2 registers
    │   │   ├── DataPath
    │   │   ├── AdcDsp[0..7]
    │   │   ├── FastDacDriver
    │   │   └── Amplifiers, TesBias, etc.
    │   └── RowBoard[0..N] (warm_tdm.RowFpgaBoard or variant)
    │       ├── WarmTdmCore2 registers
    │       ├── TimingTx (coordinator only)
    │       ├── RowDacDriver2
    │       └── RowModuleDacs
    ├── GroupLinkVariables (cross-board array access)
    ├── SaTuneProcess
    ├── Sq1TuneProcess
    ├── FasTuneProcess
    └── DataWriter (StreamWriter)
```

## HardwareGroup and Connectivity

`HardwareGroup` (`firmware/python/warm_tdm/_HardwareGroup.py`) manages UDP connections:
- **SRP port 8192** — Register access (RSSI+SRP protocol over UDP)
- **Data port 8193** — Streaming data (RSSI+SSI over UDP, jumbo frames)

The coordinator board (RING_ADDR_0) bridges Ethernet to the PGP ring. All boards in the group are accessed through the coordinator's Ethernet interface — the PGP ring router distributes register transactions to each board by ring address.

Connection modes:
- **Hardware**: `UdpRssiPack` to real hardware IP
- **Simulation**: TCP socket connections (`SIM_SRP_PORT=10000`, `SIM_DATA_PORT=20000`)
- **Emulation**: `TdmGroupEmulate` provides software-only simulation of hardware behavior

## GroupLinkVariable Pattern

`GroupLinkVariable` (`software/python/warm_tdm_api/_Group.py`) provides array-style access across multiple boards:

```python
self.add(warm_tdm_api.GroupLinkVariable(
    name='Sq1Feedback',
    dependencies=[board.FastDacDriver.DacValue for board in colBoards],
    tuneEnVar=self.TuneEn))
```

- `get(index=N)` reads a single channel; `get(index=-1)` reads all as numpy array
- `set(value, index=N)` writes a single channel; `set(array, index=-1)` writes all
- `tuneEnVar` controls which channels are active (skips disabled channels)
- Dependencies are ordered by column for consistent indexing

## Tuning Processes

Tuning algorithms are implemented as PyRogue Process devices in `software/python/warm_tdm_api/`:

| Process | File | Purpose |
|---------|------|---------|
| SaTune | `_SaTune.py` | SA (Series Array) amplifier tuning — finds optimal bias point |
| Sq1Tune | `_Sq1Tune.py` | SQ1 (first-stage SQUID) tuning — optimizes feedback |
| FasTune | `_FasTune.py` | FAS (Flux-Actuated Switch) tuning |
| SaOffset | `_SaOffset.py` | SA offset determination |
| Sq1Diag | `_Sq1Diag.py` | SQ1 diagnostic sweeps |
| TesRamp | `_TesRamp.py` | TES bias ramp for IV curves |

Process lifecycle:
- Inherit from device base and implement `_process()` method
- Started via command (e.g., `Group.SaTuneProcess.Start()`)
- Progress tracked via status variables
- Can be stopped mid-execution

## Data Streaming

Data flows from FPGA → host via:
1. `EventBuilder` (firmware) packs DSP output into AXI-Stream frames
2. PGP ring transports frames to coordinator
3. Coordinator's Ethernet bridge sends frames via RSSI/UDP to host
4. `DataRssi` on port 8193 receives frames
5. `DataWriter` (pyrogue StreamWriter) records to file
6. `TdmDataReceiver` (`_TdmDataReceiver.py`) decodes frames for real-time display

Frame format defined in `warm_tdm._DataFormats.DataReadout`.

## Configuration Management

- **Save/Load**: `GroupRoot.SaveConfig` / `GroupRoot.LoadConfig` (standard PyRogue YAML)
- **GroupConfigs** (`_GroupConfigs.py`): Manages hardware configuration profiles (IP, board counts, board classes)
- **Config files**: Stored in `software/cfg/` as YAML
- **ConfigSelect** (`_ConfigSelect.py`): UI for choosing between saved configurations

## GUI Architecture

- Framework: PyDM (Python Display Manager) + PyQt
- Main UI: `software/python/warm_tdm_api/warm_tdm_gui.ui` (Qt Designer file)
- Widget modules in `software/python/warm_tdm_api/widgets/`:
  - `_warm_tdm_display.py` — Main display container
  - `_control_tab.py` — Hardware control panel
  - `_tuning_tab.py` — Tuning process controls
  - `_waveform_tab.py` — Real-time waveform display

## Key Scripts

| Script | Purpose |
|--------|---------|
| `warmTdmServer.py` | PyRogue hardware server (main entry point) |
| `warmTdmGui.py` | Full GUI application |
| `warmTdmClientGui.py` | Remote GUI client (connects via ZMQ) |
| `warmTdmClientCmd.py` | Command-line client |
| `warmTdmEmulate.py` | Software emulation (no hardware) |
| `DataFileReader.py` | Post-processing of recorded data files |
| `PidDebugFileReader.py` | PID debug trace analysis |

## Dependencies

Core dependencies from `conda.yml`:
- `rogue` — PyRogue framework
- `numpy` — Array operations
- `pydm` — Display manager for GUIs
- `pyqt` — Qt bindings
- `matplotlib` — Plotting
- `simple-pid` — PID algorithm reference
- `pyzmq` — ZMQ server/client communication
