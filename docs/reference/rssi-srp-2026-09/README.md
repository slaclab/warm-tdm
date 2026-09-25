# RSSI/SRP bench evidence — September 2026

These reports preserve the observations and interpretations recorded on
rdsrv433 during September 24–25. Their bodies are unchanged; they are dated
evidence, not current test instructions or a claim that the entire issue is
resolved. Use the [active handoff](../../plans/register-timeout/README.md) for
remaining work and the [bench procedure](../../plans/register-timeout/hardware-handoff/README.md)
for commands.

| Report | Evidence |
| --- | --- |
| [Initial matrix](REPORT-20260924-rdsrv433.md) | Idle behavior, batched/sequential reads, first-request loss and restored ScratchPad control |
| [Follow-up comparisons](REPORT-20260924-followups.md) | Logging-off control, request validity, reset-priming dependence and RX/keepalive-image retest |
| [Combined findings and packetizer acceptance](REPORT-20260925-full-arc.md) | Fixed-workload repeats, column/row localization, image lineage and successful recovery test |

The last report records column image `743614f7`, SURF `49c1168c6`, including
packetizer fix `2b58e8251`: post-reset first reads pass 3/3 versus 5/5 failures
before the fix. L463 still resets; L439 controls pass 3/3. Implementation review
and validation are recorded in [SURF PR #1492](https://github.com/slaclab/surf/pull/1492).
Raw pcaps, logs, JSONL and checksums remain under `~/warmtdm-rssi-runs/` on
rdsrv433, at the paths listed in the reports.

Interpret the historical wording with these distinctions:

- An early report calls the first-read loss intermittent. Alternating priming
  trials subsequently established its dependence on the previous reset.
- L439/L463 describe configured workloads. Distinct addresses alone do not
  measure simultaneous outstanding transactions; in failing pre-fix runs,
  384 requests were issued and 351 completed before reset.
- Host BUSY and host-initiated RST are observations. Attributing the whole reset
  to Rogue still requires connecting the local software wait cycle to the
  deployed FPGA's ACK/BUSY behavior.
- The bench's two Rogue versions are not the immediate parent/child comparison
  used in the separate local atomic-change investigation.
- The 3/3 corrected-image result validates focused recovery on this bench;
  it does not establish burst stability, all destinations or all target builds.

Earlier PGP capacity experiments and source comparisons are preserved in the
[pinned investigation history](https://github.com/slaclab/warm-tdm/blob/baf4229/docs/plans/register-timeout/README.md#earlier-pgpring-investigation-historical-context).
Maintained ring behavior is documented in the
[PGP ring guide](../../../firmware/common/warm_tdm/doc/PGP_RING.md).
