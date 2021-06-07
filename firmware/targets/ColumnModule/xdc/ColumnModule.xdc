##############################################################################
## This file is part of 'kpix-dev'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'kpix-dev', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
create_clock -name gtRefClk0 -period 3.200 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 4.000 [get_ports {gtRefClk1P}]
create_clock -name timingRxClk -period 8.000 [get_ports {timingRxClkP}]
create_clock -name adcDClk0 -period 2.00 [get_ports {adcDClkP[0]}]
create_clock -name adcDClk1 -period 2.00 [get_ports {adcDClkP[1]}]

create_generated_clock -name fabRefClk0 [get_pins {U_ClockDist_1/U_IBUFDS_GTE2_0/ODIV2}]
create_generated_clock -name fabRefClk1 [get_pins {U_ClockDist_1/U_IBUFDS_GTE2_1/ODIV2}]

create_generated_clock -name axilClk [get_pins {U_ComCore_1/U_PgpCore_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name pgpClk [get_pins {U_ComCore_1/U_PgpCore_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT1}]

create_generated_clock -name dnaDivClk [get_pins U_WarmTdmCommon_1/U_AxiVersion_1/GEN_DEVICE_DNA.DeviceDna_1/GEN_7SERIES.DeviceDna7Series_Inst/BUFR_Inst/O]
create_generated_clock -name icapClk [get_pins U_WarmTdmCommon_1/U_AxiVersion_1/GEN_ICAP.Iprog_1/GEN_7SERIES.Iprog7Series_Inst/DIVCLK_GEN.BUFR_ICPAPE2/O]


create_generated_clock -name ethClk [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name ethClkDiv2 [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]

#create_generated_clock -name ethClk [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
#create_generated_clock -name ethClkDiv2 [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]


create_generated_clock -name idelayClk [get_pins {U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]

## create_generated_clock -name timingTxClk [get_pins {U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ U_Timing_1/U_TimingTx_1/*/*/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ U_Timing_1/U_TimingTx_1/*/*/CLKOUT1}]

create_generated_clock -name timingRxBitClk  [get_pins -hier -filter {NAME =~ U_Timing_1/U_TimingRx_1/*/*/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ U_Timing_1/U_TimingRx_1/*/*/CLKOUT1}]


#set ethRxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/RXOUTCLK}
#set ethTxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/TXOUTCLK}

#set_clock_groups -asynchronous \
#    -group [get_clocks {gtRefClk0Div2}] \
#    -group [get_clocks ${ethTxClk}] \
    #    -group [get_clocks ${ethRxClk}]

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
    -group [get_clocks timingRxWordClk] \        
    -group [get_clocks -include_generated_clocks adcDClk0] 

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingRxWordClk] \    
    -group [get_clocks -include_generated_clocks adcDClk1]

# This isn't right
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks adcDClk0] \
    -group [get_clocks -include_generated_clocks adcDClk1]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] 


# MGT Mapping
# Clocks
set_property PACKAGE_PIN H6 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN H5 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN K6 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN K5 [get_ports {gtRefClk1N}]

# PGP
set_property PACKAGE_PIN P2 [get_ports {pgpTxP[1]}]
set_property PACKAGE_PIN P1 [get_ports {pgpTxN[1]}]
set_property PACKAGE_PIN R4 [get_ports {pgpRxP[1]}]
set_property PACKAGE_PIN R3 [get_ports {pgpRxN[1]}]

# GT Timing
set_property PACKAGE_PIN N4 [get_ports {pgpRxP[0]}]
set_property PACKAGE_PIN N3 [get_ports {pgpRxN[0]}]
set_property PACKAGE_PIN M2 [get_ports {pgpTxP[0]}]
set_property PACKAGE_PIN M1 [get_ports {pgpTxN[0]}]


# IO Timing
set_property -dict { PACKAGE_PIN AC9  IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkP }];
set_property -dict { PACKAGE_PIN AD9  IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkN }];
set_property -dict { PACKAGE_PIN AB11 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataP }];
set_property -dict { PACKAGE_PIN AC11 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataN }];
set_property -dict { PACKAGE_PIN Y11  IOSTANDARD LVDS } [get_ports { timingTxClkP }];
set_property -dict { PACKAGE_PIN Y10  IOSTANDARD LVDS } [get_ports { timingTxClkN }];
set_property -dict { PACKAGE_PIN V9   IOSTANDARD LVDS } [get_ports { timingTxDataP }];
set_property -dict { PACKAGE_PIN W8   IOSTANDARD LVDS } [get_ports { timingTxDataN }];


