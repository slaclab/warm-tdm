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

create_generated_clock -name gtRefClk0Div2 [get_pins {U_ComCore_1/U_IBUFDS_GTE2/ODIV2}]

create_generated_clock -name axilClk [get_pins {U_ComCore_1/U_PgpCore_1/REAL_PGP_GEN.U_Pgp2bGtx7VarLatWrapper_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT0}]

create_generated_clock -name dnaDivClk [get_pins U_WarmTdmCommon_1/U_AxiVersion_1/GEN_DEVICE_DNA.DeviceDna_1/GEN_7SERIES.DeviceDna7Series_Inst/BUFR_Inst/O]
create_generated_clock -name icapClk [get_pins U_WarmTdmCommon_1/U_AxiVersion_1/GEN_ICAP.Iprog_1/GEN_7SERIES.Iprog7Series_Inst/DIVCLK_GEN.BUFR_ICPAPE2/O]

#create_generated_clock -name dacClk -divide_by 200 -source [get_ports {timingRxClkP}] [get_pins {U_TimingRx_1/DAC_CLK_BUFG/O}]


create_generated_clock -name ethClk [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name ethClkDiv2 [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]


create_generated_clock -name idelayClk [get_pins {U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT1}]

create_generated_clock -name timingTxClk [get_pins {U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name timingTxBitClk [get_pins {U_Timing_1/U_TimingTx_1/U_TimingMmcm_1/U_Mmcm/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins {U_Timing_1/U_TimingTx_1/U_TimingMmcm_1/U_Mmcm/CLKOUT1}]

create_generated_clock -name timingRxBitClk [get_pins {U_Timing_1/U_TimingRx_1/U_TimingMmcm_1/U_Mmcm/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins {U_Timing_1/U_TimingRx_1/U_TimingMmcm_1/U_Mmcm/CLKOUT1}]


#set ethRxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/RXOUTCLK}
#set ethTxClk {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.TEN_GIG_ETH_GEN.U_TenGigEthGtx7_1/U_TenGigEthGtx7Core/U0/gt0_gtwizard_10gbaser_multi_gt_i/gt0_gtwizard_10gbaser_i/gtxe2_i/TXOUTCLK}

#set_clock_groups -asynchronous \
#    -group [get_clocks {gtRefClk0Div2}] \
#    -group [get_clocks ${ethTxClk}] \
    #    -group [get_clocks ${ethRxClk}]

set_clock_groups -asynchronous \
    -group [get_clocks {gtRefClk0Div2}] \
    -group [get_clocks {ethClk}] 

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks axilClk] \
    -group [get_clocks -include_generated_clocks timingRxClk] 

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks gtRefClk0Div2]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks -include_generated_clocks dnaDivClk] \
    -group [get_clocks icapClk]

 set_clock_groups -asynchronous \
     -group [get_clocks axilClk] \
     -group [get_clocks ethClk] \


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
set_property -dict { PACKAGE_PIN E11  IOSTANDARD LVDS_25 } [get_ports { timingRxClkP }];
set_property -dict { PACKAGE_PIN D11  IOSTANDARD LVDS_25 } [get_ports { timingRxClkN }];
set_property -dict { PACKAGE_PIN G11  IOSTANDARD LVDS_25 } [get_ports { timingRxDataP }];
set_property -dict { PACKAGE_PIN G10  IOSTANDARD LVDS_25 } [get_ports { timingRxDataN }];
set_property -dict { PACKAGE_PIN H12  IOSTANDARD LVDS_25 } [get_ports { timingTxClkP }];
set_property -dict { PACKAGE_PIN G12  IOSTANDARD LVDS_25 } [get_ports { timingTxClkN }];
set_property -dict { PACKAGE_PIN F9   IOSTANDARD LVDS_25 } [get_ports { timingTxDataP }];
set_property -dict { PACKAGE_PIN E9   IOSTANDARD LVDS_25 } [get_ports { timingTxDataN }];


# SFP
set_property PACKAGE_PIN B2 [get_ports {sfp0TxP}]
set_property PACKAGE_PIN B1 [get_ports {sfp0TxN}]
set_property PACKAGE_PIN C4 [get_ports {sfp0RxP}]
set_property PACKAGE_PIN C3 [get_ports {sfp0RxN}]
# set_property PACKAGE_PIN A4 [get_ports {sfp1TxP}]
# set_property PACKAGE_PIN A3 [get_ports {sfp1TxN}]
# set_property PACKAGE_PIN B6 [get_ports {sfp1RxP}]
# set_property PACKAGE_PIN B4 [get_ports {sfp1RxN}]


# DACs
set_property -dict { PACKAGE_PIN T19  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[0] }];
set_property -dict { PACKAGE_PIN U18  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[1] }];
set_property -dict { PACKAGE_PIN U20  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[2] }];
set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVCMOS25 } [get_ports { dacCsB[3] }];
set_property -dict { PACKAGE_PIN W19  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[4] }];
set_property -dict { PACKAGE_PIN AB18 IOSTANDARD LVCMOS25 } [get_ports { dacCsB[5] }];
set_property -dict { PACKAGE_PIN AA15 IOSTANDARD LVCMOS25 } [get_ports { dacCsB[6] }];
set_property -dict { PACKAGE_PIN Y16  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[7] }];
set_property -dict { PACKAGE_PIN C14  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[8] }];
set_property -dict { PACKAGE_PIN B17  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[9] }];
set_property -dict { PACKAGE_PIN E17  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[10] }];
set_property -dict { PACKAGE_PIN J16  IOSTANDARD LVCMOS25 } [get_ports { dacCsB[11] }];

