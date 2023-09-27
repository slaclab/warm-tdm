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

create_generated_clock -name fabRefClk0 [get_pins {U_ClockDist_1/U_IBUFDS_GTE2_0/ODIV2}]
create_generated_clock -name fabRefClk1 [get_pins {U_ClockDist_1/U_IBUFDS_GTE2_1/ODIV2}]

create_generated_clock -name axilClk [get_pins {U_ComCore_1/U_PgpCore_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name pgpClk [get_pins {U_ComCore_1/U_PgpCore_1/ClockManager7_Inst/MmcmGen.U_Mmcm/CLKOUT1}]

create_generated_clock -name dnaDivClk [get_pins U_WarmTdmCommon_1/U_AxiVersion_1/GEN_DEVICE_DNA.DeviceDna_1/GEN_7SERIES.DeviceDna7Series_Inst/BUFR_Inst/O]
create_generated_clock -name icapClk [get_pins U_WarmTdmCommon_1/U_AxiVersion_1/GEN_ICAP.Iprog_1/GEN_7SERIES.Iprog7Series_Inst/DIVCLK_GEN.BUFR_ICPAPE2/O]

#create_generated_clock -name dacClk -divide_by 200 -source [get_ports {timingRxClkP}] [get_pins {U_TimingRx_1/DAC_CLK_BUFG/O}]


create_generated_clock -name ethClk [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name ethClkDiv2 [get_pins {U_ComCore_1/U_EthCore_1/REAL_ETH_GEN.GIG_ETH_GEN.U_MMCM/MmcmGen.U_Mmcm/CLKOUT1}]


create_generated_clock -name idelayClk [get_pins {U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]

## create_generated_clock -name timingTxClk [get_pins {U_Timing_1/U_MMCM_IDELAY/MmcmGen.U_Mmcm/CLKOUT0}]
create_generated_clock -name timingTxBitClk  [get_pins  -hier -filter {NAME =~ U_Timing_1/U_TimingTx_1/*/*/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins  -hier -filter {NAME =~ U_Timing_1/U_TimingTx_1/*/*/CLKOUT1}]
												       
create_generated_clock -name timingRxBitClk  [get_pins  -hier -filter {NAME =~ U_Timing_1/U_TimingRx_1/*/*/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins  -hier -filter {NAME =~ U_Timing_1/U_TimingRx_1/*/*/CLKOUT1}]


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
    -group [get_clocks -include_generated_clocks dnaDivClk] \
    -group [get_clocks icapClk]

 set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks ethClk] \

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] 



# MGT Mapping
# Clocks
set_property PACKAGE_PIN D6 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN D5 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN F6 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN F5 [get_ports {gtRefClk1N}]

# PGP
set_property PACKAGE_PIN F2 [get_ports {pgpTxP[1]}]
set_property PACKAGE_PIN F1 [get_ports {pgpTxN[1]}]
set_property PACKAGE_PIN G4 [get_ports {pgpRxP[1]}]
set_property PACKAGE_PIN G3 [get_ports {pgpRxN[1]}]

# Timing
set_property PACKAGE_PIN D2 [get_ports {pgpTxP[0]}]
set_property PACKAGE_PIN D1 [get_ports {pgpTxN[0]}]
set_property PACKAGE_PIN E4 [get_ports {pgpRxP[0]}]
set_property PACKAGE_PIN E3 [get_ports {pgpRxN[0]}]

set_property -dict { PACKAGE_PIN E11  IOSTANDARD LVDS_25  DIFF_TERM TRUE} [get_ports { timingRxClkP }];
set_property -dict { PACKAGE_PIN D11  IOSTANDARD LVDS_25  DIFF_TERM TRUE} [get_ports { timingRxClkN }];
set_property -dict { PACKAGE_PIN G11  IOSTANDARD LVDS_25  DIFF_TERM TRUE} [get_ports { timingRxDataP }];
set_property -dict { PACKAGE_PIN G10  IOSTANDARD LVDS_25  DIFF_TERM TRUE} [get_ports { timingRxDataN }];
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
set_property -dict { PACKAGE_PIN T19 IOSTANDARD LVCMOS33 } [get_ports {dacClk[0]}];
set_property -dict { PACKAGE_PIN T21 IOSTANDARD LVCMOS33 } [get_ports {dacClk[1]}];
set_property -dict { PACKAGE_PIN U21 IOSTANDARD LVCMOS33 } [get_ports {dacClk[2]}];
set_property -dict { PACKAGE_PIN U22 IOSTANDARD LVCMOS33 } [get_ports {dacClk[3]}];
set_property -dict { PACKAGE_PIN V22 IOSTANDARD LVCMOS33 } [get_ports {dacClk[4]}];
set_property -dict { PACKAGE_PIN T18 IOSTANDARD LVCMOS33 } [get_ports {dacClk[5]}];
set_property -dict { PACKAGE_PIN U18 IOSTANDARD LVCMOS33 } [get_ports {dacClk[6]}];
set_property -dict { PACKAGE_PIN W21 IOSTANDARD LVCMOS33 } [get_ports {dacClk[7]}];
set_property -dict { PACKAGE_PIN W22 IOSTANDARD LVCMOS33 } [get_ports {dacClk[8]}];
set_property -dict { PACKAGE_PIN U17 IOSTANDARD LVCMOS33 } [get_ports {dacClk[9]}];
set_property -dict { PACKAGE_PIN V18 IOSTANDARD LVCMOS33 } [get_ports {dacClk[10]}];
set_property -dict { PACKAGE_PIN T20 IOSTANDARD LVCMOS33 } [get_ports {dacClk[11]}];
set_property -dict { PACKAGE_PIN U20 IOSTANDARD LVCMOS33 } [get_ports {dacClk[12]}];
set_property -dict { PACKAGE_PIN Y21 IOSTANDARD LVCMOS33 } [get_ports {dacClk[13]}];
set_property -dict { PACKAGE_PIN Y22 IOSTANDARD LVCMOS33 } [get_ports {dacClk[14]}];
set_property -dict { PACKAGE_PIN AA20 IOSTANDARD LVCMOS33 } [get_ports {dacClk[15]}];

set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[0]}];
set_property -dict { PACKAGE_PIN AA19 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[1]}];
set_property -dict { PACKAGE_PIN AB20 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[2]}];
set_property -dict { PACKAGE_PIN V20 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[3]}];
set_property -dict { PACKAGE_PIN W20 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[4]}];
set_property -dict { PACKAGE_PIN V19 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[5]}];
set_property -dict { PACKAGE_PIN W19 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[6]}];
set_property -dict { PACKAGE_PIN Y18 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[7]}];
set_property -dict { PACKAGE_PIN Y19 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[8]}];
set_property -dict { PACKAGE_PIN W17 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[9]}];
set_property -dict { PACKAGE_PIN Y17 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[10]}];
set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[11]}];
set_property -dict { PACKAGE_PIN AB18 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[12]}];
set_property -dict { PACKAGE_PIN AB15 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[13]}];
set_property -dict { PACKAGE_PIN AB16 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[14]}];
set_property -dict { PACKAGE_PIN AA16 IOSTANDARD LVCMOS33 } [get_ports {dacWrt[15]}];

