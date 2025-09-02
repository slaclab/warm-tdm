##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'kpix-dev', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
############################
# DO NOT EDIT THE CODE BELOW
############################

# Load RUCKUS environment and library
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

# Load submodules' code and constraints
loadRuckusTcl $::env(TOP_DIR)/submodules/surf

# Load common code
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

# Load target's source code and constraints
loadSource      -lib warm_tdm -dir  "$::DIR_PATH/rtl/"
loadSource      -lib warm_tdm -sim_only -dir "$::DIR_PATH/sim/" -fileType "VHDL 2008"
loadConstraints  -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -dir  "$::DIR_PATH/xdc/"

loadIpCore -doUpgrade -path $::DIR_PATH/../ColumnFpgaBoard/ip/Int2Fp/Int2Fp.xci
loadIpCore -doUpgrade -path $::DIR_PATH/../ColumnFpgaBoard/ip/FpMac/FpMac.xci

set_property top "ColumnFpgaBoardTb"     [get_filesets sim_1]

set_property target_language Verilog [current_project]
