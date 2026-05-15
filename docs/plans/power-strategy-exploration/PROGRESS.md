# Power Strategy Exploration — Progress

## 2026-05-14: Initial investigation

- Examined ruckus build infrastructure (`build.tcl`, `properties.tcl`,
  `system_vivado.mk`)
- Confirmed ruckus is single-run (`synth_1` + `impl_1`) by default
- Confirmed the target already uses `Performance_ExplorePostRoutePhysOpt`
- Found that `project_setup.tcl` has power opt steps commented out but available
- Decided on approach: Vivado native multi-run configured in `project_setup.tcl`
- Created plan document

## 2026-05-14: Implementation

### Files modified/created

1. **`firmware/targets/ColumnFpgaBoard325Coordinator10G/vivado/project_setup.tcl`** — rewritten
   - Creates `synth_power` run with `-power_opt` synthesis argument
   - Creates 4 impl runs:
     - `impl_power_default` — Power_DefaultOpt strategy (from synth_1)
     - `impl_power_area` — Power_ExploreArea strategy (from synth_1)
     - `impl_perf_power_opt` — Performance_ExplorePostRoutePhysOpt + power opts enabled (from synth_1)
     - `impl_synth_power` — Power_DefaultOpt strategy (from synth_power)
   - All power impl runs have POWER_OPT_DESIGN and POST_PLACE_POWER_OPT_DESIGN enabled
   - Guards against re-creation with `[get_runs -quiet]` checks

2. **`firmware/targets/ColumnFpgaBoard325Coordinator10G/vivado/power_explore.tcl`** — new
   - Launches all synth runs, waits, validates
   - Launches all impl runs to route_design step, waits
   - Generates per-run reports: power, utilization, timing summary (both .rpt and .csv)
   - Prints a comparison table (Total/Dynamic/Static power + WNS)

3. **`firmware/targets/ColumnFpgaBoard325Coordinator10G/Makefile`** — added `power_explore` target

### Usage

```bash
cd firmware/targets/ColumnFpgaBoard325Coordinator10G

# Normal build (unchanged)
make

# Launch power exploration (all strategies)
make power_explore

# Or open GUI to see/launch runs interactively
make gui
```

### Current state
- Implementation complete
- Not yet tested against a live Vivado build
- Next: run `make power_explore` and analyze results
