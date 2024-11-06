##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'Warm TDM', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
create_clock -name gtRefClk0 -period 4.000 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 8.000 [get_ports {gtRefClk1P}]


set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingRxWordClk] 

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingRxWordClk] 


# MGT Mapping
# Clocks
set_property PACKAGE_PIN H6 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN H5 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN K6 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN K5 [get_ports {gtRefClk1N}]

# PGP
# set_property PACKAGE_PIN P2 [get_ports {pgpTxP[1]}]
# set_property PACKAGE_PIN P1 [get_ports {pgpTxN[1]}]
# set_property PACKAGE_PIN R4 [get_ports {pgpRxP[1]}]
# set_property PACKAGE_PIN R3 [get_ports {pgpRxN[1]}]

# # GT Timing
set_property PACKAGE_PIN N4 [get_ports {pgpRxP[0]}]
set_property PACKAGE_PIN N3 [get_ports {pgpRxN[0]}]
set_property PACKAGE_PIN M2 [get_ports {pgpTxP[0]}]
set_property PACKAGE_PIN M1 [get_ports {pgpTxN[0]}]


# IO Timing
set_property -dict { PACKAGE_PIN AA3 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkP }];
set_property -dict { PACKAGE_PIN AA2 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkN }];
set_property -dict { PACKAGE_PIN W1  IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataP }];
set_property -dict { PACKAGE_PIN Y1  IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataN }];
set_property -dict { PACKAGE_PIN U7  IOSTANDARD LVDS } [get_ports { timingTxClkP }];
set_property -dict { PACKAGE_PIN V6  IOSTANDARD LVDS } [get_ports { timingTxClkN }];
set_property -dict { PACKAGE_PIN V4  IOSTANDARD LVDS } [get_ports { timingTxDataP }];
set_property -dict { PACKAGE_PIN W4  IOSTANDARD LVDS } [get_ports { timingTxDataN }];


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
# set_property -dict { PACKAGE_PIN AA17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[0] }];
# set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[0] }];
# set_property -dict { PACKAGE_PIN AB16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[0] }];
# set_property -dict { PACKAGE_PIN AC16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[0] }];

# set_property -dict { PACKAGE_PIN AE17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][0] }];
# set_property -dict { PACKAGE_PIN AF17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][0] }];
# set_property -dict { PACKAGE_PIN AE18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][1] }];
# set_property -dict { PACKAGE_PIN AF18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][1] }];
# set_property -dict { PACKAGE_PIN AF19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][2] }];
# set_property -dict { PACKAGE_PIN AF20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][2] }];
# set_property -dict { PACKAGE_PIN AA14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][3] }];
# set_property -dict { PACKAGE_PIN AA15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][3] }];
# set_property -dict { PACKAGE_PIN AA19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][4] }];
# set_property -dict { PACKAGE_PIN AA20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][4] }];
# set_property -dict { PACKAGE_PIN AB19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][5] }];
# set_property -dict { PACKAGE_PIN AB20 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][5] }];
# set_property -dict { PACKAGE_PIN V16  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][6] }];
# set_property -dict { PACKAGE_PIN V17  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][6] }];
# set_property -dict { PACKAGE_PIN W15  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][7] }];
# set_property -dict { PACKAGE_PIN W16  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][7] }];

# set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[1] }];
# set_property -dict { PACKAGE_PIN AC17 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[1] }];
# set_property -dict { PACKAGE_PIN AC18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[1] }];
# set_property -dict { PACKAGE_PIN AD18 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[1] }];

