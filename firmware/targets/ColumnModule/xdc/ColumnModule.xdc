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

create_generated_clock -name gtRefClk0Div2 [get_pins {U_ComCore_1/U_IBUFDS_GTE2/ODIV2}]

create_generated_clock -name axilClk [get_pins {U_ComCore_1/U_PgpCore_1/REAL_PGP_GEN.U_Pgp2bGtx7VarLatWrapper_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT0}]

create_generated_clock -name ethClk [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name ethClkDiv2 [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]

create_generated_clock -name idelayClk [get_pins {U_TimingRx_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]


set ethRxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/RXOUTCLK}
set ethTxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/TXOUTCLK}

set_clock_groups -asynchronous \
    -group [get_clocks {gtRefClk0Div2}] \
    -group [get_clocks ${ethTxClk}] \
    -group [get_clocks ${ethRxClk}]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks axilClk] \
    -group [get_clocks -include_generated_clocks timingRxClk] 

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks ethClk] \
    -group [get_clocks gtRefClk0Div2]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingRxClk] \        
    -group [get_clocks -include_generated_clocks adcDClk0] 

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingRxClk] \    
    -group [get_clocks -include_generated_clocks adcDClk1]

# This isn't right
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks adcDClk0] \
    -group [get_clocks -include_generated_clocks adcDClk1]

# MGT Mapping
# Clocks
set_property PACKAGE_PIN H6 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN H5 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN K6 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN K5 [get_ports {gtRefClk1N}]

# PGP
set_property PACKAGE_PIN P2 [get_ports {pgpTxP}]
set_property PACKAGE_PIN P1 [get_ports {pgpTxN}]
set_property PACKAGE_PIN R4 [get_ports {pgpRxP}]
set_property PACKAGE_PIN R3 [get_ports {pgpRxN}]

# GT Timing
#set_property PACKAGE_PIN N4 [get_ports {timingRxP}]
#set_property PACKAGE_PIN N3 [get_ports {timingRxN}]
#set_property PACKAGE_PIN M2 [get_ports {timingTxP}]
#set_property PACKAGE_PIN M1 [get_ports {timingTxN}]


# IO Timing
set_property -dict { PACKAGE_PIN AC9  IOSTANDARD LVDS } [get_ports { timingRxClkP }];
set_property -dict { PACKAGE_PIN AD9  IOSTANDARD LVDS } [get_ports { timingRxClkN }];
set_property -dict { PACKAGE_PIN AB7  IOSTANDARD LVDS } [get_ports { timingRxDataP }];
set_property -dict { PACKAGE_PIN AC7  IOSTANDARD LVDS } [get_ports { timingRxDataN }];
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
set_property -dict { PACKAGE_PIN AB14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[0] }];
set_property -dict { PACKAGE_PIN AB15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[0] }];
set_property -dict { PACKAGE_PIN AA17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[0] }];
set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[0] }];
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
set_property -dict { PACKAGE_PIN AD20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[1] }];
set_property -dict { PACKAGE_PIN AE20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[1] }];
set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[1] }];
set_property -dict { PACKAGE_PIN AC17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[1] }];
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
set_property -dict { PACKAGE_PIN V8  IOSTANDARD LVCMOS18 } [get_ports { adcCsb1 }];
set_property -dict { PACKAGE_PIN V7  IOSTANDARD LVCMOS18 } [get_ports { adcCsb2 }];
set_property -dict { PACKAGE_PIN W10 IOSTANDARD LVCMOS18 } [get_ports { adcSync }];
set_property -dict { PACKAGE_PIN W9  IOSTANDARD LVCMOS18 } [get_ports { adcPdwn }];


