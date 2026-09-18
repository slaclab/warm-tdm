# Shared ADC accumulator

`AdcAccumulator` separates sampling from integer/FP feedback computation. It
allows one row's controller work to overlap later sampling, rather than making
the row period the sum of both latencies. The practical schedule still has to
cover sampling, state-machine overhead, RAM access and DAC delivery. Historical
12/34/40-cycle sketches are not supported row-rate limits.

## Data and row association

`DataPath` selects ADC streams and matching `LocalTimingType` records, then
instantiates an accumulator for each column ahead of either `AdcDsp` or
`AdcDspFp`. Waveform capture still sees the ADC stream separately.

The accumulator owns baseline RAM. On `rowStrobe` it clears the running sum
and sample count and captures sequence/DAQ flags. At `firstSample` it captures
the applied SQ1-feedback DAC. It then accumulates valid ADC samples minus the
baseline and emits an `AdcAccumResultType` pulse after the last sample.
The record carries a 32-bit signed error sum, eight-bit sample count, logical
row, 14-bit captured feedback DAC, and sequence/DAQ-start flags. Register and
record definitions remain authoritative in `WarmTdmPkg.vhd`,
`AdcAccumulator.vhd` and `_AdcAccumulator.py`.

Capturing feedback at `rowStrobe` is too early: the fast-DAC path has not yet
applied the new row's value and can associate each row with its predecessor.
The capture at `firstSample` preserves the required association. Controllers
must also wait for the selected row's state RAM output before computing;
changing the row address and consuming the old RAM output in the same stage
reintroduces cross-row state errors.

The accumulator's 32-bit sum is shared by both controllers. The integer DSP
uses a saturating fixed-point conversion to its 18-bit error range
(-131072..131071); slicing the low 18 bits would wrap a large positive error
negative. FP converts the full signed sum. Do not move integer saturation
into the shared front end and silently reduce the FP input range.

There is no ready/backpressure handshake on `accumValid`. A busy controller
can miss a visit; qualify the intended schedule and the controller's actual
loss diagnostics. Do not interpret the original plan's proposed dropped-row
counter as an implemented accumulator guarantee.

## Integration and verification

The split changes baseline ownership and the driver/register tree. Use matching
firmware and Python modules. Row capacity must match `ROW_ADDR_BITS_G`; runtime
capacity discovery remains [#73](https://github.com/slaclab/warm-tdm/issues/73).

Whole-path tests drive ADC data through the real accumulator and feed actual
DAC writes into later visits. Include independently varying rows, nonzero
baselines, overflow rails, timing boundaries and retained feedback. Preserve
the frozen pre-split reference; intentional later numerical changes use
independent expectations rather than replacing that golden.

See [integer feedback](integer-feedback.md), [FP PI](floating-point.md), and
[regression procedures](../../../tests/README.md). Controller/system/build
acceptance belongs to [#70](https://github.com/slaclab/warm-tdm/issues/70).
