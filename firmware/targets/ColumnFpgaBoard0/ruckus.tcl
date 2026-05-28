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
loadSource      -lib warm_tdm -dir  "$::DIR_PATH/../ColumnFpgaBoard/rtl/"
loadSource      -lib warm_tdm -sim_only -dir "$::DIR_PATH/../ColumnFpgaBoard/sim/"
loadConstraints  -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -dir  "$::DIR_PATH/../ColumnFpgaBoard/xdc/"

set_property top {ColumnFpgaBoard} [get_filesets {sources_1}]
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=false GEN_ADC_FILTER_G=false GEN_PID_DEBUG_G=false RSSI_WINDOW_ADDR_SIZE_G=2 ROW_ADDR_BITS_G=6" [current_fileset]

set_property strategy Power_DefaultOpt [get_runs impl_1]



#puts("TEST!!!")
