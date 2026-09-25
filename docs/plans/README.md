# Active work and proposals

Use [the documentation index](../README.md) for implemented behavior and
permanent design references. This directory holds unfinished work that needs
a handoff, proposals and a few redirects preserving old issue/wiki URLs.
Issues own acceptance and remaining checks; [project 43](https://github.com/orgs/slaclab/projects/43)
owns priority and stage. Follow the [workflow](../WORKFLOW.md).

Update one existing workstream note when its current state or next step changes.
Do not add a file for each session, review, merge check or issue audit. Put
revision-specific results on the owning issue/PR. Retire completed handoffs
after preserving unique evidence and repairing incoming links; use Git history
for obsolete hypotheses and implementation chronology.

## Integration and unresolved investigations

[PR #106](https://github.com/slaclab/warm-tdm/pull/106) combines frame-format,
integer/FP controller, resource and verification work. Its branch name is not
a complete scope description. [PR #107](https://github.com/slaclab/warm-tdm/pull/107)
reviews the operations follow-up separately. Integration and hardware acceptance
remain distinct.

| Workstream | Current handoff | Owner or boundary |
|---|---|---|
| Software entry points and measurement notebooks | [Software workflows](software-workflows/README.md) | Local implementation; issue owner not assigned |
| Frame identity and file-channel integration | [Channelization](channelization/PLAN.md) | [#82](https://github.com/slaclab/warm-tdm/issues/82) |
| Resource settings, legacy removal and build coverage | [Resource integration](resource-integration/README.md) | [#70](https://github.com/slaclab/warm-tdm/issues/70); capacity discovery is [#73](https://github.com/slaclab/warm-tdm/issues/73) |
| Coordinator-only Ethernet and constraints | [Coordinator Ethernet](coordinator-ethernet/README.md) | Related #70 resource work; explicit acceptance ownership remains to be assigned |
| Register timeouts and RSSI/SRP hardware investigation | [Register timeout](register-timeout/README.md); [hardware agent instructions and scripts](register-timeout/hardware-handoff/README.md) | Packetizer recovery fix awaiting hardware acceptance; Rogue backpressure cycle reproduced locally, bench attribution open |
| Static/muxed SQ1 operating point and tuning | [SQ1 retune](pid-cosim-verification/SQ1_RETUNE.md) | [#70](https://github.com/slaclab/warm-tdm/issues/70); historical fixture settings are [here](pid-cosim-verification/cosim-tuning-settings.md) |
| TES stimulus and multi-flux-jump capture | [TES scaling](tes-scaling/PROGRESS.md) | #70; distinguish later measured results from superseded attempts |
| Two-level FAS discovery and shared-line verification | [FAS follow-up](fas-two-level/README.md) | [#99](https://github.com/slaclab/warm-tdm/issues/99) |
| Live PID plots and GUI acceptance | [PID lock monitor](pid-lock-monitor/README.md) | Acceptance owner remains to be assigned; distinct from offline analysis #108 |

Controller contracts now live in [design/controllers](../design/controllers/README.md).
Reproduction and verification layers live in [the regression guide](../../tests/README.md).
[#70](https://github.com/slaclab/warm-tdm/issues/70),
[#90](https://github.com/slaclab/warm-tdm/issues/90) and
[#82](https://github.com/slaclab/warm-tdm/issues/82) own their acceptance.
Operations, mask graduation and tuning follow-up remain on
[#68](https://github.com/slaclab/warm-tdm/issues/68),
[#83](https://github.com/slaclab/warm-tdm/issues/83) and #99.

## Proposals

| Proposal | Record | Owning issue |
|---|---|---|
| Offline PID metrics, diagnosis and integer/FP comparison | [PID analyzer](pid-debug-analysis/PLAN.md) | [#108](https://github.com/slaclab/warm-tdm/issues/108) |
| RSSI segment sizing and throughput | [RSSI tuning](rssi-tuning/PLAN.md) | [#109](https://github.com/slaclab/warm-tdm/issues/109) |

Tune-point/run-settings design is in [muxed-run bring-up](../design/muxed-run-bringup.md)
([#81](https://github.com/slaclab/warm-tdm/issues/81)); physical-unit analysis is a
[dated reference](../reference/pid-coefficients.md)
([#44](https://github.com/slaclab/warm-tdm/issues/44)). Old FAS, group-variable,
sensor-model and target paths are short redirects, not additional active plans.
