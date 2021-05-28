##############################################################################
## This file is part of 'kpix-dev'.
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

set_property top {ColumnModule} [get_filesets {sources_1}]
set sysGeneric [get_property generic -object [current_fileset]]
set testGeneric "${sysGeneric}, RING_ADDR_G=true"
set_property generic ${testGeneric} -object [current_fileset]

# Load submodules' code and constraints
loadRuckusTcl $::env(TOP_DIR)/submodules/surf

# Load common code
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

# Load target's source code and constraints
#loadSource      -lib warm_tdm -dir  "$::DIR_PATH/rtl/"
loadSource      -lib warm_tdm -dir  "$::DIR_PATH/../ColumnModule/rtl/"
loadSource      -lib warm_tdm -sim_only -dir "$::DIR_PATH/../ColumnModule/sim/"
loadConstraints -dir  "$::DIR_PATH/../ColumnModule/xdc/"




