# Power Strategy Exploration — Progress

## 2026-05-14: Initial investigation

- Examined ruckus build infrastructure (`build.tcl`, `properties.tcl`,
  `system_vivado.mk`)
- Confirmed ruckus is single-run (`synth_1` + `impl_1`) by default
- Confirmed the target already uses `Performance_ExplorePostRoutePhysOpt`
- Found that `project_setup.tcl` has power opt steps commented out but available
- Decided on approach: Vivado native multi-run configured in `project_setup.tcl`
- Created plan document

### Current state
- Plan written, not yet implemented
- Next: implement the `project_setup.tcl` changes and `power_explore.tcl` script
