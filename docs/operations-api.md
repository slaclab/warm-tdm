# The `warm_tdm_api.operations` API

`warm_tdm_api.operations` (imported as `ops`) is the **client-side operational
layer** for running a Warm-TDM Group: session/board management, hardware setup,
data acquisition, tuning, stream reading, and offline analysis/plotting. It drives
the Rogue tree remotely and is deliberately kept separate from the pyrogue-tree
device modules (`_Group`, `_SaTune`, …).

This page is the how-to-use reference. Two companion documents cover the pieces
this one only points at:

- **[`docs/design/muxed-run-bringup.md`](design/muxed-run-bringup.md)** — the
  *why*: the three configuration layers (enabled set / tune point / run settings),
  their ordering, and the planned tune-point save/restore.
- **[`software/jupyter/operations_template.py`](../software/jupyter/operations_template.py)**
  — a worked, runnable end-to-end workflow on this API (jupytext `.py` source of
  truth + generated `.ipynb`).

## Getting started

`operations` is **not** auto-imported by `warm_tdm_api` (that keeps
matplotlib/scipy off the server import path). Import it explicitly:

```python
import warm_tdm_api.operations as ops
```

### Connect

Hardware-coupled operations live on a `Session` — an explicit handle bound to one
`Group`. `connect()` builds a client to a running `warmTdmServer`, wraps its
`Group` in a `Session`, and caches that as the process-wide default:

```python
sess = ops.connect(host="localhost", port=9099)   # returns the default Session
```

Because a default is now cached, the free-function shims call it without a
`session.` prefix — convenient at a notebook prompt:

```python
ops.status()          # same as sess.status()
ops.take_raw(0)        # same as sess.take_raw(0)
```

If you already have a connected client (e.g. a `VirtualClient`), use
`ops.use(client)` instead of `connect()`. **Scripts and tests should prefer an
explicit `Session`** — construct `ops.Session(client.root.Group)` and call methods
on it directly, rather than relying on the global default.

### The Session model

A `Session` binds to **one `Group` node**, not the client's global `root.Group`.
That is deliberate: the Group is the topology unit, and binding per-Group is the
seam a future multi-Group `Instrument` needs (one Session per Group). Per-Group
topology — channels-per-board, board maps — is **derived from the bound Group**,
never hardcoded, so a differently-shaped Group works without code changes. The one
fixed convention is that the timing coordinator is always `ColumnBoard[0]`.

The client/server seam is unchanged: `warmTdmServer` owns the real
`GroupRoot` + ZMQ server; a `VirtualClient` mirrors that tree over ZMQ, and the
Session drives the mirror.

## The operator arc

The API is organized around the end-to-end operator workflow. It maps onto the
three configuration layers from
[`muxed-run-bringup.md`](design/muxed-run-bringup.md):

```
connect ─► status ─► (A) enabled set ─► (B) tune ─► (C) setup_mux ─► take_data ─► analyze
                     ColTuneEnable      sa_offset    run settings    acquire      plot_stream_data
                     RowMap/order       sa_tune      + PID enable
                                        sq1_tune
```

- **A — enabled set (the anchor):** which columns/rows participate
  (`group.ColTuneEnable`, the row map/order). Set it first; B and C are meaningful
  only relative to it.
- **B — tune point:** the servo setpoints a tune produces. Driven by the tuning
  wrappers (`sa_offset`, `sa_tune`, `sq1_tune`).
- **C — run settings:** how the muxed run is clocked and servoed
  (`setup_mux` — timing, sample window, PID enable).

See [`operations_template.py`](../software/jupyter/operations_template.py) for the
full sequence with real parameters.

## API reference

`sess.` methods and the matching `ops.` shims are interchangeable once a default
Session exists (`ops.foo(...)` delegates to `sess.foo(...)`).

### Session & connection

| Call | What it does |
|---|---|
| `ops.connect(host, port, path=…, group='Group')` | Build a `VirtualClient`, wrap its Group, cache as default. Returns the `Session`. |
| `ops.use(client, path=…, group='Group')` | Wrap an already-connected client's Group, cache as default. |
| `ops.Session(group_node, output=…)` | Construct an explicit Session (preferred in scripts/tests). |
| `ops.get_default_session()` / `ops.set_default_session(s)` | Read / set the cached default. |
| `sess.new_session(base=…)` | Start a fresh timestamped output directory. |

`OutputDir` owns the `<base>/<YYYYMMDD>/<ctime>/` data directory and falls back to
a local `data` dir then `$HOME` if the requested base is not writable.

### Hardware info & setup

| Call | What it does |
|---|---|
| `sess.status()` | One-shot instrument-state summary (board counts, run/MUX mode, tune-enabled columns, output dir). Read-only; returns a dict. |
| `sess.print_hardware()` | Firmware/build info (BuildStamp, DeviceDna, GitHash, ImageName) per board. |
| `sess.setup_mux(num_pts, sample_end_offset, sample_num, …, enable_pid, enable_pid_debug)` | Configure the coordinator timing (row period + sample window), put row DACs in timing mode, and enable SQ1 PID for every active column. |
| `sess.set_cryo_resistance(Rcryo_Ohm)` | Set the cryostat roundtrip cable resistance on every board's analog-front-end amp model. |
| `sess.set_ps_synch(mode)` / `sess.check_ps_synch()` | Set / read the board power-supply synchronization state. |
| `sess.disable_leds()` | Turn off the status-blink LEDs on all boards. |
| `sess.apply_dead_masks(dead_masks)` | Write per-column dead-row masks to `AdcDsp[col].RowEnableMask`. Takes `{col: mask}` from `make_dead_masks` / `read_dead_masks`. |
| `sess.save_config()` / `sess.load_config(path)` | Save / restore all RW+WO variables (a recallable config YAML). |
| `sess.save_state()` | Save the full system state (adds RO) — a complete snapshot. |
| `sess.stop_and_zero()` | Best-effort return to a safe baseline (see the caveat below). |

