# Software Deep-Dive Guide

Supplementary reference for AI agents working on warm-tdm software. For the project overview, see the root [`AGENTS.md`](../AGENTS.md).

## Supported boards and maintained entry points

The `channelization` integration supports `ColumnFpgaBoard`,
`ColumnAwaXeFpgaBoard` and `RowFpgaBoard` device families. Removed legacy
ColumnModule/RowModule board constructors are not alternative supported
configurations. Validate release packaging and CLI choices against the selected
candidate; existing bitfiles still require a matching register tree.

Use `software/scripts/warmTdmServer.py` (`--gui` for the server GUI).
`warmTdmGui.py` launches the same implementation with the GUI enabled;
`warmTdmClientGui.py` connects a remote display. See the [entry-point index](README.md)
and [notebook run workflow](../docs/notebook-runs.md).
`GroupConfig` carries column/row board counts, `maxRows` and host; logical-row
mapping is separate from physical row/chip select topology. Group variable
implementations live in `_GroupVariables.py` and tuning algorithms in `tuning/`.

The maintained `_WarmTdmCore.py` and `_WarmTdmCommon.py` names now refer to the
active implementations after their `2` suffix was removed. Old cleanup lists
naming those files describe deleted legacy versions and must not be used as
instructions to delete the current drivers. Supported front ends still use
shared SURF DAC drivers; removing legacy boards does not resolve the remaining
AD5679R work on [#103](https://github.com/slaclab/warm-tdm/issues/103).

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
hardware setup helpers (`setup_mux`, `stop_and_zero`, `set_cryo_resistance`), stream
reading (`StreamReader`), pure channel helpers (`channels.py` — addressing,
identifiers, dead masks), raw→physical unit conversions (`unit_conversions.py`),
and offline analysis/plotting (`plot_stream_data`, `analyze_pair`). It drives the rogue tree
remotely and is deliberately kept distinct from the pyrogue-tree device modules
(`_Group`, `_SaTune`, …). See [`docs/operations-api.md`](../docs/operations-api.md)
for the how-to-use reference. It is **not** auto-imported by `warm_tdm_api` (so the
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
ZMQ. This subpackage was formerly the standalone `warm_tdm_jupyter` package.

Keep operations client-side while runtime editability matters: changing a
server-owned method requires restarting the server and rebuilding its state.
Move a capability onto `Group` when it needs server-side execution or state,
such as a continuous process, GUI control, or serialized configuration. Retain
a thin operations delegator when making that move. Both `warm_tdm_api` and
`warm_tdm` contribute nodes to the same tree; choose placement by which node
owns the capability. [Issue #83](https://github.com/slaclab/warm-tdm/issues/83)
tracks future graduations; [#80](https://github.com/slaclab/warm-tdm/issues/80)
owns the future multi-Group `Instrument` design.

Both are loaded via `pyrogue.addLibraryPath()` in scripts:
```python
pyrogue.addLibraryPath(f'../python/')            # warm_tdm_api
pyrogue.addLibraryPath(f'../../firmware/python/') # warm_tdm
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')
```

## Device Tree Hierarchy

The maintained drivers are `warm_tdm.WarmTdmCore` and
`warm_tdm.WarmTdmCommon` (formerly the `*2` classes). The common-register
subtree is now `WarmTdmCore.WarmTdmCommon`. Update older scripts and saved
YAML configuration keys from `WarmTdmCommon2` to `WarmTdmCommon`; the register
addresses are unchanged. The original legacy implementations have been removed.

```
GroupRoot (pyrogue.Root)
└── Group (pr.Device)
    ├── HardwareGroup (pr.Device)
    │   ├── SrpRssi (UdpRssiPack, port 8192)
    │   ├── DataRssi (UdpRssiPack, port 8193)
    │   ├── ColumnBoard[0..N] (warm_tdm.ColumnFpgaBoard or variant)
    │   │   ├── WarmTdmCore registers
    │   │   ├── DataPath
    │   │   ├── AdcDsp[0..7]
    │   │   ├── FastDacDriver
    │   │   └── Amplifiers, TesBias, etc.
    │   └── RowBoard[0..N] (warm_tdm.RowFpgaBoard or variant)
    │       ├── WarmTdmCore registers
    │       ├── TimingTx (coordinator only)
    │       └── RowDacDriver
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
- **Emulation**: `MemEmulate` provides register-memory plumbing without analog/RTL behavior

## GroupLinkVariable Pattern

The classes in `software/python/warm_tdm_api/_GroupVariables.py` provide
array-style access across boards. Scalar-column groups, board-array groups, and
per-row fast-DAC tables have distinct dependency layouts. For example:

```python
group.SaBiasCurrent.get(index=0)  # Explicit read of column 0
group.SaBiasCurrent.get()         # Refresh enabled columns; return all columns
```

Whole-array reads use the column mask to select refreshes; disabled entries may
be cached. Explicit indexed reads still read the requested column. Writes are
masked, and `FastDacVariable` uses `(column, row)` indices. See
[Group variable I/O contracts](../docs/design/group-variables.md) for batching,
dependency ownership, normalized PID gains, and the legacy TES-write limitation.

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

### FAS commissioning

`FasTuneProcess` supports stopped one-level and two-level row maps. It uses
`RowReadoutOrder` and `RowMap` to actuate physical outputs through
`RowDacDriver.manual_set()` and measure the nulled SA-feedback response.
The active map entries automatically select the topology on every run; the
same `session.fas_tune()` call or GUI Start button handles either configuration
without a mode flag. One-level maps use the row-select sweep. Two-level maps
find an RS/CS bootstrap pair with a two-dimensional grid, refine both axes,
and check final shared currents in all four on/off states before programming.
`FasOff` is never changed and must already provide isolation.

Run it through the operations API after SA tuning:

```python
import warm_tdm_api.operations as ops

session = ops.use(client)
session.sa_tune()
fas_result = session.fas_tune()
```

Timing must already be stopped. Sweep bounds, settling delay, servo values,
and two-level response/isolation thresholds must be established on the
applicable cryogenic hardware. For an existing 8×10 map, setting
`session.group.RowReadoutOrder.set([10, 11, 12, 13])` tunes RS 0–3 with shared
CS 11 without remapping logical rows. Discovery needs no prior on-currents.
It records grids in `FasDiscoveryOutput`, curves in `FasTuneOutput`, and final
pair checks in `FasValidationOutput`. Pass `SetAfterFinish=True` to program
only after all requested rows pass. Physical lines shared with inactive rows
also affect those rows when programmed; only requested rows are measured.

The [FAS design record](../docs/design/fas-tuning.md) explains the temporary
`ManualSet` register, discovery algorithm, cancellation behavior, and limits. Hardware
acceptance remains on [#99](https://github.com/slaclab/warm-tdm/issues/99).

For software-clocked TES bias sine/square generation, configuration migration,
and Stop/error behavior, see [Software TES bias waveforms](../docs/tes-bias-waveform.md).

## Data Streaming

Data flows from FPGA → host via:
1. `EventBuilder` (firmware) packs DSP output into AXI-Stream frames
2. PGP ring transports frames to coordinator (each board's data tagged with its
   ring address in `tDest[6:4]`; stream type in `tDest[3:0]`)
3. Coordinator's Ethernet bridge sends frames via RSSI/UDP to host
4. `DataRssi` on port 8193 receives frames (one RSSI link carries all boards)
5. Host demuxes by board (`application(dest=index)`) then by stream type; readout
   → `DataWriter` file channel 9, PID-debug → channels 0–7, config → channel 255
6. `DataWriter` (pyrogue StreamWriter, at `GroupRoot`) records to file; readers in
   `operations/streamreader.py` demux the channels back out

Frame formats defined in `warm_tdm._DataFormats` (`DataReadout`, `PidDebug`).

**Full channelization** — the end-to-end TDEST scheme (per-board stream tagging,
the ring board tag, host demux, file-channel layout, the multi-board file-channel
collision, and the migration plan) is documented in
[`firmware/common/DataChannelization.md`](../firmware/common/DataChannelization.md).
Read it before touching stream wiring or adding a data format.

## Configuration Management

- **Save/Load**: `GroupRoot.SaveConfig` / `GroupRoot.LoadConfig` (standard PyRogue YAML)
- **GroupConfigs** (`_GroupConfig.py`): Manages hardware configuration profiles (IP, board counts, board classes)
- **Config files**: Measurement snapshots live in each run’s `config/` directory;
  see [notebook runs](../docs/notebook-runs.md).
- **ConfigSelect** (`_ConfigSelect.py`): UI for choosing between saved configurations

## GUI Architecture

- Framework: PyDM (Python Display Manager) + PyQt
- Main display: `software/python/warm_tdm_api/widgets/_warm_tdm_display.py`
  (`WarmTdmDisplay`), used by both the server GUI and remote GUI client
- Widget modules in `software/python/warm_tdm_api/widgets/`:
  - `_warm_tdm_display.py` — Main display container
  - `_control_tab.py` — Hardware control panel
  - `_tuning_tab.py` — Tuning process controls
  - `_waveform_tab.py` — Real-time waveform display
  - `_pid_lock_tab.py` — Live multi-channel PID feedback, flux count and error

The Python display uses a local light palette with white plot surfaces, subdued
axes/grids and dark labels. Shared styling lives in `widgets/_plot_style.py`;
`LightPlotter` applies it to incoming tuning and waveform figures while preserving
their data and trace colors. The PID monitor assigns colors by channel and uses solid DAC / dashed
full-feedback traces in Both mode. Styling does not change global Matplotlib
or PyQtGraph defaults.

FAS Tuning places its two-column process controls in a scrollable left pane.
The right pane has separate **Sweep**, **Tune Summary**, and **Discovery** plot
tabs, with the row selectors on their respective Sweep and Discovery tabs.
Drag the divider to adjust the space allocated to controls and plots.

### PID Lock tab

Use **Add channels…** to search board/column names or enter **global columns**
(`board * 8 + channel`) and **logical rows** as comma-separated indices and
inclusive ranges, e.g. columns `0, 3, 8` and rows `10-15`. The dialog previews the
Cartesian product (18 channels in this example), skips duplicates, and validates
against the server's available rows and columns. Selections are local to each GUI
window and do not change `ConfigSelect` or the legacy monitor's selection.
Logical rows work with flat or two-level physical RowMap configurations.

The sidebar lists only selected channels. **Show** hides/reveals a channel while
retaining its history; **Remove** deletes highlighted entries; **Clear list**
removes all selections. **Overlay** compares channels on common metric plots;
**Separate panels** gives each visible channel its own feedback/error/flux plots
in a scrollable view. Colors identify channels across all plots. In Both mode,
DAC is solid and full feedback is dashed. Detailed plots are limited to **32
selected channels**, with a crowding notice above eight; colors repeat after
eight. Use the sidebar to identify traces rather than a large overlay legend.
Saved selections, a channel heatmap and acquisition-mask presets are not yet
implemented.

Under **Debug stream — per column**, choose one of the selected columns and
explicitly enable/disable its stream. All selected rows on that column share the
same hardware enable. Adding, hiding or removing channels never changes enables.
These enables remain shared across clients; turn off unwanted streams before
removing the last selected row on that column. The monitor does not start timing
or enable PID; it displays visits from the existing run.

The feedback selector offers **DAC + flux jumps**, **Full feedback**, and
**Both**. Feedback is in signed controller DAC-code units, before the output
polarity/offset-binary conversion, with a synchronized mean PID-error trace in
ADC counts per sample. Flux count is a net signed count of configured wrap
periods, not a count of events or a jump rate. An FP wrap period can represent
multiple physical flux quanta through `WrapMultiplier`.

FP full feedback comes directly from the accepted post-visit `sq1FbNewFp`.
Integer full feedback is reconstructed as fractional post-wrap `sq1FbFull +
numFluxJumps * FluxQuantumRaw`; its displayed DAC value rounds that fractional
state. All values come from the same debug frame. The integer path requires
debug v2 or newer for the DAC trace and current v3 firmware for full feedback.
Full feedback is withheld for truncated or saturated integer counts. Feedback
from a disabled PID or masked row is withheld because those debug values can
be computed candidates that were not applied.

The existing `PidDebugger` and `PidDebuggerFp` receivers publish a `Sample` array
on each `HardwareGroup.PidDebug[column].RowPids.PID[row]`, at up to **10 Hz per
row**. Each array holds the header timestamp, identity, feedback, net count,
error and drops from one decoded frame. The existing scalar diagnostics still
update on every received visit. The GUI attaches/detaches listeners directly on
selected per-row Sample variables and their columns' debug-enable variables. It
reuses the shared VirtualClient without stopping it when selections or windows
are removed, bypassing the installed Rogue PyDM plugin's client-stopping channel
teardown. Receive-thread callbacks copy samples into bounded queues; a 100 ms Qt
timer updates histories and draws once per batch. No new stream receiver,
background worker or register polling is added. The legacy
`HardwareGroup.PidLockMonitor` adapter remains available to older clients.

Integer reconstruction and applied-feedback gating use cached DSP settings,
with no additional register transactions for the sample. These settings are
not timestamped in the debug frame: refresh the cache after out-of-band writes,
and interpret samples around configuration changes with care. The GUI keeps
5–600 seconds of bounded history per channel on the hardware timebase. Visible
traces use the latest visible hardware timestamp as a common origin, so a stalled
channel falls behind its peers rather than shifting its final point to zero.
This assumes board timing is synchronized. Pausing freezes all histories; resume,
Clear history, and link transitions reset them. Adding/removing channels leaves
other histories intact; re-added channels wait for fresh samples. A timestamp
reversal resets the shared history, while drop-counter resets clear the affected
channel. Missing samples and increases in debug-drop count break plotted lines.
The list reports per-channel waiting/stale/disconnected status and missing
feedback; selecting an entry shows its net wraps, debug drops and feedback status. This sampled view can miss fast
transients; use recorded debug data for spectral analysis or event counting.

Run `software/tests/rogue_pid_lock_smoke.py` explicitly in a Rogue/PyDM/Qt
environment for a synthetic stream → localhost ZMQ → GUI smoke test. It uses no
hardware. `QT_QPA_PLATFORM=offscreen` supports headless runs;
`PID_MONITOR_SCREENSHOT=/path/to/example.png` saves overlay and separate-panel
examples. The smoke covers integer/FP streams on two boards, independent windows,
column enables, layout changes, pause/resume and removal/re-addition/teardown.

## Key Scripts

| Script | Purpose |
|--------|---------|
| `warmTdmServer.py` | PyRogue hardware server (use `--gui` to launch GUI) |
| `warmTdmClientGui.py` | Remote GUI client (connects via ZMQ) |
| `warmTdmClientCmd.py` | Interactive Python client (`client`, `group`, `sess`, `ops`) |
| `warmTdmServer.py --emulate` | Register-memory emulation (no hardware) |
| `inspect_stream.py` | Summary of recorded readout, integer/FP PID, waveform and config |
| `new_run.py` | Offline creation of a measurement notebook/run directory |
| `sync_notebooks.py` | Generate/check maintained notebook templates |

## Dependencies

Core dependencies from `conda.yml`:
- `rogue` — PyRogue framework
- `numpy` — Array operations
- `pydm` — Display manager for GUIs
- `pyqt` — Qt bindings
- `matplotlib` — Plotting
- `simple-pid` — PID algorithm reference
- `pyzmq` — ZMQ server/client communication
