# Hardware ReadAll / register timeout investigation

## Goal and reported behavior

Latest bench report: one column coordinator and one row board, both AxiVersion
blocks accessible. ReadAll fails on the row, followed by loss of column SRP
access. RSSI and PGP links remain up without reported link errors. The first
failing address, exact error, both image identities, and reset/reconnect recovery
behavior are still needed. This supersedes the initial assumption that even the
coordinator's first register read fails.

The earlier comparison used working firmware/software `1045236eecac9719092883b78dee6e850c63698b`
(`ColumnFpgaBoard325Coord10G`) with the loaded image
`ColumnFpgaBoard325Int10G-0x00000000-20260918115303-bareese-d0bedaa.mcs.gz`.
Determine whether the bench failure is transport loss, an endpoint timeout, or
shared transport blockage, and find the smallest discriminating hardware test.

## Status

Source investigation at `da08863`, SURF `70191c1`; root cause remains unconfirmed
on hardware. Before the local diagnostic change below, PgpCore, RingRouter,
PgpEthCore and EthCore had no source diff from `d0bedaa` to this revision.
Current bench image identities are not yet confirmed.
The image revision exists locally as
`d0bedaae8b65e648d6cec101c39564f5bcbb2b9a`. Compare committed revisions explicitly.
No hardware access or build reports have been supplied. Local `firmware/build/`
contains simulation directories, not this target's synthesis/implementation.

The local diagnostic change restores both ring RX FIFOs (VC0 and VC1) on every
board to address width 10 (8 KiB each) and selects the inferred backend with
block RAM. Transmit FIFOs, the pause threshold and Ethernet bridge settings
are unchanged. Rebuild the boards with Vivado 2024.1, check resource fit and
repeat the failing ReadAll plus before/after overflow-counter checks. Revisit
the sizing if synthesis does not fit. Hardware acceptance remains outstanding.

## Current transport findings

The remote response path is row SRP TX -> PGP TX FIFO/packetizer -> coordinator
PGP RX FIFO -> RingRouter depacketizer/demux -> EthCore remote TX FIFO -> shared
SRP RSSI mux/packetizer/window -> host. Coordinator-local replies join at the
RSSI mux; remote replies do not execute through the coordinator's local SRP
AXI-Lite master.

The table describes the failing source configuration before the local change.

| Buffer | Baseline nominal payload storage | Consequence |
|---|---:|---|
| PgpCore RX FIFO, per VC | 256 x 8 bytes = 2 KiB | Reduced from 8 KiB by `857a104`; hardware cannot stop incoming writes |
| EthCore remote TX FIFO, per channel | 32 x 8 bytes = 256 bytes | CDC elasticity, not a full large-response buffer |
| Row PGP SRP TX FIFO | 1024 x 16 bytes = 16 KiB | Can accumulate substantially more response data upstream |
| Coordinator local SRP TX FIFO | 512 x 16 bytes = 8 KiB | Local reads have a separate backpressurable response buffer |

These are nominal RAM capacities, excluding pipeline words and packet overhead.
The receive FIFO uses the wider 8-byte application width, not the 2-byte PHY
width. The usual Rogue SRPv3 maximum memory transaction is 4096 bytes; a read
reply includes another 24 bytes of SRP header/footer plus ring framing. The
2 KiB + 256-byte path cannot absorb a whole such reply if RSSI stops draining.
Streaming is valid only with an adequate bound on the stall and in-flight data;
buffering one packet alone does not bound a burst of multiple packets/replies.

- **Flow control is forced off.** PgpCore initializes `locPgpTxIn` with
  `PGP2B_TX_IN_HALF_DUPLEX_C`, which sets `flowCntlDis=1`. Pgp2bAxi ORs that
  value into the PHY control, so clearing its software bit cannot enable pause.
  The pause propagation in PgpCore therefore does not stop transmitters.
  PgpRxVcFifo uses `SLAVE_READY_EN_G=ROGUE_SIM_EN_G`; hardware writes ignore
  ready. Do not enable ordinary point-to-point pause blindly in a directed ring:
  the received status belongs to the preceding receiver, not necessarily the
  next receiver served by this transmitter.
- **Remote replies already have priority.** EthCore assigns priority 2 to
  remote SRP replies versus 1 to local replies, with interleaving enabled.
  Local AXI work does not directly monopolize the remote path. Shared RSSI
  window exhaustion, host busy, retransmission, or downstream stalls still can.
- **Overflow is not repaired here.** PgpRxVcFifo wraps AxiStreamFifoV2 directly,
  without an SSI frame-drop/termination filter. Once full it can lose payload
  and packet boundaries. RingRouter discards the depacketizer debug output;
  the ring packetizer CRC is disabled. RSSI retransmission cannot restore bytes
  already lost before Ethernet packetization.
- **Link errors are not the decisive counter.** Check VC0
  `TxLocOverflow0Count` on each board (Pgp2bAxi offset `0x4c`, absolute
  `0xA000004C`). Despite its TX name this reports local receive-buffer overflow
  advertised by that board's transmitter. `RxRemOverflow0Count` at offset
  `0x34` reports the preceding board's advertised overflow. Also capture
  `TxLocPause`, `RxRemPause` and host RSSI `locBusyCnt`/`remBusyCnt`.