# SFP
set_property PACKAGE_PIN K2 [get_ports {sfp0TxP}]
set_property PACKAGE_PIN K1 [get_ports {sfp0TxN}]
set_property PACKAGE_PIN L4 [get_ports {sfp0RxP}]
set_property PACKAGE_PIN L3 [get_ports {sfp0RxN}]
# set_property PACKAGE_PIN H2 [get_ports {sfp1TxP}]
# set_property PACKAGE_PIN H1 [get_ports {sfp1TxN}]
# set_property PACKAGE_PIN J4 [get_ports {sfp1RxP}]
# set_property PACKAGE_PIN J3 [get_ports {sfp1RxN}]


# ADC
set_property -dict { PACKAGE_PIN AA17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[0] }];
set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[0] }];
set_property -dict { PACKAGE_PIN AB16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[0] }];
set_property -dict { PACKAGE_PIN AC16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[0] }];

set_property -dict { PACKAGE_PIN AE17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][0] }];
set_property -dict { PACKAGE_PIN AF17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][0] }];
set_property -dict { PACKAGE_PIN AE18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][1] }];
set_property -dict { PACKAGE_PIN AF18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][1] }];
set_property -dict { PACKAGE_PIN AF19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][2] }];
set_property -dict { PACKAGE_PIN AF20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][2] }];
set_property -dict { PACKAGE_PIN AA14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][3] }];
set_property -dict { PACKAGE_PIN AA15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][3] }];
set_property -dict { PACKAGE_PIN AA19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][4] }];
set_property -dict { PACKAGE_PIN AA20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][4] }];
set_property -dict { PACKAGE_PIN AB19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][5] }];
set_property -dict { PACKAGE_PIN AB20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][5] }];
set_property -dict { PACKAGE_PIN V16  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][6] }];
set_property -dict { PACKAGE_PIN V17  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][6] }];
set_property -dict { PACKAGE_PIN W15  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][7] }];
set_property -dict { PACKAGE_PIN W16  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][7] }];

set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[1] }];
set_property -dict { PACKAGE_PIN AC17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[1] }];
set_property -dict { PACKAGE_PIN AC18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[1] }];
set_property -dict { PACKAGE_PIN AD18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[1] }];

set_property -dict { PACKAGE_PIN AF14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][0] }];
set_property -dict { PACKAGE_PIN AF15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][0] }];
set_property -dict { PACKAGE_PIN AD15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][1] }];
set_property -dict { PACKAGE_PIN AE15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][1] }];
set_property -dict { PACKAGE_PIN AD16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][2] }];
set_property -dict { PACKAGE_PIN AE16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][2] }];
set_property -dict { PACKAGE_PIN AC14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][3] }];
set_property -dict { PACKAGE_PIN AD14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][3] }];
set_property -dict { PACKAGE_PIN AC19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][4] }];
set_property -dict { PACKAGE_PIN AD19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][4] }];
set_property -dict { PACKAGE_PIN Y17  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][5] }];
set_property -dict { PACKAGE_PIN Y18  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][5] }];
set_property -dict { PACKAGE_PIN W18  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][6] }];
set_property -dict { PACKAGE_PIN W19  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][6] }];
set_property -dict { PACKAGE_PIN V18  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][7] }];
set_property -dict { PACKAGE_PIN V19  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][7] }];

set_property -dict { PACKAGE_PIN V14  IOSTANDARD LVDS } [get_ports { adcClkP }];
set_property -dict { PACKAGE_PIN W14  IOSTANDARD LVDS } [get_ports { adcClkN }];


set_property -dict { PACKAGE_PIN V11 IOSTANDARD LVCMOS18 } [get_ports { adcSclk }];
set_property -dict { PACKAGE_PIN W11 IOSTANDARD LVCMOS18 } [get_ports { adcSdio }];
set_property -dict { PACKAGE_PIN V8  IOSTANDARD LVCMOS18 } [get_ports { adcCsb }];
set_property -dict { PACKAGE_PIN V7  IOSTANDARD LVCMOS18 } [get_ports { adcSync }];


