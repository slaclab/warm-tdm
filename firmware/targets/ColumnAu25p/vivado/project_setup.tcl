##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

########################################################
## Power Strategy Exploration Runs
########################################################

# Get the flow strings from the default runs for portability across Vivado versions
set impl_flow [get_property FLOW [get_runs impl_1]]
set synth_flow [get_property FLOW [get_runs synth_1]]

# -- Synthesis: area-optimized run (fewer resources = less dynamic power) --
if { [llength [get_runs -quiet synth_power]] == 0 } {
    create_run synth_power -flow $synth_flow -constrset constrs_1 -strategy Flow_AreaOptimized_high
}
set_property strategy Flow_AreaOptimized_high [get_runs synth_power]

# -- Impl: Power_DefaultOpt strategy (from default synth) --
if { [llength [get_runs -quiet impl_power_default]] == 0 } {
    create_run impl_power_default -parent_run synth_1 -flow $impl_flow -strategy Power_DefaultOpt
}
set_property strategy Power_DefaultOpt [get_runs impl_power_default]
set_property STEPS.POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_power_default]
set_property STEPS.POST_PLACE_POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_power_default]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_power_default]

# -- Impl: Power_ExploreArea strategy (from default synth) --
if { [llength [get_runs -quiet impl_power_area]] == 0 } {
    create_run impl_power_area -parent_run synth_1 -flow $impl_flow -strategy Power_ExploreArea
}
set_property strategy Power_ExploreArea [get_runs impl_power_area]
set_property STEPS.POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_power_area]
set_property STEPS.POST_PLACE_POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_power_area]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_power_area]

# -- Impl: Performance strategy + power opt steps enabled (from default synth) --
if { [llength [get_runs -quiet impl_perf_power_opt]] == 0 } {
    create_run impl_perf_power_opt -parent_run synth_1 -flow $impl_flow -strategy Performance_ExplorePostRoutePhysOpt
}
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_perf_power_opt]
set_property STEPS.POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_perf_power_opt]
set_property STEPS.POST_PLACE_POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_perf_power_opt]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_perf_power_opt]

# -- Impl: Power_DefaultOpt from power-aware synthesis --
if { [llength [get_runs -quiet impl_synth_power]] == 0 } {
    create_run impl_synth_power -parent_run synth_power -flow $impl_flow -strategy Power_DefaultOpt
}
set_property strategy Power_DefaultOpt [get_runs impl_synth_power]
set_property STEPS.POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_synth_power]
set_property STEPS.POST_PLACE_POWER_OPT_DESIGN.IS_ENABLED true [get_runs impl_synth_power]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_synth_power]
