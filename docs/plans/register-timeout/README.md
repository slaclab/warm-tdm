# Hardware ReadAll / register timeout investigation

## Hardware agent handoff

The [September 24 RSSI/SRP handoff](hardware-handoff/README.md) contains the
normal-server startup instructions, virtual-client probes, packet decoder and report template for
the current bench investigation. It covers the keepalive-patched image,
missing first responses and batched versus sequential reads. Sync that directory
and the server software changes with the checkout; keep collected logs and captures outside Git as instructed.
The earlier investigation and implementation evidence remain below.

The next firmware candidate is prepared on SURF branch
`fix/rssi-rx-keepalive-integration`, based on `8d256ca84` and incorporating
[SURF PR #1456](https://github.com/slaclab/surf/pull/1456) at `5641e673f`.
Its [integration handoff](../../../firmware/submodules/surf/docs/plans/rssi-rx-keepalive/README.md)
records the source boundary, passing focused simulations and original-RX
comparison failures. The SURF submodule pins the combined candidate; update
submodules after pulling this checkout. Build and hardware acceptance remain
pending; compare against the tested `0b73019` image with the keepalive fix
retained in both candidates.

## Goal and reported behavior

Bench topology: one column coordinator and one row board, both AxiVersion
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

The pause/recovery implementation is described [below](#ring-pause-and-overflow-recovery-implementation); the historical characterization that follows records the pre-fix behavior. Vendor and hardware acceptance remain outstanding.

Source investigation began at `da08863`, SURF `70191c1`; root cause remains unconfirmed
on hardware. The latest user report supplies strong evidence of a width-8
cosim reproduction and a successful width-10 hardware run. The remaining
question is whether width 10 prevents overflow for all supported read workloads
and whether a lost response causes persistent firmware blockage. Before the buffering change below, PgpCore, RingRouter,
PgpEthCore and EthCore had no source diff from `d0bedaa` to this revision.
Current bench image identities are not yet confirmed.
The image revision exists locally as
`d0bedaae8b65e648d6cec101c39564f5bcbb2b9a`. Compare committed revisions explicitly.
Hardware results are user-reported; image identities, counters and build reports
have not been supplied. Local `firmware/build/`
contains simulation directories, not this target's synthesis/implementation.

Commit `40c131c` restores both ring RX FIFOs (VC0 and VC1) on every
board to address width 10 (8 KiB each) and selects the inferred backend with
block RAM. It also restores coordinator flow control (`flowCntlDis=0` on the
coordinator, 1 on other boards). Transmit FIFOs, the pause threshold and Ethernet
bridge settings are unchanged. Rebuild the boards with Vivado 2024.1, check resource fit and
repeat the failing ReadAll plus before/after overflow-counter checks. The user
reports the width-10 hardware run succeeds. Worst-case buffering and recovery
acceptance remain outstanding.

## Width-10 bound investigation

**Width 10 does not establish a lossless bound for queued responses.** Pause
is asserted at 192 eight-byte entries (1536 bytes), leaving nominal RX RAM
headroom of 512 bytes at width 8 or 6656 bytes at width 10. Only the coordinator
obeys PGP pause. Other boards OR received pause with their own and forward it
around the ring, but continue transmitting. Stopping new coordinator requests
therefore does not stop responses to requests that remote SRP endpoints have
already accepted. The row SRP receive and transmit FIFOs each have 16 KiB of
nominal storage; a short read request can expand into a much larger reply.
VC1 also has locally generated data that is not bounded by host read requests.

Two software details make this relevant to changing global read parameters:

- `RowFpgaBoard.forceCheckEach=True` waits between **blocks**. In Rogue 6.15,
  `memory::Hub::doTransaction` splits a larger block into 4096-byte transactions
  and forwards all pieces before waiting for completion. An isolated fake-memory
  test with the installed Rogue 6.15 on rdsrv419 submitted addresses 0, 4096 and
  8192, each of length 4096, before completing any part of one 12 KiB read. It
  opened no sockets and did not use the active cosim. Multiple boards/clients
  can also contribute outstanding work. The current small row memory blocks
  are not evidence that this larger-block case caused the reported failure.
- 4096 bytes is the standard Rogue SRPv3 transaction limit, not an RTL read-size
  limit. `SrpV3AxiLite` checks that limit for writes; reads use the requested
  length. Increasing client limits would need an explicit response-size bound.

The maintained [RX buffer characterization](../../../tests/warm_tdm/pgp_ring/test_rx_buffer.py)
uses actual SURF packetizer, gearbox, RX FIFO, depacketizer and a 256-byte bridge
FIFO. It holds the sink until queued responses have arrived, releases it, then
sends three distinct 32-byte probes. It models already accepted responses,
not the complete request admission/pause loop. It omits GTX overhead, router
arbitration and RSSI; bridge RAM is inferred. Run it independently of GroupTb:

```bash
.venv/bin/python -m pytest tests/warm_tdm/pgp_ring/test_rx_buffer.py -q -n 3
```

A 4 KiB read-sized reply is 4120 bytes including SRP metadata. With 496 bytes
of payload per full 512-byte ring packet, nine packets occupy 4264 RX bytes.
Two such replies require 8528 bytes before downstream draining. Pipeline words
affect the precise threshold; the test measures loss instead of assuming only
the nominal RAM capacities. This is a finite queued-response counterexample,
not a claim that ordinary row ReadAll always generates that backlog.

All six characterization cases passed against SURF `70191c1` with GHDL; a pass
includes the deliberately expected loss cases below. Counts are taken after
releasing the sink and before sending the fresh probes. Overflow cycles are
not PGP's edge-counted overflow register value.

| RX width / mode | Sent bytes | Received bytes | Completed frames | Overflow cycles |
|---|---:|---:|---:|---:|
| 8, one reply, stalled | 4120 | 2288 | 0 / 1 | 237 |
| 10, one reply, stalled | 4120 | 4120 | 1 / 1 | 0 |
| 10, two replies, stalled | 8240 | 8224 | 1 / 2 | 2 |
| 10, three replies, stalled | 12360 | 8224 | 1 / 3 | 535 |
| 10, three replies, stalled, former sim ready enabled | 12360 | 8088 | 1 / 3 | 0 |
| 10, three replies, no stall | 12360 | 12360 | 3 / 3 | 0 |

**Pre-fix overflow recovery behavior.** In each lossy case the first fresh probe
was absorbed into the unfinished prior frame. At width 10 its intended
32-byte frame instead terminated a 4152-byte frame, with EOFE clear. The next
two probes passed length, payload and SOF/EOF checks. Depacketizer `packetError`
remained zero throughout. In `MOVE_S`, the depacketizer consumes input until
`tLast`; it does not use a new SOF to abort a packet whose tail was lost. With
CRC disabled, the new packet's valid tail can close the merged frame without
an error indication. This demonstrates damaged framing followed by recovery,
not a permanent full-ring deadlock. The SRP/host consequences still need the
full-system test. Raw run logs are saved in pytest's temporary build directories;
the source bench and assertions retain the reproducible evidence.

### Cosim fidelity and reproduction limits

The committed cosim-fidelity correction enables the FIFO ready handshake only for a Rogue
stream model (`SIMULATION_G and SIM_PORT_NUM_G /= 0`). Real GTX mode now ignores
ready in simulation just as in hardware. Previously `SIMULATION_G=true` made
the FIFO gate its writes when full even though GTX cannot honor `pgpRxSlaves`.
This can lose data before the RAM without asserting its overflow output.
Hardware depth, memory implementation and pause policy are unchanged by this
simulation correction. It has not been rebuilt in VCS; the user's active
rdsrv419 simulator and build were left untouched.

The reproduction script in remote commit `771ee04` runs `row.ReadDevice(True)`
through a VirtualClient and starts the column probe after a watchdog expires.
The watchdog leaves the row RPC alive. Rogue's ZMQ client serializes requests
under `reqLock_`, and the server executes its request callback synchronously.
Consequently, a column watchdog failure can mean the column request has not
reached SRP at all. This does not invalidate the reported width A/B behavior,
but the script alone cannot distinguish FPGA-wide deadlock from one failed
row transaction holding up software. `RemoteVariable.get()` already defaults
to `read=True` in the installed version; cached reads are not the issue here.
The script's 120-second watchdog covers the entire subtree sweep, whereas the
simulation root's extended timeout covers individual transactions. Record
per-block progress before treating a long whole-tree sweep as stalled.

### Required bound and next discriminating test

With remote response transmission unthrottled, a lossless admission policy must
reserve receive capacity for **all outstanding response bytes**, including ring
overhead and in-flight pipeline data, and release that reservation only as
downstream delivery frees capacity. Alternatively, backpressure at every source's
ring injection point can leave queued response bytes at their source; then the
required receive headroom covers control latency and traffic already admitted
to the ring. Increasing RAM alone needs a supported maximum backlog/stall bound.
For SRP, one globally outstanding, size-limited wire transaction across the
ring is a useful containment experiment; per-device block waiting is weaker.
A production policy could use host admission limits or firmware response
credits/size enforcement. VC1 needs separate treatment. Enabling pause on every
ring transmitter is not a safe substitute: stopping forwarding can prevent a
full intermediate receiver from draining.

After the current user run finishes, capture the first failing transaction and
RX overflow/pause on both boards, with the corrected GTX receive semantics.
Separate response size, number outstanding, board count and sink-stall duration.
Record flow-control/backend settings as well as depth, since `40c131c` changed
all three. Check column SRP from inside the server outside the blocked RPC, or
use passive RTL request/response observations; do not infer its state from a
second RPC waiting behind the first. Finally, after deliberately overflowing
and releasing the sink, verify fresh row and column transactions complete
without reset. Capacity prevention and defined termination/recovery of damaged
frames are separate requirements.

### Ring pause and overflow recovery implementation

The collection/broadcast and packet admission design is now implemented in
`PgpRingFlowControl`, `RingRouter` and `PgpRingRxFifo`, with integration and shared
limits in `PgpCore` / `PgpRingPkg`. See the permanent
[ring protocol and headroom budget](../../../firmware/common/warm_tdm/doc/PGP_RING.md#flow-control).
All boards require the new status semantics; host SRP addressing is unchanged.

Local admission pauses at complete ring packets while raw transit packets keep
forwarding. RX RAM stays inferred, width 10. Production packets are 128 bytes;
the post-admission TX FIFO is 128 bytes, RX pressure uses 64/32-byte watermarks,
and native cells have at most 32 payload bytes. Early collection stop limits
source admission before broadcast reaches every board. The eight-board budget
is 7168 bytes, conditional on a 64-PGP-clock control hop and the documented
pipeline allowance. Vendor GTX timing must validate those assumptions.

Overflow now queues an error terminator and an ordered per-VC abort marker.
Each router clears reassembly and terminates every application frame it has
started; the origin removes the returning marker. No subsequent application
traffic is required. Fresh SOF also closes a packet with a missing tail without
consuming the new header. Explicit two/eight-bit TUSER conversion repairs error
flags previously lost at the SURF depacketizer boundary. Lost bytes still require
host retry; this is not retransmission.

The isolated regression is `tests/warm_tdm/pgp_ring/test_ring_control.py`. It uses
actual production RTL with delayed logical links, separate clocks and payload/
framing scoreboards. The original expected-loss characterization remains intact
as evidence for the unguarded SURF path. A separate native PGP lane bench
measured a largest digital status delay of 35 clocks across 128 transitions,
with both VCs active and idle; 29 clocks remain for GTX and external control/CDC
in the conditional hop budget. PgpCore also passes entity-interface analysis.
These tests do not run SRP, RSSI or GTX.

Implementation validation: all 24 maintained local checks passed (22 routing,
control, congestion and recovery cases, plus native-PGP status timing and
PgpCore interface analysis). Congestion covered every sink position in 2-, 3-
and 8-board rings; the queued-response case offered 16 KiB to an 8 KiB stalled
receiver without loss. Router recovery, native PGP status and interface analysis
also passed with unchanged full-width SURF records. The full congestion sweep
used the documented temporary reduction of unused record capacity; it did not
reduce any configured stream/FIFO width or latency. SURF itself is unchanged.

Remaining acceptance after the user's current run finishes:

- Rebuild GroupTb with the corrected unthrottled receive semantics and new ring
  protocol; measure control delay and post-gate storage, including mixed VCs.
- Repeat queued large reads and sink stalls, capture first failure/overflow
  counters, then verify fresh row and column SRP transactions without reset.
- Force overflow and link interruption; verify EOFE, marker completion and
  first-fresh-transaction recovery through real SRP/RSSI, outside a blocked RPC.
- Build affected targets with Vivado 2024.1; check resource fit, timing and the
  throughput impact of shorter packets/cells. Repeat the failing hardware sweep.

The active rdsrv419 simulation/build is untouched. No source was staged or
committed by the implementation task.

## GTX cosim startup: verified at `fc8f751`

The reported 1.272 us freeze was not reproduced. On `rdsrv419`, the existing
GroupTb binary advanced through 2, 10, 20, 100 and 300 us without rebuilding or
changing RTL, serial wiring, delay, model version, warnings or time resolution.
The ICAP initialization warning at 1.272 us was the last unsolicited timestamp,
not the simulator's stopping time. Both PGP links were ready at 100 us. At
300 us both CPLLs were locked, both refclk-lost signals were clear, TX/RX resets
were deasserted, and both primitive and reset-FSM done signals were asserted.

A minimal Rogue 6.15.0 client, with startup reads/writes and polling disabled
and a 45-second timeout, read three registers on each board through coordinator
sockets 10000 and 10002:

| Register | Column | Row |
|---|---:|---:|
| AxiVersion FpgaVersion (`0x0`) | `0x1` | `0x1` |
| PGP status (`0xA0000020`) | `0x1f` | `0x1f` |
| Peer link data (`0xA0000024`) | `0x1` | `0x0` |

Column reads took 0.17–0.18 seconds each; row reads took 1.26–1.28 seconds.
Short host timeouts can therefore fail even with advancing simulation time,
although that has not been established as the cause of the earlier client
failure. The full Warm-TDM simulation roots already select a 1000-second
timeout. This test establishes GTX startup and isolated SRP access, not ReadAll
stability, buffering under stalls, or real Ethernet/RSSI behavior.

Remote artifacts are in `/tmp/warm-tdm-gtx-startup-codex/` on `rdsrv419`:
`baseline.log`, `progress.log`, `interactive.log`, `read_srp.py` and
`read_srp.log`. `progress.log` is a deliberately wall-time-limited run stopped
after its 20 us checkpoint; `interactive.log` contains the completed 300 us
run and status captures. Local copies of the SRP results and status tail are in
`/private/tmp/warm-tdm-gtx-startup-check/remote-{read-srp,gtx-status}.log`.
The diagnostic simulator was quit after the checks.

Historical references confirm real GTX ring simulation existed: `e2a3314`
(2021-11-02) sets all six StackTb boards' PGP ports to zero; `a966972`
(2023-05-30, "Use real PGP GT in sim") forces the GTX implementation on.
That source uses zero-delay serial wiring, `SIM_VERSION_G="4.0"`, and the same
free-running user-clock arrangement. The earlier claim that StackTb never
exercised GTX is incorrect. In current PgpCore both recovered-clock outputs are
open, so the proposed recovered-RX-clock feedback into fabric does not exist.

Next: reproduce the hardware's actual failing read sequence and capture overflow
counters. Use the [GroupTb progress checks](../../../firmware/simulations/GroupTb/README_cosim.md#checking-simulation-progress-and-gtx-startup)
to distinguish a quiet simulation from a stall.

## Current transport findings

The remote response path is row SRP TX -> PGP TX FIFO/packetizer -> coordinator
PGP RX FIFO -> RingRouter depacketizer/demux -> EthCore remote TX FIFO -> shared
SRP RSSI mux/packetizer/window -> host. Coordinator-local replies join at the
RSSI mux; remote replies do not execute through the coordinator's local SRP
AXI-Lite master.

The table describes the failing source configuration before `40c131c`.

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

- **Flow control was forced off in the failing baseline.** PgpCore initializes `locPgpTxIn` with
  `PGP2B_TX_IN_HALF_DUPLEX_C`, which sets `flowCntlDis=1`. Pgp2bAxi ORs that
  value into the PHY control, so clearing its software bit cannot enable pause.
  Commit `40c131c` overrides this field to zero for the coordinator; other boards
  still force it high. Its pause propagation therefore needs validation with
  the restored coordinator control, rather than assuming all transmitters ignore it.
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
- **GroupTb bypass mode misses this path.** The new GTX ring mode with
  `--simPgpRing` reaches the row through the coordinator and real PGP models.
  EthCore still bypasses RSSI in simulation. The local correction described
  above disables the FIFO ready handshake in real GTX mode; earlier builds
  passed `ROGUE_SIM_EN_G=SIMULATION_G` and can mask overflow indications.

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
5. Build and test `40c131c` with ring RX depth restored from 8 to 10 and inferred
   RAM on both VCs and all boards. This changes capacity, backend and coordinator
   flow control together, so recovery alone will not distinguish their effects. Enlarging EthCore's
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
