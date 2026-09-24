# Warm-TDM RSSI/SRP — follow-up tests and results (rdsrv433, 2026-09-24)

Companion to `REPORT-20260924-rdsrv433.md`. Same bench, host, and conventions
(`rdsrv433`, FPGA `192.168.3.11`, NIC `enp1s0f0`, host `192.168.3.31`, Rogue v6.15.0,
conda `warm-tdm-r615`, one hardware owner per session). Server launched via
`software/scripts/warmTdmServer.py`; probes via the bundle `probe.py`. All raw evidence
(per-session `server.log`, `*.client.jsonl`, `traffic.pcap`, decoded CSVs, per-run
findings + checksums) is preserved **outside Git** on `rdsrv433` under
`~/warmtdm-rssi-runs/…`; run directories are named inline below. tcpdump capture uses
the operator-granted file capability (`cap_net_raw,cap_net_admin+eip`); every session
below has a full pcap with **0 kernel drops**. No hardware was tuned, reset, or
reconfigured; the only writes were the earlier ScratchPad control (already restored).

These follow-ups resolve three questions left open by the initial report and then
re-test after a column-board reflash. The headline outcome: **the two symptoms are
causally linked and deterministic — a batched-read RSSI reset leaves persistent
FPGA-side state that makes the *next* connection's first SRP request go unanswered — and
this is not fixed by the new column firmware.**

## 1. Is verbose logging contributing to the batched-read backpressure?

**Run dir:** `20260924T191408Z-firstreq/` (sessions `20-smallAB-nodebug`,
`21-smallAB-nodebug-rev`). Compared against the initial report's `srp-debug` SAFb runs
(`20260924T182950Z/10-smallAB`, `11-smallAB-rev`).

Method: repeat the SAFb batched-vs-sequential comparison with **DEBUG logging off** —
server started with `--transport-diagnostics --no-initRead` and **no**
`--srp-debug/--rssi-debug/--transaction-debug`. Verified logging was actually off (0
`pyrogue.SrpV3` lines in `server.log`; `server_ready` shows
`srp_debug/rssi_debug/transaction_debug = False`, `transport_diagnostics = True`). Both
orders (batched-first and sequential-first), stock column mode.

| Run | batched ×3 (ms) | sequential ×3 (ms) | batched `locBusyCnt` after |
|---|---|---|---|
| srp-debug (`10-smallAB`) | 145.5 / 129.8 / 86.1 | 8.5 / 11.0 / 10.1 | 6 → 10 → 15 |
| **nodebug (`20`)** | **131.6 / 110.9 / 92.3** | **9.3 / 9.2 / 10.6** | 4 → 6 → 10 |
| srp-debug rev (`11`) | 129.4 / 138.5 / 141.3 | 9.6 / 9.8 / 10.8 | 4 → 7 → 10 |
| **nodebug rev (`21`)** | **126.5 / 105.8 / 143.3** | **10.6 / 10.3 / 10.3** | 4 → 6 → 13 |

**Result (observed):** turning DEBUG logging off makes **no material difference**.
Batched SAFb stays ~10× slower than sequential and still drives host-side RSSI BUSY
growth (`locBusyCnt` climbs per iteration; sequential stays flat); total SRP BUSY packet
counts are comparable (8–13) with or without DEBUG. `remBusy` stayed 0 throughout (the
FPGA never asserted BUSY). **Verbose logging is not necessary to produce the batched
backpressure symptom** → per the agreed decision rule, the batched-read backpressure is a
**host receive-processing** issue, not a logging artifact and not (for this symptom) the
firmware.

## 2. Is the failed first request itself malformed? (zero-hardware evidence check)

**Run dir:** `20260924T191408Z-firstreq/` (analysis only, from existing captures). The
initial report confirmed RSSI header checksums but noted that does not establish the
packetizer/SRP request was valid. Here the first host→FPGA SRP `id=1` request from the
**failed** case (`20260924T182950Z/14-columnB`, no reply) is compared field-by-field to
the first `id=1` request from a **successful** case (`17-coldseq-t1`, replied).

| Field | FAILED (`14-columnB`) | SUCCESS (`17-coldseq-t1`) |
|---|---|---|
| udp_bytes | 48 | 48 |
| flags | 0x40 | 0x40 |
| seq / ack | 119 / 128 | 119 / 128 |
| rssi_checksum_ok | 1 | 1 |
| tdest | 0 | 0 |
| sof / eof | 1 / 1 | 1 / 1 |
| packetizer_crc_ok | **1** | **1** |
| srp_id / addr / size / op | 1 / 0x0 / 4 / 0(read) | 1 / 0x0 / 4 / 0(read) |
| payload_hash | **f086611226a7aef7** | **f086611226a7aef7** |
| FPGA reply for id=1 | **NONE** | **YES** |

**Result (observed):** the failed request is **byte-identical** to the successful one —
same payload hash, valid packetizer CRC, valid SOF/EOF, correct tdest/dport, valid SRP
header, valid RSSI checksum. The request that reached the wire was fully valid; the FPGA
simply produced no SRP reply. This rules out a malformed/corrupt host-side request and
strengthens localization to **FPGA-side first-request processing**.

## 3. Does the missing first reply depend on a preceding batched-read reset?

**Run dir:** `20260924T191408Z-firstreq/` (`ctrl-prime-*`, `ctrl-probe-*`,
`test-prime-*`, `test-probe-*`). This is the decisive experiment.