# set_property -dict { PACKAGE_PIN AF14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][0] }];
# set_property -dict { PACKAGE_PIN AF15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][0] }];
# set_property -dict { PACKAGE_PIN AD15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][1] }];
# set_property -dict { PACKAGE_PIN AE15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][1] }];
# set_property -dict { PACKAGE_PIN AD16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][2] }];
# set_property -dict { PACKAGE_PIN AE16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][2] }];
# set_property -dict { PACKAGE_PIN AC14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][3] }];
# set_property -dict { PACKAGE_PIN AD14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][3] }];
# set_property -dict { PACKAGE_PIN AC19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][4] }];
# set_property -dict { PACKAGE_PIN AD19 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][4] }];
# set_property -dict { PACKAGE_PIN Y17  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][5] }];
# set_property -dict { PACKAGE_PIN Y18  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][5] }];
# set_property -dict { PACKAGE_PIN W18  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][6] }];
# set_property -dict { PACKAGE_PIN W19  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][6] }];
# set_property -dict { PACKAGE_PIN V18  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][7] }];
# set_property -dict { PACKAGE_PIN V19  IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][7] }];

# set_property -dict { PACKAGE_PIN V14  IOSTANDARD LVDS } [get_ports { adcClkP }];
# set_property -dict { PACKAGE_PIN W14  IOSTANDARD LVDS } [get_ports { adcClkN }];


set_property -dict { PACKAGE_PIN AF2 IOSTANDARD LVCMOS18 } [get_ports { adcSclk }];
set_property -dict { PACKAGE_PIN AE2 IOSTANDARD LVCMOS18 } [get_ports { adcSdio }];
set_property -dict { PACKAGE_PIN AE1 IOSTANDARD LVCMOS18 } [get_ports { adcCsb }];
set_property -dict { PACKAGE_PIN AF3 IOSTANDARD LVCMOS18 } [get_ports { adcSync }];
set_property -dict { PACKAGE_PIN AE6 IOSTANDARD LVCMOS18 } [get_ports { adcPdwn }];


## Fast DACS
set_property -dict { PACKAGE_PIN AE26 IOSTANDARD LVCMOS33 } [get_ports { dacDb0[0] }];
set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVCMOS33 } [get_ports { dacDb0[1] }];
set_property -dict { PACKAGE_PIN AD26 IOSTANDARD LVCMOS33 } [get_ports { dacDb0[2] }];
set_property -dict { PACKAGE_PIN AB25 IOSTANDARD LVCMOS33 } [get_ports { dacDb0[3] }];
set_property -dict { PACKAGE_PIN AA25 IOSTANDARD LVCMOS33 } [get_ports { dacDb0[4] }];
set_property -dict { PACKAGE_PIN Y23  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[5] }];
set_property -dict { PACKAGE_PIN Y25  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[6] }];
set_property -dict { PACKAGE_PIN W26  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[7] }];
set_property -dict { PACKAGE_PIN V22  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[8] }];
set_property -dict { PACKAGE_PIN Y26  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[9] }];
set_property -dict { PACKAGE_PIN V24  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[10] }];
set_property -dict { PACKAGE_PIN V23  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[11] }];
set_property -dict { PACKAGE_PIN V26  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[12] }];
set_property -dict { PACKAGE_PIN U25  IOSTANDARD LVCMOS33 } [get_ports { dacDb0[13] }];

set_property -dict { PACKAGE_PIN AC23 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[0] }];
set_property -dict { PACKAGE_PIN AB26 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[1] }];
set_property -dict { PACKAGE_PIN W24  IOSTANDARD LVCMOS33 } [get_ports { dacWrt[2] }];
set_property -dict { PACKAGE_PIN AC24 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[3] }];

set_property -dict { PACKAGE_PIN AD24 IOSTANDARD LVCMOS33 } [get_ports { dacClk[0] }];
set_property -dict { PACKAGE_PIN AC26 IOSTANDARD LVCMOS33 } [get_ports { dacClk[1] }];
set_property -dict { PACKAGE_PIN W23  IOSTANDARD LVCMOS33 } [get_ports { dacClk[2] }];
set_property -dict { PACKAGE_PIN AE25 IOSTANDARD LVCMOS33 } [get_ports { dacClk[3] }];

