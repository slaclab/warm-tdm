# RSSI/SRP backpressure and reconnect recovery

## Current scope

The packetizer recovery defect is fixed and passed the focused hardware test.
The remaining investigation is burst-induced host backpressure and RSSI resets,
including how Rogue's reproduced wait cycle interacts with FPGA flow control.
Keep those outcomes separate.

| Work | Evidence / boundary | Next step |
| --- | --- | --- |
| Packetizer recovery | SURF `2b58e8251`; corrected image `743614f7` / SURF `49c1168c6` passes first-read probes 3/3 after reset, versus 5/5 failures before | Review [SURF PR #1492](https://github.com/slaclab/surf/pull/1492); broader coverage is not implied |
| Rogue wait cycle | Reproduced without injected delays with real PyRogue reads and finite peer buffering; predates `b1a669c965` | Evaluate a concurrency correction and match the bench workload |
| FPGA RSSI BUSY | Simulation shows RX delivery/ACK can stop before BUSY asserts | Correlate with hardware retry exhaustion and evaluate a separate correction |
| PGP ring acceptance | Separate admission/overflow-recovery implementation and conditional capacity budget | Complete the vendor/full-system checks below |

## Reproduce and interpret the bench failure

Use the [hardware procedure and scripts](hardware-handoff/README.md). Run the
normal `software/scripts/warmTdmServer.py`, one hardware owner, with VirtualClient
probes and packet capture. Keep startup reads/polling off for first-request
checks. Record loaded hashes after that first read; avoid identity helpers that
consume it. Serialize column reads for ordinary operation while investigating;
parent `forceWaitEach` does not necessarily cover direct child-device calls.

The fixed-register, fixed-order comparison on pre-fix `96a974f` / SURF
`7504a23b3` gave L439 clean 5/5 and L463 reset 5/5. Failing trials issued 384
requests, completed 351, and orphaned the same 33 IDs (352–384). This is a
boundary between configured workloads, not a measured 439/463 simultaneous
outstanding limit. Match SRP requests/replies within each connection epoch;
count repeated RSSI segments separately from unique transactions.

The host advertises BUSY and freezes its reply ACK while still sending requests,
then initiates RST; the FPGA echoes it. On the corrected image, L463 still resets
3/3 but the next connection's first read passes 3/3. L439 controls remain clean
3/3. Earlier idle observation had zero down/drop/retransmit growth over 60 seconds
and no RST during about 105 seconds of capture. These are distinct checks.

Record both ACK directions, BUSY intervals, reset initiator/scope, outstanding
IDs and client return time. A transport ACK is not an SRP completion; a watchdog
ending a process is not recovery. The L439/L463 sweep helpers and exact register
lists are in the bench run directory, not in the portable probe bundle.

## Rogue: reproduced mechanism and remaining gap

The receive path is:

```text
RSSI application queue (BUSY threshold 2; unbounded capacity)
  → RssiApp → PacketizerV2 reassembly
  → Packetizer application queue (capacity 8 completed frames)
  → PackApp → SRP response lookup/completion
```

Request submission holds its transaction mutex across `sendFrame()`. Response
lookup holds the pending-map mutex while refreshing other transactions' timers,
which takes each transaction's mutex. Finite peer buffering can therefore close
this wait cycle without injected sleeps:

```text
Host transmit queue full while submitter holds transaction mutex
  → response timer refresh waits on that mutex
  → Packetizer receive queue fills; RssiApp stops draining
  → host BUSY / reply ACK progress stops
  → peer reply and request paths cannot drain
  → host transmit queue remains full
```

The local follow-up used 1024-byte segments/eight-segment windows, native and
real PyRogue workloads: 402 cases, 360 completed and 42 watchdog stalls. Stalls
occurred with 4096-byte responses and configured burst limits 256/600 under
finite peer request buffering. Full-sweep cases through 64 outstanding requests,
and all 4-/256-byte response cases, passed. Both sides of April commit
`b1a669c965` reproduce the cycle; atomics did not introduce it. The earlier
injected-lock experiment established the same receive-queue stop point.

The software peer advertises BUSY correctly; the captured natural stalls do not
retransmit or reset. The synthetic map is not Warm-TDM's tree, and peer bounds
are not measured FPGA capacities. This explains a Rogue failure mechanism,
not yet the small SAFb-batch slowdown or the complete bench reset sequence.

Local evidence lives separately in `~/rogue/docs/plans/srp-rssi-burst/REPORT.md`
and `WARM_TDM_FOLLOWUP.md`; reproduction instructions are in
`~/rogue/tests/perf/srp_rssi/README.md`. At the last review, work was pending on
`investigate/srp-rssi-burst` with production sources unchanged. Sync and inspect
that checkout before continuing; it is not supplied by a Warm-TDM pull.

Next: evaluate breaking the submission/timer-refresh dependency while preserving
transaction lifetime, timeout and concurrency semantics. Require correct data
and completion in formerly stalled cases. Match fixed bench addresses/order,
response sizes, outstanding profile and peer queue coupling, then correlate
lock waits, queue occupancy and ACK/BUSY on the bench. Do not treat a local fix
or larger queues as proof of the bench cause.

## FPGA flow control and packetizer boundary

At segment address width 7, RSSI RX FIFO pause asserts at 112 eight-byte words,
while advertised BUSY uses count bit 7 (128 words). The directed characterization
stops delivery/ACK with BUSY clear; draining restores progress. Thus `remBusy=0`
cannot exclude FPGA application backpressure. Host receive BUSY does not suppress
its own outbound retries; peer BUSY does. The missing-BUSY condition is a possible
connection between a host stall and retry-limit reset, not yet hardware attribution.

The separate depacketizer correction clears the destination entry just examined
and consumes output-stage validity when advancing pending beats. This restores
one error termination per unfinished destination under backpressure. In the old
SRP path, missing termination left the frame limiter consuming the first fresh
SOF as the old frame's ending. Complete-request integrated simulations reproduced
and fixed that loss without fixing preceding congestion.

[SURF PR #1492](https://github.com/slaclab/surf/pull/1492) contains only RTL plus
standalone tests (`cdde579cb`, cherry-picked from `2b58e8251`, base `ce66ccf99`).
All 28 packetizer cases, VSG, Flake8 and compliance checks passed on the clean
branch. Warm-TDM still pins the integration candidate `49c1168c6`, which also
contains the separate RSSI characterization/integration tests. See the
[SURF simulation handoff](../../../firmware/submodules/surf/docs/plans/rssi-rx-keepalive/README.md)
for detailed cases; its hardware-pending statements predate the accepted bench run.
Vendor-specific simulation and implementation timing reports were not supplied
with the hardware result.

Both Warm-TDM instances use 1024-byte segments and a default eight-segment window;
no recent committed reduction was found. The legacy segment-address generic is
ignored by the wrapper, which derives core width from maximum segment size.
[RSSI throughput tuning](../rssi-tuning/PLAN.md) remains a separate proposal (#109).

## Width-10 bound investigation

This earlier PGP work is separate from Ethernet RSSI reconnect recovery. Width
10 alone did not bound queued response bytes. Ring admission and ordered abort
recovery are now documented in the permanent
[PGP ring guide](../../../firmware/common/warm_tdm/doc/PGP_RING.md#flow-control),
with [isolated regressions](../../../tests/warm_tdm/pgp_ring/test_ring_control.py).
The eight-board 7168-byte budget remains conditional on a 64-PGP-clock control
hop and the documented pipeline allowance. Earlier source comparisons and
characterization tables remain in
[pinned history](https://github.com/slaclab/warm-tdm/blob/baf4229/docs/plans/register-timeout/README.md#width-10-bound-investigation).

Outstanding checks are preserved here until their acceptance record is updated:

- Rebuild GroupTb with unthrottled GTX receive semantics and the new ring
  protocol; measure control-hop delay and post-gate storage, including mixed VCs.
- Repeat queued large reads/sink stalls; capture overflow and verify fresh row
  and column SRP transactions without reset, outside a blocked client RPC.
- Force overflow/link interruption and verify EOFE, ordered marker completion
  and first-fresh-transaction recovery through real SRP/RSSI.
- Build affected targets with Vivado 2024.1; check resource fit, timing and
  throughput with shorter packets/cells. Successful GTX startup and isolated
  reads at `fc8f751` did not establish those properties.

## Evidence and ownership

The September 24–25 bench used rdsrv433, Rogue v6.15.0 (`warm-tdm-r615`),
FPGA `192.168.3.11`, host `192.168.3.31` and NIC `enp1s0f0`. The tested column
changed from `96a974f` / SURF `7504a23b3` to `743614f7` / SURF `49c1168c6`
(including `2b58e8251`); the row stayed `b73019c`. Loaded hashes were read from
hardware and fix ancestry verified. Builds used Vivado 2024.1. Post-reset first
reads changed from **5/5 failures to 3/3 passes**, with fresh `--no-initRead`
servers and no warmup reads. L463 resets persisted; L439 controls passed 3/3.
This validates focused recovery on that bench, not every destination or target.

Supporting controls found the failed request byte-identical to a successful
one and transport-ACKed. Alternating clean/reset priming gave first-read
pass/fail 4/4 per arm. Three column reads after reset gave fail/pass/pass;
a row-first read succeeded without consuming the column failure. DEBUG-off
SAFb batches remained slow. These controls and the local Rogue reproducer
address different parts of the failure; they do not establish the complete
hardware reset mechanism.

Raw pcaps, server logs, client JSONL, findings and checksums remain on rdsrv433
under `~/warmtdm-rssi-runs/`:

| Run directory | Evidence |
| --- | --- |
| `20260924T182950Z/` | Idle baseline, initial matrix, both failures and ScratchPad restoration |
| `20260924T191408Z-firstreq/` | Logging-off control, request validity and alternating reset-priming trials |
| `20260924T213308Z-newfw/` | Pre-fix retest, row/column localization, fixed register lists, L439/L463 repeats and `THRESHOLD_REPEATS_FINDINGS.txt` |
| `20260925T050252Z-pktfix/` | Corrected-image acceptance and `PKTFIX_RETEST_FINDINGS.txt` |

The [original combined report](https://github.com/slaclab/warm-tdm/blob/baf4229/docs/plans/register-timeout/hardware-handoff/REPORT-20260925-full-arc.md)
preserves the detailed chronology in Git history and is linked from
[SURF PR #1492](https://github.com/slaclab/surf/pull/1492). It refers to L439/L463
as outstanding-read counts; use the workload/transaction distinction above.
Its bench Rogue-version comparison is not the immediate parent/child atomic
comparison used in the local tests. Raw captures have not been reviewed locally.

This note owns the remaining investigation handoff, not issue closure:
burst/reset and PGP acceptance still need explicit ownership/checklists in the
tracker. Removing historical report files does not mark those checks passed.