Several of these setup helpers now delegate to a `Group` variable that owns the
broadcast (cable resistance, power-supply sync, LED enable, dead masks); the
`ops.*` call sites are unchanged. Graduating more of them onto `Group` is tracked
in **Issue #83 (graduate operations helpers onto Group)**.

### Tuning wrappers

Each Warm-TDM tuning algorithm is a `pr.Process` on `Group` with a uniform
`Start`/`Stop`/`Running`/`Progress`/`Message` interface. `run_process` replaces the
old hand-rolled `proc.Start(); while proc.Running.get(): …` idiom — it applies
parameters, starts the process, blocks (with an optional timeout), surfaces the
result `Message`, and returns the process's output variable.

| Call | What it does |
|---|---|
| `sess.run_process(name, block=True, timeout_sec=None, **params)` | Configure, start, and optionally block on any Group `pr.Process` by node name. |
| `sess.sa_offset(**params)` | SA offset determination (`SaOffsetProcess`). |
| `sess.sa_tune(**params)` | SA amplifier tuning (`SaTuneProcess`), e.g. `sa_tune(SaBiasNumSteps=5)`. |
| `sess.sq1_tune(**params)` | First-stage SQUID tuning (`Sq1TuneProcess`). |

Interrupting a blocking wait (`KeyboardInterrupt`) stops the process rather than
orphaning it.

### Data acquisition

| Call | What it does |
|---|---|
| `sess.take_raw(col, …, timeout_sec=30.0)` | Capture one raw waveform for a single column; returns the saved path. Raises `TimeoutError` if no file appears. |
| `sess.multi_raw(col, nraw, …)` | Capture `nraw` waveforms into a `raw_<ctime>/` dir; returns a text index file. |
| `sess.take_data(acq_time_sec, start_delay_sec=1.0)` | Open the `DataWriter`, acquire for `acq_time_sec`, then close. Starts the run if stopped and restores the run state afterward — always closes the file, even on interrupt. |

### Offline analysis & plotting

| Call | What it does |
|---|---|
| `ops.plot_stream_data(channels, stream_data_id=…)` | Plot time-domain + amplitude spectral density for the readout stream. Accepts a `StreamData`, a file path (first-class), or `-1` for the most recent capture. |
| `ops.analyze_pair(ch_a, ch_b, …, do_fit=…)` | Compare two channels with an optional noise-model fit. |
| `ops.plot_sq1curves(sq1_out, cols=…, rows=…)` | Plot SQ1 V/φ curves from an `sq1_tune` output. |
| `ops.plot_pid_debug(channels, field=…, pid_data_id=…)` | Plot the per-(col,row) PID-debug stream (only populated when `PidDebugEnable` was set). |
| `ops.get_mean_raw_asd(col, idxpath=…)` | Mean ASD across a `multi_raw` capture set. |
| `ops.compute_asd(...)`, `ops.channel_timeseries(...)` | Shared spectral / timeseries primitives. |

Calibration (sample rate `fs`, SQ1FB→pA scale) is **derived automatically** from
each file's embedded Rogue config channel; pass explicit overrides if you need
them.

### Channel helpers, unit conversions, data containers

Pure (no-hardware) helpers:

- **Channels** (`channels.py`): `get_row_col`, `make_dead_masks`,
  `write_dead_masks`, `read_dead_masks` — addressing, identifiers, dead-row masks.
- **Unit conversions** (`unit_conversions.py`): `derive_fs`, `derive_sq1fb_to_pA`,
  `resolve_fs`, `resolve_sq1fb_to_pA`, plus `DEFAULT_FS` / `DEFAULT_SQ1FB_TO_PA`
  fallbacks.
- **Data containers**: `StreamData` (readout stream) and `PidDebugData`
  (PID-debug stream); `StreamReader` decodes all channels of a `.dat` file in one
  pass (readout, PID-debug, and the embedded config).

## `stop_and_zero` is best-effort, not an interlock

`stop_and_zero()` ends any active run, drops to manual timing, and zeros the
column outputs — the fast-DAC force outputs with **read-back verification and
bounded retry** (via `DacCurrentNow`), the slow bias/offset outputs with a single
write. Row DACs are currently left untouched.

It is **not** a hardware safety interlock. It works around the FastDacDriver
override one-shot race (**Issue #86**) in software, and gives real confirmation the
fast DACs reached zero — but if a channel cannot be driven to ~0 within the retry
budget it logs a warning rather than guaranteeing the state. The underlying
firmware fix (a pending-latch in `FastDacDriver`) is written up in
[`docs/design/fastdac-override-race.md`](design/fastdac-override-race.md).

## See also

- [`software/SOFTWARE_GUIDE.md`](../software/SOFTWARE_GUIDE.md) — package structure,
  device-tree hierarchy, tuning processes, data streaming.
- [`docs/design/row-mapping.md`](design/row-mapping.md) — logical/physical row
  addressing.
- [`firmware/common/DataChannelization.md`](../firmware/common/DataChannelization.md)
  — the end-to-end data path and channel scheme.