set_property -dict { PACKAGE_PIN U21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][0] }];
set_property -dict { PACKAGE_PIN U22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][1] }];
set_property -dict { PACKAGE_PIN V22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][2] }];
set_property -dict { PACKAGE_PIN U24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][3] }];
set_property -dict { PACKAGE_PIN U25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][4] }];
set_property -dict { PACKAGE_PIN V23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][5] }];
set_property -dict { PACKAGE_PIN V24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][6] }];
set_property -dict { PACKAGE_PIN U26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][7] }];
set_property -dict { PACKAGE_PIN V26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][8] }];
set_property -dict { PACKAGE_PIN W25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][9] }];
set_property -dict { PACKAGE_PIN W26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][10] }];
set_property -dict { PACKAGE_PIN V21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][11] }];
set_property -dict { PACKAGE_PIN W21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][12] }];
set_property -dict { PACKAGE_PIN AA25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0][13] }];
set_property -dict { PACKAGE_PIN AB25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][0] }];
set_property -dict { PACKAGE_PIN W23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][1] }];
set_property -dict { PACKAGE_PIN W24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][2] }];
set_property -dict { PACKAGE_PIN AB26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][3] }];
set_property -dict { PACKAGE_PIN AC26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][4] }];
set_property -dict { PACKAGE_PIN Y25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][5] }];
set_property -dict { PACKAGE_PIN Y26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][6] }];
set_property -dict { PACKAGE_PIN AA23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][7] }];
set_property -dict { PACKAGE_PIN AB24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][8] }];
set_property -dict { PACKAGE_PIN Y23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][9] }];
set_property -dict { PACKAGE_PIN AA24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][10] }];
set_property -dict { PACKAGE_PIN Y22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][11] }];
set_property -dict { PACKAGE_PIN AA22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][12] }];
set_property -dict { PACKAGE_PIN AC23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1][13] }];
set_property -dict { PACKAGE_PIN AC24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][0] }];
set_property -dict { PACKAGE_PIN W20 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][1] }];
set_property -dict { PACKAGE_PIN Y21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][2] }];
set_property -dict { PACKAGE_PIN AD23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][3] }];
set_property -dict { PACKAGE_PIN AD24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][4] }];
set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][5] }];
set_property -dict { PACKAGE_PIN AC22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][6] }];
set_property -dict { PACKAGE_PIN AB21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][7] }];
set_property -dict { PACKAGE_PIN AC21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][8] }];
set_property -dict { PACKAGE_PIN AD21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][9] }];
set_property -dict { PACKAGE_PIN AE21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][10] }];
set_property -dict { PACKAGE_PIN AF24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][11] }];
set_property -dict { PACKAGE_PIN AF25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][12] }];
set_property -dict { PACKAGE_PIN AD26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2][13] }];
set_property -dict { PACKAGE_PIN N16 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][0] }];
set_property -dict { PACKAGE_PIN K25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][1] }];
set_property -dict { PACKAGE_PIN K26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][2] }];
set_property -dict { PACKAGE_PIN R26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][3] }];
set_property -dict { PACKAGE_PIN P26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][4] }];
set_property -dict { PACKAGE_PIN M25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][5] }];
set_property -dict { PACKAGE_PIN L25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][6] }];
set_property -dict { PACKAGE_PIN P24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][7] }];
set_property -dict { PACKAGE_PIN N24 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][8] }];
set_property -dict { PACKAGE_PIN N26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][9] }];
set_property -dict { PACKAGE_PIN M26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][10] }];
set_property -dict { PACKAGE_PIN R25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][11] }];
set_property -dict { PACKAGE_PIN P25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][12] }];
set_property -dict { PACKAGE_PIN N19 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3][13] }];

set_property -dict { PACKAGE_PIN AE26 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt }];
set_property -dict { PACKAGE_PIN AE23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk }];
set_property -dict { PACKAGE_PIN AF23 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel }];
set_property -dict { PACKAGE_PIN AD25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset }];
set_property -dict { PACKAGE_PIN AE25 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSleep }];

set_property -dict { PACKAGE_PIN M20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][0] }];
set_property -dict { PACKAGE_PIN M24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][1] }];
set_property -dict { PACKAGE_PIN L24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][2] }];
set_property -dict { PACKAGE_PIN P19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][3] }];
set_property -dict { PACKAGE_PIN P20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][4] }];
set_property -dict { PACKAGE_PIN M21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][5] }];
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][6] }];
set_property -dict { PACKAGE_PIN P23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][7] }];
set_property -dict { PACKAGE_PIN N23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][8] }];
set_property -dict { PACKAGE_PIN N21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][9] }];
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][10] }];
set_property -dict { PACKAGE_PIN R21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][11] }];
set_property -dict { PACKAGE_PIN P21 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][12] }];
set_property -dict { PACKAGE_PIN R22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0][13] }];
set_property -dict { PACKAGE_PIN R23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][0] }];
set_property -dict { PACKAGE_PIN T24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][1] }];
set_property -dict { PACKAGE_PIN T25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][2] }];
set_property -dict { PACKAGE_PIN T20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][3] }];
set_property -dict { PACKAGE_PIN R20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][4] }];
set_property -dict { PACKAGE_PIN T22 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][5] }];
set_property -dict { PACKAGE_PIN T23 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][6] }];
set_property -dict { PACKAGE_PIN U19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][7] }];
set_property -dict { PACKAGE_PIN U20 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][8] }];
set_property -dict { PACKAGE_PIN T18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][9] }];
set_property -dict { PACKAGE_PIN T19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][10] }];
set_property -dict { PACKAGE_PIN P16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][11] }];
set_property -dict { PACKAGE_PIN N17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][12] }];
set_property -dict { PACKAGE_PIN R16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1][13] }];
set_property -dict { PACKAGE_PIN K15 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][0] }];
set_property -dict { PACKAGE_PIN C16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][1] }];
set_property -dict { PACKAGE_PIN B16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][2] }];
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][3] }];
set_property -dict { PACKAGE_PIN A19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][4] }];
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][5] }];
set_property -dict { PACKAGE_PIN A17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][6] }];
set_property -dict { PACKAGE_PIN C19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][7] }];
set_property -dict { PACKAGE_PIN B19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][8] }];
set_property -dict { PACKAGE_PIN C17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][9] }];
set_property -dict { PACKAGE_PIN C18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][10] }];
set_property -dict { PACKAGE_PIN D15 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][11] }];
set_property -dict { PACKAGE_PIN D16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][12] }];
set_property -dict { PACKAGE_PIN H16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2][13] }];
set_property -dict { PACKAGE_PIN G16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][0] }];
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][1] }];
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][2] }];
set_property -dict { PACKAGE_PIN J15 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][3] }];
set_property -dict { PACKAGE_PIN J16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][4] }];
set_property -dict { PACKAGE_PIN E15 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][5] }];
set_property -dict { PACKAGE_PIN E16 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][6] }];
set_property -dict { PACKAGE_PIN G17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][7] }];
set_property -dict { PACKAGE_PIN F18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][8] }];
set_property -dict { PACKAGE_PIN F17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][9] }];
set_property -dict { PACKAGE_PIN E17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][10] }];
set_property -dict { PACKAGE_PIN E18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][11] }];
set_property -dict { PACKAGE_PIN D18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][12] }];
set_property -dict { PACKAGE_PIN H17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3][13] }];

