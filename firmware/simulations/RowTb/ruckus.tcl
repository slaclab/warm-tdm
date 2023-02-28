##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'warm-tdm', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
# Load RUCKUS environment and library
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

# SURF
loadRuckusTcl $::env(TOP_DIR)/submodules/surf

# Warm TDM Common
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

# Target tops
loadSource  -lib warm_tdm   -dir           $::env(TOP_DIR)/targets/RowModule/rtl
loadSource  -lib warm_tdm   -sim_only -dir $::env(TOP_DIR)/targets/RowModule/sim
#loadSource  -lib warm_tdm   -dir           $::env(TOP_DIR)/targets/ColumnModule/rtl
#loadSource  -lib warm_tdm   -sim_only -dir $::env(TOP_DIR)/targets/ColumnModule/sim

# Load target's source code and constraints
loadSource -lib warm_tdm -sim_only -dir $::env(PROJ_DIR)/tb

# Set the top level synth_1 and sim_1
set_property top {RowModule}       [get_filesets {sources_1}]
set_property top {RowTb} [get_filesets {sim_1}]