set_property -dict { PACKAGE_PIN T21  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[0] }];
set_property -dict { PACKAGE_PIN W21  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[1] }];
set_property -dict { PACKAGE_PIN Y21  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[2] }];
set_property -dict { PACKAGE_PIN AA19 IOSTANDARD LVCMOS25 } [get_ports { dacSdio[3] }];
set_property -dict { PACKAGE_PIN Y18  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[4] }];
set_property -dict { PACKAGE_PIN AB15 IOSTANDARD LVCMOS25 } [get_ports { dacSdio[5] }];
set_property -dict { PACKAGE_PIN U16  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[6] }];
set_property -dict { PACKAGE_PIN W14  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[7] }];
set_property -dict { PACKAGE_PIN C15  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[8] }];
set_property -dict { PACKAGE_PIN A18  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[9] }];
set_property -dict { PACKAGE_PIN E18  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[10] }];
set_property -dict { PACKAGE_PIN J17  IOSTANDARD LVCMOS25 } [get_ports { dacSdio[11] }];

set_property -dict { PACKAGE_PIN U21  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[0] }];
set_property -dict { PACKAGE_PIN W22  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[1] }];
set_property -dict { PACKAGE_PIN Y22  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[2] }];
set_property -dict { PACKAGE_PIN AB20 IOSTANDARD LVCMOS25 } [get_ports { dacSdo[3] }];
set_property -dict { PACKAGE_PIN Y19  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[4] }];
set_property -dict { PACKAGE_PIN AB16 IOSTANDARD LVCMOS25 } [get_ports { dacSdo[5] }];
set_property -dict { PACKAGE_PIN V17  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[6] }];
set_property -dict { PACKAGE_PIN Y14  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[7] }];
set_property -dict { PACKAGE_PIN B16  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[8] }];
set_property -dict { PACKAGE_PIN D15  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[9] }];
set_property -dict { PACKAGE_PIN E16  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[10] }];
set_property -dict { PACKAGE_PIN F18  IOSTANDARD LVCMOS25 } [get_ports { dacSdo[11] }];

set_property -dict { PACKAGE_PIN U22  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[0] }];
set_property -dict { PACKAGE_PIN U17  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[1] }];
set_property -dict { PACKAGE_PIN AA20 IOSTANDARD LVCMOS25 } [get_ports { dacSclk[2] }];
set_property -dict { PACKAGE_PIN V20  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[3] }];
set_property -dict { PACKAGE_PIN W17  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[4] }];
set_property -dict { PACKAGE_PIN AA16 IOSTANDARD LVCMOS25 } [get_ports { dacSclk[5] }];
set_property -dict { PACKAGE_PIN R16  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[6] }];
set_property -dict { PACKAGE_PIN V15  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[7] }];
set_property -dict { PACKAGE_PIN A16  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[8] }];
set_property -dict { PACKAGE_PIN D16  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[9] }];
set_property -dict { PACKAGE_PIN D17  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[10] }];
set_property -dict { PACKAGE_PIN E19  IOSTANDARD LVCMOS25 } [get_ports { dacSclk[11] }];