set_property -dict { PACKAGE_PIN AC22 IOSTANDARD LVCMOS33 } [get_ports { dacSel[0] }];
set_property -dict { PACKAGE_PIN AB24 IOSTANDARD LVCMOS33 } [get_ports { dacSel[1] }];
set_property -dict { PACKAGE_PIN AA24 IOSTANDARD LVCMOS33 } [get_ports { dacSel[2] }];
set_property -dict { PACKAGE_PIN AE23 IOSTANDARD LVCMOS33 } [get_ports { dacSel[3] }];

set_property -dict { PACKAGE_PIN AD23 IOSTANDARD LVCMOS33 } [get_ports { dacReset[0] }];
set_property -dict { PACKAGE_PIN AD25 IOSTANDARD LVCMOS33 } [get_ports { dacReset[1] }];
set_property -dict { PACKAGE_PIN AA23 IOSTANDARD LVCMOS33 } [get_ports { dacReset[2] }];
set_property -dict { PACKAGE_PIN AF25 IOSTANDARD LVCMOS33 } [get_ports { dacReset[3] }];


set_property -dict { PACKAGE_PIN U19 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[0] }];
set_property -dict { PACKAGE_PIN T19 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[1] }];
set_property -dict { PACKAGE_PIN P18 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[2] }];
set_property -dict { PACKAGE_PIN P19 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[3] }];
set_property -dict { PACKAGE_PIN R20 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[4] }];
set_property -dict { PACKAGE_PIN T23 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[5] }];
set_property -dict { PACKAGE_PIN R21 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[6] }];
set_property -dict { PACKAGE_PIN P21 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[7] }];
set_property -dict { PACKAGE_PIN T24 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[8] }];
set_property -dict { PACKAGE_PIN R23 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[9] }];
set_property -dict { PACKAGE_PIN P20 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[10] }];
set_property -dict { PACKAGE_PIN P23 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[11] }];
set_property -dict { PACKAGE_PIN P24 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[12] }];
set_property -dict { PACKAGE_PIN P26 IOSTANDARD LVCMOS33 } [get_ports { dacDb1[13] }];
				    
set_property -dict { PACKAGE_PIN R18  IOSTANDARD LVCMOS33 } [get_ports { dacWrt[4] }];
set_property -dict { PACKAGE_PIN P25  IOSTANDARD LVCMOS33 } [get_ports { dacWrt[5] }];
set_property -dict { PACKAGE_PIN T22  IOSTANDARD LVCMOS33 } [get_ports { dacWrt[6] }];
set_property -dict { PACKAGE_PIN R17  IOSTANDARD LVCMOS33 } [get_ports { dacWrt[7] }];
				    
set_property -dict { PACKAGE_PIN T17 IOSTANDARD LVCMOS33 } [get_ports { dacClk[4] }];
set_property -dict { PACKAGE_PIN R26 IOSTANDARD LVCMOS33 } [get_ports { dacClk[5] }];
set_property -dict { PACKAGE_PIN T25 IOSTANDARD LVCMOS33 } [get_ports { dacClk[6] }];
set_property -dict { PACKAGE_PIN T18 IOSTANDARD LVCMOS33 } [get_ports { dacClk[7] }];
				    
set_property -dict { PACKAGE_PIN U16 IOSTANDARD LVCMOS33 } [get_ports { dacSel[4] }];
set_property -dict { PACKAGE_PIN R22 IOSTANDARD LVCMOS33 } [get_ports { dacSel[5] }];
set_property -dict { PACKAGE_PIN U20 IOSTANDARD LVCMOS33 } [get_ports { dacSel[6] }];
set_property -dict { PACKAGE_PIN P16 IOSTANDARD LVCMOS33 } [get_ports { dacSel[7] }];
				    
set_property -dict { PACKAGE_PIN U17 IOSTANDARD LVCMOS33 } [get_ports { dacReset[4] }];
set_property -dict { PACKAGE_PIN R25 IOSTANDARD LVCMOS33 } [get_ports { dacReset[5] }];
set_property -dict { PACKAGE_PIN T20 IOSTANDARD LVCMOS33 } [get_ports { dacReset[6] }];
set_property -dict { PACKAGE_PIN R16 IOSTANDARD LVCMOS33 } [get_ports { dacReset[7] }];


