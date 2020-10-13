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
create_clock -name gtRefClk1 -period 5.000 [get_ports {gtRefClk1P}]

create_generated_clock -name axilClk [get_pins {U_RowModulePgp_1/REAL_PGP_GEN.U_Pgp2bGtx7VarLatWrapper_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT0}]

# MGT Mapping
# Clocks
set_property PACKAGE_PIN D6 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN D5 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN F6 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN F5 [get_ports {gtRefClk1N}]

# PGP
set_property PACKAGE_PIN F2 [get_ports {pgpTxP}]
set_property PACKAGE_PIN F1 [get_ports {pgpTxN}]
set_property PACKAGE_PIN G4 [get_ports {pgpRxP}]
set_property PACKAGE_PIN G3 [get_ports {pgpRxN}]

# Timing
#set_property PACKAGE_PIN E4 [get_ports {timingRxP}]
#set_property PACKAGE_PIN E3 [get_ports {timingRxN}]

# SFP
set_property PACKAGE_PIN B2 [get_ports {sfp0TxP}]
set_property PACKAGE_PIN B1 [get_ports {sfp0TxN}]
set_property PACKAGE_PIN C4 [get_ports {sfp0RxP}]
set_property PACKAGE_PIN C3 [get_ports {sfp0RxN}]
set_property PACKAGE_PIN A4 [get_ports {sfp1TxP}]
set_property PACKAGE_PIN A3 [get_ports {sfp1TxN}]
set_property PACKAGE_PIN B6 [get_ports {sfp1RxP}]
set_property PACKAGE_PIN B4 [get_ports {sfp1RxN}]


# DACs
set_property -dict { PACKAGE_PIN T19  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[0] }];
set_property -dict { PACKAGE_PIN U18  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[1] }];
set_property -dict { PACKAGE_PIN U20  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[2] }];
set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVCMOS25 } [get_ports { dacCsB[3] }];
set_property -dict { PACKAGE_PIN W19  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[4] }];
set_property -dict { PACKAGE_PIN AB18 IOSTANDARD LVCMOS25 } [get_ports { dacCsB[5] }];
set_property -dict { PACKAGE_PIN AA15 IOSTANDARD LVCMOS25 } [get_ports { dacCsB[6] }];
set_property -dict { PACKAGE_PIN Y16  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[7] }];
set_property -dict { PACKAGE_PIN D12  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[8] }];
set_property -dict { PACKAGE_PIN F16  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[9] }];
set_property -dict { PACKAGE_PIN D14  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[10] }];
set_property -dict { PACKAGE_PIN A15  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[11] }];

set_property -dict { PACKAGE_PIN T21  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[0] }];
set_property -dict { PACKAGE_PIN W21  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[1] }];
set_property -dict { PACKAGE_PIN Y21  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[2] }];
set_property -dict { PACKAGE_PIN AA19 IOSTANDARD LVCMOS25 } [get_ports { dacSdio[3] }];
set_property -dict { PACKAGE_PIN Y18  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[4] }];
set_property -dict { PACKAGE_PIN AB15 IOSTANDARD LVCMOS25 } [get_ports { dacSdio[5] }];
set_property -dict { PACKAGE_PIN U16  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[6] }];
set_property -dict { PACKAGE_PIN W14  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[7] }];
set_property -dict { PACKAGE_PIN G15  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[8] }];
set_property -dict { PACKAGE_PIN A13  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[9] }];
set_property -dict { PACKAGE_PIN C14  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[10] }];
set_property -dict { PACKAGE_PIN B17  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[11] }];

set_property -dict { PACKAGE_PIN U21  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[0] }];
set_property -dict { PACKAGE_PIN W22  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[1] }];
set_property -dict { PACKAGE_PIN Y22  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[2] }];
set_property -dict { PACKAGE_PIN AB20 IOSTANDARD LVCMOS25 } [get_ports { dacSdo[3] }];
set_property -dict { PACKAGE_PIN Y19  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[4] }];
set_property -dict { PACKAGE_PIN AB16 IOSTANDARD LVCMOS25 } [get_ports { dacSdo[5] }];
set_property -dict { PACKAGE_PIN V17  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[6] }];
set_property -dict { PACKAGE_PIN Y14  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[7] }];
set_property -dict { PACKAGE_PIN G16  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[8] }];
set_property -dict { PACKAGE_PIN A14  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[9] }];
set_property -dict { PACKAGE_PIN C15  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[10] }];
set_property -dict { PACKAGE_PIN A18  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[11] }];

set_property -dict { PACKAGE_PIN U22  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[0] }];
set_property -dict { PACKAGE_PIN U17  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[1] }];
set_property -dict { PACKAGE_PIN AA20 IOSTANDARD LVCMOS25 } [get_ports { dacSclk[2] }];
set_property -dict { PACKAGE_PIN V20  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[3] }];
set_property -dict { PACKAGE_PIN W17  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[4] }];
set_property -dict { PACKAGE_PIN AA16 IOSTANDARD LVCMOS25 } [get_ports { dacSclk[5] }];
set_property -dict { PACKAGE_PIN R16  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[6] }];
set_property -dict { PACKAGE_PIN V15  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[7] }];
set_property -dict { PACKAGE_PIN C12  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[8] }];
set_property -dict { PACKAGE_PIN C13  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[9] }];
set_property -dict { PACKAGE_PIN B16  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[10] }];
set_property -dict { PACKAGE_PIN D15  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[11] }];

