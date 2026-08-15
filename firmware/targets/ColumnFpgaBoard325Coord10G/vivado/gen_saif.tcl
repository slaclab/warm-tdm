##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file, may be
## copied, modified, propagated, or distributed except according to the terms
## contained in the LICENSE.txt file.
##############################################################################
## Convert a VCD file from VCS simulation into SAIF for Vivado power analysis
##
## Usage:
##   vivado -mode batch -source gen_saif.tcl -tclargs <vcd_file> [dcp_file]
##
## Arguments:
##   vcd_file  - Path to VCD file dumped from VCS GroupTb simulation
##   dcp_file  - (Optional) Path to routed DCP. Defaults to the standard
##               build location.
##
## Output:
##   Writes SAIF file to the impl_1 directory as:
##     <project>_power.saif
##   This file is automatically picked up by post_route_run.tcl on next build.
##
## The VCD should be scoped to the ColumnFpgaBoard instance in the sim hierarchy:
##   /GroupTb/GEN_COL_BOARDS[0]/U_ColumnFpgaBoardSim/U_ColumnFpgaBoard/U_ColumnFpgaBoard_1
##############################################################################

if {$argc < 1} {
    puts "ERROR: Must provide VCD file path"
    puts "Usage: vivado -mode batch -source gen_saif.tcl -tclargs <vcd_file> \[dcp_file\]"
    exit 1
}

set vcd_file [lindex $argv 0]

if {![file exists $vcd_file]} {
    puts "ERROR: VCD file not found: $vcd_file"
    exit 1
}

# Default DCP path based on standard ruckus build location
set script_dir [file dirname [file normalize [info script]]]
set target_dir [file dirname $script_dir]
set target_name [file tail $target_dir]
set build_dir [file normalize "${target_dir}/../../build/${target_name}"]
set impl_dir "${build_dir}/${target_name}_project.runs/impl_1"
set default_dcp "${impl_dir}/ColumnFpgaBoard_routed.dcp"

if {$argc >= 2} {
    set dcp_file [lindex $argv 1]
} else {
    set dcp_file $default_dcp
}

if {![file exists $dcp_file]} {
    puts "ERROR: DCP file not found: $dcp_file"
    puts "Build the target first, or provide the DCP path as the second argument."
    exit 1
}

set saif_file "${impl_dir}/ColumnFpgaBoard325Coordinator_power.saif"

puts "==============================================="
puts "VCD to SAIF Conversion"
puts "==============================================="
puts "VCD file:  $vcd_file"
puts "DCP file:  $dcp_file"
puts "SAIF file: $saif_file"
puts "==============================================="

# Open the routed design
open_checkpoint $dcp_file

# Read VCD and convert to SAIF
# -scope maps the VCD hierarchy to the design top
# The VCD was dumped from:
#   /GroupTb/GEN_COL_BOARDS[0]/U_ColumnFpgaBoardSim/U_ColumnFpgaBoard/U_ColumnFpgaBoard_1
# which corresponds to the synthesized top "ColumnFpgaBoard"
read_vcd -strip_path {GROUPTB/GEN_COL_BOARDS(0)/U_COLUMNFPGABOARDSIM/U_COLUMNFPGABOARD/U_COLUMNFPGABOARD_1} $vcd_file

# Write SAIF
write_saif -force $saif_file

puts "==============================================="
puts "SAIF written to: $saif_file"
puts "Re-run the build or use post_route_run.tcl to"
puts "generate an updated power report."
puts "==============================================="

close_design
exit 0