set_property -dict { PACKAGE_PIN R17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt }];
set_property -dict { PACKAGE_PIN N18 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk }];
set_property -dict { PACKAGE_PIN M19 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel }];
set_property -dict { PACKAGE_PIN U17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset }];
set_property -dict { PACKAGE_PIN T17 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSleep }];

set_property -dict { PACKAGE_PIN H18 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][0] }];
set_property -dict { PACKAGE_PIN D19 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][1] }];
set_property -dict { PACKAGE_PIN D20 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][2] }];
set_property -dict { PACKAGE_PIN G19 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][3] }];
set_property -dict { PACKAGE_PIN F20 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][4] }];
set_property -dict { PACKAGE_PIN F19 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][5] }];
set_property -dict { PACKAGE_PIN E20 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][6] }];
set_property -dict { PACKAGE_PIN H19 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][7] }];
set_property -dict { PACKAGE_PIN G20 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][8] }];
set_property -dict { PACKAGE_PIN K20 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][9] }];
set_property -dict { PACKAGE_PIN J20 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][10] }];
set_property -dict { PACKAGE_PIN J18 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][11] }];
set_property -dict { PACKAGE_PIN J19 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][12] }];
set_property -dict { PACKAGE_PIN L19 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0][13] }];
set_property -dict { PACKAGE_PIN J8 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][0] }];
set_property -dict { PACKAGE_PIN H9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][1] }];
set_property -dict { PACKAGE_PIN H8 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][2] }];
set_property -dict { PACKAGE_PIN G10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][3] }];
set_property -dict { PACKAGE_PIN G9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][4] }];
set_property -dict { PACKAGE_PIN J13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][5] }];
set_property -dict { PACKAGE_PIN H13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][6] }];
set_property -dict { PACKAGE_PIN J11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][7] }];
set_property -dict { PACKAGE_PIN J10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][8] }];
set_property -dict { PACKAGE_PIN H14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][9] }];
set_property -dict { PACKAGE_PIN G14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][10] }];
set_property -dict { PACKAGE_PIN H12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][11] }];
set_property -dict { PACKAGE_PIN H11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][12] }];
set_property -dict { PACKAGE_PIN F9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1][13] }];
set_property -dict { PACKAGE_PIN F8 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][0] }];
set_property -dict { PACKAGE_PIN D9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][1] }];
set_property -dict { PACKAGE_PIN D8 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][2] }];
set_property -dict { PACKAGE_PIN A9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][3] }];
set_property -dict { PACKAGE_PIN A8 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][4] }];
set_property -dict { PACKAGE_PIN C9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][5] }];
set_property -dict { PACKAGE_PIN B9 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][6] }];
set_property -dict { PACKAGE_PIN G11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][7] }];
set_property -dict { PACKAGE_PIN F10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][8] }];
set_property -dict { PACKAGE_PIN E10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][9] }];
set_property -dict { PACKAGE_PIN D10 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][10] }];
set_property -dict { PACKAGE_PIN C12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][11] }];
set_property -dict { PACKAGE_PIN C11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][12] }];
set_property -dict { PACKAGE_PIN E11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2][13] }];
set_property -dict { PACKAGE_PIN D11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][0] }];
set_property -dict { PACKAGE_PIN F14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][1] }];
set_property -dict { PACKAGE_PIN F13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][2] }];
set_property -dict { PACKAGE_PIN G12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][3] }];
set_property -dict { PACKAGE_PIN F12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][4] }];
set_property -dict { PACKAGE_PIN D14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][5] }];
set_property -dict { PACKAGE_PIN D13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][6] }];
set_property -dict { PACKAGE_PIN E13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][7] }];
set_property -dict { PACKAGE_PIN E12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][8] }];
set_property -dict { PACKAGE_PIN C14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][9] }];
set_property -dict { PACKAGE_PIN C13 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][10] }];
set_property -dict { PACKAGE_PIN B12 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][11] }];
set_property -dict { PACKAGE_PIN B11 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][12] }];
set_property -dict { PACKAGE_PIN B14 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3][13] }];