set_property -dict { PACKAGE_PIN J18 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[0] }];  
set_property -dict { PACKAGE_PIN H17 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[1] }];  
set_property -dict { PACKAGE_PIN H18 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[2] }];  
set_property -dict { PACKAGE_PIN G19 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[3] }];  
set_property -dict { PACKAGE_PIN F19 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[4] }];  
set_property -dict { PACKAGE_PIN F17 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[5] }];  
set_property -dict { PACKAGE_PIN F20 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[6] }];  
set_property -dict { PACKAGE_PIN E18 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[7] }];  
set_property -dict { PACKAGE_PIN E17 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[8] }];  
set_property -dict { PACKAGE_PIN E16 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[9] }];  
set_property -dict { PACKAGE_PIN E15 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[10] }]; 
set_property -dict { PACKAGE_PIN D19 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[11] }]; 
set_property -dict { PACKAGE_PIN E20 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[12] }]; 
set_property -dict { PACKAGE_PIN D18 IOSTANDARD LVCMOS33 } [get_ports { dacDb2[13] }]; 
				    						       
set_property -dict { PACKAGE_PIN K16 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[8] }]; 
set_property -dict { PACKAGE_PIN L17 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[9] }]; 
set_property -dict { PACKAGE_PIN G17 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[10] }]; 
set_property -dict { PACKAGE_PIN J19 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[11] }]; 
				    						       
set_property -dict { PACKAGE_PIN J20 IOSTANDARD LVCMOS33 } [get_ports { dacClk[8] }]; 
set_property -dict { PACKAGE_PIN M17 IOSTANDARD LVCMOS33 } [get_ports { dacClk[9] }]; 
set_property -dict { PACKAGE_PIN F18 IOSTANDARD LVCMOS33 } [get_ports { dacClk[10] }]; 
set_property -dict { PACKAGE_PIN K17 IOSTANDARD LVCMOS33 } [get_ports { dacClk[11] }]; 
				    						       
set_property -dict { PACKAGE_PIN K20 IOSTANDARD LVCMOS33 } [get_ports { dacSel[8] }]; 
set_property -dict { PACKAGE_PIN L19 IOSTANDARD LVCMOS33 } [get_ports { dacSel[9] }]; 
set_property -dict { PACKAGE_PIN H19 IOSTANDARD LVCMOS33 } [get_ports { dacSel[10] }]; 
set_property -dict { PACKAGE_PIN M16 IOSTANDARD LVCMOS33 } [get_ports { dacSel[11] }]; 
				    						       
set_property -dict { PACKAGE_PIN K18 IOSTANDARD LVCMOS33 } [get_ports { dacReset[8] }];
set_property -dict { PACKAGE_PIN L20 IOSTANDARD LVCMOS33 } [get_ports { dacReset[9] }];
set_property -dict { PACKAGE_PIN G20 IOSTANDARD LVCMOS33 } [get_ports { dacReset[10] }];
set_property -dict { PACKAGE_PIN L18 IOSTANDARD LVCMOS33 } [get_ports { dacReset[11] }];