## Fast DACS
set_property -dict { PACKAGE_PIN U21  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0] }];
set_property -dict { PACKAGE_PIN U22  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1] }];
set_property -dict { PACKAGE_PIN V22  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2] }];
set_property -dict { PACKAGE_PIN U24  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3] }];
set_property -dict { PACKAGE_PIN U25  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[4] }];
set_property -dict { PACKAGE_PIN V23  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[5] }];
set_property -dict { PACKAGE_PIN V24  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[6] }];
set_property -dict { PACKAGE_PIN U26  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[7] }];
set_property -dict { PACKAGE_PIN V26  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[8] }];
set_property -dict { PACKAGE_PIN W25  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[9] }];
set_property -dict { PACKAGE_PIN W26  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[10] }];
set_property -dict { PACKAGE_PIN V21  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[11] }];
set_property -dict { PACKAGE_PIN W21  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[12] }];
set_property -dict { PACKAGE_PIN AA25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[13] }];

set_property -dict { PACKAGE_PIN AE26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[0] }];
set_property -dict { PACKAGE_PIN W23  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[1] }];
set_property -dict { PACKAGE_PIN W24  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[2] }];
set_property -dict { PACKAGE_PIN AB26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[3] }];

set_property -dict { PACKAGE_PIN AC26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[0] }];
set_property -dict { PACKAGE_PIN Y25  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[1] }];
set_property -dict { PACKAGE_PIN Y26  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[2] }];
set_property -dict { PACKAGE_PIN AA23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[3] }];

set_property -dict { PACKAGE_PIN AB24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[0] }];
set_property -dict { PACKAGE_PIN Y23  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[1] }];
set_property -dict { PACKAGE_PIN AA24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[2] }];
set_property -dict { PACKAGE_PIN Y22  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[3] }];

set_property -dict { PACKAGE_PIN AA22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[0] }];
set_property -dict { PACKAGE_PIN AC23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[1] }];
set_property -dict { PACKAGE_PIN AC24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[2] }];
set_property -dict { PACKAGE_PIN W20  IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[3] }];


set_property -dict { PACKAGE_PIN N16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0] }];
set_property -dict { PACKAGE_PIN K25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1] }];
set_property -dict { PACKAGE_PIN K26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2] }];
set_property -dict { PACKAGE_PIN R26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3] }];
set_property -dict { PACKAGE_PIN P26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[4] }];
set_property -dict { PACKAGE_PIN M25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[5] }];
set_property -dict { PACKAGE_PIN L25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[6] }];
set_property -dict { PACKAGE_PIN P24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[7] }];
set_property -dict { PACKAGE_PIN N24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[8] }];
set_property -dict { PACKAGE_PIN N26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[9] }];
set_property -dict { PACKAGE_PIN M26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[10] }];
set_property -dict { PACKAGE_PIN R25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[11] }];
set_property -dict { PACKAGE_PIN P25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[12] }];
set_property -dict { PACKAGE_PIN N19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[13] }];

set_property -dict { PACKAGE_PIN M20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[0] }];
set_property -dict { PACKAGE_PIN M24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[1] }];
set_property -dict { PACKAGE_PIN L24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[2] }];
set_property -dict { PACKAGE_PIN P19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[3] }];

set_property -dict { PACKAGE_PIN P20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[0] }];
set_property -dict { PACKAGE_PIN M21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[1] }];
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[2] }];
set_property -dict { PACKAGE_PIN P23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[3] }];

set_property -dict { PACKAGE_PIN N23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[0] }];
set_property -dict { PACKAGE_PIN N21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[1] }];
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[2] }];
set_property -dict { PACKAGE_PIN R21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[3] }];

set_property -dict { PACKAGE_PIN P21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[0] }];
set_property -dict { PACKAGE_PIN R22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[1] }];
set_property -dict { PACKAGE_PIN R23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[2] }];
set_property -dict { PACKAGE_PIN T24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[3] }];


set_property -dict { PACKAGE_PIN J8  IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0] }];
set_property -dict { PACKAGE_PIN H9  IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1] }];
set_property -dict { PACKAGE_PIN H8  IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2] }];
set_property -dict { PACKAGE_PIN G10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3] }];
set_property -dict { PACKAGE_PIN G9  IOSTANDARD LVCMOS33 } [get_ports { saFbDb[4] }];
set_property -dict { PACKAGE_PIN J13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[5] }];
set_property -dict { PACKAGE_PIN H13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[6] }];
set_property -dict { PACKAGE_PIN J11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[7] }];
set_property -dict { PACKAGE_PIN J10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[8] }];
set_property -dict { PACKAGE_PIN H14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[9] }];
set_property -dict { PACKAGE_PIN G14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[10] }];
set_property -dict { PACKAGE_PIN H12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[11] }];
set_property -dict { PACKAGE_PIN H11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[12] }];
set_property -dict { PACKAGE_PIN F9  IOSTANDARD LVCMOS33 } [get_ports { saFbDb[13] }];

