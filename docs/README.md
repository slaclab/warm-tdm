# Warm TDM documentation

Start with the guide for the work you are doing. Documentation describes the
source revision you are reading; the controller changes on `channelization`
are reviewed in [PR #106](https://github.com/slaclab/warm-tdm/pull/106) and are
not a claim that those changes have been released or accepted on hardware.

## Development and operation

| Need | Guide |
|---|---|
| Firmware layout, conventions and builds | [Firmware guide](../firmware/FIRMWARE_GUIDE.md), [targets](../firmware/targets/README.md) |
| Python device tree, tuning and GUI | [Software guide](../software/SOFTWARE_GUIDE.md) |
| Copied notebooks, measurement records and reconnecting | [Notebook run workflow](notebook-runs.md) |
| Client sessions, setup, acquisition and analysis | [Operations API](operations-api.md) |
| Software TES waveforms | [TES bias waveform guide](tes-bias-waveform.md) |
| Local software/RTL regressions and their limits | [Regression guide](../tests/README.md) |
| Full GroupTb simulation | [Build/server setup](../firmware/simulations/GroupTb/README_cosim.md), [client checks](../software/cosim/README_cosim.md) |
| Physical bench checks | [Hardware-test scripts](../software/hwtest/README.md) |
| Issues, acceptance and PR integration | [Development workflow](WORKFLOW.md) |
| Candidate selection and releases | [Release guide](RELEASE.md) |

## Design

- [Accumulator and integer/FP controllers](design/controllers/README.md)
- [Frame formats and channel identities](../firmware/common/DataChannelization.md)
- [Timing protocol](../firmware/common/TimingProtocol.md) and
  [cross-Group timing proposal](design/timing-distribution.md)
- [Logical and physical row mapping](design/row-mapping.md)
- [Muxed-run configuration and tune-point proposal](design/muxed-run-bringup.md)
- [FAS tuning and two-level discovery](design/fas-tuning.md)
- [Group variable I/O contracts](design/group-variables.md)
- [Fast-DAC force/override behavior](design/fastdac-override-race.md)
- [Wafer simulation model](../firmware/common/warm_tdm/sim/README.md) and
  [SQUID response shaping](design/squid-vphi-shaping/README.md)

## Dated technical references

These analyses retain their stated source revisions and assumptions. They
are useful evidence and rationale, not current tuning presets or acceptance.

- [RSSI/SRP bench evidence, September 2026](reference/rssi-srp-2026-09/README.md)
- [Historical measurement notebooks](reference/measurements/README.md)
- [Integer/FP path comparison](reference/pid-path-comparison.md)
- [MCE feedback-law comparison](reference/mce-controller-comparison.md)
- [Physical PID coefficient derivation](reference/pid-coefficients.md)
- [Recovered SQ1 feedback scale](reference/sq1-feedback-scale.md)
- [Recovered hardware tuning sequence](reference/hardware-tuning-sequence.md)

## Active work and generated API documentation

The [active-work index](plans/README.md) links unresolved investigations and
proposals. Issues own remaining acceptance; PRs own implementation review.
Session journals and completed audit inventories do not belong in this tree.

Sphinx sources are in [src](src/); build configuration is in
[Makefile](Makefile). Generated device pages in `src/generated/` are outputs
of the PyRogue documentation pipeline and should be regenerated with the
matching tree rather than used for session notes.
