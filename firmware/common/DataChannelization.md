# Data Channelization

## Overview

Warm TDM streams three kinds of bulk data from the column boards to the host:
the **readout** stream (the tuned/servoed MUX data — the operational product),
the **waveform** captures (raw digitized ADC — a debugging aid), and the
**PID-debug** stream (per-servo-visit diagnostics — loop bring-up only). All
three share one physical path: the PGP ring aggregates every board's data onto a
single stream, the coordinator board bridges it to Ethernet, and it arrives at
the host over **one RSSI/UDP connection** (data port 8193). Register access is a
separate SRP/RSSI connection (port 8192) and is not covered here.

This document is the source of truth for how those streams are tagged, routed,
and separated — i.e. what `tDest`/channel a given frame carries at each stage,
and where board and stream identity live. It matters because a single `.dat`
file interleaves all of them, and because the layout must migrate cleanly to
multiple column boards and, eventually, multiple Groups.

The identity of a frame is carried in an 8-bit **TDEST** on the wire, which the
host uses to demultiplex. Read the TDEST as two nibbles:

```
 tDest[7:4] = source board (PGP ring address)
 tDest[3:0] = stream type within that board
```

## Stage 1 — per-board stream tagging (`DataPath.vhd`)

Each column board's `DataPath` muxes its outgoing streams into the low nibble of
TDEST (`U_AxiStreamMux_2`, `MODE_G => "ROUTED"`):

| tDest[3:0] | Stream | Producer | Role |
|---|---|---|---|
| `0`–`7` | PID-debug | `AdcDsp` per board-channel (gated by `PidDebugEnable`) | debug (loop bring-up) |
| `8` | Waveform | `WaveformCapture` | debug (raw ADC) |
| `9` | Readout | `EventBuilder` | **operational data** |

The board then packetizes the combined stream (`AxiStreamPacketizer2`).

> Note (historical): the readout — the operational product — sits at `9`, *above*
> the eight debug channels `0`–`8`. This is a relic of development order (the
> debug streams were built first). It is a wire/format contract now and is likely
> too costly to renumber; treat `9 = readout` as fixed and document around it.

### Readout frame body (`EventBuilder.vhd`)

The readout stream additionally embeds per-sample identity in the frame body
(not just TDEST). In `DO_DATA_S`, each 64-bit event word packs:

```
 tData[31:0]  = sample value (float32 SQ1FB DAC code)
 tData[39:32] = tID   (source channel id from the DSP mux)
 tData[47:40] = tDest (per-sample column, low 3 bits meaningful today)
 tData[63:48] = high sample bits
```

The per-column index here is currently only 3 bits (`tDest(2 downto 0)`,
`doneCols`), i.e. **one board's 8 columns** — see "Multi-board / multi-Group
migration" below.

## Stage 2 — PGP ring aggregation and the board tag (`RingRouter.vhd`)

Boards are wired in a ring; each has a 3-bit `address`. This is where **board
identity enters the TDEST**. When a board injects its local data toward the
coordinator, `TAG_SRC` stamps its address into TDEST bits `[6:4]`:

```vhdl
v.tdest(6 downto 4) := address;   -- outgoing data tagged with source board
```

On receive, `SWAP_TDEST` swaps the nibbles so the demux can dispatch by
destination address; the demux (`AxiStreamDeMux`, `DYNAMIC`) routes
`tDest == address` frames to the local app, dumps frames that have looped the
ring without a destination, and passes everything else through toward the
coordinator. The result: the coordinator sees a single aggregated stream in
which **every frame's TDEST is `(board << 4) | stream_type`** — e.g.

| Wire tDest | Meaning |
|---|---|
| `0x09` | board 0, readout |
| `0x19` | board 1, readout |
| `0x08` | board 0, waveform |
| `0x23` | board 2, PID-debug channel 3 |

An 8-bit TDEST therefore addresses **8 boards × 16 stream types**. The
coordinator (`RING_ADDR_0`) bridges this aggregated ring stream to Ethernet
(`PgpEthCore`), and it leaves the instrument over the single RSSI data link.

## Stage 3 — host demultiplexing (`_HardwareGroup.py`)

The host separates the single RSSI stream back out in two layers:

1. **By board** — `dataUdp.application(dest=index)` (an `UdpRssiPack`
   application demux) yields one `dataStream` per board, keyed on the TDEST high
   bits. Board identity is preserved here.
2. **By stream type** — each board's stream is depacketized and
   `packetizer.application(i)` demuxes the low nibble into apps `0`–`9`.

The apps are then wired to their sinks:

