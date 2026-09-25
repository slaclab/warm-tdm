# Warm-TDM hardware RSSI/SRP investigation — agent handoff

Use [the current investigation](../README.md) for findings and next steps,
and its [evidence index](../README.md#evidence-and-ownership) for acceptance
results, raw-data locations and commit-pinned historical reports. This bundle
remains at its original path so existing probe and capture commands continue
to work. Record burst resets and first-read recovery
separately; the packetizer fix passed the latter on the tested image.

## Task and scope

Choose the controlled cases needed for the current question, preserve raw evidence, and return a report using `REPORT.md`. Do not automatically repeat the entire historical matrix. Measure separately:

1. A missing first SRP response after connecting or after an idle interval.
2. Delayed acknowledgments/backpressure and retransmissions during batched reads.
3. RSSI resets during load versus idle and deliberate shutdown.

You are authorized to launch and stop your diagnostic server, make the listed register reads, and write/verify/restore the column AxiVersion ScratchPad test register. Run only when the bench is available. There must be **one process owning the hardware RSSI connections**. A GUI that creates its own GroupRoot is another owner; close that server before launching this one. If an existing process belongs to an active acquisition or another user, coordinate availability rather than killing it. A VirtualClient connects to the existing server over ZMQ and does not open another hardware connection.

Do not tune, start acquisition, load configuration, WriteAll, change DAC/bias/PID settings, reset/reflash boards, change RSSI/network settings, or edit the checked-out source. Do not stage, commit, publish, or send results elsewhere. Put captures and reports outside Git. Do not change transaction timeouts to hide the failure. If the bench configuration differs from the example, use its known configuration and record the difference.

## Bench and current test selection

The recorded bench is rdsrv433, Rogue v6.15.0 (`warm-tdm-r615`), one FPGA column
coordinator and one row board, host `192.168.3.31`, FPGA `192.168.3.11`, NIC
`enp1s0f0`. SRP uses UDP 8192; data uses 8193. ZMQ normally uses localhost:9099;
use the address printed by the server and the installed environment/configuration.

For burst/backpressure work, start with a batched/sequential SAFb comparison or
`column-batched`, recording both transport and SRP results. To match the exact
L439/L463 boundary, use the fixed register lists and sweep tools preserved in
`~/warmtdm-rssi-runs/20260924T213308Z-newfw/` on the bench; `probe.py` does not
implement those named levels.

For a recovery check, first record a trigger session that actually resets.
Start a fresh server with `--no-initRead`, then invoke `version-only` with no
warmup read. If it fails, invoke `version-only` separately again against that
same server to distinguish one consumed request from a blocked path. Compare
with a clean priming session. Never count an ordinary server shutdown as the
trigger reset.

In the tested Rogue version, a parent's `forceWaitEach` does not serialize every
direct child-device call. Preserve the actual flags and transaction timing.
ACK delay also cannot be established by an out-of-window warning alone; use
the captured packets and both ACK directions.

## Files in this bundle

| File | Purpose |
|---|---|
| [`software/scripts/warmTdmServer.py`](../../../../software/scripts/warmTdmServer.py) | Normal server entry point, with opt-in transport logging and column serialization settings in its shared `runServer` implementation. |
| `probe.py` | Executes named tests through a VirtualClient. Logs operation times, results/errors, serialization flags and host RSSI counters. Only `scratch-write` writes registers. |
| `pcap_summary.py` | Converts classic tcpdump pcap to CSV with RSSI sequence/ACK/BUSY, checksums, payload fingerprints and supported SRP fields. Standard-library Python only. |
| `REPORT.md` | Report template to copy into the result directory. |

These helpers were prepared against Rogue v6.15.0 and exercised in the September 24 hardware reports linked from the investigation summary. Check launch errors and record the installed version rather than assuming compatibility with another checkout. `probe.py` uses the verified but private VirtualClient `_remoteAttr` API to invoke server device methods; if the installed API differs, report the mismatch and inspect that version before adapting it. Assigning attributes on a virtual client is not a substitute for changing the server's `forceWaitEach`.

## Preparation and metadata

Sync this directory **and the server software changes** with the repository to the hardware machine. Run the maintained `software/scripts/warmTdmServer.py` entry point. Example shell setup (retain these variables in each terminal/tool session):

```bash
conda activate warm-tdm-r615
export RSSI_REPO=/u1/warm-tdm/warm-tdm
export WARM_TDM_PATH="$RSSI_REPO"
export RSSI_BUNDLE="$RSSI_REPO/docs/plans/register-timeout/hardware-handoff"
export RSSI_RUN="$HOME/warmtdm-rssi-runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RSSI_RUN"
cd "$RSSI_REPO"
cp "$RSSI_BUNDLE/REPORT.md" "$RSSI_RUN/REPORT.md"
```

Record hostname, UTC and local time with timezone, OS, Python/Rogue versions and module locations, conda package versions, the Warm-TDM branch/commit/status, SURF commit/status, and any existing uncommitted changes relevant to communication. Do not dump environment variables or credentials. For example:

```bash
{
  hostname
  date -Ins
  date -u -Ins
  uname -a
  python --version
  python -c 'import rogue, pyrogue; print(rogue.__file__); print(pyrogue.__file__)'
  conda list rogue
  git branch --show-current
  git rev-parse HEAD
  git status --short
  git -C firmware/submodules/surf rev-parse HEAD
  git -C firmware/submodules/surf status --short
  ip route get 192.168.3.11
  ip -s link show dev enp1s0f0
} > "$RSSI_RUN/metadata.txt" 2>&1
```

Use `ps`/`ss` to identify existing hardware owners and ZMQ listeners. Record relevant NIC counters before and after testing (`ip -s link`, and `ethtool -S` if available). Resolve the actual interface with `ip route get`; do not assume the historical interface name. No offload/MTU/coalescing changes in the initial experiments.

## One recorded session

A session is one server lifetime, one capture and one or more **non-overlapping** client cases. Use a new directory and new logs for each server restart. Do not overwrite failed runs.

### 1. Capture before server startup

Example for session `01-idle`:

```bash
export RSSI_SESSION="$RSSI_RUN/01-idle"
mkdir -p "$RSSI_SESSION"
```

In a dedicated foreground terminal or persistent tool session, start:

```bash
sudo -n tcpdump -i enp1s0f0 -nn -s 0 -B 4096 -U \
  -w "$RSSI_SESSION/traffic.pcap" \
  'udp and host 192.168.3.11 and (port 8192 or port 8193)' \
  2> "$RSSI_SESSION/tcpdump.log"
```

Use existing capture privileges. If `sudo -n` is unavailable, report capture as blocked and continue the server/client tests; do not request a password in chat. A human may establish capture privileges separately. Prefer the actual NIC over `-i any` to reduce capture duplicates. `-i any` is an acceptable fallback; the decoder supports Linux cooked capture formats.

Keep the foreground capture session open; later send Ctrl-C **to that session** and wait for tcpdump to finish and write its statistics. Do not use a limit such as `-c 80`: it previously stopped before the failure interval. Keep captures bounded by the test window, generally 15–30 seconds for short probes or approximately 70–90 seconds for the idle test. Monitor size if data traffic is unexpectedly high. Do not rotate over the beginning of a failing trace. Record if the capture ended before the failure or recovery.

### 2. Start a headless server with its complete output retained

In another persistent terminal/tool session, using the same session path:

```bash
python -u "$RSSI_REPO/software/scripts/warmTdmServer.py" \
  --transport-diagnostics --column-mode stock \
  --ip 192.168.3.11 --rowBoards 1 --maxRows 80 --columnBoards 1 \
  --columnBoardType FPGA --rowBoardType FPGA \
  --columnFrontEnd FpgaColFebLnTes --rowFrontEnd FpgaRowFeb \
  --no-initRead \
  > "$RSSI_SESSION/server.log" 2>&1
```

Wait for the `server_ready` JSON line and verify the ZMQ address. `tail` the log from another session as needed. Diagnostic flags make the normal server log its PID, selected column mode, forced devices and startup arguments. The three modes are:

- `stock`: retain the installed column driver's setting.
- `batched`: set the column parent's `forceWaitEach=False`.
- `sequential`: set that parent's `forceWaitEach=True`.

Do not launch an interactive GUI or another hardware server alongside this process. Leave polling off. Preserve the bench's actual board/frontend/row-address configuration if it differs. Pass `--no-initRead` as shown; diagnostic logging itself does not disable startup reads or polling. Initialization writes retain the normal disabled default (confirm `init_write=false` in the startup record). Do not load configuration.

For fresh-first-request comparisons, use a consistent delay of approximately five seconds after `server_ready`, record the actual delay, and **do not read firmware identity or use a connection helper that prints identity first**. The probe's flag and RSSI-counter snapshots are host metadata, not FPGA register reads. Confirm from the server/capture that no unexpected earlier SRP request occurred.

### 3. Execute exactly one client case at a time

Example idle test (replace port if the server printed a different one):

```bash
timeout --signal=INT --kill-after=5s 90s \
  python -u "$RSSI_BUNDLE/probe.py" --host localhost --port 9099 \
  --case baseline --seconds 60 \
  > "$RSSI_SESSION/01-baseline.client.jsonl" 2>&1
```

Record each process exit code. Use the same pattern with `--case safb-batched --repeat 3`, for example, and give each invocation a separate numbered log file. JSON events include wall-clock epoch time for packet correlation and monotonic elapsed time for durations. Rogue may print a banner among the JSON lines; parse lines beginning with `{` as JSON rather than assuming every line is JSON.

A probe stops its repeats after the first exception. An operation can report completion yet have counter growth or warnings; analyze both. `timeout` is an outer watchdog, **not** an SRP timeout adjustment. Killing a client does not cancel a server-side operation. If a call hangs or the watchdog fires, preserve logs/capture, do not overlap another probe, and stop/restart only the diagnostic server you own. Record whether it shut down cleanly; do not silently force recovery or reset hardware. Use up to about 30 seconds for cleanup; if it remains stuck, report that state before further interventions.

### 4. Finish and preserve

After the case returns, allow roughly five seconds to capture trailing responses/retransmissions. Stop the diagnostic server with Ctrl-C in its own session, then stop tcpdump with Ctrl-C and wait for both to exit. This retains connection closure in the capture; distinguish deliberate shutdown from failures during a case. For a short session with several healthy cases, keep both running until the last case.

Record identities **after** the first-request-sensitive cases, using `--case identity` while the server is still running. If the server is wedged, do not disturb that trace to obtain identity; collect it in a separate recovery session and label it accordingly. Missing identity is not a reason to discard failure evidence.

## Test order and bounds

The following is the available diagnostic matrix; select cases for the current hypothesis. Stop a session after a real timeout/reset failure, save it, and restart the diagnostic server for the next independent experiment. A deliberately labeled same-session retry is allowed in the cold-read investigation. Never retry silently.

| Phase | Server mode | Client case(s) | Purpose / bound |
|---|---|---|---|
| Idle | stock | `baseline --seconds 60`, then `identity` | No hardware requests during baseline. Both RSSI cores must be evaluated separately. Record any reset/retransmit/drop growth. |
| Cold A | sequential | `version-only` | First hardware read is column FpgaVersion. Three fresh-server trials. |
| Cold B | sequential | `scratch-first`, then `axi-batched --repeat 2` if healthy | First read is ScratchPad, followed by FpgaVersion. Three fresh-server trials; compare with Cold A. |
| Cold C | sequential | `readall-stock` | First hardware operation is recursive ReadAll with column serialization. One fresh trial initially. If it fails, preserve evidence and, only after the call returns, record one explicitly labeled same-session retry. |
| Small A/B | stock | `safb-batched --repeat 3`, then `safb-sequential --repeat 3` | Compact comparison; explicit `waitEach` on SAFb itself. If both complete, repeat on a fresh server in reverse order. |
| Version A/B | stock | `axi-batched --repeat 3`, then `axi-sequential --repeat 3` | Smaller device comparison. Preserve first-request status separately from warmed reads. |
| Column A | batched | `column-batched` | One full batched column read; restart after failure. |
| Column B | sequential | `column-sequential --repeat 3`, then `row-stock --repeat 3` | Serialized controls. Row uses its own installed serialization setting. |
| Root control | sequential | `readall-sequential --repeat 3` | Explicit recursive waitEach at the root. |
| Write control | sequential | `scratch-write` | Two ScratchPad patterns, readback, and original-value restoration; one trial after read tests. |

No more than five fresh cold trials or ten repetitions of any small comparison are needed without a specific new finding. If initial comparisons are consistently clean, report failure-to-reproduce with those counts and configurations; do not claim the issue is fixed.

`scratch-write` saves the original column ScratchPad value before writing `0xA5A55A5A` and `0x5A5AA5A5`, checks each, then restores/verifies the original in a `finally` block. If it cannot read the original, it writes nothing. A timeout, server crash, or forced process termination can prevent restoration: verify a `scratch_restored` event and record the original value. If restoration is uncertain, stop further write tests and report the exact register/value and failure. Do not substitute a DAC or other live register for this test.

“Sequential” means Rogue waits between blocks at the invoked device scope. It is not a guarantee that every possible large split transaction or unrelated client operation is globally serialized. Keep other clients and polling quiet. The helper refuses a named batched case when its target directly forces serialization; also inspect `forced_devices` for descendant overrides and verify observed request timing.

## Additional logging only after a baseline reproduction

The baseline command above retains startup metadata with normal logging levels. For SRP transaction detail, add `--srp-debug`; for host RSSI detail, add `--rssi-debug` to the same server command and repeat the smallest failing test on a fresh server. There is no wrapper or `--` separator. This records more transport detail but can alter timing. Retain the original lower-verbosity run as the comparison.

If ACK/BUSY timing suggests host backpressure, capture a short RSSI-debug reproduction and record CPU usage/thread state with already available tools. A stack sample of a demonstrably stalled server is useful if existing local tooling permits it; document the tool and any pause it introduces. Do not install new tracing dependencies or change scheduling during the baseline.

Use `--transaction-debug` only for a short targeted follow-up. Repeated “Transaction timer refresh! Possible slow link!” warnings alone are not evidence of a one-second delay; interpret them against actual request/reply timestamps. If logging appears to change the behavior, repeat the same probe/capture with `--transport-diagnostics` in place of `--srp-debug` and omit the other DEBUG flags. This retains startup metadata with normal logging levels. Record the exact command; no source edits are needed.

## Decode and analyze the evidence

After tcpdump has exited:

```bash
python "$RSSI_BUNDLE/pcap_summary.py" "$RSSI_SESSION/traffic.pcap" \
  --board-ip 192.168.3.11 --port 8192 \
  > "$RSSI_SESSION/srp-packets.csv" \
  2> "$RSSI_SESSION/decode-srp.log"
python "$RSSI_BUNDLE/pcap_summary.py" "$RSSI_SESSION/traffic.pcap" \
  --board-ip 192.168.3.11 --port 8193 \
  > "$RSSI_SESSION/data-packets.csv" \
  2> "$RSSI_SESSION/decode-data.log"
```

Check decoder exit codes. It supports classic pcap, IPv4 UDP, Ethernet/VLAN, raw IP and Linux SLL/SLL2. It does **not** reassemble fragmented IP or multi-fragment packetizer messages. Packetizer CRC is checked only for complete single-fragment packets; blank CRC/status fields mean unavailable, not success. SRP decoding is restricted to port 8192. Keep raw capture even if decoding fails, and report unsupported traffic. Use installed Wireshark/tshark or a separate reviewed parser for reassembly if necessary.

Analyze these questions, citing session, case, timestamps, transaction IDs and packet numbers:

1. **Idle connections:** Were SrpRssi and DataRssi both open? What were their separate before/after counter values and deltas? Did a reset occur during idle, a read, or deliberate shutdown? Missing counters are unknown, not zero. If counters reset or wrap, show raw values and segment the timeline rather than summing a negative delta.
2. **Application transactions:** Match SRP IDs within each RSSI connection epoch and server session; a reset can reconnect within one process. Count sent requests, received replies, errors/timeouts and outstanding IDs. “Send frame” in a server log is not proof that a UDP frame reached the wire. “Got frame” alone is not proof that the transaction completed successfully. Include elapsed times and response status words.
3. **First missing response:** Did the first request actually appear on the wire? Did FPGA acknowledgment progress cover it? Was a matching SRP response captured? Were later replies delivered without an RSSI sequence gap? Was the capture long enough to cover timeout/recovery? Do not call a short trace proof of permanent loss.
4. **ACK timing:** For each FPGA-to-host data packet, find the first host ACK that cumulatively covers its sequence. Include ACKs piggybacked on data packets, not just ACK-only packets. Report representative/maximum data-to-ACK delays, 20 ms clustering, and BUSY transitions. Show what happens immediately before and after each retransmission/reset. A promptly emitted host ACK with subsequent retransmission points toward the return path or FPGA handling; a late host ACK with sustained BUSY points toward host delivery/backpressure. These are discriminators, not conclusive localization from a host-only capture.
5. **Duplicates:** Compare sequence and packetizer payload fingerprint within the same connection. A repeated sequence with the same payload is evidence of a retransmission/duplicate. Check whether the original was already cumulatively acknowledged when the duplicate arrived. The RSSI header checksum may change when the ACK field changes; that does not make the payload different.
6. **Scope:** Separate UDP 8192 and 8193 and each host ephemeral port/connection epoch. `server=0` in a Rogue warning means client role, not board zero or a particular RSSI core. Sequence and ACK fields wrap at 256. Interpret cumulative ACK advancement against the live sequence window and reset on SYN/RST/reconnection; never compare raw integers across wrap or across connections.
7. **Capture quality:** Report tcpdump captured/received/kernel-drop counts and NIC-counter changes. Zero kernel drops does not prove no network/FPGA loss. Host TX UDP checksum warnings can be offload artifacts; RSSI-header/packetizer checksums are separate checks. A host capture does not prove arrival at the FPGA.

The CSV flags are RSSI bits: SYN `0x80`, ACK `0x40`, RST `0x10`, NULL `0x08`, BUSY `0x01`. Record exact packet flags instead of treating every packet as an acknowledgment. ACKed RSSI transport data is not the same as a completed SRP register transaction.

## Deliverables and report-back

Fill in `REPORT.md`. Preserve metadata, exact launch/probe commands, source changes if any, server logs, client JSONL, original pcaps, tcpdump statistics, decoder output/errors, and a checksum manifest. Include a short timeline around the first representative failure and a comparable successful sequential run. Preserve successful controls as well as failures.

For each case report: software and loaded firmware identity, server mode/actual flags, fresh or warmed session, repeat count, first requested register, result, duration, missing SRP IDs, per-core RSSI deltas, and evidence filenames. Distinguish **observed**, **inferred**, and **not tested**. If no failure reproduced, explicitly report the number of clean trials and coverage limits.

Archive the run directory only after processes have exited and files are stable. Keep the archive on the hardware machine; uploading the pcap is not required. Return the report text, archive path/size/checksum, and compact packet/log excerpts with timestamps sufficient for review here. Do not paste megabytes of raw logs or discard the originals. A useful initial response states whether the idle resets persist, whether the first request fails, and whether explicit serialization changes the result.

## Helper validation and provenance

The scripts were exercised in the linked hardware reports. Before that, local
checks covered mocked VirtualClient dispatch, ScratchPad restoration on injected
exceptions, server diagnostic argument handling, and decoding 80 reconstructed
packets across raw-IP/Ethernet/SLL/SLL2 capture formats. These were limited helper
checks, not hardware acceptance; the
[dated validation record](https://github.com/slaclab/warm-tdm/blob/baf4229/docs/plans/register-timeout/hardware-handoff/VALIDATION.md)
retains their exact scope. Record the checkout commit and relevant modifications
with every new run. Generate checksums for that run's actual evidence; an old
bundle checksum manifest does not identify a subsequently edited checkout.