set_property -dict { PACKAGE_PIN H8  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[0] }];  
set_property -dict { PACKAGE_PIN G10 IOSTANDARD LVCMOS33 } [get_ports { dacDb3[1] }];  
set_property -dict { PACKAGE_PIN F9  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[2] }];  
set_property -dict { PACKAGE_PIN H9  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[3] }];  
set_property -dict { PACKAGE_PIN G9  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[4] }];  
set_property -dict { PACKAGE_PIN F10 IOSTANDARD LVCMOS33 } [get_ports { dacDb3[5] }];  
set_property -dict { PACKAGE_PIN F13 IOSTANDARD LVCMOS33 } [get_ports { dacDb3[6] }];  
set_property -dict { PACKAGE_PIN E11 IOSTANDARD LVCMOS33 } [get_ports { dacDb3[7] }];  
set_property -dict { PACKAGE_PIN F8  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[8] }];  
set_property -dict { PACKAGE_PIN E10 IOSTANDARD LVCMOS33 } [get_ports { dacDb3[9] }];  
set_property -dict { PACKAGE_PIN D9  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[10] }]; 
set_property -dict { PACKAGE_PIN D10 IOSTANDARD LVCMOS33 } [get_ports { dacDb3[11] }]; 
set_property -dict { PACKAGE_PIN D8  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[12] }]; 
set_property -dict { PACKAGE_PIN C9  IOSTANDARD LVCMOS33 } [get_ports { dacDb3[13] }]; 
				 						       
set_property -dict { PACKAGE_PIN J8  IOSTANDARD LVCMOS33 } [get_ports { dacWrt[12] }]; 
set_property -dict { PACKAGE_PIN G11 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[13] }]; 
set_property -dict { PACKAGE_PIN E12 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[14] }]; 
set_property -dict { PACKAGE_PIN G14 IOSTANDARD LVCMOS33 } [get_ports { dacWrt[15] }]; 
				 						       
set_property -dict { PACKAGE_PIN G12 IOSTANDARD LVCMOS33 } [get_ports { dacClk[12] }]; 
set_property -dict { PACKAGE_PIN J11 IOSTANDARD LVCMOS33 } [get_ports { dacClk[13] }]; 
set_property -dict { PACKAGE_PIN F12 IOSTANDARD LVCMOS33 } [get_ports { dacClk[14] }]; 
set_property -dict { PACKAGE_PIN F14 IOSTANDARD LVCMOS33 } [get_ports { dacClk[15] }]; 
				 						       
set_property -dict { PACKAGE_PIN D11 IOSTANDARD LVCMOS33 } [get_ports { dacSel[12] }]; 
set_property -dict { PACKAGE_PIN H11 IOSTANDARD LVCMOS33 } [get_ports { dacSel[13] }]; 
set_property -dict { PACKAGE_PIN J13 IOSTANDARD LVCMOS33 } [get_ports { dacSel[14] }]; 
set_property -dict { PACKAGE_PIN J14 IOSTANDARD LVCMOS33 } [get_ports { dacSel[15] }]; 
				 						       
set_property -dict { PACKAGE_PIN J10 IOSTANDARD LVCMOS33 } [get_ports { dacReset[12] }];
set_property -dict { PACKAGE_PIN H12 IOSTANDARD LVCMOS33 } [get_ports { dacReset[13] }];
set_property -dict { PACKAGE_PIN H13 IOSTANDARD LVCMOS33 } [get_ports { dacReset[14] }];
set_property -dict { PACKAGE_PIN H14 IOSTANDARD LVCMOS33 } [get_ports { dacReset[15] }];

## Slow DACs
set_property -dict { PACKAGE_PIN N17 IOSTANDARD LVCMOS33 } [get_ports { feDacSclk }];
set_property -dict { PACKAGE_PIN N19 IOSTANDARD LVCMOS33 } [get_ports { feDacMosi }];
set_property -dict { PACKAGE_PIN N18 IOSTANDARD LVCMOS33 } [get_ports { feDacMiso }];
set_property -dict { PACKAGE_PIN N16 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[0] }];
set_property -dict { PACKAGE_PIN M20 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[1] }];
set_property -dict { PACKAGE_PIN M21 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[2] }];
set_property -dict { PACKAGE_PIN M19 IOSTANDARD LVCMOS33 } [get_ports { feDacLdacB[0] }];
set_property -dict { PACKAGE_PIN N21 IOSTANDARD LVCMOS33 } [get_ports { feDacLdacB[1] }];
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS33 } [get_ports { feDacLdacB[2] }];
set_property -dict { PACKAGE_PIN K26 IOSTANDARD LVCMOS33 } [get_ports { feDacResetB[0] }];
set_property -dict { PACKAGE_PIN L24 IOSTANDARD LVCMOS33 } [get_ports { feDacResetB[1] }];
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS33 } [get_ports { feDacResetB[2] }];