| App | Sink | In the `.dat` file? |
|---|---|---|
| `0`–`7` (PID-debug) | `dataWriter.getChannel(i)` + live `PidDebugger` decoders | yes |
| `8` (waveform) | `WaveformCaptureReceiver` → separate `.npy` | **no** (bypasses the file) |
| `9` (readout) | `dataWriter.getChannel(9)` | yes |

The tree config/status YAML is written to reserved file **channel 255** on
`DataWriter` open/close (see `_GroupRoot.py`).

### File-channel layout (as written today)

The `DataWriter` is a `StreamWriter` at `GroupRoot` scope. The file frame header
carries a 1-byte `channel` field (256 slots). Current mapping:

| File channel | Contents |
|---|---|
| `0`–`7` | PID-debug (per board-channel) |
| `9` | Readout |
| `255` | Tree config/status YAML |

Waveform is not in the file (it takes the `.npy` path).

## Multi-board / multi-Group migration

**Known gap (single-board assumption in the file layer).** Board identity is
carried correctly all the way to the host (TDEST `[6:4]`, then the per-board
`application(dest=index)` demux) — but it is **dropped at file-write time**. In
`_HardwareGroup.py` the `for index in range(colBoards)` loop wires every board's
apps to the *same* file channels:

```python
packetizer.application(i) >> ... >> dataWriter.getChannel(i)   # no `index`
packetizer.application(9) >> ... >> dataWriter.getChannel(9)   # no `index`
```

So with two column boards, both boards' readout lands on file channel `9` and
their PID-debug on `0`–`7`, interleaved with no board tag in the file. This is a
host-side bug, not a firmware one — the wire already distinguishes the boards.

**Migration direction (not yet implemented — see the wtj-refactor plan):**

- **Namespace file channels by board** (host-only fix): e.g.
  `channel = board*16 + stream_type`, mirroring the wire TDEST. The uint8 channel
  field holds 16 boards × 16 streams. No RTL change needed.
- **Namespace by Group** for a single Instrument-wide file: add group bits to the
  channel encoding. This is coupled to the federated-vs-non-federated decision —
  a single Root/DataWriter needs group bits in the channel; a writer-per-Group
  (federated) does not, and the Instrument correlates files client-side.
- **Fold waveform into the file** (host-only): route app `8` to a
  `getChannel(...)` like readout/PID instead of the `.npy` side path, so one file
  holds all streams with config embedded.
- **Widen the readout column field**: the 3-bit per-sample column in the
  EventBuilder body (`tData[47:40]`, low 3 bits) only distinguishes 8 columns of
  one board. A global column index (board·8 + channel) would make the readout
  frame self-describing across boards — a coordinated RTL change (see below).

**Keep the channel scheme in one place.** The channel numbers are a contract
shared by the write side (`_HardwareGroup.py`) and the read side
(`operations/streamreader.py`, which decodes channels `9`, `0`–`7`, `255`).
Define the encoding once so board/group migration is a single-point edit rather
than a hunt across both sides.

## Self-describing frames (proposed — see wtj-refactor plan)

Large `.dat` files are routinely reprocessed into derived files, at which point
the *file channel number* may be renumbered or lost. To make each frame
independently interpretable — and to provide a sanity check against the channel
id — the frame **bodies** should carry their own channelization metadata:
Group id, board id, and (for readout) a global column index, in addition to the
existing per-sample col/row. The PID-debug frame already carries `col`/`row` in
its body; the readout frame carries per-sample `col` (3-bit) but no board/Group;
waveform carries the least. Making all three formats self-describing is a
firmware-track item (frame layout + `_DataFormats` decoders + the host readers).
This is captured in `docs/plans/wtj-refactor/PLAN.md`.

## Reference

| Layer | File | Role |
|---|---|---|
| Per-board stream mux | `firmware/common/warm_tdm/rtl/DataPath.vhd` | tDest[3:0] stream-type assignment |
| Readout frame build | `firmware/common/warm_tdm/rtl/EventBuilder.vhd` | packs per-sample col/row/value |
| Ring board tag + route | `firmware/common/warm_tdm/rtl/RingRouter.vhd` | tDest[6:4] = board address |
| Eth bridge | `firmware/common/warm_tdm/rtl/PgpEthCore.vhd` | ring ↔ Ethernet on coordinator |
| Host demux + file wiring | `firmware/python/warm_tdm/_HardwareGroup.py` | per-board + per-stream demux, `getChannel` |
| Frame formats (decode) | `firmware/python/warm_tdm/_DataFormats.py` | `DataReadout`, `PidDebug` (+ dtypes) |
| Config/DataWriter | `software/python/warm_tdm_api/_GroupRoot.py` | `StreamWriter`, config → channel 255 |
| Host readers | `software/python/warm_tdm_api/operations/streamreader.py` | channel demux → `data`/`pid`/`config` |