set_property -dict { PACKAGE_PIN L20 IOSTANDARD LVCMOS33 } [get_ports { saFbWrt }];
set_property -dict { PACKAGE_PIN K16 IOSTANDARD LVCMOS33 } [get_ports { saFbClk }];
set_property -dict { PACKAGE_PIN K17 IOSTANDARD LVCMOS33 } [get_ports { saFbSel }];
set_property -dict { PACKAGE_PIN M17 IOSTANDARD LVCMOS33 } [get_ports { saFbReset }];
set_property -dict { PACKAGE_PIN L18 IOSTANDARD LVCMOS33 } [get_ports { saFbSleep }];

set_property -dict { PACKAGE_PIN A10 IOSTANDARD LVCMOS33 } [get_ports { ad5679Sclk }];
set_property -dict { PACKAGE_PIN B15 IOSTANDARD LVCMOS33 } [get_ports { ad5679Mosi }];
set_property -dict { PACKAGE_PIN A15 IOSTANDARD LVCMOS33 } [get_ports { ad5679Miso }];
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVCMOS33 } [get_ports { ad5679SyncB }];
set_property -dict { PACKAGE_PIN A12 IOSTANDARD LVCMOS33 } [get_ports { ad5679LdacB }];
set_property -dict { PACKAGE_PIN J14 IOSTANDARD LVCMOS33 } [get_ports { ad5679ResetB }];



# Boot Memory Port Mapping
set_property -dict { PACKAGE_PIN C23 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }];
set_property -dict { PACKAGE_PIN B24 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }];
set_property -dict { PACKAGE_PIN A25 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }];

# LEDs
set_property -dict { PACKAGE_PIN L22 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }];
set_property -dict { PACKAGE_PIN K22 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }];
set_property -dict { PACKAGE_PIN K23 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }];
set_property -dict { PACKAGE_PIN J23 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }];

# I2C PROM
set_property -dict { PACKAGE_PIN D23 IOSTANDARD LVCMOS33 } [get_ports { promScl }];
set_property -dict { PACKAGE_PIN D24 IOSTANDARD LVCMOS33 } [get_ports { promSda }];

# Power Monitoring
set_property -dict { PACKAGE_PIN C22 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }];
set_property -dict { PACKAGE_PIN B20 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }];

# RJ-45 LEDs
# set_property -dict { PACKAGE_PIN H26 IOSTANDARD LVCMOS33 } [get_ports { rj45RxGrn }];
# set_property -dict { PACKAGE_PIN H21 IOSTANDARD LVCMOS33 } [get_ports { rj45RxYlw }];
# set_property -dict { PACKAGE_PIN G21 IOSTANDARD LVCMOS33 } [get_ports { rj45TxGrn }];
# set_property -dict { PACKAGE_PIN H23 IOSTANDARD LVCMOS33 } [get_ports { rj45TxYlw }];

# Light Pipe LEDs
# set_property -dict { PACKAGE_PIN E25 IOSTANDARD LVCMOS33 } [get_ports { redL[0] }];
# set_property -dict { PACKAGE_PIN D25 IOSTANDARD LVCMOS33 } [get_ports { blueL[0] }];
# set_property -dict { PACKAGE_PIN G25 IOSTANDARD LVCMOS33 } [get_ports { greenL[0] }];
# set_property -dict { PACKAGE_PIN G26 IOSTANDARD LVCMOS33 } [get_ports { redL[1] }];
# set_property -dict { PACKAGE_PIN F25 IOSTANDARD LVCMOS33 } [get_ports { blueL[1] }];
# set_property -dict { PACKAGE_PIN E26 IOSTANDARD LVCMOS33 } [get_ports { greenL[1] }];



set_property BITSTREAM.CONFIG.CONFIGRATE 33  [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

