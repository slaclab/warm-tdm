# Warm-TDM RSSI/SRP hardware report

## Result

- Idle SrpRssi / DataRssi behavior:
- Burst resets during the operation (excluding deliberate shutdown)? Trials:
- First read after reset/reconnect: trials, successes, and any same-session retry:
- Batched versus sequential behavior:
- ScratchPad original restored and verified?
- Best-supported explanation; remaining uncertainty:

## Setup

- Host, timezone, run UTC start/end, result directory:
- Python/Rogue versions and module locations:
- Warm-TDM branch/commit and relevant local modifications:
- SURF checkout revision:
- Loaded column and row BuildStamp/GitHash/DeviceDna (when read):
- IP, interface, ZMQ address, board/frontend/row configuration:
- Exact commands and server serialization flags (file references):
- Other clients/polling/DAQ activity:
- Capture availability and any omitted tests:

## Test results

| Session / case | Fresh or warmed; mode | Trials / passed | Duration | Missing/error SRP IDs | SRP down/drop/retrans delta | Data down/drop/retrans delta | Evidence |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

For counter resets, include raw values and split the interval. Do not treat absent counters as zero. State same-session retries explicitly. Distinguish requested workload size, unique issued SRP IDs, completed replies and peak outstanding count; address coverage alone does not measure concurrency. Match IDs within each RSSI connection epoch.

## Representative failure and successful control

- Session/case and requested register/device:
- Timeline with epoch times, SRP IDs, RSSI sequence/ACK/BUSY, packet numbers:
- First request captured / acknowledged / response captured / API completion:
- ACK delays and whether they precede retransmissions:
- Resets, duplicate frames and checksum/status results:
- Matched sequential control and relevant differences:
- Observation versus inference:

## Integrity and cleanup

- Capture window covers the complete operation and trailing recovery?
- Tcpdump kernel drops; NIC counter changes; decoder limitations/errors:
- Any watchdog expiration, hung server, forced termination or interrupted case:
- ScratchPad original value, restoration event/readback or unresolved restoration:
- Diagnostic server/capture processes stopped; remaining processes:
- Archive path, size and SHA-256; evidence manifest path:
- Recommended next experiment tied to the evidence:
