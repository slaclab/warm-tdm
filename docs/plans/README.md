# Plans and design records

Start here to find a workstream. Issues own remaining work and acceptance;
[project 43](https://github.com/orgs/slaclab/projects/43) owns priority and stage.
These documents support active work and intentional design records. An old
unchecked plan item is not a second backlog. See [the workflow](../WORKFLOW.md).

After implementation is integrated into `pre-release`, move enduring guidance
into a permanent README, guide, or `docs/design/` record. Remove superseded
checklists and execution logs; their history stays in Git. Retain a task
directory only for active follow-up, an intentional design record, or a short
redirect for existing links. Keep unfinished acceptance on its owning issue.

## Work carried by the channelization integration

[PR #106](https://github.com/slaclab/warm-tdm/pull/106) combines several related
changes. Its branch name describes only one of them. Use the separate entry
points below before editing a shared module.

| Workstream | Start here | Owning issue |
|---|---|---|
| Frame identity, file channels, live/file decoders | [Channelization](channelization/PLAN.md) | [#82](https://github.com/slaclab/warm-tdm/issues/82) |
| Floating-point PI and configuration/lifecycle | [FP PID](fp-dsp-pid/README.md) | [#70](https://github.com/slaclab/warm-tdm/issues/70) |
| Accumulator split and integer PID corrections | [Integer PID](integer-pid/README.md), [split rationale](pipelined-dsp-accumulator/PLAN.md) | [#70](https://github.com/slaclab/warm-tdm/issues/70) |
| Resource options, legacy-driver removal, target/build coverage | [Resource integration](resource-integration/README.md) | [#70](https://github.com/slaclab/warm-tdm/issues/70); capacity discovery remains [#73](https://github.com/slaclab/warm-tdm/issues/73) |
| Regression harness and layered verification | [Verification index](pid-cosim-verification/README.md) | [#90](https://github.com/slaclab/warm-tdm/issues/90); feature acceptance stays on #70/#82 |
| Sensor fixture updates and V–Φ shaping | [Model architecture](../../firmware/common/warm_tdm/sim/README.md), [shaping design](../design/squid-vphi-shaping/) | Foundation integrated via [#98](https://github.com/slaclab/warm-tdm/issues/98); later PID comparison acceptance on #70 |

The operations baseline comes from PR #78 and tuning/model work from
#101/#102/#104/#105. PR #107 contains the enabled-set, logical-row vocabulary
and operations follow-up. Those changes also occur in the integration history;
acceptance remains with [#68](https://github.com/slaclab/warm-tdm/issues/68),
[#83](https://github.com/slaclab/warm-tdm/issues/83) and
[#99](https://github.com/slaclab/warm-tdm/issues/99).

## Separate work and historical context

| Topic | Document | Owning issue / context |
|---|---|---|
| Register timeouts after the September 18 integer 10G image | [Source comparison and diagnostic checks](register-timeout/README.md) | Active hardware regression investigation; cause unconfirmed |
| Live PyDM feedback, flux count and PID error plots | [PID lock monitor](pid-lock-monitor/README.md) | Active GUI work; related metrics proposal #108 |
| Current integer/FP DSP behavior and performance comparison | [PID path comparison](pid-path-comparison/README.md) | September 17 source review and local timing probe; acceptance stays on #70 |
| PID metrics, diagnosis and comparison proposal | [PID analyzer](pid-debug-analysis/PLAN.md) | [#108](https://github.com/slaclab/warm-tdm/issues/108) |
| RSSI segment-size proposal | [RSSI tuning](rssi-tuning/PLAN.md) | [#109](https://github.com/slaclab/warm-tdm/issues/109) |
| Integrated FAS tuning rationale | [FAS tuning design](../design/fas-tuning.md) | [#99](https://github.com/slaclab/warm-tdm/issues/99) |
| Two-level FAS discovery and shared-line verification | [Active handoff](fas-two-level/README.md) | Extension under [#99](https://github.com/slaclab/warm-tdm/issues/99) |
| Integrated group variable I/O contracts | [Group variable design](../design/group-variables.md) | [#103](https://github.com/slaclab/warm-tdm/issues/103) owns deferred AD5679R writes; #83 owns graduation decisions |
| Physical PID units | [PID coefficients](sensor-wafer-model/PID_COEFFICIENTS.md) | [#44](https://github.com/slaclab/warm-tdm/issues/44) |
| Software cleanup, including unmerged legacy removal | [Software cleanup](sw-cleanup/PLAN.md) | Remaining resource/legacy/build obligations are on #70 |
| Integrated target organization | [Firmware targets](../../firmware/targets/README.md) | Current candidate build acceptance remains on #70 |
| September 16 cleanup audit | [Accounting and handoff](work-tracking-cleanup/README.md) | Dated snapshot; use linked live records afterward |

Do not create another omnibus plan under `channelization` or the verification
log. Put a new independently managed effort in its own task directory and link
its issue here. Leave a short redirect when moving a linked plan so existing
issue/wiki links remain useful.