## Timing Source Select
set_property -dict { PACKAGE_PIN U24 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[0] }];
set_property -dict { PACKAGE_PIN U22 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[1] }];
set_property -dict { PACKAGE_PIN U26 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[0] }];
set_property -dict { PACKAGE_PIN W25 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[1] }];
set_property -dict { PACKAGE_PIN W20 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[0] }];
set_property -dict { PACKAGE_PIN V21 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[1] }];
set_property -dict { PACKAGE_PIN U21 IOSTANDARD LVCMOS33 } [get_ports { xbarTimingSel[0] }];
set_property -dict { PACKAGE_PIN Y20 IOSTANDARD LVCMOS33 } [get_ports { xbarTimingSel[1] }];

## TES Delatch
set_property -dict { PACKAGE_PIN N26 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[0] }];
set_property -dict { PACKAGE_PIN M25 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[1] }];
set_property -dict { PACKAGE_PIN N23 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[2] }];
set_property -dict { PACKAGE_PIN K25 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[3] }];
set_property -dict { PACKAGE_PIN N24 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[4] }];
set_property -dict { PACKAGE_PIN M26 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[5] }];
set_property -dict { PACKAGE_PIN L25 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[6] }];
set_property -dict { PACKAGE_PIN M24 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[7] }];

# Boot Memory Port Mapping
set_property -dict { PACKAGE_PIN C23 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }];
set_property -dict { PACKAGE_PIN B24 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }];
set_property -dict { PACKAGE_PIN A25 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }];

# LEDs
set_property -dict { PACKAGE_PIN G25 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }];
set_property -dict { PACKAGE_PIN F25 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }];
set_property -dict { PACKAGE_PIN E25 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }];
set_property -dict { PACKAGE_PIN E26 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }];
set_property -dict { PACKAGE_PIN C26 IOSTANDARD LVCMOS33 } [get_ports { leds[4] }];
set_property -dict { PACKAGE_PIN D26 IOSTANDARD LVCMOS33 } [get_ports { leds[5] }];
set_property -dict { PACKAGE_PIN C24 IOSTANDARD LVCMOS33 } [get_ports { leds[6] }];
set_property -dict { PACKAGE_PIN D25 IOSTANDARD LVCMOS33 } [get_ports { leds[7] }];


# I2C PROM
set_property -dict { PACKAGE_PIN J26 IOSTANDARD LVCMOS33 } [get_ports { locScl }];
set_property -dict { PACKAGE_PIN H26 IOSTANDARD LVCMOS33 } [get_ports { locSda }];

# Power Monitoring
set_property -dict { PACKAGE_PIN B20 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }];
set_property -dict { PACKAGE_PIN D21 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }];
set_property -dict { PACKAGE_PIN J24 IOSTANDARD LVCMOS33 } [get_ports { tempAlertL }];

# SFP I2C
set_property -dict { PACKAGE_PIN C22 IOSTANDARD LVCMOS33 } [get_ports { sfpScl[0] }];
set_property -dict { PACKAGE_PIN C21 IOSTANDARD LVCMOS33 } [get_ports { sfpSda[0] }];
set_property -dict { PACKAGE_PIN B21 IOSTANDARD LVCMOS33 } [get_ports { sfpScl[1] }];
set_property -dict { PACKAGE_PIN A20 IOSTANDARD LVCMOS33 } [get_ports { sfpSda[1] }];

# Analog Power Enable
set_property -dict { PACKAGE_PIN G26 IOSTANDARD LVCMOS33 } [get_ports { anaPwrEn }];

# VR Sync
set_property -dict { PACKAGE_PIN K22 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncA }];
set_property -dict { PACKAGE_PIN H24 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncB }];
set_property -dict { PACKAGE_PIN J25 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncC }];