- **Ordinary GroupTb host access misses this path.** HardwareGroup simulation
  connects each board directly to its own TCP SRP port. EthCore also bypasses
  RSSI in simulation. Even a PGP FIFO test using `ROGUE_SIM_EN_G=true` can mask
  loss by respecting ready; a useful stress test must disable that handshake.

## Focused buffer experiment

A scratch GHDL 6.0.0 bench at `/private/tmp/warm-tdm-srp-buffer-probe/` connects
the actual SURF Packetizer2 (512-byte packets, CRC NONE), 8-to-2-byte gearbox,
PgpRxVcFifo (`ROGUE_SIM_EN_G=false`), Depacketizer2 and remote-sized AXIS FIFO.
Clocks are 62.5 MHz at the PHY stream, 125 MHz at the receiver application,
and 156.25 MHz at the sink. Traffic starts at 10 us; stalled cases hold sink
ready low until 50 us and drain until 60 us. Each response is a synthetic byte
stream with the stated SRP-equivalent length, not an executed AXI transaction.

| Scenario | Sent / received bytes | Completed frames | RX overflow cycles |
|---|---:|---:|---:|
| Current depths, no sink stall | 4120 / 4120 | 1 | 0 |
| Current depths, stalled 1 KiB + 24-byte reply | 1048 / 1048 | 1 | 0 |
| Current depths, stalled 4 KiB + 24-byte reply | 4120 / 2288 | 0 | 237 |
| RX depth restored to 10, stalled large reply | 4120 / 4120 | 1 | 0 |
| Only bridge depth increased to 10, stalled large reply | 4120 / 4120 | 1 | 0 |
| Current depths, four queued small replies, stalled | 4192 / 2256 | 2 | 252 |

Non-overflow cases assert byte and completed-frame counts. All runs complete;
the lossy cases retain truncated traffic, and depacketizer `packetError` stays
zero within this observation window. Thus that signal alone is insufficient
to diagnose overflow, particularly when no subsequent packet arrives.

This isolates a real capacity limitation, not the reported hardware failure or
column lockup. It substitutes inferred FIFOs for XPM, omits PGP wire overhead,
router demux/pipeline stages and the complete RSSI/host, and injects a downstream
stall rather than demonstrating how one arises. The queued-response case also
does not model the current row driver's per-block waiting. Vendor simulation,
the actual failing read size and bench counter evidence remain necessary.

## Discriminating checks for this bench

1. Capture the *first* failing path/address/length and exact exception. Distinguish
   a host timeout/errored or truncated frame from an SRP timeout footer (`0x2100`
   when timeout/bus-lock are the only flags). Record both firmware Git hashes and
   the actual Rogue version. Read AxiVersion explicitly with `read=True`.
2. With startup bulk reads and polling off, test the row alone, column alone,
   then the whole tree with one outstanding block at a time. Use
   `root.readBlocks(recurse=True, checkEach=True)` on the older Rogue API
   (`waitEach=True` on newer versions). RowFpgaBoard already sets
   `forceCheckEach=True`, which propagates into children; column reads submitted
   earlier by a whole-tree ReadAll can nevertheless still be outstanding.
3. Separate read size from concurrency. Compare individual reads with a known
   valid RAM block read, staying inside the deployed row capacity. The current
   RowMap is only 512 bytes at 128 rows, or 1024 bytes at 256 rows. A single such
   reply fits the nominal RX buffers; a reproducible isolated failure is not
   explained just by the 4 KiB worst-case calculation. Check RowDacDriver's
   timing-clock AXI bridge if its small control registers fail consistently.
4. Compare VC0 overflow counters before/after, and capture SRP traffic at the
   host. If column requests still reach destination 0 but no replies return,
   inspect the common RSSI path and local bridge separately. A row's sticky
   SRP timeout cannot directly set the independent column bridge's timeout bit.
   Shared request-stream head-of-line blocking remains possible if a remote
   sink stops accepting and its buffers fill; it is not yet demonstrated here.
5. Build and test the local ring RX depth restoration from 8 to 10 with inferred
   RAM on both VCs and all boards. This changes capacity and backend together,
   so recovery alone will not distinguish their effects. Enlarging EthCore's
   remote SRP return FIFO remains a separate possible experiment. Deeper FIFOs alone do not
   guarantee stability for unbounded bursts or host stalls. A durable solution
   needs bounded outstanding response bytes or ring-appropriate flow control,
   plus observable overflow and defined frame recovery.

The existing XPM/`"bram"` spelling still needs a Vivado build-log check, but
successful reads of both boards weaken the original global-payload-failure
hypothesis. The current change leaves those Ethernet/RSSI settings in place.

## Earlier image-comparison findings

- Both target configurations enable `RING_ADDR_0_G=true` and `ETH_10G_G=true`.
  The new target explicitly selects the integer PID path. Its default RSSI
  window is still 3 and segment size still 1024 bytes.
