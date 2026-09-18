# Integer PID implementation timing review

## Scope and evidence

September 18, 2026: source review of `AdcDsp.vhd` at `1c590f7` on
`channelization`; the latest change to that file is `558cad9` (multi-flux
wrapping). The user reported Timing 38-282 and RTSTAT-1/-2/-6 failures for
`ColumnFpgaBoard325Int10G`. Issue [#70](https://github.com/slaclab/warm-tdm/issues/70)
remains the integer PID acceptance owner.

The user approved the two-state fix. `AdcDsp.vhd` now adds `FLUX_COMMIT_S`
and `DAC_ROUND_S`, removes the combinational `finishFlux` tail, and consumes
registered wrap results and clipped feedback in those states respectively.
Local validation passed all 67 cocotb cases across 12 pytest configurations.
The failed build is not present under
the local `firmware/build/`, and Vivado is not available on the local PATH.
The failed run's Vivado version, source revision, utilization and congestion
reports have not been established. The repository requires Vivado 2024.1.
The user subsequently supplied a timing-path excerpt, recorded below; the
complete report has not been inspected locally. Pipelining is not yet proven
to resolve the routing failure.

The target selects `XC7K325TFFG676-2`, integer PID, 10G Ethernet and coordinator
mode. Entity defaults enable PID debug, disable the optional ADC filter,
select 128 rows and set RSSI window address size to 3. Its implementation
strategy is already `Performance_ExplorePostRoutePhysOpt`.

### Timing evidence supplied after the source review

The other agent inspected the build under
`/sdf/group/faders/users/bareese/projects/warm-tdm-channelization`, reading
`firmware/build/ColumnFpgaBoard325Int10G/ColumnFpgaBoard325Int10G_project.runs/impl_1/ColumnFpgaBoard_timing_summary_routed.rpt`.
The user pasted that agent's analysis and extracted cell chain:

- Launch: channel 0 `r_reg[fluxCandidate][-23]`.
- Capture: channel 0 `r_reg[sq1Fb][11]`.
- The excerpt explicitly reports 39 logic levels, including 21 CARRY4 cells.
- The accompanying analysis reports approximately 12.6 ns data-path delay
  against an 8 ns clock, WNS approximately -4.7 ns, and 1774 failing endpoints
  across eight channels. The full summary header was not included.

This supports the predicted candidate-to-DAC completion path as a measured
setup problem and strengthens the case for the proposed register boundaries.
The path starts at the least-significant fractional bit, traverses several
carry chains and LUT stages, and ends at the integer DAC register. The
excerpt also shows appreciable interconnect delay, so describing the delay
as purely logic delay would be inaccurate.

The other agent attributes the unrouted/conflicting nets to post-route
physical optimization attempting to fix this path. The pasted timing path
does not establish that causality; confirming it requires the routing and
physical-optimization logs. Keep that claim separate from the demonstrated
setup failure.

## Principal finding at the failed revision

`finishFlux` is a combinational Boolean, not another FSM state. Both
`FLUX_JUMP_S` and `FLUX_CORRECT_S` set it, causing the block after the case
statement to execute in the same clock interval. That block consumes
`v.fluxCandidate`, `v.visitFluxJumps` and `v.fluxNegative`: the newly computed
values, with no intervening register. The only sequential boundary is
`r <= rin`.

For the quantum-one bypass, the dependency chain is:

```text
r.fluxCandidate
  -> absolute value and fractional-zero detection
  -> excess and wrap count calculation
  -> signed candidate adjustment
  -> rail comparisons and clamp selection
  -> nearest-even DAC rounding / saturation
  -> r.sq1Fb on the next edge
```

Other branches use the candidate and wrap count to update integral admission,
the saturating net count and its sticky overflow flag. Those branches run in
parallel with the DAC branch; they are not all one serial arithmetic chain.
Quantum is runtime configuration, so using the nominal value 1239 does not
remove the quantum-one bypass from the implemented logic or timing analysis.

## State-by-state risk assessment

Line numbers refer to the reviewed revision of
[`AdcDsp.vhd`](../../../firmware/common/warm_tdm/rtl/AdcDsp.vhd).

| Priority | Location | Combinational work and implication |
|---|---|---|
| First | `FLUX_JUMP_S`, lines 907–945, plus `finishFlux`, 1046–1094 | 43-bit fixed-point magnitude, threshold/quantum classification, several candidate-update choices, then post-wrap completion. Quantum one additionally derives the update operand from the magnitude within the same cycle. The zero/one-wrap latency shortcut combines too many dependent operations. |
| First | `FLUX_CORRECT_S`, 975–985, plus `finishFlux` | Threshold comparison, conditional add/subtract and count increment feed the same clamp/round and net-count logic immediately. Splitting only `FLUX_JUMP_S` would leave this path. |
| First | `finishFlux`, 1046–1094 | Rail comparisons control anti-windup and feedback clipping. Updated jump count feeds signed count arithmetic, overflow detection and saturation. Clamped feedback immediately feeds DAC rounding. These operations need explicit register boundaries. |
| Second | `FLUX_COUNT_S`, 951–958 | Variable shift of the 42-bit raw MAC result, then a 19-bit increment, then operand selection for the next MAC. The five-bit shift control implies a variable shifter; synthesis can prune unused outputs. Check this after breaking flux completion. |
| Check reports | `PID_P_S`, `PID_I_S`, `PID_D_S`, `FLUX_ESTIMATE_S`, `FLUX_PRODUCT_S`, `DATA_STREAM_FLUX_JUMP_1_S` | Each uses the same 24-by-18 multiply plus 42-bit accumulator with saturating resize in one clock. There is no explicit product register. Inspect actual DSP48 mapping and register use before deciding to pipeline the MAC. The derivative subtraction in `PID_I_S` is a parallel operand-preparation path, not serial after that cycle's MAC. |
| Lower | `SQ1FB_ADJUST_S`, 899–905; `FLUX_REMAINDER_S`, 964–973 | Candidate formation is already registered separately. Remainder calculation also registers before correction. Preserve these boundaries. |
| Check fanout | Clear/enable dispatch, 632–743 | AXI decode, enable-edge detection and clear priority affect many datapath registers. The reported `fllEnable` net makes this worth inspecting, but source alone cannot establish its physical fanout or delay. |
| Lower | Entry, RAM preparation, debug and output states | Entry includes input saturation and row-mask selection; preparation largely selects RAM/seed values; output states mostly format registered data. None has the same visible arithmetic chain as flux completion. FIFO internals still require separate physical analysis. |

`FixedPkg.vhd` explicitly selects `fixed_round` and `fixed_saturate`.
Consequently `resize()` is not generally a wiring operation. The final
38-bit-to-14-bit conversion examines fractional bits and can increment the
integer result. Narrowing arithmetic results can also introduce overflow
selection. Widening and same-fraction resizes do not all incur rounding.
This was checked against the installed IEEE `fixed_generic_pkg` source.
The supplied excerpt measures total path depth, but the exact optimized
arithmetic widths and mapping of each carry segment remain to be checked.

## Implemented two-state fix

The arithmetic is preserved, with two common states added after both
ordinary/bypass completion and reciprocal cleanup:

```text
FLUX_JUMP_S (ordinary or quantum-one completion) --+
                                                +-> FLUX_COMMIT_S
FLUX_CORRECT_S ----------------------------------+      |
                                                       v
                                                  DAC_ROUND_S
                                                       |
                                                       v
                                           DATA_STREAM_FLUX_JUMP_0_S
```

- The wrap states register `fluxCandidate`, `visitFluxJumps` and direction.
  They do not execute a combinational completion tail.
- `FLUX_COMMIT_S` consumes only those registered values. It evaluates
  post-wrap rail clipping, admits/holds integral state, updates/saturates the
  net count and registers clamped `sq1FbFull` and associated RAM writes.
- `DAC_ROUND_S` consumes registered `sq1FbFull`, rounds it to `sq1Fb` and
  asserts the DAC-queue valid pulse. Output reconstruction then uses that
  rounded feedback and the updated total count.

This change adds two clocks (16 ns at 125 MHz) to every completed visit;
all existing states remain. The prior simulation record measured
16/21 clocks between accepted ordinary/reciprocal visits and 20/25 clocks to
the unstalled DAC-register sink. The updated regression measures:

| Path | Minimum accepted visit interval | DAC-register sink latency |
|---|---:|---:|
| Ordinary / single-wrap / quantum-one / quantum-zero clipping | 18 clocks / 144 ns | 22 clocks / 176 ns |
| Reciprocal multi-wrap | 23 clocks / 184 ns | 27 clocks / 216 ns |

These results pass in both eight-row/inverted-DAC and 256-row/normal-DAC
configurations. Each minimum interval accepts all ten visits in a burst;
one clock below it accepts five. Debug is disabled for this timing measurement.
The input is unbuffered, so increased occupancy must be accounted for in row
scheduling and in the regression expectations.

`FLUX_JUMP_S` still contains magnitude-to-update dependencies after this
split. If updated reports still identify that path, the next candidate
boundary is a separate magnitude/sign register ahead of wrap classification,
with further separation of quantum-one excess calculation from candidate
adjustment if needed. This change implements only the two requested states.
Registering the single-wrap threshold and the integral candidate/sign during
earlier available states can also remove work from flux completion. Do not
restore the original latency by folding dependent arithmetic back together.

The 43-bit candidate must retain its 23 fractional bits throughout wrapping.
Keep exact threshold behavior, quantum-zero clipping, quantum-one handling,
post-wrap directional anti-windup, signed 19-bit count saturation and its
sticky overflow flag. Preserve masked-row state, active-configuration
snapshots, disable/drain behavior, clear priority, RAM addressing and debug
word order. Do not remove saturation or replace rounding with truncation
without a separate range/behavior proof.

## Physical evidence and validation still needed

The RTSTAT names include candidate-update logic, `fllEnable`, and XPM-backed
debug-FIFO pipeline nets in several channels. These identify unresolved
routes, not necessarily the worst setup paths. Inspect the failed run's
route log for congestion and routing conflicts as well as its timing report.
AMD documents congestion analysis through
[`report_design_analysis`](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/Congestion?contentId=pSMkQ31LhD_iBC6NHCBpVw).

From the failed implementation design in Vivado 2024.1, collect:

```tcl
report_route_status -file adc_dsp_route_status.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file adc_dsp_timing_summary.rpt
report_timing -delay_type max -max_paths 50 -path_type full_clock_expanded -file adc_dsp_setup_paths.rpt
report_design_analysis -congestion -file adc_dsp_congestion.rpt
report_utilization -hierarchical -file adc_dsp_utilization.rpt
report_high_fanout_nets -file adc_dsp_high_fanout.rpt
```

Use startpoints/endpoints, logic-versus-net delay and congestion to prioritize
further changes. Check DSP48 mapping rather than assuming the repeated MAC
expression guarantees a particular resource count or pipeline placement.
The debug FIFOs use XPM in hardware and inferred implementations in the
local GHDL tests, so GHDL cannot qualify those physical routes.

Rebuild `ColumnFpgaBoard325Int10G` with Vivado 2024.1 and require complete
routing and passing timing before claiming the implementation failure fixed.

## Local regression validation

The visit-timing regression now checks nine scenarios: no wrap, plus both
signs of single wrap, quantum-one multi-wrap, quantum-zero clipping, and
reciprocal multi-wrap. Each checks a ten-visit burst at the minimum accepted
interval and one clock below it, exact DAC-write latency, DAC values and
reconstructed outputs against the independent rational reference.

`make rtl_import` passed. All **12 pytest configurations / 67 cocotb cases
passed**, with no failures or skips, in 830.04 seconds. Both existing
row-count/polarity configurations ran where supported; the basic-control and
historical-comparison suites retain their single configurations.

| Suite | Passing cocotb cases |
|---|---:|
| Multi-wrap arithmetic, extrema, overflow/masks, snapshots and expanded timing | 10 |
| Fractional feedback | 18 |
| Integral/state lifecycle | 12 |
| DAC delivery under stalls | 2 |
| Historical comparison (golden unchanged) | 1 |
| Flux direction, count, readout and anti-windup | 16 |
| Basic PID/control | 8 |

`git diff --check` and local document-link checks passed. Vivado implementation
and hardware acceptance remain open; simulation does not establish timing
closure. Logs are `/private/tmp/warm-tdm-flux-pipeline-import.log` and
`/private/tmp/warm-tdm-flux-pipeline-regression.log`.

Reproduce from the repository root:

```bash
make rtl_import
.venv/bin/python -m pytest -n 4 -q \
  tests/warm_tdm/adc_dsp/test_AdcDsp_multi_flux.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_fractional.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_lifecycle.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_delivery.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_bitexact_compare.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp_flux.py \
  tests/warm_tdm/adc_dsp/test_AdcDsp.py
```
