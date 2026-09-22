# PGP Ring Network Architecture

## Overview

The warm-tdm system uses a PGP2b-based unidirectional ring network to connect a ColumnFpgaBoard (coordinator) with one or more RowFpgaBoards. The ring carries SRP (register access) traffic and optionally streaming data between boards.

Each board has a `PgpCore` module that manages the PGP physical layer and a `RingRouter` that handles frame routing around the ring.

## Physical Topology

The ring is a unidirectional daisy chain. Each node's TX connects to the next node's RX. The last node's TX connects back to node 0's RX, closing the ring.

### Minimal Configuration (1 Column + 1 Row)

```
    ┌──────────────────┐         ┌──────────────────┐
    │  ColumnFpgaBoard │         │   RowFpgaBoard   │
    │   (Address 0)    │  PGP    │   (Address 1)    │
    │   Coordinator    │         │                  │
    │           TX ────┼────────►┼── RX             │
    │           RX ◄───┼─────────┼── TX             │
    │                  │         │                  │
    │  [Ethernet/SFP]  │         │                  │
    └──────────────────┘         └──────────────────┘
```

### Full Configuration (4 Columns + 1 Row)

A typical warm-tdm deployment with 4 column boards and 1 row board. Node 0 is always the coordinator with the Ethernet uplink. Each column board reads out 8 ADC channels; the row board drives row-select switches.

```
                                    PGP Ring Direction ──►

    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │ Column 0     │     │ Column 1     │     │ Column 2     │     │ Column 3     │     │ Row Board    │
    │ (Addr 0)     │     │ (Addr 1)     │     │ (Addr 2)     │     │ (Addr 3)     │     │ (Addr 4)     │
    │ Coordinator  │     │              │     │              │     │              │     │              │
    │              │ PGP │              │ PGP │              │ PGP │              │ PGP │              │
    │         TX ──┼────►┼── RX    TX ──┼────►┼── RX    TX ──┼────►┼── RX    TX ──┼────►┼── RX    TX ──┼──┐
    │              │     │              │     │              │     │              │     │              │  │
    │         RX ◄─┼─────┼─────────────────────────────────────────────────────────────────────────────┼──┘
    │              │     │              │     │              │     │              │     │              │
    └──────┬───────┘     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
           │
           │ Ethernet (SFP)
           │
     ┌─────▼─────┐
     │  Host PC  │
     │ (pyrogue) │
     └───────────┘
```

Only the coordinator (Column 0) has an Ethernet uplink to the host. All register access to other nodes in the ring is proxied through the coordinator's Ethernet-to-ring bridge.

**Routing example:** Host PC wants to read a register on the Row Board (address 4):
1. Host sends SRP frame via Ethernet to Column 0's EthCore
2. EthCore bridges it onto the ring with TDEST[2:0]=4 (destination), TDEST[6:4]=0 (source)
3. Column 0's RingRouter packetizes and transmits on PGP TX
4. Columns 1, 2, 3 read the packet header, check TDEST[2:0]≠their address, and forward the original packet unchanged
5. Row Board receives it, depacketizes, checks TDEST[2:0]=4 → local delivery → SRP processes register read
6. Row Board sends SRP response with TDEST[2:0]=0 (original source becomes destination after swap)
7. Response traverses: Row Board TX → Column 0 RX → local delivery → EthCore → Host

**Key properties:**
- The coordinator (node 0) is the sole gateway between the host and the ring
- Any node's registers are accessible from the host via ring-routed SRP through the coordinator
- Every board pauses local injection on congestion; forwarding remains enabled
- Passthrough traffic always has priority over locally-originated traffic at the TX mux
- A frame that loops the entire ring without finding its destination is dumped (detected by source address in TDEST[6:4])

### Wiring

The PGP ring uses dedicated MGT lanes. On the ColumnFpgaBoard these are exposed on RJ45 connectors carrying differential pairs:
- `rj45TimingMgt` or `pgpTxP/N`, `pgpRxP/N` — 1.25 Gbps PGP2b

Each board's PGP transceiver uses a 250 MHz reference clock.

Data flows in one direction around the ring. Each node receives on RX, processes/routes, and forwards on TX. The ring uses PGP2b in half-duplex mode over GTX transceivers (Kintex-7) with a 250 MHz reference clock generating a 1.25 Gbps line rate.