set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVCMOS33 } [get_ports {dacSel[0]}];
set_property -dict { PACKAGE_PIN AA14 IOSTANDARD LVCMOS33 } [get_ports {dacSel[1]}];
set_property -dict { PACKAGE_PIN AA15 IOSTANDARD LVCMOS33 } [get_ports {dacSel[2]}];
set_property -dict { PACKAGE_PIN U16 IOSTANDARD LVCMOS33 } [get_ports {dacSel[3]}];
set_property -dict { PACKAGE_PIN V17 IOSTANDARD LVCMOS33 } [get_ports {dacSel[4]}];
set_property -dict { PACKAGE_PIN R16 IOSTANDARD LVCMOS33 } [get_ports {dacSel[5]}];
set_property -dict { PACKAGE_PIN T16 IOSTANDARD LVCMOS33 } [get_ports {dacSel[6]}];
set_property -dict { PACKAGE_PIN W16 IOSTANDARD LVCMOS33 } [get_ports {dacSel[7]}];
set_property -dict { PACKAGE_PIN Y16 IOSTANDARD LVCMOS33 } [get_ports {dacSel[8]}];
set_property -dict { PACKAGE_PIN W14 IOSTANDARD LVCMOS33 } [get_ports {dacSel[9]}];
set_property -dict { PACKAGE_PIN Y14 IOSTANDARD LVCMOS33 } [get_ports {dacSel[10]}];
set_property -dict { PACKAGE_PIN V15 IOSTANDARD LVCMOS33 } [get_ports {dacSel[11]}];
set_property -dict { PACKAGE_PIN W15 IOSTANDARD LVCMOS33 } [get_ports {dacSel[12]}];
set_property -dict { PACKAGE_PIN T15 IOSTANDARD LVCMOS33 } [get_ports {dacSel[13]}];
set_property -dict { PACKAGE_PIN U15 IOSTANDARD LVCMOS33 } [get_ports {dacSel[14]}];
set_property -dict { PACKAGE_PIN V14 IOSTANDARD LVCMOS33 } [get_ports {dacSel[15]}];

