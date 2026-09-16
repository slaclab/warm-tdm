# Sensor-wafer model documentation

The model foundation is integrated into `pre-release`. Architecture, topology,
electrical interfaces, equation conventions, calibration limits, and literature
provenance now live in the
[simulation README](../../../firmware/common/warm_tdm/sim/README.md).
It distinguishes the integrated foundation from later variation and V–Φ shaping
carried by the `channelization` integration.

The [PID coefficient analysis](PID_COEFFICIENTS.md) remains an intentional design
record for the physical-unit work on
[#44](https://github.com/slaclab/warm-tdm/issues/44); its numerical examples are
historical, not a current tuned configuration. Original model acceptance is
recorded on [#98](https://github.com/slaclab/warm-tdm/issues/98), and later PID
fixture/closed-loop comparisons belong to
[#70](https://github.com/slaclab/warm-tdm/issues/70).

This pointer preserves existing issue and wiki links. The superseded phased
implementation plan and dated status log remain available in Git history.