- Host SRP remains UDP 8192, packetizer v2, SRPv3, application destination
  equal to board index. EthCore's local SRP route and bridge are unchanged.
- Commit `857a104` changed both RSSI cores from the default inferred backend
  to `SYNTH_MODE_G => "xpm"`. This selects different RSSI payload RAM and output
  FIFO implementations. Handshake success alone does not validate payloads.
- That commit also changed local data and remote-ring bridge FIFOs to XPM,
  using `MEMORY_TYPE_G => "bram"`. The SURF FIFO wrapper documents `block`,
  `distributed`, `auto`, and `ultra`, and passes the string directly to XPM.
  Investigate separately from the coordinator's direct SRP path.
- SURF changed from `4acecf9` to `70191c1`. Its AXI, RAM/FIFO, RSSI, SRP,
  Ethernet MAC, IP/UDP, and 10G core sources have no diff between those pins.
- The core/common rename preserves the maintained AXI address map. Ethernet
  gating still includes the coordinator. Ethernet XDC was split and hierarchy
  paths updated; actual synthesized constraints/timing remain unverified.
- Target `vivado/project_setup.tcl` now enables both `POWER_OPT_DESIGN` and
  `POST_PLACE_POWER_OPT_DESIGN`; both were commented out for the working target.
- The new target inherits `ROW_ADDR_BITS_G=7` (128 rows), versus 8 (256 rows)
  in the working image. Host defaults remain `--rowAddrBits 8 --maxRows 256`.
  Use `--rowAddrBits 7 --maxRows 128` (or fewer mapped rows) with this image.
  This mismatch does not change the coordinator AxiVersion address.
- EthCore simulation replaces the physical Ethernet/RSSI stack with a TCP
  bridge. Passing ordinary group co-simulation does not exercise the RSSI
  backend change.

## Endpoint timeout and persistent failure

SURF `protocols/srp/rtl/SrpV3AxiLite.vhd` deliberately retains `r.timeout`
across requests (line 343). With its request timeout enabled, an AXI transaction
that never completes sets this flag (read path line 671). Subsequent requests
skip AXI execution and return a timeout footer (lines 513 and 580/585), until
the bridge's `axilRst` resets its state. An RSSI reconnect does not reset this
AXI-domain state in EthCore.

This means "all registers now fail" does not prove that the very first access
failed: a startup read to one nonresponding endpoint can spoil later access
through the same SRP bridge. When the transport works, the expected symptom is
an SRP error response with timeout bits 8 and 13 (`0x2100` if no other flags),
not necessarily a host timeout from receiving no response. With a zero timeout
field in the request, the bridge can remain waiting instead of latching that
error. The exact first error message or packet trace distinguishes these.

DataPath's bus crosses into `timingRxClk125` through `AxiLiteAsync`; however,
this SURF bridge has a local error responder while its remote reset is asserted.
Do not equate any timing-reset condition with a bus hang: a stopped clock with
reset not properly reported, or a nonresponding endpoint, is a different case.
No particular new endpoint has been proven to cause such a hang.

## Effective clock-constraint comparison

The proposed 312.5-to-250 MHz source regression was ruled out: the old target
loaded `WarmTdmCore2.xdc`, renamed to `WarmTdmCore.xdc` in the new target. Both
selected files constrain `gtRefClk0` to 4.000 ns and `gtRefClk1` to 6.400 ns;
the old unused legacy file caused the misleading filename-only comparison.
Both maintained cores use `CLK_0_DIV2_G=true`, MMCM input period 8 ns, input
divider 1, multiplier 8, and output divider 8. Successful AxiVersion reads now
also argue against a persistent absence of the AXI clock/reset release. Actual
implementation reports remain necessary for timing/constraint acceptance.

## Validation and handoff

- Compared exact committed sources at `1045236` and `d0bedaa`; followed the
  `WarmTdmCore2`/`WarmTdmCommon2` rename in RTL and Python to avoid comparing
  against the removed legacy implementations.
- Verified no source changes between the pinned SURF revisions in `axi`,
  `base`, RSSI, SRP, PGP, Ethernet MAC, IPv4, UDP, and 10G core directories.
- Verified local EthCore, PgpEthCore, and the new target's ruckus configuration
  are byte-identical to the loaded image's named commit.
- Vivado is unavailable locally; candidate implementation reports and the
  actual image's build-state provenance are unavailable. The filename identifies
  a commit but cannot prove the build checkout/submodules were clean.
- No vendor-XPM simulation or hardware read was run. Source inspection cannot
  establish hardware recovery. Current host revision and a concrete timeout
  path/address remain requested information.
- The focused inferred-FIFO experiment above reproduces truncation with the
  current capacities and avoids it when either receive-side buffer is enlarged.
  It does not establish a permanent firmware fix or reproduce cross-board lockup.

The ring RX depth/backend change and this existing handoff are local
changes; the diagnostic bench and logs are scratch artifacts. No staging,
commits, hardware writes, or external issue updates have been made.
