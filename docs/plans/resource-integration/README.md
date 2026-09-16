# Resource and compatibility integration

[#70](https://github.com/slaclab/warm-tdm/issues/70) owns the resource/build
obligations carried by [#106](https://github.com/slaclab/warm-tdm/pull/106).
Historical PR #88 isolates the earlier delta but is superseded for integration.

This includes `GEN_PID_DEBUG_G`, memory/FIFO implementation choices,
FastDacDriver BRAM use, row-address sizing, target generics, power-analysis
scripts and legacy Python/board-selector removal. Relevant source is in
`firmware/common/warm_tdm/rtl`, `firmware/targets`, and the board constructors.

- [Target organization](../../../firmware/targets/README.md) documents the
  integrated structure. Verify the actual release target matrix in `firmware/releases.yaml`
  against the candidate; static source checks do not establish a build.
- [Software cleanup](../sw-cleanup/PLAN.md) mixes changes already integrated
  through #67/#78 with legacy removal still carried by #106. Do not treat that
  old plan's completion statements as a pass for current imports/packaging.
- [#73](https://github.com/slaclab/warm-tdm/issues/73) remains separate: passing
  `maxRows` through software and slicing RAM addresses does not implement
  runtime firmware-capacity discovery and startup clamp/warn.
- [#109](https://github.com/slaclab/warm-tdm/issues/109) owns the proposed larger
  RSSI segments. Current `MAX_SEG_SIZE_G` is still 1024; window configurability
  is already part of this integration.

Required candidate checks are maintained on #70/#90: reconcile removed-driver
imports and test coverage, verify packaging paths, build the affected fixed/FP
and debug/memory/row-depth configurations with Vivado 2024.1, and record timing
and resource reports. Preserve pending hardware checks on their owning issues.
