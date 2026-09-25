# Warm-TDM RSSI/SRP investigation — full arc and resolution (rdsrv433)

Synthesis of the whole investigation, 2026-09-24 → 2026-09-25. Ties together the two
earlier reports (`REPORT-20260924-rdsrv433.md`, `REPORT-20260924-followups.md`) and the
subsequent sweep, threshold, and firmware-fix runs. Bench: `rdsrv433`, FPGA
`192.168.3.11`, host `192.168.3.31`, NIC `enp1s0f0`, Rogue v6.15.0 (conda
`warm-tdm-r615`) unless noted. One hardware owner per session; server via
`software/scripts/warmTdmServer.py` with diagnostic flags; probes via the bundle
`probe.py` plus small run-dir evidence tools. All raw evidence (per-session
`server.log`, `*.jsonl`, `traffic.pcap`, decoded CSVs, per-run findings, checksums) is
preserved **outside Git** on `rdsrv433` under `~/warmtdm-rssi-runs/…`; run directories are
named inline. tcpdump uses an operator-granted file capability; captures have 0 kernel
drops. The only hardware writes were the documented ScratchPad control (restored).

## Bottom line

The investigation found **two independent faults**, localized each, and confirmed a
firmware fix for one:

1. **Missing first SRP response after a reset — FIXED in firmware.** A batched-read RSSI
   reset left the column depacketizer unable to answer the *first* SRP request on the next
   connection. The SURF packetizer fix `2b58e8251f` ("preserve frame termination across
   link loss"), loaded as column image `743614f7`, **closes it**: post-reset first reads
   now succeed 3/3 where they failed 5/5 before.
2. **Batched-read host backpressure → RSSI reset — STILL OPEN (host/Rogue side).** Reading
   more than ~439–463 outstanding column registers at once drives host-side RSSI BUSY, the
   host freezes its cumulative ACK, and the **host** tears down the link (RST), orphaning
   the in-flight batch. This is unchanged by the firmware fix and is a separate host-side
   issue.

## Firmware image lineage (all built Vivado 2024.1, column board)

| Column image | SURF pin | Packetizer fix `2b58e8251f`? | Role in this arc |
|---|---|---|---|
| `0b73019` (surf `6b6771a9`) | keepalive fix only | no | initial bench image; idle-reset era |
| `b73019c` | — | no | image during first full matrix run |
| `96a974f` (surf `7504a23b3a`) | RSSI RX + keepalive candidate | **no** (fix is 2 commits later) | reset-dependency + sweep/threshold runs |
| **`743614f7`** (surf `49c1168c`) | + packetizer fix | **YES** | fix-confirmation run |

Row board stayed `b73019c` throughout. Loaded hashes were read from hardware each session;
`2b58e8251f` ancestry verified with `git merge-base --is-ancestor`.

## Timeline of findings

### 1. Idle is healthy; the historical resets are gone
(`20260924T182950Z/01-idle`, `02-idle-cap`.) Over a 60 s counter baseline and ~105 s
capture, both SrpRssi and DataRssi stayed open with zero down/drop/retran and no RST — only
NULL keepalives. The historical ~52 resets/min did **not** reproduce. *Observed.*

### 2. Two distinct failures surfaced under load
(`20260924T182950Z`.) The prescribed matrix reproduced **two** different failures:
- **Batched full-column read → reset** (`13-columnA`): 176 host→FPGA BUSY packets, 112
  retransmits, one mid-op RSSI reset ~260 ms in, transaction timeout, ~33 orphaned IDs.
- **Missing first response** (`14-columnB`, sequential): the first request (FpgaVersion,
  id=1) was transport-ACKed by the FPGA within ~5 ms but never answered at the SRP layer;
  timeout at exactly `root_timeout` = 1.0 s on an otherwise-healthy link. Sequential/root
  ReadAll and the ScratchPad write control were clean.

### 3. Logging is not a factor; the failed request is well-formed
(`20260924T191408Z-firstreq`.)
- **Logging-off SAFb comparison:** with all DEBUG off (`--transport-diagnostics` only),
  batched reads stayed ~10× slower than sequential and still drove host BUSY growth — so
  verbose logging is not the cause (→ host receive processing, not a logging artifact).
- **Request-validity check:** the failed first request was **byte-identical** to a
  successful one (same payload hash, valid packetizer CRC, SOF/EOF, tdest, SRP header). The
  request that reached the wire was valid; the FPGA simply produced no reply.

### 4. The missing first response is deterministic after a reset (not random)
(`20260924T191408Z-firstreq`, alternating pairs.) A **perfect 4/4 correlation**: a clean
priming session → next fresh server's first read always succeeds; a batched-reset priming
session → next fresh server's first read always fails, with the transport-ACKed-but-
unanswered signature. This reframed the earlier "1/13 intermittent" as **persistent
FPGA-side state that survives the host server restart**. *Observed (4/4); mechanism
inferred.*

### 5. New column image `96a974f` did not fix it
(`20260924T213308Z-newfw`.) Same deterministic 4/4: batched read still reset, post-reset
first read still failed. That image predates the packetizer fix (surf `7504a23b3a`).

### 6. The dead transaction is one consumed request, specific to the column path
(`20260924T213308Z-newfw`, consume-vs-block.) Using packetizer `tdest` to route
(`tdest=0`=column, `tdest=1`=row):
- **Test A** (3 separate column reads on one persistent post-reset server): call 1 FAIL,
  calls 2 & 3 PASS → the failure **consumes exactly one request; the path is not blocked**.
- **Test B** (row read first, then column): the **row** read (tdest=1) succeeded over the
  same shared RSSI transport; the **column** read (tdest=0) failed — even as the *second*
  request on the link.
→ The fault is **local to the column SRP/depacketizer recovery after `linkGood`**, not the
shared transport, and not a persistent block. This matched the (corrected) understanding
that the V2 depacketizer *does* terminate unfinished frames on connection loss — the
question was whether that recovery works, and it was dropping exactly the first
post-reconnect frame.

### 7. The reset boundary is a reproducible outstanding-reads threshold
(`20260924T213308Z-newfw`, sweep + fine sweep + repeats.) Holding firmware fixed and
sweeping the number of outstanding reads (via `readAndWaitBlocks`/accumulating `readBlocks`
scope; count measured on-wire as distinct SRP request addresses):
- Coarse: reset only above ~320–525; **fine: clean at 439, resets at 463.**
- **Repeats (5× each): L439 5/5 clean (439/439 complete, no reset); L463 5/5 reset**
  (RST at +6.4–7.3 s, exactly 351 completed, the same 33 IDs 352–384 orphaned). A hard,
  reproducible boundary — not timing-dependent.
- **Mechanism at the reset:** as BUSY floods, the **host freezes its own cumulative ACK**
  (receive path backed up) while still issuing new requests, then the **host sends the RST**
  (FPGA only echoes it). So the reset is host-initiated backpressure, not FPGA loss.
- **Before/after the Rogue atomic/BUSY change** (v6.15.0 vs v6.15.0-44-g31ae93c75): the
  threshold did **not** move; only host BUSY *accounting* differed. → the reachability
  boundary is set FPGA/host-datapath-side, not by Rogue's atomic/BUSY handling.

Note: `--rssi-debug` logs only the **host** Rogue controller; it cannot show FPGA-internal
state (an earlier report recommendation was corrected on this point).

### 8. Packetizer fix confirmed: first-read-loss closed
(`20260925T050252Z-pktfix`.) Column image `743614f7` (surf `49c1168c`, **includes
`2b58e8251f`**). Same L463-trigger / L439-control design; post-reset probe on a fresh
`--no-initRead` server, first read with no warmup, second read attempted if the first
failed.

| Arm | reset still occurs? | post-reset first read | vs pre-fix (`96a974f`) |
|---|---|---|---|
| L463 (trigger), 3/3 | **yes** (midRST=2, downΔ=1, ~33 orphaned) | **read #1 SUCCEEDS, 3/3 (~0 ms)** | pre-fix failed **5/5** |
| L439 (control), 3/3 | no (439/439 complete) | ok | unchanged |

**Resets continue while post-reset first reads consistently succeed** — the exact signature
that supports the packetizer recovery fix. The first SRP request after reconnect is now
answered. *Observed, 3/3 per arm (quick confirmatory run).*

## Conclusions

- **Fault 1 (missing first response): RESOLVED in firmware.** Root cause was column
  depacketizer recovery dropping the first frame after a `linkGood`/reset; SURF
  `2b58e8251f` (image `743614f7`) fixes it. Confirmed by direct before/after on the same
  bench with loaded-hash verification.
- **Fault 2 (batched-read reset): OPEN, host/Rogue side.** Above ~439–463 outstanding
  column reads, host RSSI backpressure (BUSY + frozen cumulative ACK) makes the host RST the
  link and orphan the in-flight batch. Reproducible and independent of the firmware fix and
  of the Rogue atomic/BUSY change. Operationally, serializing column reads avoids it.

## Recommended next steps

1. **Regression-guard the fix:** keep column reads serialized in normal operation until
   Fault 2 is addressed; the first-read-loss no longer compounds it, but the reset itself
   still aborts a large batched read.
2. **Pursue Fault 2 on the host/Rogue side** with a concrete workload target — **not "~500
   reads" but the 439-clean / 463-reset boundary**, where the host asserts BUSY, freezes
   cumulative ACK (~ack=148 in the traces), keeps issuing requests, then RSTs. Investigate
   the host RSSI RX queue / application delivery backpressure at that operating point.
3. **Optional:** extend N on the `743614f7` first-read test for tighter statistics before
   declaring Fault 1 closed in the tracker.

## Evidence index (on rdsrv433, outside Git)

- `~/warmtdm-rssi-runs/20260924T182950Z/` — idle baseline, full matrix, both original
  failures; `REPORT.md`, per-session findings, `MANIFEST.sha256`, archive.
- `~/warmtdm-rssi-runs/20260924T191408Z-firstreq/` — logging-off SAFb, request-validity,
  deterministic reset-dependency (4/4).
- `~/warmtdm-rssi-runs/20260924T213308Z-newfw/` — `96a974f` retest, consume-vs-block,
  outstanding-reads sweep + fine sweep + L439/L463 repeats, before/after Rogue builds;
  `THRESHOLD_REPEATS_FINDINGS.txt`, `SWEEP_BEFORE_AFTER_COMPARISON.txt`,
  `FINE_SWEEP_BEFORE_FINDINGS.txt`.
- `~/warmtdm-rssi-runs/20260925T050252Z-pktfix/` — `743614f7` fix confirmation;
  `PKTFIX_RETEST_FINDINGS.txt`.
