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
4. Columns 1, 2, 3 each receive, depacketize, check TDEST[2:0]≠their address → passthrough → re-packetize → TX
5. Row Board receives it, depacketizes, checks TDEST[2:0]=4 → local delivery → SRP processes register read
6. Row Board sends SRP response with TDEST[2:0]=0 (original source becomes destination after swap)
7. Response traverses: Row Board TX → Column 0 RX → local delivery → EthCore → Host

**Key properties:**
- The coordinator (node 0) is the sole gateway between the host and the ring
- Any node's registers are accessible from the host via ring-routed SRP through the coordinator
- Only the coordinator's PGP transmitter obeys received pause; other transmitters do not throttle their locally originated traffic
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

Address is broadcast via `locPgpTxIn.locData <= "00000" & address`.

## Frame Routing (RingRouter)

Each node has a `RingRouter` instance per virtual channel (2 VCs active: VC0=SRP, VC1=Data).

### Receive Path

```
PGP RX → PgpRXVcFifo (CDC + buffering) → Depacketizer → DeMux → {Local, Passthrough, Dump}
```

1. **Depacketizer** (`AxiStreamDepacketizer2`): Reassembles packetized PGP frames back into full AXI-Stream transactions, restoring TDEST routing info.

2. **DeMux** (dynamic mode, 3 outputs):
   - **Local** (output 0): Frame's TDEST[2:0] matches this node's address → delivered to application
   - **Dump** (output 1): Frame's TDEST[6:4] matches this node's address → frame has looped the ring without finding its destination; silently discarded
   - **Passthrough** (output 2): All other frames → forwarded to TX for the next node

### Transmit Path

```
{Passthrough, Local App TX} → Mux → Packetizer → PgpTXVcFifo → PGP TX
```

1. **Mux** (interleaved, priority-based):
   - **Passthrough has priority** (`disableSel(0) => passthroughMaster.tValid`): When passthrough data is valid, local TX is held off. This prevents ring congestion since passthrough cannot backpressure.
   - Local application TX gets the link when no passthrough data is flowing.
   - Interleaving every 31 cycles (`ILEAVE_REARB_G => 31`).

2. **Packetizer** (`AxiStreamPacketizer2`): Segments frames into 512-byte packets for PGP transport. Uses distributed RAM, no CRC.

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

**Current implementation is asymmetric and does not provide complete ring backpressure.**

- **Node 0 (Coordinator):** `flowCntlDis='0'` makes its transmitter obey received pause, stopping transmission on the affected VC.
- **Other nodes:** `flowCntlDis='1'` makes their transmitters ignore received pause. Their receivers still generate and advertise pause/overflow status.

In a ring of three or more boards, the preceding board whose status is received
is different from the following board that receives this transmitter's data.
Ordinary point-to-point PGP flow control therefore does not directly provide
next-hop backpressure. In a two-board ring, both directions connect the same
peer, so that topology can use ordinary PGP pause with local status advertisement
and flow control enabled on both boards.

Non-coordinator nodes merge local and remote pause signals:
```vhdl
tmp(i).pause := locPgpRxCtrl(i).pause or pgpRxOut(0).remPause(i);
```

The coordinator advertises only its own local pause, breaking the OR feedback
loop. This collects congestion around the ring and stops coordinator transmission.
It does **not** stop local injection at other boards: `RingRouter` disables its
local mux input only when passthrough is valid, with no pause input. An earlier
version of this guide incorrectly claimed local injection was already paused.

Consequently, responses to previously accepted SRP reads can continue arriving
at a stalled coordinator. Passthrough priority reduces contention but does not
guarantee freedom from overflow. Applying the relayed OR at every PHY transmitter
can also stop the forwarding needed to drain intermediate receivers. Simply
extending the OR loop through the coordinator would let an asserted pause
circulate indefinitely after the original congestion clears.

See the [active investigation and proposed admission control](../../../../docs/plans/register-timeout/README.md#proposed-ring-pause-control)
for a collection/broadcast scheme that would throttle local injection while
keeping forwarding and sideband status running. That scheme is not implemented.

## FIFO Sizing

| FIFO | Depth | Memory | Purpose |
|------|-------|--------|---------|
| PgpRXVcFifo | 1024 x 8 bytes (nominal 8 KiB) | Inferred block RAM | CDC from pgpClk→axilClk, packet buffering |
| PgpTXVcFifo | 256 x 8 bytes (nominal 2 KiB) | XPM block RAM | CDC from axilClk→pgpClk, packet buffering |
| Depacketizer | Internal | BRAM | Per-destination framing state, not full-response storage |
| Packetizer | Internal | Distributed | Per-destination framing state |
| Ring SRP (SrpV3AxiLite) | 1024 x 16 bytes per RX/TX FIFO | Inferred block RAM | AXI-Lite transaction buffering |

Commit `40c131c` restored both active RX VCs on every board to address width 10.
A normal Rogue read can return 4096 data bytes plus SRP and ring metadata, and
a larger memory block can issue several such transactions before waiting.
The pause threshold remains 192 eight-byte entries. Width 10 supplies additional
headroom; it does not establish a bound on unthrottled queued responses.

## Packet Size

Ring packets are at most 512 bytes (`PACKET_SIZE_BYTES_C = 512`). The RX FIFO's
`VALID_THOLD_G=64` with burst mode permits output when a packet is complete or
64 entries are available. This is a prefill/burst policy, not an overflow filter
or an atomic whole-SRP-response guarantee.
