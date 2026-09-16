##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
# Shared build body for the non-coordinator ColumnFpgaBoard targets
# (ColumnFpgaBoard325Fp / ColumnFpgaBoard325Int). The per-target ruckus.tcl sets
# `useFloatPid` (true = AdcDspFp, false = integer AdcDsp) then sources this file.
#
# These are non-coordinators (RING_ADDR_0_G=false). Their bare name signifies "no
# Ethernet", but ColumnFpgaBoard cannot yet be built without an Ethernet core, so
# for now they still instantiate the 1G Ethernet (ETH_10G_G=false), cloned from
# the 1G coordinator generics.
# TODO: drop the Ethernet core here once ColumnFpgaBoard gains an Ethernet-disable
# generic; until then these carry an unused 1G Ethernet.

loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/ColumnFpgaBoard.xdc

set_property top {ColumnFpgaBoard} [get_filesets {sources_1}]

set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=false ETH_10G_G=false GEN_ADC_FILTER_G=false GEN_PID_DEBUG_G=false RSSI_WINDOW_ADDR_SIZE_G=2 ROW_ADDR_BITS_G=6 USE_FLOAT_PID_G=$useFloatPid" [current_fileset]

set_property strategy Power_DefaultOpt [get_runs impl_1]