Method: alternating **pairs**. Each pair is a *priming* session (fresh server) followed
by a *probe* session (a **separate** fresh server running `version-only`, first read =
column `FpgaVersion`). Probe servers use `--no-initRead`, an identical ~5 s
post-`server_ready` delay, and **no preliminary hardware reads** (distinct PIDs each
time). Priming differs by arm:

- **CONTROL** — sequential server, `row-stock` read (row board self-serializes → no reset).
- **TEST** — batched server, `column-batched` read (reproduces the RSSI reset).

Priming verification (SRP core; RST total, mid-op resets): CONTROL = (2, **0**) every
time (RSTs only at shutdown); TEST = (4, **2**) every time (reset + reconnect
reproduced).

| Pair | CONTROL probe (after clean priming) | TEST probe (after reset priming) |
|---|---|---|
| 1 | PASS — id1 req/rep 1/1, ACKed, link 0/0/0/0 | FAIL — id1 req/rep 1/0, request ACKed ~5 ms, link 0/0/0/0, timeout @1.0 s |
| 2 | PASS | FAIL (same signature) |
| 3 | PASS | FAIL (same signature) |
| 4 | PASS | FAIL (same signature) |

**Result (observed): a perfect 4/4 correlation.** A clean previous session → the next
fresh server's first read always succeeds. A previous session that ended in a
batched-read reset → the next fresh server's first read always fails, with the exact
`14-columnB` signature: the first request is transport-ACKed by the FPGA within ~5 ms but
never answered at the SRP layer, on an otherwise-healthy link (host counters
`locBusy/drop/retran/down` = 0/0/0/0), timing out at `root_timeout` = 1.0 s.

**Interpretation (inferred):** the "missing first response" is **not random**. A
batched-read RSSI reset leaves **persistent FPGA-side state that survives the host server
restart** (new PID, new RSSI connection, new SYN handshake) and causes the next
connection's first SRP request to be transport-ACKed but never processed to a reply. This
reframes the initial report's lone "1/13 intermittent" failure — that `14-columnB` case
directly *followed* the `13-columnA` batched reset. **Caveat:** N = 4 per arm; the
persistent-post-reset-state mechanism is the working hypothesis, strongly supported but
not yet observed from FPGA-internal state.

**Combined causal chain:**

1. Batched full-column/SAFb read → **host** receive backpressure (host asserts RSSI BUSY;
   `remBusy` = 0). *[host-side; §1 shows logging is not the cause]*
2. Backpressure escalates BUSY → drops/retrans → **RSSI reset**.
3. The reset leaves the **FPGA** in a bad recovery state that persists across the server
   restart. *[FPGA-side]*
4. The next connection's **first SRP request is transport-ACKed but never answered** →
   1.0 s timeout. *[FPGA-side; §2 shows the request is valid]*

## 4. Re-test after column-board reflash (new firmware)

**Run dir:** `20260924T213308Z-newfw/` (`00-identity`, then 4 alternating pairs as in §3).

New **column** image loaded by the operator; row board unchanged. Identity read
(`00-identity`):

| Board | GitHash (short) | BuildStamp | Note |
|---|---|---|---|
| Column | **96a974f** (`0x96a974f3a5aaf10f…`) | ColumnFpgaBoard325Int10G, Vivado v2024.1, **built 2026-09-24 12:51 PDT** | **new** |
| Row | b73019c (`0xb73019cc73de828f…`) | RowFpgaBoard160, built 2026-09-23 | unchanged |

The column GitHash `96a974f` matches repo commit `96a974f` ("Pin SURF RSSI RX and
keepalive integration candidate"), which pins SURF to `7504a23b3` — the keepalive fix
plus the RX fixes from SURF PR #1456. (`FpgaVersion` still reads 0 on both boards while
GitHash/BuildStamp/DeviceDna read valid — the same build-field quirk noted before, not a
comms failure.)

Re-ran the §3 deterministic reproducer on the new image. Results are **identical** to the
prior firmware:

- Priming resets: CONTROL (2, 0) ×4; TEST (4, **2**) ×4 — the batched read **still**
  causes mid-op RSSI resets.
- Probes: **CONTROL PASS 4/4** (id1 req/rep 1/1); **TEST FAIL 4/4** (id1 req/rep 1/0,
  request transport-ACKed within ~5 ms, healthy link 0/0/0/0, timeout @1.0 s).
- Perfect 4/4 correlation again; failure signature byte-for-byte matches `b73019c`.

**Result (observed): the new column firmware `96a974f` does NOT fix either symptom.** The
batched-read reset still occurs, and the post-reset first request is still transport-ACKed
but unanswered. The persistent cross-connection FPGA-side state survives on the new image.

## Recommended next steps

1. **Capture FPGA-side state at the dead first request.** Repeat §3 with `--rssi-debug`
   added to the *failing probe* server command (retain a matched non-rssi-debug run for
   timing) to record RSSI/SRP controller state immediately after reconnection, and
   confirm from the FPGA side why the first transaction is ACKed but not answered.
2. **Address the host backpressure that triggers the reset (§1).** Since batched reads
   reliably drive host-side RSSI BUSY → reset, either keep column reads serialized
   operationally, or investigate the host receive path (RSSI RX queue / application
   delivery) that overruns under a concurrent batch.
3. **Firmware recovery path.** The core defect exposed by §3/§4 is that a reset leaves the
   FPGA unable to answer the first post-reconnect SRP request. A firmware/stack fix should
   target RSSI/SRP recovery after a mid-transaction reset; `96a974f` (SURF `7504a23b3`,
   PR #1456 RX fixes) does not resolve it.
