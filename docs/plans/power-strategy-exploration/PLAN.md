# Power Strategy Exploration

## Goal

Reduce FPGA power consumption by exploring multiple Vivado synthesis and
implementation strategies per target. Use Vivado's native multi-run capability
configured in `project_setup.tcl` so that all runs are visible in the GUI and
can be launched from a single project.

## Scope

- Initially target: `ColumnFpgaBoard325Coordinator10G` (Kintex-7 K325T)
- Extend to other targets once the approach is validated

## Approach: Vivado Native Multi-Run in project_setup.tcl

### How Vivado Multi-Run Works

Vivado projects support multiple synthesis and implementation runs. Each run
has its own strategy, directives, and results directory. Runs sharing a
synthesis parent can be launched in parallel.

```tcl
# Create an additional impl run parented to synth_1
create_run impl_power_opt -parent_run synth_1 -flow {Vivado Implementation 2023}
set_property strategy Power_DefaultOpt [get_runs impl_power_opt]
```

### Strategy Matrix

We will create impl runs exploring these axes:

| Run Name | Strategy | Key Settings |
|----------|----------|--------------|
| `impl_1` (default) | Performance_ExplorePostRoutePhysOpt | Current baseline |
| `impl_power_default` | Power_DefaultOpt | Vivado's built-in power strategy |
| `impl_power_explore` | Power_ExploreArea | Power + area trade-off |
| `impl_perf_power_opt` | Performance_ExplorePostRoutePhysOpt | Baseline + POWER_OPT + POST_PLACE_POWER_OPT enabled |

Additional synth strategies to explore:

| Run Name | Key Settings |
|----------|--------------|
| `synth_1` (default) | Current baseline (FLATTEN_HIERARCHY none) |
| `synth_power` | `-power_opt` synth arg (Vivado power-aware synthesis) |

### Integration with Ruckus

Ruckus's `build.tcl` only drives `synth_1` → `impl_1`. We preserve this so
that `make` continues to produce the normal build. The additional runs are:

1. **Created** in `vivado/project_setup.tcl` (so they exist in every project open)
2. **Launched** via:
   - The Vivado GUI (right-click → Launch Runs), or
   - A new Makefile target `make power_explore` that invokes a custom TCL script

### Files to Create/Modify

1. `firmware/targets/ColumnFpgaBoard325Coordinator10G/vivado/project_setup.tcl`
   - Add `create_run` commands for the power-focused impl (and optionally synth) runs
   - Set strategy properties on each new run

2. `firmware/targets/ColumnFpgaBoard325Coordinator10G/vivado/power_explore.tcl` (new)
   - TCL script that launches all power exploration runs
   - Waits for completion
   - Generates and collects power reports (`report_power`)
   - Outputs a comparison summary

3. `firmware/targets/ColumnFpgaBoard325Coordinator10G/Makefile`
   - Add a `power_explore` target that invokes the exploration script

### Validation

- Confirm that `make` still produces a normal build using `impl_1`
- Confirm that `make gui` shows all runs in the project
- Confirm that `make power_explore` launches and reports on all runs
- Compare power reports across strategies to identify the best trade-off

## Power-Relevant Vivado Knobs

### Synthesis
- `-power_opt` argument to `synth_design`
- `-flatten_hierarchy` (less hierarchy = more optimization opportunity)
- `-gated_clock_conversion on`

### Implementation
- `POWER_OPT_DESIGN.IS_ENABLED true` — clock gating optimization
- `POST_PLACE_POWER_OPT_DESIGN.IS_ENABLED true` — post-placement power opt
- Strategy presets: `Power_DefaultOpt`, `Power_ExploreArea`
- Directive: `NoBramPowerOpt` (disable BRAM power opt if timing-critical)

## Open Questions

- Which targets should ultimately get multi-strategy runs? All, or only the
  power-critical ones?
- Should we track power results in version control (e.g. a CSV/JSON summary)?
- What is the acceptable timing degradation for power savings?
- Do we want to explore `CLOCK_LOW_FANOUT_THRESHOLD` or manual clock gating?