set_property -dict { PACKAGE_PIN F8  IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[0] }];
set_property -dict { PACKAGE_PIN D9  IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[1] }];
set_property -dict { PACKAGE_PIN D8  IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[2] }];
set_property -dict { PACKAGE_PIN A9  IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[3] }];

set_property -dict { PACKAGE_PIN A8  IOSTANDARD LVCMOS33 } [get_ports { saFbClk[0] }];
set_property -dict { PACKAGE_PIN C9  IOSTANDARD LVCMOS33 } [get_ports { saFbClk[1] }];
set_property -dict { PACKAGE_PIN B9  IOSTANDARD LVCMOS33 } [get_ports { saFbClk[2] }];
set_property -dict { PACKAGE_PIN G11 IOSTANDARD LVCMOS33 } [get_ports { saFbClk[3] }];

set_property -dict { PACKAGE_PIN F10 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[0] }];
set_property -dict { PACKAGE_PIN E10 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[1] }];
set_property -dict { PACKAGE_PIN D10 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[2] }];
set_property -dict { PACKAGE_PIN C12 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[3] }];

set_property -dict { PACKAGE_PIN C11 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[0] }];
set_property -dict { PACKAGE_PIN E11 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[1] }];
set_property -dict { PACKAGE_PIN D11 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[2] }];
set_property -dict { PACKAGE_PIN F14 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[3] }];


## Slow DACs
set_property -dict { PACKAGE_PIN AB12 IOSTANDARD LVCMOS18 } [get_ports { saDacSclk }];
set_property -dict { PACKAGE_PIN AC12 IOSTANDARD LVCMOS18 } [get_ports { saDacMosi }];
set_property -dict { PACKAGE_PIN AA13 IOSTANDARD LVCMOS18 } [get_ports { saDacMiso }];
set_property -dict { PACKAGE_PIN AA12 IOSTANDARD LVCMOS18 } [get_ports { saDacSyncB }];
set_property -dict { PACKAGE_PIN AC13 IOSTANDARD LVCMOS18 } [get_ports { saDacLdacB }];
set_property -dict { PACKAGE_PIN AD13 IOSTANDARD LVCMOS18 } [get_ports { saDacResetB }];

set_property -dict { PACKAGE_PIN AD11 IOSTANDARD LVCMOS18 } [get_ports { tesDacSclk }];
set_property -dict { PACKAGE_PIN AE11 IOSTANDARD LVCMOS18 } [get_ports { tesDacMosi }];
set_property -dict { PACKAGE_PIN AD10 IOSTANDARD LVCMOS18 } [get_ports { tesDacMiso }];
set_property -dict { PACKAGE_PIN AE10 IOSTANDARD LVCMOS18 } [get_ports { tesDacSyncB }];
set_property -dict { PACKAGE_PIN AE12 IOSTANDARD LVCMOS18 } [get_ports { tesDacLdacB }];
set_property -dict { PACKAGE_PIN AF12 IOSTANDARD LVCMOS18 } [get_ports { tesDacResetB }];

## Timing Source Select
set_property -dict { PACKAGE_PIN AF23 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[0] }];
set_property -dict { PACKAGE_PIN AD25 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[1] }];
set_property -dict { PACKAGE_PIN AE25 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[0] }];
set_property -dict { PACKAGE_PIN AE22 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[1] }];
set_property -dict { PACKAGE_PIN AF22 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[0] }];
set_property -dict { PACKAGE_PIN Y20  IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[1] }];

## TES Delatch
set_property -dict { PACKAGE_PIN R17  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[0] }];
set_property -dict { PACKAGE_PIN N18  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[1] }];
set_property -dict { PACKAGE_PIN M19  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[2] }];
set_property -dict { PACKAGE_PIN U17  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[3] }];
set_property -dict { PACKAGE_PIN T17  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[4] }];
set_property -dict { PACKAGE_PIN R18  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[5] }];
set_property -dict { PACKAGE_PIN P18  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[6] }];
set_property -dict { PACKAGE_PIN U16  IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[7] }];