set_property -dict { PACKAGE_PIN V22  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[0] }];
set_property -dict { PACKAGE_PIN V18  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[1] }];
set_property -dict { PACKAGE_PIN AB21 IOSTANDARD LVCMOS25 } [get_ports { dacResetB[2] }];
set_property -dict { PACKAGE_PIN W20  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[3] }];
set_property -dict { PACKAGE_PIN Y17  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[4] }];
set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVCMOS25 } [get_ports { dacResetB[5] }];
set_property -dict { PACKAGE_PIN T16  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[6] }];
set_property -dict { PACKAGE_PIN W15  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[7] }];
set_property -dict { PACKAGE_PIN B15  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[8] }];
set_property -dict { PACKAGE_PIN C17  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[9] }];
set_property -dict { PACKAGE_PIN H17  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[10] }];
set_property -dict { PACKAGE_PIN D19  IOSTANDARD LVCMOS25 } [get_ports { dacResetB[11] }];

set_property -dict { PACKAGE_PIN T18  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[0] }];
set_property -dict { PACKAGE_PIN T20  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[1] }];
set_property -dict { PACKAGE_PIN AA21 IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[2] }];
set_property -dict { PACKAGE_PIN V19  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[3] }];
set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[4] }];
set_property -dict { PACKAGE_PIN AA14 IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[5] }];
set_property -dict { PACKAGE_PIN W16  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[6] }];
set_property -dict { PACKAGE_PIN T15  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[7] }];
set_property -dict { PACKAGE_PIN A15  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[8] }];
set_property -dict { PACKAGE_PIN C18  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[9] }];
set_property -dict { PACKAGE_PIN G17  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[10] }];
set_property -dict { PACKAGE_PIN D20  IOSTANDARD LVCMOS25 } [get_ports { dacTriggerB[11] }];

set_property -dict { PACKAGE_PIN D10  IOSTANDARD LVDS_25 } [get_ports { dacClkP[0] }];
set_property -dict { PACKAGE_PIN C10  IOSTANDARD LVDS_25 } [get_ports { dacClkN[0] }];
set_property -dict { PACKAGE_PIN G13  IOSTANDARD LVDS_25 } [get_ports { dacClkP[1] }];
set_property -dict { PACKAGE_PIN F13  IOSTANDARD LVDS_25 } [get_ports { dacClkN[1] }];
set_property -dict { PACKAGE_PIN H14  IOSTANDARD LVDS_25 } [get_ports { dacClkP[2] }];
set_property -dict { PACKAGE_PIN H13  IOSTANDARD LVDS_25 } [get_ports { dacClkN[2] }];
set_property -dict { PACKAGE_PIN E13  IOSTANDARD LVDS_25 } [get_ports { dacClkP[3] }];
set_property -dict { PACKAGE_PIN E12  IOSTANDARD LVDS_25 } [get_ports { dacClkN[3] }];
set_property -dict { PACKAGE_PIN F11  IOSTANDARD LVDS_25 } [get_ports { dacClkP[4] }];
set_property -dict { PACKAGE_PIN F10  IOSTANDARD LVDS_25 } [get_ports { dacClkN[4] }];
set_property -dict { PACKAGE_PIN H9   IOSTANDARD LVDS_25 } [get_ports { dacClkP[5] }];
set_property -dict { PACKAGE_PIN H8   IOSTANDARD LVDS_25 } [get_ports { dacClkN[5] }];
set_property -dict { PACKAGE_PIN G8   IOSTANDARD LVDS_25 } [get_ports { dacClkP[6] }];
set_property -dict { PACKAGE_PIN F8   IOSTANDARD LVDS_25 } [get_ports { dacClkN[6] }];
set_property -dict { PACKAGE_PIN D9   IOSTANDARD LVDS_25 } [get_ports { dacClkP[7] }];
set_property -dict { PACKAGE_PIN C9   IOSTANDARD LVDS_25 } [get_ports { dacClkN[7] }];
set_property -dict { PACKAGE_PIN B11  IOSTANDARD LVDS_25 } [get_ports { dacClkP[8] }];
set_property -dict { PACKAGE_PIN B10  IOSTANDARD LVDS_25 } [get_ports { dacClkN[8] }];
set_property -dict { PACKAGE_PIN A9   IOSTANDARD LVDS_25 } [get_ports { dacClkP[9] }];
set_property -dict { PACKAGE_PIN A8   IOSTANDARD LVDS_25 } [get_ports { dacClkN[9] }];
set_property -dict { PACKAGE_PIN C8   IOSTANDARD LVDS_25 } [get_ports { dacClkP[10] }];
set_property -dict { PACKAGE_PIN B8   IOSTANDARD LVDS_25 } [get_ports { dacClkN[10] }];
set_property -dict { PACKAGE_PIN A11  IOSTANDARD LVDS_25 } [get_ports { dacClkP[11] }];
set_property -dict { PACKAGE_PIN A10  IOSTANDARD LVDS_25 } [get_ports { dacClkN[11] }];



