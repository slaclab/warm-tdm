##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'Warm TDM', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
create_clock -name gtRefClk0 -period 3.200 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 4.000 [get_ports {gtRefClk1P}]
create_clock -name timingRxClk -period 8.000 [get_ports {timingRxClkP}]

create_generated_clock -name fabRefClk0 [get_pins {U_WarmTdmCore_1/U_ClockDist_1/U_IBUFDS_GTE2_0/ODIV2}]
create_generated_clock -name fabRefClk1 [get_pins {U_WarmTdmCore_1/U_ClockDist_1/U_IBUFDS_GTE2_1/ODIV2}]

create_generated_clock -name axilClk [get_pins {U_WarmTdmCore_1/U_PgpEthCore_1/GEN_PGP.U_PgpCore_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name pgpClk [get_pins {U_WarmTdmCore_1/U_PgpEthCore_1/GEN_PGP.U_PgpCore_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT1}]

create_generated_clock -name dnaDivClk [get_pins U_WarmTdmCore_1/U_WarmTdmCommon_1/U_AxiVersion_1/GEN_DEVICE_DNA.DeviceDna_1/GEN_7SERIES.DeviceDna7Series_Inst/BUFR_Inst/O]
create_generated_clock -name icapClk [get_pins U_WarmTdmCore_1/U_WarmTdmCommon_1/U_AxiVersion_1/GEN_ICAP.Iprog_1/GEN_7SERIES.Iprog7Series_Inst/DIVCLK_GEN.BUFR_ICPAPE2/O]


create_generated_clock -name ethClk [get_pins {U_WarmTdmCore_1/U_PgpEthCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name ethClkDiv2 [get_pins {U_WarmTdmCore_1/U_PgpEthCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]

create_generated_clock -name idelayClk [get_pins {U_WarmTdmCore_1/U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]



create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingTx_1/*/*/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingTx_1/*/*/CLKOUT1}]

create_generated_clock -name timingRxBitClk  [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingRx_1/*/*/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingRx_1/*/*/CLKOUT1}]

set_clock_groups -asynchronous \
    -group [get_clocks {fabRefClk1}] \
    -group [get_clocks {ethClk}] 

set_clock_groups -asynchronous \
    -group [get_clocks {fabRefClk1}] \
    -group [get_clocks {pgpClk}]

set_clock_groups -asynchronous \
    -group [get_clocks {axilClk}] \
    -group [get_clocks {pgpClk}] 


set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks axilClk] \
    -group [get_clocks -include_generated_clocks timingRxClk] 

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks fabRefClk1]

 set_clock_groups -asynchronous \
     -group [get_clocks axilClk] \
     -group [get_clocks ethClk] \

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks -include_generated_clocks dnaDivClk] \
    -group [get_clocks icapClk]


set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk] 



#create_generated_clock -name ethClk [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
#create_generated_clock -name ethClkDiv2 [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]


#set ethRxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/RXOUTCLK}
#set ethTxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/TXOUTCLK}
