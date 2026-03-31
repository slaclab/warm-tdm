##############################################################################
## This file is part of 'kpix-dev'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'kpix-dev', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################

# Get variables and procedures
source -quiet $::env(RUCKUS_DIR)/vivado/env_var.tcl
source -quiet $::env(RUCKUS_DIR)/vivado/proc.tcl

# Define the file path
set simTbOutDir ${OUT_DIR}/${PROJECT}_project.sim/sim_1/behav
set filePath "${simTbOutDir}/sim_vcs_mx.sh"

# Read the file
set fh [open $filePath r]
set data [read $fh]
close $fh

# Perform the substitution
set newData [string map \
    {"vhdlan -work xil_defaultlib $vhdlan_opts" \
     "vhdlan -work xil_defaultlib -full64 -nc -l +v2k -vhdl08"} \
    $data]

# Write the updated content back
set fh [open $filePath w]
puts $fh $newData
close $fh