## Address Discovery

- **Node 0 (Coordinator):** Has `RING_ADDR_0_G = true`. Its address is hardcoded to `"000"`.
- **Other nodes:** Discover their address from the PGP sideband channel. They read `pgpRxOut.remLinkData(2:0)` (the upstream node's transmitted address) and add 1. This propagates around the ring so each node gets a unique 3-bit address (0-7).

Address occupies `locPgpTxIn.locData(2:0)`. The upper bits carry the ring flow-control protocol described below.

## Frame Routing (RingRouter)

Each node has a `RingRouter` instance per virtual channel (2 VCs active: VC0=SRP, VC1=Data).

### Receive Path

```
PGP RX -> PgpRingRxFifo -> packet-header route -> {Depacketizer -> Local, Transit, Dump}
```

`PgpRingRxFifo` crosses from `pgpClk` to `axilClk`, tracks occupancy, and
terminates damaged packets on overflow. `RingRouter` reads TDEST from the
packetizer-v2 header. Matching destination bits `[2:0]` select local
reassembly. Otherwise matching source bits `[6:4]` discard a packet that made
one full circuit; remaining packets go to transit. The route holds through the
packet tail. Transit preserves sequence numbers and packet boundaries without
reassembly or repacketization.

### Transmit Path

```
Local App TX -> source tag -> Packetizer -> complete-packet FIFO --+
                                                                Mux -> PgpTXVcFifo -> PGP TX
Transit --------------------------------------------------------+
```

Local frames are segmented into at most 128-byte packets. The local FIFO releases
only complete packets: a producer stalled halfway through a packet cannot hold
the mux and block transit. Arbitration happens at packet boundaries. Transit
has priority over a new local packet, and pause disables only new local
admission. A selected packet completes even if pause asserts or its downstream
ready deasserts. This bounds the remaining local injection independently of SRP
response size. The shared TX FIFO after the mux holds only 128 bytes.

The SURF packetizer/depacketizer application interfaces use **eight TUSER bits
per byte**, while ring/application streams use two. `RingRouter` explicitly
converts first/last-byte user fields in both directions. Treating these records
as interchangeable preserved SOF at byte zero but lost EOFE on later bytes.
Packetizer CRC remains disabled; native PGP cell CRC is separate.

### TDEST Encoding

Frames on the ring carry source and destination in the TDEST field:
- `TDEST[2:0]`: Destination address
- `TDEST[6:4]`: Source address (set by TAG_SRC process on transmit)

On local delivery, the SWAP_TDEST process swaps nibbles so the application sees source in the lower bits.

## Virtual Channels

The ring carries 2 active virtual channels (VCs), each with its own RingRouter instance:

| VC | Name | Purpose |
|----|------|---------|
| 0 | SRP | Register read/write access (SrpV3AxiLite) |
| 1 | DATA | Streaming data (waveform capture, DAQ) |
| 2-3 | Unused | Tied off |

## Ethernet Bridge

The coordinator (node 0) bridges between the Ethernet uplink and the PGP ring. This is implemented across three modules: `EthCore`, `PgpEthCore`, and `PgpCore`.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PgpEthCore (Coordinator)                                   │
│                                                                                              │
│  ┌──────────────────────────────────────────────────┐    ┌────────────────────────────────┐  │
│  │                    EthCore                         │    │            PgpCore              │  │
│  │                                                   │    │                                │  │
│  │  ┌───────────┐     ┌──────────────────────────┐  │    │  ┌──────────────────────────┐  │  │
│  │  │ GigE MAC  │     │     RSSI (SRP)           │  │    │  │     ETH_STREAM_MUX       │  │  │
│  │  │ + UDP     │◄───►│  Port 8192               │  │    │  │     (per VC, i=0,1)      │  │  │
│  │  │           │     │  ┌─────────────────────┐ │  │    │  │                          │  │  │
│  │  │           │     │  │ TDEST 0x00: Local   │─┼──┼─SRP──►│ appLocalRx ──► PGP SRP   │  │  │
│  │  │           │     │  │   SrpV3AxiLite ─────┼─┼──┼─AXIL─►│              (local regs)│  │  │
│  │  │           │     │  │ TDEST 0x10: Loopback│ │  │    │  │                          │  │  │
│  │  │           │     │  │ TDEST 0x0-: Remote  │─┼──┼─┐  │  │                          │  │  │
│  │  │           │     │  │ TDEST 0x1-: Remote  │ │  │ │  │  │                          │  │  │
│  │  │           │     │  └─────────────────────┘ │  │ │  │  │                          │  │  │
│  │  │           │     └──────────────────────────┘  │ │  │  │                          │  │  │
│  │  │           │     ┌──────────────────────────┐  │ │  │  │                          │  │  │
│  │  │           │     │     RSSI (DATA)          │  │ │  │  │                          │  │  │
│  │  │           │◄───►│  Port 8193               │  │ │  │  │                          │  │  │
│  │  │           │     │  ┌─────────────────────┐ │  │ │  │  │                          │  │  │
│  │  │           │     │  │ TDEST 0x00: Local   │─┼──┼─DATA─►│ appLocalTx ◄── DataPath  │  │  │
│  │  │           │     │  │   Batcher + FIFO    │ │  │ │  │  │ appLocalRx ──► (unused)  │  │  │
│  │  │           │     │  │ TDEST 0x10: Loopback│ │  │ │  │  │                          │  │  │
│  │  │           │     │  │ TDEST 0x0-: Remote  │─┼──┼─┤  │  │                          │  │  │
│  │  │           │     │  │ TDEST 0x1-: Remote  │ │  │ │  │  │                          │  │  │
│  │  │           │     │  └─────────────────────┘ │  │ │  │  │                          │  │  │
│  │  │           │     └──────────────────────────┘  │ │  │  │                          │  │  │
│  │  └───────────┘                                   │ │  │  │                          │  │  │
│  │                      ┌───────────────────────┐   │ │  │  │                          │  │  │
│  │                      │   Remote CDC FIFOs    │   │ │  │  │                          │  │  │
│  │                      │   (ethClk ↔ axilClk)  │◄──┼─┘  │  │                          │  │  │
│  │                      │   4× RX + 4× TX       │───┼────────► ethTxAxisMasters        │  │  │
│  │                      │                       │◄──┼────────  ethRxAxisMasters        │  │  │
│  │                      └───────────────────────┘   │    │  │                          │  │  │
│  └──────────────────────────────────────────────────┘    │  │                          │  │  │
│                                                          │  │  ┌────────────────────┐  │  │  │
│                                                          │  │  │ DeMux (TDEST[7])   │  │  │  │
│                                                          │  │  │                    │  │  │  │
│                                                          │  │  │ bit7=0: Local ─────┼──┼──┼──── appLocal{Rx,Tx}
│                                                          │  │  │ bit7=1: Remote ────┼──┼──┼──── ethTx/RxAxisMasters
│                                                          │  │  │                    │  │  │
│                                                          │  │  └────────────────────┘  │  │
│                                                          │  │                          │  │  │
│                                                          │  │  ┌────────────────────┐  │  │  │
│                                                          │  │  │ RingRouter (×2 VC) │  │  │  │
│                                                          │  │  │                    │  │  │  │
│                                                          │  │  │ appRx/Tx ◄────────►│  │  │  │
│                                                          │  │  │                    │  │  │  │
│                                                          │  │  │ linkRx ◄── PgpRXVC │  │  │  │
│                                                          │  │  │ linkTx ──► PgpTXVC │  │  │  │
│                                                          │  │  └────────────────────┘  │  │  │
│                                                          │  │          │         │     │  │  │
│                                                          │  └──────────┼─────────┼─────┘  │  │
│                                                          │             │         │        │  │
│                                                          │           PGP TX    PGP RX     │  │
└──────────────────────────────────────────────────────────┘             │         │        │  │
                                                                         ▼         │        │  │
       ┌─────────┐                                                    To Ring   From Ring   │  │
       │ Host PC │◄── Ethernet (SFP, 1G or 10G) ──────────────────────────────────────────────┘
       └─────────┘
```

### Data Flow: Host to Remote Node (SRP Register Access)

The host connects to `EthCore` via 1G/10G Ethernet. Two RSSI connections are established on UDP ports 8192 (SRP) and 8193 (DATA). Each RSSI connection demultiplexes frames by TDEST into 4 streams:

| TDEST Range | Name | Destination |
|-------------|------|-------------|
| `0x00` | Local SRP/Data | Coordinator's own SrpV3AxiLite or local DataPath |
| `0x10` | Local Loopback | Wired back (diagnostic) |
| `0x0-` (bit 4=0, others vary) | Remote SRP/Data | Bridged to PGP ring via CDC FIFOs |
| `0x1-` (bit 4=1, others vary) | Remote Loopback | Bridged to PGP ring via CDC FIFOs |

For remote register access:
1. Host pyrogue sends an SRP frame on RSSI port 8192 with TDEST encoding the target node address
2. EthCore's RSSI depacketizes and routes by TDEST — the "Remote" streams exit EthCore via `remoteRxAxisMasters`
3. CDC FIFOs (`GEN_REMOTE_FIFOS`) cross from `ethClk` to `axilClk`
4. PgpEthCore connects these to PgpCore's `ethRxAxisMasters` ports
5. In PgpCore, the `ETH_STREAM_MUX` merges Ethernet-originated frames with locally-originated frames onto `appTxAxisMasters`
6. The RingRouter packetizes and sends them onto the PGP ring

### Data Flow: Local DAQ Streaming

For the coordinator's own DAQ data (EventBuilder output):
1. DataPath produces event frames on `dataTxAxisMaster`
2. PgpEthCore routes this directly to EthCore's `localDataTxAxisMaster` (since `RING_ADDR_0_G=true`)
3. EthCore buffers it in a FIFO, batches small frames via `AxiStreamBatcherAxil` (up to 8KB super-frames), then sends via the DATA RSSI connection to the host

### ETH_STREAM_MUX Detail

In PgpCore, the `ETH_STREAM_MUX` (one per VC) handles the boundary between local/Ethernet traffic and ring traffic:

```
                     From RingRouter (appRxAxisMaster)
                              │
                     ┌────────▼────────┐
                     │  AxiStreamDeMux │
                     │  TDEST[7] route │
                     ├─────────────────┤
                     │ bit7=0: Local   │──► appLocalRxAxisMaster (SRP decode or Data RX)
                     │ bit7=1: Eth     │──► ethTxAxisMaster (back to EthCore for host)
                     └─────────────────┘

                     ┌─────────────────┐
                     │  AxiStreamMux   │
                     │  (interleaved)  │
                     ├─────────────────┤
  appLocalTxMaster ──│► slot 0 (local) │
  ethRxAxisMaster  ──│► slot 1 (eth)   │──► appTxAxisMaster (into RingRouter for ring TX)
                     └─────────────────┘
```

TDEST bit 7 is the "remote" flag. When a frame arrives from the ring with bit 7 set, it means the frame originated from the Ethernet bridge on a different node (not currently used since only node 0 has Ethernet) or is destined for the Ethernet bridge. In practice, responses returning to the coordinator from remote SRP accesses arrive with bit 7=0 and are delivered locally to the EthCore's RSSI for return to the host.

### Clock Domains

The bridge crosses between two clock domains:
- **ethClk**: 125 MHz (1G) or 156.25 MHz (10G) — drives the MAC, UDP, and RSSI cores
- **axilClk**: 125 MHz — drives the AXI-Lite bus, PGP ring logic, and application

CDC FIFOs in EthCore (`GEN_REMOTE_FIFOS`, 4× RX + 4× TX, 32-deep distributed) handle the domain crossing for remote streams. The local SRP path uses `SrpV3AxiLite`'s built-in clock crossing.

## Flow Control

This implementation replaces the coordinator-only PHY pause policy. **Every
board in a ring must run compatible firmware.** Legacy peers transmit zero in
the protocol marker bit, so new boards keep local injection paused. This is a
firmware compatibility boundary, with unchanged host SRP/TDEST addressing.

`PgpRingFlowControl` runs in `pgpClk` and uses two separate paths, per VC:

- **Collection:** the coordinator advertises its local RX pressure in native
  PGP pause bits. Each other board advertises local pressure OR the incoming
  collection. The coordinator receives the aggregate but does not feed it back
  into collection.
- **Broadcast:** the coordinator puts the aggregate in `locData[4:3]`.
  Non-coordinators relay these bits unchanged. Local admission stops on local
  pressure, incoming collection, or broadcast. Using collection for early stop
  is part of the headroom bound, not merely an optimization.

The native whole-VC gate is disabled on **all** transmitters (`flowCntlDis=1`).
In a directed ring, received status belongs to the predecessor, not necessarily
the successor. Stopping transit on aggregate pressure could prevent receivers
from draining. The new gate sits before the shared TX FIFO; SRP and application
queues upstream can hold arbitrarily larger backlogs through normal ready.

| Link-data bits | Meaning |
|---|---|
| `[2:0]` | This board's discovered address |
| `[4:3]` | Global pause for VC1/VC0 |
| `5` | Broadcast valid |
| `6` | Collection path healthy |
| `7` | Compatible ring-control protocol present |

The coordinator seeds collection health with its own RX/TX link status.
Non-coordinators AND their link status with incoming protocol/collection health.
After a healthy collection returns continuously for at least 4096 `pgpClk` cycles, the
coordinator makes its broadcast valid. Non-coordinators relay validity only
while their collection path is healthy. Invalid control or link state holds
local injection paused. Qualification allows stale sideband values to wash out
on link recovery; it is longer than two circuits of the supported latency
budget. Three-stage synchronizers carry pause and link status into `axilClk`.

Collection never includes received broadcast. This prevents a latched OR loop:
when all FIFO pressure clears, collection and then broadcast clear even when
all application inputs are idle. PGP idle cells and link-training words continue
to carry status during application pause. VC0 and VC1 have independent pressure,
queues and admission gates.

## FIFO and latency budget

The production constants live in `PgpRingPkg.vhd`.

| Storage or limit | Setting |
|---|---|
| RX RAM per VC, every board | 1024 x 8 bytes, inferred block RAM |
| RX high / low watermarks | 8 / 4 eight-byte entries (64 / 32 bytes) |
| Local complete-packet FIFO | 32 x 8 bytes, inferred block RAM, before admission |
| Shared TX FIFO | 16 x 8 bytes, inferred block RAM, after admission |
| Router output slots | One eight-byte word each for local reassembly, transit and application delivery |
| Ring packet maximum | 128 bytes, including 16 bytes of header/tail |
| Native PGP cell payload maximum | 32 bytes (`PAYLOAD_CNT_TOP_G=3`) |
| Ring SRP RX/TX FIFOs | 1024 x 16 bytes each; before admission |

Smaller cells bound status update latency; smaller packets bound already-selected
local traffic. These choices trade throughput for headroom and should be changed
together with the following budget, not independently. RX output is streaming
(`VALID_THOLD_G=1`); packet completion metadata is not written into a separate
unthrottled FIFO.

The router registers payload and sidebands together on those three outputs.
Each slot holds its word through a stall and supports consume/refill on one
edge; ready remains combinational to reflect that edge's capacity. The 24 bytes
of output storage are included in the elasticity allowance below. Admission
inhibit also remains combinational so a newly observed pause can veto a new mux
grant without admitting another whole packet. An existing grant still completes.

For `N <= 8`, use `L=64` PGP clocks as the **per-hop control latency budget**,
including control registers, PHY/status transport and the admission CDC. A
1.25-Gbit/s 8b/10b link carries at most two payload bytes per 62.5-MHz PGP clock.
Early stop from collection (or broadcast after crossing the coordinator) reaches
sources at clockwise distances `0..N-1` from the first congested receiver. Thus
new bytes admitted while pressure travels are bounded by
`2 * L * N * (N-1) / 2`, rather than one link's worth of traffic.

Reserve, per board, 64 bytes of RX occupancy at the first pressure event,
128 bytes of shared TX RAM, 128 bytes of remaining selected local packet, and
128 bytes for elasticity outside those RAMs (gearboxes, FIFOs' output registers,
router/mux and PHY pipelines). Assigning all those bytes to one blocked receiver
is conservative. At eight boards the budget is:

```
8 * (64 + 128 + 128 + 128) + 2 * 64 * (8 * 7 / 2) = 7168 bytes
```

That leaves 1024 bytes below nominal RX RAM capacity. Queued local packets and
SRP responses before admission do not add to this bound. This is conditional
on the 64-clock hop and 128-byte elasticity budgets: **measure them with GTX in
GroupTb before claiming hardware acceptance**. Do not extrapolate to more
boards, larger TX queues, larger packets, slower status updates or a faster
line rate. Full-system mixed-VC throughput, synthesis fit and timing also remain
vendor/bench checks.

## Overflow and framing recovery

Loss prevention and recovery are separate. When the unthrottled PHY presents a
word that cannot be accepted, `PgpRingRxFifo` reports local overflow, retains
already accepted words, and discards new input while it queues:

1. An SSI error terminator to close any partial packet.
2. An ordered eight-byte abort marker, even if no further PHY traffic arrives.

The RAM always honors ready internally, so data and framing metadata cannot
advance independently on overflow. After the marker is queued, input resumes
only at a packet SOF. A link-ready falling edge also schedules this sequence.

The marker uses reserved packetizer version zero: value
`0x52494E47000000F0`, with origin address in bits `[18:16]` and the first/local
traversal flag in bit `8` (mask `0xFFFFFFFFFFF8FEFF`). It is an SSI frame with
SOF and EOF on its sole eight-byte word, carried on the affected VC. Each router
holds the marker while it clears depacketizer contexts and terminates open
application frames with EOFE. A bitmap tracks frames actually delivered to the
application, independently of the reassembly RAM's termination scan. Only after
those terminations are accepted does the marker advance. The first router clears
bit 8, and the origin removes the returning marker without aborting again.
Transit markers bypass local admission pause like other transit packets. A
marker waits for stable RX/TX link status before forwarding so the TX FIFO does
not discard it in link-down flush mode.

Before clearing reassembly, the router drains its local and transit output
slots so a marker cannot overtake previously accepted words. Error terminators
use the same registered application output as normal data and remain stable
while the application is stalled. A shared synchronous reset cancels all slots
and frame tracking.

This deliberately abandons all open reassemblies on that VC; it does not recover
lost bytes or promise successful completion of the affected SRP request. The
host may need to retry. Complete frames already delivered remain complete. Once
the sink drains, no subsequent application packet is required to release a
partial frame. Another overflow can generate another ordered marker.

Separately, a fresh SOF encountered before an old packet's tail causes an error
tail to be synthesized **without consuming the fresh header**. The header is
then processed normally. Error tails are normalized before reassembly because a
PHY terminator may occur on any two-byte boundary and its data is not a valid
packetizer tail.

## Isolated regression

Run locally without connecting to GroupTb or hardware:

```bash
.venv/bin/python -m pytest tests/warm_tdm/pgp_ring/test_ring_control.py -q -n 3
```

The cocotb scenarios in `ring_control_cocotb.py` drive thin VHDL fixtures in
`tests/warm_tdm/pgp_ring/tb/`. They exercise the production router, RX guard/FIFO,
TX FIFO and control; stimulus and scoreboards live in Python.
Traffic links transfer two bytes per PGP clock without physical overhead and
apply a configurable sideband delay; they do not model GTX, native cell CRC,
RSSI or SRP transactions. A separate bench exercises the actual PGP2b lane,
cell scheduler, CRC and status RTL at the decoded symbol interface with both
VCs active and then idle. Its 128 status transitions measured a largest digital
latency of 35 PGP clocks; GTX and the external control/CDC delay must fit in
the remaining 29 clocks of the 64-clock hop budget. This observed maximum is
not a vendor-PHY timing proof. Another check analyzes `PgpCore` against the
actual SURF entity interfaces without elaborating vendor blocks.

Tests check source/word ordering, SOF/EOF/EOFE, congestion at every sink
position in 2-, 3- and 8-board rings, idle resume, control compatibility,
missing-tail recovery and abort propagation/removal. A separate two-board
case offers 16 KiB to an 8 KiB blocked receiver. The old `test_rx_buffer.py` remains an expected-loss
characterization of the unguarded SURF path.

Forced-loss cases use one reply at width 8 and three replies at width 10, and
require overflow plus EOFE before fresh probes. With the guarded router's
pipeline storage, two replies fit at width 10 in this fixture and must arrive
without loss. Router checks also reset an admitted, stalled packet and verify
fresh framing after reset.

For runtime, the default test build reduces only unused AXI record capacity
from 128 to 16 bytes in a temporary copy of `AxiPkg`; all configured streams
remain 2 or 8 bytes and all FIFO sizes/pipelines remain unchanged. Set
`WARM_TDM_RING_FULL_RECORDS=1` to use the unchanged SURF package. No submodule
source is modified. Eight-board full-record runs are substantially slower.
