# Channelization: frame identity and file channels

[#82](https://github.com/slaclab/warm-tdm/issues/82) owns this feature through
acceptance. [PR #106](https://github.com/slaclab/warm-tdm/pull/106) reviews its
integration into `pre-release`. The branch also carries other work: use the
[plans index](../README.md) to find its separate owners.

## Goal and contract

Make readout, PID-debug and waveform frames interpretable from their bodies,
while keeping each board's data separate in a shared file. The canonical byte,
channel and timebase contract is
[DataChannelization.md](../../../firmware/common/DataChannelization.md).

The chosen design is a shared 16-byte identity header: format type/version,
board identity, reserved/zero group identity, and a 64-bit nanosecond timestamp.
Type/version select the decoder; body length validates the selected format.
File channel is a cross-checkable routing hint. A renumbered capture must retain
its body identity, and inconsistent channel/body identities must be detectable.

Board-local streams are PID debug 1, waveform 8 and readout 9. Files use
`board * 16 + stream`; config remains 255. `_Channels.py` is the shared encoding
source for write and read paths. Per-column PID streams collapse onto stream 1,
with the body identifying the column. `groupId` semantics remain with
[#80](https://github.com/slaclab/warm-tdm/issues/80); this effort does not claim
multi-Group operation.

## Integration and scope boundaries

The original `cleanup` base supplied the resource interface, including
`GEN_PID_DEBUG_G`. The implementation is now consolidated with the FP/accumulator
and resource work in #106; #87/#88 are superseded review records. Use merges
when updating from `pre-release`, and review the combined diff after updating.

Framing, host decoders and live dispatch must land together as a matching
firmware/software pair. Required simulation and affected Vivado 2024.1 builds
precede integration. Physical acceptance may follow integration and stays open
on #82/#70 under [the workflow policy](../../WORKFLOW.md). There is no inherited
requirement to finish all analog tests before merging the implementation.

The following are separately owned:

- Controller/accumulator behavior and resource builds: #70; see
  [integer PID](../integer-pid/README.md) and [FP PID](../fp-dsp-pid/README.md).
- Regression infrastructure: #90; see [verification](../pid-cosim-verification/README.md).
- Existing leading-empty-readout/count defect: #100. A tolerant parser does not fix it.
- Offline PID diagnosis/comparison: #108, [analyzer proposal](../pid-debug-analysis/PLAN.md).
- Larger RSSI segments: #109, [transport proposal](../rssi-tuning/PLAN.md).

## Implementation map

| Component | Files / responsibility |
|---|---|
| File namespace and live routing | `_Channels.py`, `_HardwareGroup.py`, `PidDebugDispatch` |
| Shared header | `FrameHeaderPkg.vhd`, `FrameHeader` / format dispatch in `_DataFormats.py` |
| Readout / waveform emitters | `EventBuilder.vhd`, `WaveformCapture.vhd` |
| Fixed/FP debug emitters | `AdcDsp.vhd`, `AdcDspFp.vhd` |
| Live decoders | `_PidDebugger.py`, `_PidDebuggerFp.py` |
| File readers and analysis | `operations/streamreader.py`, `operations/data.py`, canonical format helpers |

Source at audit revision `fae7151` contains the board namespace, waveform file
routing, tagged frames and PID stream collapse. Later integer changes use v3
(96-byte frame) for retained fractional feedback and the signed nine-bit count;
FP remains v1 (56-byte frame). Source presence and format unit tests do not
establish transport/timebase/multi-board acceptance.

## Verification guidance

Use the live checklist on #82. Important boundaries are:

1. Check emitted bytes against version-specific decoders, including signed
   fields, older v1/v2 integer data and malformed/truncated frames.
2. Exercise both the file parser and live per-column dispatch. Tree construction
   in emulate mode skips real stream/file wiring and cannot prove separation.
3. Capture matching firmware/software from at least two column boards; verify
   body identity, channels, timestamps and unambiguous column mapping for all
   streams. Preserve the config channel and test a channel/body mismatch.
4. Check standalone timebase initialization and monotonic behavior against the
   contract; do not equate a reserved nanosecond field with a tested external
   timing source. Future distributed time remains in
   [timing-distribution.md](../../design/timing-distribution.md).
5. Record exact revisions, generics, images and results on #82, sharing the
   same candidate evidence with #70 where appropriate.

The [original phased plan](https://github.com/slaclab/warm-tdm/blob/fae7151/docs/plans/channelization/PLAN.md)
preserves the earlier alternatives and implementation chronology. Its old
stack, worktree, uncommitted-work and hardware-before-merge statements are
superseded by this scope/ownership guide.
