# Integer PID MAC reuse review

## Scope and status

September 18, 2026 source review at `dd466894de965d48a9756901b2ea830f88e1a4fe`.
At the initial review, `AdcDsp.vhd` matched HEAD; its latest change was
`0009740`. The audit below describes that revision; the follow-up cleanup is
recorded at the end. The question is
whether recent lifecycle, multi-flux and pipeline changes preserve the shared
integer MAC. Build/resource acceptance remains with [#70](https://github.com/slaclab/warm-tdm/issues/70).

**The current RTL preserves the shared operand/result register structure.**
There is no source-level evidence that the new wrap states require additional
MACs. Actual DSP48 count and register packing are unverified: this checkout's
`firmware/build/` contains simulation outputs, no Column synthesis reports or
checkpoints, and Vivado 2024.1 is unavailable locally. The follow-up removes
the redundant temporary and adds comments without changing arithmetic or
latency. Simulation cannot establish the physical resource mapping.

## Operand and result audit

The six runtime multiplication sites in
[`AdcDsp.vhd`](../../../firmware/common/warm_tdm/rtl/AdcDsp.vhd) all evaluate:

```vhdl
resize(r.pidResult + (r.pidCoef * r.pidMultiplier), <result template>)
```

| State | Source line at reviewed revision | Destination |
|---|---:|---|
| `PID_P_S` | 864 | `v.pidResult` |
| `PID_I_S` | 876 | `v.pidResult` |
| `PID_D_S` | 889–890 | `pidResultNext`, immediately copied to `v.pidResult` |
| `FLUX_ESTIMATE_S` | 947 | `v.pidResult` |
| `FLUX_PRODUCT_S` | 960 | `v.pidResult` |
| `DATA_STREAM_FLUX_JUMP_1_S` | 1056 | `v.pidResult` |

Every site reads the same current-cycle registers. Operand selection happens
when loading `v.pidCoef` and `v.pidMultiplier` for the following state. There
are no state-specific multipliers with independent operand registers.

- `pidCoef`: `sfixed(0 downto -23)`, 24 signed bits.
- `pidMultiplier`: `sfixed(17 downto 0)`, 18 signed bits.
- Product: `sfixed(18 downto -23)`, 42 bits.
- Addition: `sfixed(19 downto -23)`, 43 bits before resize.
- `pidResult` and `pidResultNext`: `sfixed(18 downto -23)`, 42 bits.

`pidResultNext` is a process variable, assigned before use in the same case
branch. It adds no clock boundary or independent stored result. Its type and
resize bounds exactly match `v.pidResult`; the template argument supplies
bounds, not another arithmetic input. It now has no other consumers, so the
D stage could use the same direct assignment as the other five sites purely
to make the convention clearer. The alias does not establish DSP duplication.

The new wrap count is 19 bits, but the MAC ports were not widened. The count
is loaded into the 24-bit coefficient side for reconstructed readout; the
quantum occupies the 18-bit side. The 43-bit `fluxCandidate` is a separate
feedback-add/wrap path, not a wider multiplier operand. The comment about
`iSfixed * accumError` in `FLUX_COMMIT_S` describes a sign test; that state
does not perform a multiplication.

## History

- `5d326dd` introduced the D-stage temporary and a separate
  `iContribution := resize(iSfixed * r.accumError, iContribution)` for
  anti-windup. That second product had different operands and was evaluated
  alongside the D-stage MAC. Its actual hardware mapping is unknown.
- `33599a9` retained that structure while snapshotting visit configuration.
- `558cad9` added the two wrap MAC states using the existing registers and
  removed `iContribution`, replacing it with sign comparisons. The temporary
  D-stage result became a redundant alias.
- `0009740` added `FLUX_COMMIT_S` and `DAC_ROUND_S`. It did not alter any MAC
  expression or MAC operand/result width.

Thus the recent multi-flux change removed the separate arithmetic expression
that was a more plausible source of additional multiplication hardware.
Whether synthesis previously optimized that expression away also requires a
netlist; do not claim a measured DSP reduction from this source change.

## Sharing versus DSP packing

Identical expressions over identical register bits are candidates for common
logic merging. That is stronger evidence for sharing than merely placing
different multiplications in mutually exclusive FSM states. It is still an
inference from RTL, not a measured utilization result.

The 24-by-18 product fits the 7-series DSP48E1 multiplier, and the 43-bit sum
fits its 48-bit arithmetic path. See AMD's
[DSP48E1 reference](https://docs.amd.com/r/2024.1-English/ug953-vivado-7series-libraries/DSP48E1).
One shared DSP48 for this MAC per integer `AdcDsp` is the expected mapping to
check, not a guarantee. There are eight column instances in `DataPath`;
filters and other modules contribute additional DSPs to the board total.

[`FixedPkg.vhd`](../../../firmware/common/warm_tdm/rtl/FixedPkg.vhd) selects
saturating overflow. Each MAC resize clamps the 43-bit sum to 42 bits. There
is no fractional-bit removal in this resize, so the MAC resize is saturation,
not fractional rounding. The feedback-to-DAC rounding is a different path.
Saturation/control logic can affect absorption of the result register and
timing even when the multiplier is shared. There is no explicit product
register separating multiply and add. Inspect the actual DSP's `AREG`,
`BREG`, `MREG`, `PREG`, feedback connections, and surrounding fabric logic.

AMD documents that Vivado attempts MAC inference and register absorption;
it does not promise a particular packing for every expression. Its
`resource_sharing=auto` setting is timing-dependent, and `USE_DSP` controls
arithmetic mapping rather than declaring that several operations must share
one physical instance. See [MAC implementation](https://docs.amd.com/r/2024.1-English/ug901-vivado-synthesis/Macro-Implementation-on-DSP-Block-Resources),
[synthesis settings](https://docs.amd.com/r/2024.1-English/ug901-vivado-synthesis/Using-Synthesis-Settings),
and [USE_DSP](https://docs.amd.com/r/2024.1-English/ug901-vivado-synthesis/USE_DSP).
No explicit resource-sharing override was found in this checkout's target,
common or ruckus Tcl/Makefiles; the actual project's settings need inspection.

## Netlist confirmation

Use the existing Vivado 2024.1 `ColumnFpgaBoard325Int10G` project and open its
completed synthesized design. Record its source revision, generics and
synthesis strategy. Then run these queries in the Tcl console:

```tcl
get_property STEPS.SYNTH_DESIGN.ARGS.RESOURCE_SHARING [get_runs synth_1]
report_utilization -hierarchical -file adc_dsp_mac_utilization.rpt
set adcMacCells [get_cells -hierarchical -filter {REF_NAME =~ DSP48* && NAME =~ *U_AdcDsp_1/*}]
puts "DSP48 cells below integer AdcDsp instances: [llength $adcMacCells]"
foreach adcMacCell $adcMacCells {
   puts "\n$adcMacCell"
   report_property $adcMacCell
}
```

These Vivado queries have not been run locally. Inspect the hierarchical
report and schematic for each column: a total count alone cannot distinguish
an additional wrap MAC from a separately mapped adder. A missing hierarchy
match is not a zero-DSP result; with flattened/renamed hierarchy, enumerate
all `REF_NAME =~ DSP48*` cells and trace their operands and result cones.

Verify that P/I/D, reciprocal estimate, jump product, and reconstructed
readout reach the same multiplier/adder instance. Check saturation and
feedback placement as well as DSP count. Repeat on the implemented design
to catch physical optimization changes and inspect the MAC timing paths.
For a historical comparison, use identical target, generics, tool version
and synthesis settings at `33599a9`, `558cad9`, and `0009740`.

If duplication is observed, first consolidate the repeated arithmetic into
one expression and keep state-specific operand loading and result enables.
Preserve per-stage saturation, reset/clear priority, RAM-write data and visit
latency. Re-run the integer regression suites listed in
[the timing review](TIMING_REVIEW.md), then compare synthesis mapping. Adding
an attribute or renaming a temporary is not a substitute for that comparison.

## Initial review validation

Compared the six MAC sites, fixed-point types and surrounding register loads
against Git history; enumerated runtime multiplications after excluding
comments and constant expressions. Checked the target generics, build
directory and available tools. No functional tests were re-run because no
RTL changed, and no synthesis/resource result is claimed. The next required
evidence is the Vivado netlist inspection above.

## Follow-up cleanup

Removed `pidResultNext` and its immediate copy; `PID_D_S` now assigns the MAC
expression directly to `v.pidResult`, matching the other five MAC states.
Added short purpose comments at the start of `FLUX_JUMP_S`,
`FLUX_ESTIMATE_S`, `FLUX_COUNT_S`, `FLUX_PRODUCT_S`, `FLUX_REMAINDER_S`,
`FLUX_CORRECT_S`, and `FLUX_COMMIT_S`. No arithmetic, state transitions,
register widths or visit latency changed.

Validation: `make rtl_import` and `git diff --check` passed. The existing
`full_mac_and_retained_ram_extrema` and `bounded_visit_schedule_and_dac_latency`
cocotb checks passed in both configured row-count/polarity combinations:
four selected cocotb cases across two pytest configurations. The other three
cases in each configuration were deselected by `COCOTB_TEST_FILTER`. A source
comparison also confirmed that only the alias substitution and comments
changed, and that the imported RTL matched the edited source. Logs are
`/private/tmp/warm-tdm-mac-cleanup-import.log` and
`/private/tmp/warm-tdm-mac-cleanup-regression.log`. DSP48 mapping still
requires Vivado.
