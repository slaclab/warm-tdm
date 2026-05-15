##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

## Power Strategy Exploration Script
## Launches all power-focused synth/impl runs, waits for completion,
## and generates comparative power reports.

########################################################
## Setup
########################################################
source -quiet $::env(RUCKUS_DIR)/vivado/env_var.tcl
source -quiet $::env(RUCKUS_DIR)/vivado/proc.tcl

open_project -quiet ${VIVADO_PROJECT}

# Source properties and project setup to ensure runs exist
source -quiet ${RUCKUS_DIR}/vivado/properties.tcl

set NUM_JOBS $::env(PARALLEL_SYNTH)

########################################################
## Define the exploration runs
########################################################
set synth_runs [list synth_1 synth_power]
set impl_runs [list impl_1 impl_power_default impl_power_area impl_perf_power_opt impl_synth_power]

########################################################
## Ensure IP OOC synthesis is complete
########################################################
puts "================================================================"
puts "Power Exploration: Ensuring IP synthesis is up to date"
puts "================================================================"

set ip_synth_runs [list]
foreach ip [get_ips] {
    set ip_run [get_runs -quiet ${ip}_synth_1]
    if { $ip_run ne "" } {
        lappend ip_synth_runs $ip_run
    }
}

if { [llength $ip_synth_runs] > 0 } {
    set ip_to_launch [list]
    foreach run $ip_synth_runs {
        set status [get_property STATUS [get_runs $run]]
        if { $status ne "synth_design Complete!" } {
            puts "  Queuing IP synth: $run"
            reset_run $run
            lappend ip_to_launch $run
        } else {
            puts "  Already complete: $run"
        }
    }
    if { [llength $ip_to_launch] > 0 } {
        puts "  Launching [llength $ip_to_launch] IP synth runs..."
        launch_runs $ip_to_launch -jobs $NUM_JOBS
        foreach run $ip_to_launch {
            wait_on_run $run
            set status [get_property STATUS [get_runs $run]]
            if { $status ne "synth_design Complete!" } {
                puts "ERROR: IP synth $run failed with status: $status"
                close_project
                exit -1
            }
        }
    }
}

puts "IP synthesis up to date."

########################################################
## Launch synthesis runs
########################################################
puts "================================================================"
puts "Power Exploration: Launching synthesis runs"
puts "================================================================"

set synth_to_launch [list]
foreach run $synth_runs {
    set status [get_property STATUS [get_runs $run]]
    if { $status ne "synth_design Complete!" } {
        puts "  Queuing: $run"
        reset_run $run
        lappend synth_to_launch $run
    } else {
        puts "  Already complete: $run"
    }
}

if { [llength $synth_to_launch] > 0 } {
    puts "  Launching [llength $synth_to_launch] synth runs in parallel..."
    launch_runs $synth_to_launch -jobs $NUM_JOBS
}

foreach run $synth_runs {
    puts "  Waiting on: $run"
    wait_on_run $run
    set status [get_property STATUS [get_runs $run]]
    if { $status ne "synth_design Complete!" } {
        puts "ERROR: $run failed with status: $status"
        close_project
        exit -1
    }
}

puts "All synthesis runs complete."

########################################################
## Launch implementation runs
########################################################
puts "================================================================"
puts "Power Exploration: Launching implementation runs"
puts "================================================================"

set impl_to_launch [list]
foreach run $impl_runs {
    set progress [get_property PROGRESS [get_runs $run]]
    set status [get_property STATUS [get_runs $run]]
    if { $progress eq "100%" || [string match "*route_design Complete*" $status] } {
        puts "  Already complete: $run (status: $status)"
    } else {
        puts "  Queuing: $run"
        reset_run $run
        lappend impl_to_launch $run
    }
}

if { [llength $impl_to_launch] > 0 } {
    puts "  Launching [llength $impl_to_launch] impl runs in parallel..."
    launch_runs $impl_to_launch -to_step route_design -jobs $NUM_JOBS
}

foreach run $impl_runs {
    puts "  Waiting on: $run"
    if { [catch {wait_on_run $run} err] } {
        puts "WARNING: wait_on_run failed for $run: $err"
    }
    set routed_dcp [glob -nocomplain [get_property DIRECTORY [get_runs $run]]/*_routed.dcp]
    if { $routed_dcp eq "" } {
        set status [get_property STATUS [get_runs $run]]
        puts "WARNING: $run did not produce a routed checkpoint (status: $status)"
    }
}

puts "All implementation runs complete."

########################################################
## Generate power reports
########################################################
puts "================================================================"
puts "Power Exploration: Generating power reports"
puts "================================================================"

set report_dir "${OUT_DIR}/power_reports"
file mkdir $report_dir

foreach run $impl_runs {
    set status [get_property STATUS [get_runs $run]]
    set routed_dcp [glob -nocomplain [get_property DIRECTORY [get_runs $run]]/*_routed.dcp]
    if { $routed_dcp ne "" } {
        puts "  Generating report for: $run"
        open_run $run
        report_power -file "${report_dir}/${run}_power.rpt"
        report_power -format csv -file "${report_dir}/${run}_power.csv"
        report_utilization -file "${report_dir}/${run}_utilization.rpt"
        report_timing_summary -file "${report_dir}/${run}_timing.rpt" -max_paths 10
        close_design
    } else {
        puts "  Skipping $run (no routed checkpoint found)"
    }
}

########################################################
## Summary comparison
########################################################
puts "================================================================"
puts "Power Exploration: Summary"
puts "================================================================"
puts ""
puts [format "%-25s %-12s %-12s %-12s %-10s" "Run" "Total(W)" "Dynamic(W)" "Static(W)" "WNS(ns)"]
puts [format "%-25s %-12s %-12s %-12s %-10s" "---" "--------" "----------" "---------" "-------"]

foreach run $impl_runs {
    set routed_dcp [glob -nocomplain [get_property DIRECTORY [get_runs $run]]/*_routed.dcp]
    if { $routed_dcp ne "" } {
        open_run $run

        # Extract power numbers
        set total_power "N/A"
        set dynamic_power "N/A"
        set static_power "N/A"
        catch {
            set total_power [get_property POWER [current_design]]
        }
        catch {
            set dynamic_power [get_property DYNAMIC_POWER [current_design]]
        }
        catch {
            set static_power [get_property STATIC_POWER [current_design]]
        }

        # Extract WNS
        set wns "N/A"
        catch {
            set wns [get_property STATS.WNS [get_runs $run]]
        }

        puts [format "%-25s %-12s %-12s %-12s %-10s" $run $total_power $dynamic_power $static_power $wns]
        close_design
    }
}

puts ""
puts "Detailed reports written to: ${report_dir}/"
puts "================================================================"

close_project
exit 0
