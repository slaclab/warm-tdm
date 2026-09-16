##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
# Shared build body for the 10G coordinator ColumnFpgaBoard targets
# (ColumnFpgaBoard325Fp10G / ColumnFpgaBoard325Int10G). The per-target ruckus.tcl
# sets `useFloatPid` (true = AdcDspFp, false = integer AdcDsp) then sources this
# file, so the Fp/Int siblings cannot drift in anything but the PID generic.
#
# Unlike the 1G body, this leaves GEN_ADC_FILTER_G/GEN_PID_DEBUG_G/
# RSSI_WINDOW_ADDR_SIZE_G/ROW_ADDR_BITS_G at their ColumnFpgaBoard entity
# defaults, preserving the prior ColumnFpgaBoard325Coord10G behavior.

loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore_10g.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoard.xdc

set_property top {ColumnFpgaBoard} [get_filesets {sources_1}]

set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=true USE_FLOAT_PID_G=$useFloatPid" [current_fileset]

set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
