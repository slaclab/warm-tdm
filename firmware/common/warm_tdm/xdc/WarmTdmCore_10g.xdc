##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

# Load after WarmTdmCore.xdc, only for 10G coordinator targets.

create_generated_clock -name ethClk156 [get_pins {U_WarmTdmCore_1/U_PgpEthCore_1/GEN_ETH.U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks {ethClk156}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks ethClk156]

set_clock_groups -asynchronous \
    -group [get_clocks ethClk156] \
    -group [get_clocks -of_objects [get_pins -hier * -filter {name=~U_WarmTdmCore_1/U_PgpEthCore_1/GEN_ETH.U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/*/RXOUTCLK}]] \
    -group [get_clocks -of_objects [get_pins -hier * -filter {name=~U_WarmTdmCore_1/U_PgpEthCore_1/GEN_ETH.U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/*/TXOUTCLK}]]