# ASIC Interface
# set_property -dict { PACKAGE_PIN U2 IOSTANDARD LVCMOS18 } [get_ports { asicDacSclk }];
# set_property -dict { PACKAGE_PIN U1 IOSTANDARD LVCMOS18 } [get_ports { asicDacMosi }];
# set_property -dict { PACKAGE_PIN W6 IOSTANDARD LVCMOS18 } [get_ports { asicDacMiso }];
# set_property -dict { PACKAGE_PIN W5 IOSTANDARD LVCMOS18 } [get_ports { asicDacSyncB }];
# set_property -dict { PACKAGE_PIN V3 IOSTANDARD LVCMOS18 } [get_ports { asicDacLdacB }];
# set_property -dict { PACKAGE_PIN W3 IOSTANDARD LVCMOS18 } [get_ports { asicDacResetB }];

# set_property -dict { PACKAGE_PIN V4 IOSTANDARD LVDS } [get_ports { asicResetP }];
# set_property -dict { PACKAGE_PIN W4 IOSTANDARD LVDS } [get_ports { asicResetN }];
# set_property -dict { PACKAGE_PIN Y3 IOSTANDARD LVDS } [get_ports { asicCarryInP }];
# set_property -dict { PACKAGE_PIN Y2 IOSTANDARD LVDS } [get_ports { asicCarryInN }];
# set_property -dict { PACKAGE_PIN V2 IOSTANDARD LVDS } [get_ports { asicClkP }];
# set_property -dict { PACKAGE_PIN V1 IOSTANDARD LVDS } [get_ports { asicClkN }];
# set_property -dict { PACKAGE_PIN AB1 IOSTANDARD LVDS DIFF_TERM true} [get_ports { asicFbP }];
# set_property -dict { PACKAGE_PIN AC1 IOSTANDARD LVDS DIFF_TERM true} [get_ports { asicFbN }];



# Boot Memory Port Mapping
set_property -dict { PACKAGE_PIN C23 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }];
set_property -dict { PACKAGE_PIN B24 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }];
set_property -dict { PACKAGE_PIN A25 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }];

# LEDs
set_property -dict { PACKAGE_PIN E23 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }];
set_property -dict { PACKAGE_PIN G22 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }];
set_property -dict { PACKAGE_PIN F23 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }];
set_property -dict { PACKAGE_PIN G24 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }];
set_property -dict { PACKAGE_PIN F24 IOSTANDARD LVCMOS33 } [get_ports { leds[4] }];
set_property -dict { PACKAGE_PIN E25 IOSTANDARD LVCMOS33 } [get_ports { leds[5] }];
set_property -dict { PACKAGE_PIN D25 IOSTANDARD LVCMOS33 } [get_ports { leds[6] }];
set_property -dict { PACKAGE_PIN G25 IOSTANDARD LVCMOS33 } [get_ports { leds[7] }];


# I2C PROM
set_property -dict { PACKAGE_PIN D23 IOSTANDARD LVCMOS33 } [get_ports { promScl }];
set_property -dict { PACKAGE_PIN D24 IOSTANDARD LVCMOS33 } [get_ports { promSda }];

# Power Monitoring
set_property -dict { PACKAGE_PIN C22 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }];
set_property -dict { PACKAGE_PIN B20 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }];
#set_property -dict { PACKAGE_PIN K21 IOSTANDARD LVCMOS33 } [get_ports { tempAlertL }];

# RJ-45 LEDs

set_property -dict { PACKAGE_PIN H26 IOSTANDARD LVCMOS33 } [get_ports { conRxGreenLed }];
set_property -dict { PACKAGE_PIN H21 IOSTANDARD LVCMOS33 } [get_ports { conRxYellowLed }];
set_property -dict { PACKAGE_PIN G21 IOSTANDARD LVCMOS33 } [get_ports { conTxGreenLed }];
set_property -dict { PACKAGE_PIN H23 IOSTANDARD LVCMOS33 } [get_ports { conTxYellowLed }];

set_property -dict { PACKAGE_PIN J24 IOSTANDARD LVCMOS33 } [get_ports { oscOe[0] }];
set_property -dict { PACKAGE_PIN J25 IOSTANDARD LVCMOS33 } [get_ports { oscOe[1] }];

## Thermistors
set_property -dict { PACKAGE_PIN C16 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[0] }];
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[1] }];
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[2] }];
set_property -dict { PACKAGE_PIN C19 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[3] }];
set_property -dict { PACKAGE_PIN B16 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[0] }];
set_property -dict { PACKAGE_PIN A19 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[1] }];
set_property -dict { PACKAGE_PIN A17 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[2] }];
set_property -dict { PACKAGE_PIN B19 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[3] }];

set_property BITSTREAM.CONFIG.CONFIGRATE 33  [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

