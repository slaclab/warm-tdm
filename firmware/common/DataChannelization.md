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

## Open design item: collapse per-column PID-debug onto one tDest (2026-08-12)

> Status: **agreed worthwhile, not scheduled.** Firmware-track; a natural
> corollary of self-describing frames (below).

Today `DataPath.vhd` spreads the 8 per-column PID-debug streams across tDest
`0`–`7`: `U_AxiStreamMux_1` (`NUM_SLAVES_G => 8`, `MODE_G => "INDEXED"`) stamps
`tDest = input index`, then `U_AxiStreamMux_2` routes the whole `00000---` block.
But the PID frame **body already carries `col`** (`_PidDebugger`:
`col = arr[0] & 0b111`), so the per-column tDest is **redundant with the body**.

**Proposal:** merge the 8 PID streams onto a *single* board-local tDest (frames
are atomic 80-byte records; a receiver dispatches by the body's `col`). This is
what the file-based `PidDebugParser` already does.

**Why it's worth doing:**
- **Reclaims 7 of the 16 board-local stream slots.** The low nibble is nearly
  full today (`0–7` PID, `8` waveform, `9` readout); collapsing PID to one slot
  frees `1–7` — real headroom for the board/Group-aware channel scheme.
- **No information lost** — the disambiguator (`col`) is already in the body.
- **Aligns with self-describing frames**: if the body is authoritative, tDest
  carrying per-column identity is exactly the redundancy we want to remove.
- On the single serial RSSI link there is **no flow-control benefit** to keeping
  them separate (all serialized downstream anyway).

**Why it wasn't done originally (artifact, not a bug):** the host live/GUI path
attaches one `PidDebugger` receiver per column via `packetizer.application(i)`
(the `PidDebug[i]` tree nodes); the per-column tDest feeds those 8 devices
directly. Collapsing means the live path becomes one receiver that reads `col`
from the body and dispatches to `PID[col]` — a modest host rewrite. INDEXED mux
was also the path of least resistance in RTL (same development-order relic family
as readout-at-9).

**Coupling:** this is nearly the same move as "make the body authoritative"
below. If the **shared frame-identity header (option A)** is chosen, a single PID
tDest per board is the obvious layout and per-column tDest becomes clearly
vestigial — so decide this together with the A/B question, and land it in the
same firmware-track pass. PID-debug is debug-only (not in a delivered
instrument), so it does not justify a standalone effort.

## Self-describing frames (design — resolved 2026-08-17)

> Status: **design resolved; not yet built.** The frame-identity approach is
> decided — a shared 16-byte header with an absolute-epoch timestamp (see the
> DECISION and Timebase sections below); this section keeps the motivating
> discussion so it is not rehashed. It is a **firmware-track** change (RTL frame
> builders + `_DataFormats` decoders + host readers land together, since the byte
> layout is the contract), sequenced with the multi-Group Instrument decision
> (Issue #80 — the `groupId` field's meaning is gated on the federated-vs-not
> choice). See `docs/plans/channelization/PLAN.md` for the work plan.

### Motivation

Large `.dat` files are routinely reprocessed into derived files (split, merged,
downsampled). In that flow the **file channel number can be renumbered or lost**,
so it must not be the only thing that says what a frame is. Guiding principle:

> **Every frame must be interpretable from its body alone, with zero reliance on
> the file channel it arrived on.** The file channel then becomes a redundant hint
> that can be *cross-checked* (`body.boardId == file_channel >> 4`) — mismatch
> signals corruption or a reprocessing bug — rather than a decode dependency.

### What each format carries today vs. needs

| Format | Carries today | Missing (supplied by the shared header) |
|---|---|---|
| Readout (`EventBuilder`) | header `readoutCount`/`rowSeqCount`/`runTime`; per-sample `col` (3-bit, board-local), `row`, value | formatType/version, board id, Group id, global column (3-bit col cannot name column 8+), absolute-epoch timestamp |
| PID-debug (`_PidDebugger`, fixed + float) | `col`/`row` per frame (board-local); split `runTime` words | formatType/version, board id, Group id, absolute-epoch timestamp |
| Waveform | least (raw ADC; today decoded structurally, not even in the file) | formatType/version, col / board / Group id, absolute-epoch timestamp |

**This is now supplied uniformly by the 16-byte shared frame-identity header —
see "DECISION" below.** Rather than per-format ad-hoc fields, every frame gains
the same fixed prefix (`formatType`, `formatVersion`, `groupId`, `boardId`,
`timeSource`, 64-bit `timestamp`), with the format-specific body after it. The
readout reader derives `global_col = boardId·8 + local_col`; the header's
`timestamp` supersedes readout's `runTime` and PID-debug's split `runTime` words
(which become free padding); waveform gets the same header when it is folded into
the file. See the DECISION and Timebase sections for the exact layout and the
absolute-epoch semantics.

### DECISION — one shared frame-identity header (resolved 2026-08-17)

**Chosen: (A) a single shared frame-identity header on all stream frames.** The
rejected alternative was (B) per-format identity fields fitted into each layout
independently. (A) wins because the whole point of #82 is that a reprocessed
file must decode from the body alone: a fixed-location `formatType` +
`formatVersion` gives every reader ONE "read the prefix → dispatch to the body
decoder" entry point and a uniform identity-vs-channel cross-check. (B) leaves
dispatch ad hoc (each new stream re-solves identity) and would perpetuate
heuristics like distinguishing the two PID-debug layouts by frame size (80 vs 40
bytes) — exactly the fragility this design removes. (A)'s cost — re-laying-out
all three formats at once — is the firmware-track work we are scheduling anyway.

#### The 16-byte header (two 64-bit words)

Every readout, PID-debug, and waveform frame begins with this fixed prefix; the
format-specific body follows. 16 bytes preserves 64-bit word alignment (clean
numpy structured-array views) and is negligible per frame (PID-fixed 80→96,
PID-float 40→56; readout absorbs it into its existing header words).

| Word | Byte | Field | Notes |
|---|---|---|---|
| 0 | 0 | `formatType` | readout / pid-fixed / pid-float / waveform (enum; extensible) |
| 0 | 1 | `formatVersion` | starts at 1; **bump on any layout change** (see below) |
| 0 | 2 | `groupId` | reserved, 0 until the multi-Group model is fixed (#80) |
| 0 | 3 | `boardId` | source column board; cross-checks `file_channel >> 4` |
| 0 | 4 | `timeSource` | how word 1 was produced (enum; see timebase below) |
| 0 | 5–7 | reserved | future flags / `colBase`; zero-filled |
| 1 | 8–15 | `timestamp` | **64-bit absolute time** (see timebase below) |

A single `_DataFormats` entry point reads word 0, validates `formatVersion`,
cross-checks `boardId` against the file channel, and dispatches to the body
decoder named by `formatType`. `groupId`/`boardId`/global-column all live here
once, not per sample.

#### Versioning (non-negotiable)

`formatVersion` is mandatory from day one (starts at `1`). Reprocessed files
outlive the firmware that wrote them, so a decoder must be able to tell which
layout it is reading; `formatType`+`formatVersion` together are the authoritative
discriminator, and frame size becomes a cross-check rather than the selector.

### Timebase — absolute-epoch timestamp with a standalone fallback

**The frame timestamp is committed to be an absolute epoch** (64-bit, word 1 of
the header), not a run-relative counter. This is what lets frames from different
runs — and eventually different Groups — correlate after reprocessing. Today's
`runTime` (run-relative TimingClk ticks, reset at each `startRun`) is not enough
on its own; the `timeSource` byte records how the 64-bit `timestamp` was produced
so a reader knows how to interpret and compare it.

**Where absolute time comes from — the eventual target vs. today.** The timing
system already distributes a synchronized timebase within a Group: the
coordinator board (`RING_ADDR_0_G`) generates `runTime` and fans it out over the
serial timing link; every board decodes the same value (`LocalTimingType`). There
is no external/upstream timing input today — the coordinator is the root of time
for its Group.

- **Eventual target (Path 2, Instrument-distributed):** an instrument-level
  absolute time source (PTP / White Rabbit or a super-coordinator) feeds all
  Group coordinators a common absolute epoch, which they fan out unchanged. This
  is the intended long-term architecture (it matches the non-federated /
  supervisory direction in #80). **That hardware will not exist for some time**,
  so it is the target the format must accommodate, not build now.
- **Today / bench (Group self-rooted, the fallback):** with no upstream present,
  the Group's coordinator roots its own epoch — seeded from the host at run start
  (wall-clock ns written to a coordinator register, or reconstructed from a logged
  start time + TimingClk frequency in the config channel). This is the near-term
  implementation and the permanent behavior whenever no upstream source is
  attached.

**Standalone invariant (binding).** Group self-rooting is the *fallback*, not a
co-equal mode: the eventual normal source of the epoch is the Path-2 upstream
distribution, and a Group falls back to self-rooting only when no upstream is
present (every bench today; a disconnected crate later). Stated as the invariant
the design must hold: *a Group's coordinator must always be able to produce a
valid, monotonic frame `timestamp` on its own, with no external dependency; an
upstream/Instrument absolute source, when present, supersedes the self-rooted
epoch and updates `timeSource` accordingly — its absence degrades cross-Group
absolute alignment but never prevents a Group from running or timestamping data.*

`timeSource` enumerates at least: `run-relative-ticks` (pre-epoch legacy /
uninitialized), `group-epoch` (self-rooted, host-seeded — today's fallback), and
`instrument-epoch` (Path-2 upstream-distributed — the eventual target). The
frame layout is identical across all of them; only `timeSource` and the meaning
of the 64-bit value change, so moving from the fallback to Path 2 is a
`timeSource`/`formatVersion` change, not a re-layout.

The two candidate directions for that upstream absolute source (PTP/White-Rabbit
vs. an LCLS-II-style timing link with experiment-local fan-out), the likely
WarmTDM path, and the standalone-Group invariant are explored in
[`docs/design/timing-distribution.md`](../../docs/design/timing-distribution.md).
Notably, the LDMX/LCLS-II reference suggests the 64-bit `timestamp` is best
carried as a **composite fiducial** (coarse pulse/frame id in the high bits, fine
sub-count in the low bits) rather than a raw tick count — the exact encoding is
deferred to that timing effort, but the 64-bit slot accommodates it.

### Sequencing (incremental, no flag-day)

1. **Done (host-only, no RTL):** centralized channel map + board-namespaced file
   channels (`file_channel(board*16 + stream)`), unified readers, board identity
   carried in the *channel* immediately. (Phase 1, this branch.)
2. **Gated on #80:** the multi-Group file model fixes what `groupId` means
   (single Root/DataWriter needs it in-band; federated writer-per-Group may not).
   The header reserves the field regardless.
3. **Firmware track (Phase 3):** implement the 16-byte shared header across all
   three formats + `_DataFormats` decoders + host readers as one coordinated
   change, with `timestamp` populated by the Group-self-rooted epoch initially.
   After this the body is authoritative and the file channel is a checkable hint.
   The Path-2 upstream absolute-time distribution lands later as its own timing
   effort, dropping into the same 64-bit slot via `timeSource`/`formatVersion`.

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
