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

## 2026-05-15: First run & bug fixes

### Issues encountered

1. **IP black-box error** — Initial run failed because `FpMac` and `Int2Fp` IP OOC synthesis
   outputs (`.dcp` files in `.gen/sources_1/ip/`) were missing when new impl runs launched.
   The standard `impl_1` had these from its prior build, but newly-created runs didn't.
   **Fix:** Added explicit IP OOC synthesis step in `power_explore.tcl` that ensures
   `FpMac_synth_1` and `Int2Fp_synth_1` complete before launching impl runs.

2. **Run status check mismatch** — Runs with `POST_ROUTE_PHYS_OPT_DESIGN` enabled
   (`impl_1`, `impl_perf_power_opt`) report status "Not started phys_opt_design (Post-Route)"
   after routing, not "route_design Complete!". This caused the report/summary sections to
   skip them.
   **Fix:** Changed completion detection to check for existence of `*_routed.dcp` in the
   run directory instead of matching a specific status string.

### Results (XC7K325T, Vivado 2024.1)

| Run | Strategy | Total (W) | Dynamic (W) | Static (W) | WNS (ns) |
|-----|----------|-----------|-------------|------------|-----------|
| impl_1 | Perf_ExplorePostRoutePhysOpt (baseline) | **4.130** | 3.908 | 0.222 | 0.188 |
| impl_perf_power_opt | Perf_ExplorePostRoutePhysOpt + power opts | **3.776** | 3.557 | 0.219 | 0.038 |
| impl_power_default | Power_DefaultOpt | **3.763** | 3.544 | 0.218 | 0.153 |
| impl_power_area | Power_ExploreArea | **3.929** | 3.709 | 0.220 | 0.279 |
| impl_synth_power | Power_DefaultOpt (from synth_power/AreaOpt) | **3.937** | 3.719 | 0.218 | 0.153 |

### Analysis

- **Best power: `impl_power_default`** at 3.763W — **8.9% reduction** vs baseline (4.130W)
- **Lowest-risk option: `impl_perf_power_opt`** at 3.776W — keeps the performance strategy,
  just enables POWER_OPT_DESIGN + POST_PLACE_POWER_OPT_DESIGN steps. 8.6% reduction.
- Area-optimized synthesis (`synth_power` → `impl_synth_power`) did not help; it's worse
  than `impl_power_default` which uses the standard synthesis netlist
- All runs meet timing comfortably (positive WNS)
- Savings are almost entirely from dynamic power reduction (~350-365 mW); static unchanged

### Current state
- Power exploration complete with results
- `power_explore.tcl` bugs fixed (IP synth step, status detection)
- Next: decide which strategy to adopt for production builds
