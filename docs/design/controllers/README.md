# Accumulator and feedback controllers

These documents describe the implementation carried by `channelization` /
[PR #106](https://github.com/slaclab/warm-tdm/pull/106). Use matching firmware,
drivers and stream decoders. Publication of a design is separate from its
integration, generated-IP qualification, timing closure and hardware acceptance.

| Subject | Contract |
|---|---|
| Shared sampling front end and row association | [Accumulator](accumulator.md) |
| Integer retained feedback, precision and diagnostics | [Integer feedback](integer-feedback.md) |
| Masking, I changes, clearing and reconfiguration | [Integer lifecycle](integer-lifecycle.md) |
| Multiple wraps, reciprocal configuration and count bounds | [Integer flux wrapping](integer-flux-wrapping.md) |
| Float32 PI arithmetic, configuration and diagnostics | [Floating-point controller](floating-point.md) |

Both controllers retain fractional feedback between visits and round at the
DAC boundary. The integer path retains local fixed-point feedback plus a
signed net wrap count; the FP path retains unwrapped float32 feedback and
recomputes its wrap quotient. Their wrap rules and primary readout rounding
are different. Neither is specified as an MCE-equivalent controller.

[Regression procedures](../../../tests/README.md) distinguish numerical unit
tests, generated IP, full GroupTb, implementation timing and physical tests.
[#70](https://github.com/slaclab/warm-tdm/issues/70) owns controller acceptance,
[#90](https://github.com/slaclab/warm-tdm/issues/90) owns the test framework, and
[#82](https://github.com/slaclab/warm-tdm/issues/82) owns frame/file compatibility.
Candidate-specific results belong on those issues, not in a rolling design log.