set_property -dict { PACKAGE_PIN D24 IOSTANDARD LVCMOS33 } [get_ports { lemoIn[0] }];
set_property -dict { PACKAGE_PIN D23 IOSTANDARD LVCMOS33 } [get_ports { lemoIn[1] }];
set_property -dict { PACKAGE_PIN A24 IOSTANDARD LVCMOS33 } [get_ports { lemoOut[0] }];
set_property -dict { PACKAGE_PIN A23 IOSTANDARD LVCMOS33 } [get_ports { lemoOut[1] }];


# RJ-45 LEDs

set_property -dict { PACKAGE_PIN B15 IOSTANDARD LVCMOS33 } [get_ports { conRxGreenLed }];
set_property -dict { PACKAGE_PIN A14 IOSTANDARD LVCMOS33 } [get_ports { conRxYellowLed }];
set_property -dict { PACKAGE_PIN B12 IOSTANDARD LVCMOS33 } [get_ports { conTxGreenLed }];
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVCMOS33 } [get_ports { conTxYellowLed }];

## Thermistors
set_property -dict { PACKAGE_PIN C19 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[0] }];
set_property -dict { PACKAGE_PIN B19 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[0] }];
set_property -dict { PACKAGE_PIN H16 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[1] }];
set_property -dict { PACKAGE_PIN G16 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[1] }];
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[2] }];
set_property -dict { PACKAGE_PIN A17 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[2] }];
set_property -dict { PACKAGE_PIN J15 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[3] }];
set_property -dict { PACKAGE_PIN J16 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[3] }];
set_property -dict { PACKAGE_PIN C16 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[4] }];
set_property -dict { PACKAGE_PIN B16 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[4] }];
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[5] }];
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[5] }];

set_property -dict { PACKAGE_PIN C17 IOSTANDARD LVCMOS33 } [get_ports { feThermistorP[0] }];
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS33 } [get_ports { feThermistorP[1] }];
set_property -dict { PACKAGE_PIN C18 IOSTANDARD LVCMOS33 } [get_ports { feThermistorN[0] }];
set_property -dict { PACKAGE_PIN A19 IOSTANDARD LVCMOS33 } [get_ports { feThermistorN[1] }];

# ASIC signal
set_property -dict {PACKAGE_PIN C13 IOSTANDARD LVCMOS33 } [get_ports { resetB }];

# FE VR Sync
set_property -dict {PACKAGE_PIN D14 IOSTANDARD LVCMOS33 } [get_ports { feVrSyncA }];
set_property -dict {PACKAGE_PIN A15 IOSTANDARD LVCMOS33 } [get_ports { feVrSyncB }];

#FE I2C
set_property -dict {PACKAGE_PIN A8  IOSTANDARD LVCMOS33 } [get_ports { feI2cScl[0] }];
set_property -dict {PACKAGE_PIN B9  IOSTANDARD LVCMOS33 } [get_ports { feI2cSda[0] }];
set_property -dict {PACKAGE_PIN A9  IOSTANDARD LVCMOS33 } [get_ports { feI2cScl[1] }];
set_property -dict {PACKAGE_PIN B10  IOSTANDARD LVCMOS33 } [get_ports { feI2cSda[1] }];
set_property -dict {PACKAGE_PIN A10  IOSTANDARD LVCMOS33 } [get_ports { feI2cScl[2] }];
set_property -dict {PACKAGE_PIN C11  IOSTANDARD LVCMOS33 } [get_ports { feI2cSda[2] }];
set_property -dict {PACKAGE_PIN B11  IOSTANDARD LVCMOS33 } [get_ports { feI2cScl[3] }];
set_property -dict {PACKAGE_PIN A12  IOSTANDARD LVCMOS33 } [get_ports { feI2cSda[3] }];

set_property BITSTREAM.CONFIG.CONFIGRATE 33  [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