# Boot Memory Port Mapping
set_property -dict { PACKAGE_PIN L16 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }];
set_property -dict { PACKAGE_PIN H18 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }];
set_property -dict { PACKAGE_PIN H19 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }];

# LEDs
set_property -dict { PACKAGE_PIN L20 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }];
set_property -dict { PACKAGE_PIN N18 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }];
set_property -dict { PACKAGE_PIN N19 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }];
set_property -dict { PACKAGE_PIN M17 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }];
set_property -dict { PACKAGE_PIN M18 IOSTANDARD LVCMOS33 } [get_ports { leds[4] }];
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS33 } [get_ports { leds[5] }];
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS33 } [get_ports { leds[6] }];
set_property -dict { PACKAGE_PIN K21 IOSTANDARD LVCMOS33 } [get_ports { leds[7] }];

set_property -dict { PACKAGE_PIN L21 IOSTANDARD LVCMOS33 } [get_ports { conRxGreenLed }];
set_property -dict { PACKAGE_PIN R18 IOSTANDARD LVCMOS33 } [get_ports { conRxYellowLed }];
set_property -dict { PACKAGE_PIN R19 IOSTANDARD LVCMOS33 } [get_ports { conTxGreenLed }];
set_property -dict { PACKAGE_PIN P19 IOSTANDARD LVCMOS33 } [get_ports { conTxYellowLed }];



# I2C PROM
set_property -dict { PACKAGE_PIN J20 IOSTANDARD LVCMOS33 } [get_ports { promScl }];
set_property -dict { PACKAGE_PIN H20 IOSTANDARD LVCMOS33 } [get_ports { promSda }];

# Power Monitoring
set_property -dict { PACKAGE_PIN E22 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }];
set_property -dict { PACKAGE_PIN H22 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }];

#OSC Enable
set_property -dict { PACKAGE_PIN P21 IOSTANDARD LVCMOS33 } [get_ports { oscOe[0] }];
set_property -dict { PACKAGE_PIN P22 IOSTANDARD LVCMOS33 } [get_ports { oscOe[1] }];

## Thermistors
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVCMOS25 } [get_ports { vAuxP[0] }];
set_property -dict { PACKAGE_PIN C12 IOSTANDARD LVCMOS25 } [get_ports { vAuxP[1] }];
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS25 } [get_ports { vAuxP[2] }];
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVCMOS25 } [get_ports { vAuxP[3] }];
set_property -dict { PACKAGE_PIN G16 IOSTANDARD LVCMOS25 } [get_ports { vAuxN[0] }];
set_property -dict { PACKAGE_PIN B12 IOSTANDARD LVCMOS25 } [get_ports { vAuxN[1] }];
set_property -dict { PACKAGE_PIN F16 IOSTANDARD LVCMOS25 } [get_ports { vAuxN[2] }];
set_property -dict { PACKAGE_PIN A14 IOSTANDARD LVCMOS25 } [get_ports { vAuxN[3] }];




set_property BITSTREAM.CONFIG.CONFIGRATE 33  [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