set_property -dict { PACKAGE_PIN E19 IOSTANDARD LVCMOS33 } [get_ports {dacReset[0]}];
set_property -dict { PACKAGE_PIN D19 IOSTANDARD LVCMOS33 } [get_ports {dacReset[1]}];
set_property -dict { PACKAGE_PIN D20 IOSTANDARD LVCMOS33 } [get_ports {dacReset[2]}];
set_property -dict { PACKAGE_PIN C19 IOSTANDARD LVCMOS33 } [get_ports {dacReset[3]}];
set_property -dict { PACKAGE_PIN C20 IOSTANDARD LVCMOS33 } [get_ports {dacReset[4]}];
set_property -dict { PACKAGE_PIN B18 IOSTANDARD LVCMOS33 } [get_ports {dacReset[5]}];
set_property -dict { PACKAGE_PIN A19 IOSTANDARD LVCMOS33 } [get_ports {dacReset[6]}];
set_property -dict { PACKAGE_PIN C22 IOSTANDARD LVCMOS33 } [get_ports {dacReset[7]}];
set_property -dict { PACKAGE_PIN B22 IOSTANDARD LVCMOS33 } [get_ports {dacReset[8]}];
set_property -dict { PACKAGE_PIN A20 IOSTANDARD LVCMOS33 } [get_ports {dacReset[9]}];
set_property -dict { PACKAGE_PIN A21 IOSTANDARD LVCMOS33 } [get_ports {dacReset[10]}];
set_property -dict { PACKAGE_PIN D21 IOSTANDARD LVCMOS33 } [get_ports {dacReset[11]}];
set_property -dict { PACKAGE_PIN D22 IOSTANDARD LVCMOS33 } [get_ports {dacReset[12]}];
set_property -dict { PACKAGE_PIN B20 IOSTANDARD LVCMOS33 } [get_ports {dacReset[13]}];
set_property -dict { PACKAGE_PIN B21 IOSTANDARD LVCMOS33 } [get_ports {dacReset[14]}];
set_property -dict { PACKAGE_PIN H15 IOSTANDARD LVCMOS33 } [get_ports {dacReset[15]}];

set_property -dict { PACKAGE_PIN D12 IOSTANDARD LVCMOS33 } [get_ports {dacDb[0]}];
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVCMOS33 } [get_ports {dacDb[1]}];
set_property -dict { PACKAGE_PIN G16 IOSTANDARD LVCMOS33 } [get_ports {dacDb[2]}];
set_property -dict { PACKAGE_PIN C12 IOSTANDARD LVCMOS33 } [get_ports {dacDb[3]}];
set_property -dict { PACKAGE_PIN B12 IOSTANDARD LVCMOS33 } [get_ports {dacDb[4]}];
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS33 } [get_ports {dacDb[5]}];
set_property -dict { PACKAGE_PIN F16 IOSTANDARD LVCMOS33 } [get_ports {dacDb[6]}];
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVCMOS33 } [get_ports {dacDb[7]}];
set_property -dict { PACKAGE_PIN A14 IOSTANDARD LVCMOS33 } [get_ports {dacDb[8]}];
set_property -dict { PACKAGE_PIN C13 IOSTANDARD LVCMOS33 } [get_ports {dacDb[9]}];
set_property -dict { PACKAGE_PIN B13 IOSTANDARD LVCMOS33 } [get_ports {dacDb[10]}];
set_property -dict { PACKAGE_PIN E14 IOSTANDARD LVCMOS33 } [get_ports {dacDb[11]}];
set_property -dict { PACKAGE_PIN D14 IOSTANDARD LVCMOS33 } [get_ports {dacDb[12]}];
set_property -dict { PACKAGE_PIN C14 IOSTANDARD LVCMOS33 } [get_ports {dacDb[13]}];


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

set_property -dict { PACKAGE_PIN D9 IOSTANDARD LVCMOS25 } [get_ports { xbarDataSel[0] }];
set_property -dict { PACKAGE_PIN C1 IOSTANDARD LVCMOS25 } [get_ports { xbarDataSel[1] }];
set_property -dict { PACKAGE_PIN B11 IOSTANDARD LVCMOS25 } [get_ports { xbarClkSel[0] }];
set_property -dict { PACKAGE_PIN B10 IOSTANDARD LVCMOS25 } [get_ports { xbarClkSel[1]}];
set_property -dict { PACKAGE_PIN A9 IOSTANDARD LVCMOS25 } [get_ports { xbarMgtSel[0] }];
set_property -dict { PACKAGE_PIN A8 IOSTANDARD LVCMOS25 } [get_ports { xbarMgtSel[1] }];
set_property -dict { PACKAGE_PIN C8 IOSTANDARD LVCMOS25 } [get_ports { xbarTimingSel[0] }];
set_property -dict { PACKAGE_PIN B8 IOSTANDARD LVCMOS25 } [get_ports { xbarTimingSel[1] }];





# I2C PROM
set_property -dict { PACKAGE_PIN J20 IOSTANDARD LVCMOS33 } [get_ports { promScl }];
set_property -dict { PACKAGE_PIN H20 IOSTANDARD LVCMOS33 } [get_ports { promSda }];

# Power Monitoring
set_property -dict { PACKAGE_PIN E22 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }];
set_property -dict { PACKAGE_PIN H22 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }];


## Thermistors
set_property -dict { PACKAGE_PIN B16 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[0] }];
set_property -dict { PACKAGE_PIN B15 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[1] }];
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[2] }];
set_property -dict { PACKAGE_PIN D15 IOSTANDARD LVCMOS33 } [get_ports { vAuxP[3] }];
set_property -dict { PACKAGE_PIN A16 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[0] }];
set_property -dict { PACKAGE_PIN A15 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[1] }];
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[2] }];
set_property -dict { PACKAGE_PIN D16 IOSTANDARD LVCMOS33 } [get_ports { vAuxN[3] }];




set_property BITSTREAM.CONFIG.CONFIGRATE 33  [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 1 [current_design]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

