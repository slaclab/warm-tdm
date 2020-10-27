##############################################################################
## This file is part of 'kpix-dev'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'kpix-dev', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
# Load RUCKUS library
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

# Load Source Code
loadSource -lib warm_tdm -dir "$::DIR_PATH/rtl"

# Load Ip Core
loadIpCore -path "$::DIR_PATH/ip/FirFilter/FirFilter.xci"

# Load Simulation
#loadSource -sim_only -dir "$::DIR_PATH/sim"
