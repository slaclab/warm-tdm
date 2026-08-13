##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoard.xdc

set_property top {ColumnFpgaBoard} [get_filesets {sources_1}]
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=false" [current_fileset]