set_property -dict { PACKAGE_PIN V22  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[0] }];
set_property -dict { PACKAGE_PIN V18  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[1] }];
set_property -dict { PACKAGE_PIN AB21 IOSTANDARD LVCMOS25 } [get_ports { dacResetB[2] }];
set_property -dict { PACKAGE_PIN W20  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[3] }];
set_property -dict { PACKAGE_PIN Y17  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[4] }];
set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVCMOS25 } [get_ports { dacResetB[5] }];
set_property -dict { PACKAGE_PIN T16  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[6] }];
set_property -dict { PACKAGE_PIN W15  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[7] }];
set_property -dict { PACKAGE_PIN B12  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[8] }];
set_property -dict { PACKAGE_PIN B13  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[9] }];
set_property -dict { PACKAGE_PIN A16  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[10] }];
set_property -dict { PACKAGE_PIN D16  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[11] }];

set_property -dict { PACKAGE_PIN T18  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[0] }];
set_property -dict { PACKAGE_PIN T20  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[1] }];
set_property -dict { PACKAGE_PIN AA21 IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[2] }];
set_property -dict { PACKAGE_PIN V19  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[3] }];
set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[4] }];
set_property -dict { PACKAGE_PIN AA14 IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[5] }];
set_property -dict { PACKAGE_PIN W16  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[6] }];
set_property -dict { PACKAGE_PIN T15  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[7] }];
set_property -dict { PACKAGE_PIN F15  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[8] }];
set_property -dict { PACKAGE_PIN E14  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[9] }];
set_property -dict { PACKAGE_PIN B15  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[10] }];
set_property -dict { PACKAGE_PIN C17  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[11] }];

set_property -dict { PACKAGE_PIN E17  IOSTANDARD LVDS_25 } [get_ports { dacClkP[0] }];
set_property -dict { PACKAGE_PIN E18  IOSTANDARD LVDS_25 } [get_ports { dacClkN[0] }];
set_property -dict { PACKAGE_PIN E16  IOSTANDARD LVDS_25 } [get_ports { dacClkP[1] }];
set_property -dict { PACKAGE_PIN D17  IOSTANDARD LVDS_25 } [get_ports { dacClkP[1] }];
set_property -dict { PACKAGE_PIN H17  IOSTANDARD LVDS_25 } [get_ports { dacClkP[2] }];
set_property -dict { PACKAGE_PIN G17  IOSTANDARD LVDS_25 } [get_ports { dacClkN[2] }];
set_property -dict { PACKAGE_PIN J16  IOSTANDARD LVDS_25 } [get_ports { dacClkP[3] }];
set_property -dict { PACKAGE_PIN J17  IOSTANDARD LVDS_25 } [get_ports { dacClkN[3] }];
set_property -dict { PACKAGE_PIN F18  IOSTANDARD LVDS_25 } [get_ports { dacClkP[4] }];
set_property -dict { PACKAGE_PIN E19  IOSTANDARD LVDS_25 } [get_ports { dacClkN[4] }];
set_property -dict { PACKAGE_PIN D19  IOSTANDARD LVDS_25 } [get_ports { dacClkP[5] }];
set_property -dict { PACKAGE_PIN D20  IOSTANDARD LVDS_25 } [get_ports { dacClkN[5] }];
set_property -dict { PACKAGE_PIN C19  IOSTANDARD LVDS_25 } [get_ports { dacClkP[6] }];
set_property -dict { PACKAGE_PIN C20  IOSTANDARD LVDS_25 } [get_ports { dacClkN[6] }];
set_property -dict { PACKAGE_PIN B18  IOSTANDARD LVDS_25 } [get_ports { dacClkP[7] }];
set_property -dict { PACKAGE_PIN A19  IOSTANDARD LVDS_25 } [get_ports { dacClkN[7] }];
set_property -dict { PACKAGE_PIN C22  IOSTANDARD LVDS_25 } [get_ports { dacClkP[8] }];
set_property -dict { PACKAGE_PIN B22  IOSTANDARD LVDS_25 } [get_ports { dacClkN[8] }];
set_property -dict { PACKAGE_PIN A20  IOSTANDARD LVDS_25 } [get_ports { dacClkP[9] }];
set_property -dict { PACKAGE_PIN A21  IOSTANDARD LVDS_25 } [get_ports { dacClkN[9] }];
set_property -dict { PACKAGE_PIN D21  IOSTANDARD LVDS_25 } [get_ports { dacClkP[10] }];
set_property -dict { PACKAGE_PIN D22  IOSTANDARD LVDS_25 } [get_ports { dacClkN[10] }];
set_property -dict { PACKAGE_PIN B20  IOSTANDARD LVDS_25 } [get_ports { dacClkP[11] }];
set_property -dict { PACKAGE_PIN B21  IOSTANDARD LVDS_25 } [get_ports { dacClkN[11] }];



# Boot Memory Port Mapping
set_property -dict { PACKAGE_PIN L16 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }];
set_property -dict { PACKAGE_PIN H18 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }];
set_property -dict { PACKAGE_PIN H19 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }];

# LEDs
set_property -dict { PACKAGE_PIN P16 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }];
set_property -dict { PACKAGE_PIN N17 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }];
set_property -dict { PACKAGE_PIN R21 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }];
set_property -dict { PACKAGE_PIN R22 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }];

# I2C PROM
set_property -dict { PACKAGE_PIN J20 IOSTANDARD LVCMOS33 } [get_ports { promScl }];
set_property -dict { PACKAGE_PIN H20 IOSTANDARD LVCMOS33 } [get_ports { promSda }];

# Power Monitoring
set_property -dict { PACKAGE_PIN E22 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }];
set_property -dict { PACKAGE_PIN H22 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }];



set_property BITSTREAM.CONFIG.CONFIGRATE 33  [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

