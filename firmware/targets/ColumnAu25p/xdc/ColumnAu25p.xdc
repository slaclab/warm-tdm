##############################################################################
## Pin constraints for XAU25P-SFVB784 power evaluation target
##
## Bank allocation:
##   Bank 64 (HP, 1.8V): ADC 0 + ADC 1 (LVDS with ISERDES) + ADC control
##   Bank 65 (HP, 1.8V): SA FB DAC + SQ1 FB DAC (LVCMOS18)
##   Bank 66 (HP, 1.8V): SQ1 Bias DAC + AUX DAC (LVCMOS18)
##   Bank 67 (HP, 1.8V): Timing LVDS (ISERDES/OSERDES) + ADC clk + misc ctrl
##   Banks 84-87 (HD, 3.3V): Boot, I2C, LEDs, SPI, thermistors
##   Quad 225 (GT): PGP + 10G SFP
##
## Clock input rules:
##   - adcDClkP[0] on bank 64 DBC (L19/T3L) - drives BUFGCE_DIV
##   - adcDClkP[1] on bank 64 QBC (L7/T1L) - drives BUFGCE_DIV (different byte)
##   - timingRxClkP on bank 67 QBC (L7/T1L) - drives PLL
##   Each in a different byte lane to avoid BUFGCE_DIV contention
##############################################################################

##############################################################################
## GT Quad 225 - Reference Clocks and Transceivers
##############################################################################
create_clock -name gtRefClk0 -period 4.000 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 6.400 [get_ports {gtRefClk1P}]

set_property PACKAGE_PIN T7 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN T6 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN P7 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN P6 [get_ports {gtRefClk1N}]

## PGP on channel 1 (X0Y5, matches PgpGtyCore IP)
set_property PACKAGE_PIN U5 [get_ports {pgpTxP[0]}]
set_property PACKAGE_PIN U4 [get_ports {pgpTxN[0]}]
set_property PACKAGE_PIN Y2 [get_ports {pgpRxP[0]}]
set_property PACKAGE_PIN Y1 [get_ports {pgpRxN[0]}]

## SFP 10G on channel 2 (X0Y6)
set_property PACKAGE_PIN AA5 [get_ports {sfp0TxP}]
set_property PACKAGE_PIN AA4 [get_ports {sfp0TxN}]
set_property PACKAGE_PIN V2 [get_ports {sfp0RxP}]
set_property PACKAGE_PIN V1 [get_ports {sfp0RxN}]

## GT LOC constraints
set_property LOC GTYE4_CHANNEL_X0Y5 [get_cells -hier -filter {NAME =~ *U_PgpCore_1/*GTYE4_CHANNEL_PRIM_INST}]
set_property LOC GTYE4_CHANNEL_X0Y6 [get_cells -hier -filter {NAME =~ *U_EthCore_1/*GTYE4_CHANNEL_PRIM_INST}]

##############################################################################
## HP Bank 64 (VCCO=1.8V) - ADC 0 + ADC 1 (all LVDS with ISERDES)
## dClk[0] on AB22 (L19/T3L DBC), dClk[1] on AG24 (L7/T1L QBC)
## 47 of 52 pins used
##############################################################################
create_clock -name adcDClk0 -period 2.00 [get_ports {adcDClkP[0]}]
create_clock -name adcDClk1 -period 2.00 [get_ports {adcDClkP[1]}]
set_input_jitter adcDClk0 .35
set_input_jitter adcDClk1 .35

## ADC clocks (on GC-capable pins)
set_property -dict { PACKAGE_PIN AE23 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcDClkP[0] }]
set_property -dict { PACKAGE_PIN AE24 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcDClkN[0] }]
set_property -dict { PACKAGE_PIN AE19 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcDClkP[1] }]
set_property -dict { PACKAGE_PIN AF20 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcDClkN[1] }]
set_property -dict { PACKAGE_PIN AF21 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcFClkP[0] }]
set_property -dict { PACKAGE_PIN AF22 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcFClkN[0] }]
set_property -dict { PACKAGE_PIN AC21 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcFClkP[1] }]
set_property -dict { PACKAGE_PIN AD21 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcFClkN[1] }]

## ADC control (single-ended)
set_property -dict { PACKAGE_PIN AB18 IOSTANDARD LVCMOS18 } [get_ports { adcSclk }]
set_property -dict { PACKAGE_PIN AB19 IOSTANDARD LVCMOS18 } [get_ports { adcSdio }]
set_property -dict { PACKAGE_PIN AD17 IOSTANDARD LVCMOS18 } [get_ports { adcCsb }]
set_property -dict { PACKAGE_PIN AE17 IOSTANDARD LVCMOS18 } [get_ports { adcSync }]
set_property -dict { PACKAGE_PIN AG22 IOSTANDARD LVCMOS18 } [get_ports { adcPdwn }]

## ADC 0 data channels (remaining bank 64 pairs)
set_property -dict { PACKAGE_PIN AB17 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][0] }]
set_property -dict { PACKAGE_PIN AC17 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][0] }]
set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][1] }]
set_property -dict { PACKAGE_PIN AC22 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][1] }]
set_property -dict { PACKAGE_PIN AC19 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][2] }]
set_property -dict { PACKAGE_PIN AC20 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][2] }]
set_property -dict { PACKAGE_PIN AD18 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][3] }]
set_property -dict { PACKAGE_PIN AD19 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][3] }]
set_property -dict { PACKAGE_PIN AD22 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][4] }]
set_property -dict { PACKAGE_PIN AD23 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][4] }]
set_property -dict { PACKAGE_PIN AE20 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][5] }]
set_property -dict { PACKAGE_PIN AE21 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][5] }]
set_property -dict { PACKAGE_PIN AE25 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][6] }]
set_property -dict { PACKAGE_PIN AE26 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][6] }]
set_property -dict { PACKAGE_PIN AE28 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[0][7] }]
set_property -dict { PACKAGE_PIN AF28 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[0][7] }]

## ADC 1 data channels
set_property -dict { PACKAGE_PIN AF17 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][0] }]
set_property -dict { PACKAGE_PIN AG17 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][0] }]
set_property -dict { PACKAGE_PIN AF18 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][1] }]
set_property -dict { PACKAGE_PIN AG18 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][1] }]
set_property -dict { PACKAGE_PIN AF23 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][2] }]
set_property -dict { PACKAGE_PIN AG23 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][2] }]
set_property -dict { PACKAGE_PIN AF25 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][3] }]
set_property -dict { PACKAGE_PIN AF26 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][3] }]
set_property -dict { PACKAGE_PIN AF27 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][4] }]
set_property -dict { PACKAGE_PIN AG28 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][4] }]
set_property -dict { PACKAGE_PIN AG19 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][5] }]
set_property -dict { PACKAGE_PIN AH19 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][5] }]
set_property -dict { PACKAGE_PIN AG20 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][6] }]
set_property -dict { PACKAGE_PIN AH20 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][6] }]
set_property -dict { PACKAGE_PIN AG24 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChP[1][7] }]
set_property -dict { PACKAGE_PIN AH24 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { adcChN[1][7] }]

##############################################################################
## HP Bank 67 (VCCO=1.8V) - Timing LVDS + ADC clk out + misc
## timingRxClkP on D18 (L7/T1L QBC) - drives PLL for ISERDES
##############################################################################
create_clock -name timingRxClk -period 8.000 [get_ports {timingRxClkP}]

## timingRxClk on bank 67 (uses MMCM which has flexible input routing via BUFGCE)
set_property -dict { PACKAGE_PIN D21 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkP }]
set_property -dict { PACKAGE_PIN C21 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkN }]
set_property -dict { PACKAGE_PIN E18 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataP }]
set_property -dict { PACKAGE_PIN E19 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataN }]
set_property -dict { PACKAGE_PIN E20 IOSTANDARD LVDS } [get_ports { timingTxClkP }]
set_property -dict { PACKAGE_PIN E21 IOSTANDARD LVDS } [get_ports { timingTxClkN }]
set_property -dict { PACKAGE_PIN F20 IOSTANDARD LVDS } [get_ports { timingTxDataP }]
set_property -dict { PACKAGE_PIN F21 IOSTANDARD LVDS } [get_ports { timingTxDataN }]
set_property -dict { PACKAGE_PIN G19 IOSTANDARD LVDS } [get_ports { adcClkP }]
set_property -dict { PACKAGE_PIN G20 IOSTANDARD LVDS } [get_ports { adcClkN }]

## AUX DAC (30 pins, remaining bank 67 space)
set_property -dict { PACKAGE_PIN A17 IOSTANDARD LVCMOS18 } [get_ports { auxDb[0] }]
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS18 } [get_ports { auxDb[1] }]
set_property -dict { PACKAGE_PIN A20 IOSTANDARD LVCMOS18 } [get_ports { auxDb[2] }]
set_property -dict { PACKAGE_PIN A21 IOSTANDARD LVCMOS18 } [get_ports { auxDb[3] }]
set_property -dict { PACKAGE_PIN A22 IOSTANDARD LVCMOS18 } [get_ports { auxDb[4] }]
set_property -dict { PACKAGE_PIN A23 IOSTANDARD LVCMOS18 } [get_ports { auxDb[5] }]
set_property -dict { PACKAGE_PIN B19 IOSTANDARD LVCMOS18 } [get_ports { auxDb[6] }]
set_property -dict { PACKAGE_PIN B20 IOSTANDARD LVCMOS18 } [get_ports { auxDb[7] }]
set_property -dict { PACKAGE_PIN B23 IOSTANDARD LVCMOS18 } [get_ports { auxDb[8] }]
set_property -dict { PACKAGE_PIN B24 IOSTANDARD LVCMOS18 } [get_ports { auxDb[9] }]
set_property -dict { PACKAGE_PIN B25 IOSTANDARD LVCMOS18 } [get_ports { auxDb[10] }]
set_property -dict { PACKAGE_PIN A25 IOSTANDARD LVCMOS18 } [get_ports { auxDb[11] }]
set_property -dict { PACKAGE_PIN C17 IOSTANDARD LVCMOS18 } [get_ports { auxDb[12] }]
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS18 } [get_ports { auxDb[13] }]
set_property -dict { PACKAGE_PIN C19 IOSTANDARD LVCMOS18 } [get_ports { auxWrt[0] }]
set_property -dict { PACKAGE_PIN C20 IOSTANDARD LVCMOS18 } [get_ports { auxWrt[1] }]
set_property -dict { PACKAGE_PIN C22 IOSTANDARD LVCMOS18 } [get_ports { auxWrt[2] }]
set_property -dict { PACKAGE_PIN B22 IOSTANDARD LVCMOS18 } [get_ports { auxWrt[3] }]
set_property -dict { PACKAGE_PIN C24 IOSTANDARD LVCMOS18 } [get_ports { auxClk[0] }]
set_property -dict { PACKAGE_PIN C25 IOSTANDARD LVCMOS18 } [get_ports { auxClk[1] }]
set_property -dict { PACKAGE_PIN H20 IOSTANDARD LVCMOS18 } [get_ports { auxClk[2] }]
set_property -dict { PACKAGE_PIN H21 IOSTANDARD LVCMOS18 } [get_ports { auxClk[3] }]
set_property -dict { PACKAGE_PIN D22 IOSTANDARD LVCMOS18 } [get_ports { auxSel[0] }]
set_property -dict { PACKAGE_PIN D23 IOSTANDARD LVCMOS18 } [get_ports { auxSel[1] }]
set_property -dict { PACKAGE_PIN E24 IOSTANDARD LVCMOS18 } [get_ports { auxSel[2] }]
set_property -dict { PACKAGE_PIN E25 IOSTANDARD LVCMOS18 } [get_ports { auxSel[3] }]
set_property -dict { PACKAGE_PIN F22 IOSTANDARD LVCMOS18 } [get_ports { auxReset[0] }]
set_property -dict { PACKAGE_PIN E23 IOSTANDARD LVCMOS18 } [get_ports { auxReset[1] }]
set_property -dict { PACKAGE_PIN G18 IOSTANDARD LVCMOS18 } [get_ports { auxReset[2] }]
set_property -dict { PACKAGE_PIN F18 IOSTANDARD LVCMOS18 } [get_ports { auxReset[3] }]

##############################################################################
## HP Bank 65 (VCCO=1.8V) - SA FB DAC + SQ1 FB DAC (no clocks)
##############################################################################
set_property -dict { PACKAGE_PIN AA21 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[0] }]
set_property -dict { PACKAGE_PIN AA22 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[1] }]
set_property -dict { PACKAGE_PIN AA26 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[2] }]
set_property -dict { PACKAGE_PIN AA27 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[3] }]
set_property -dict { PACKAGE_PIN AB23 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[4] }]
set_property -dict { PACKAGE_PIN AB24 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[5] }]
set_property -dict { PACKAGE_PIN AB25 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[6] }]
set_property -dict { PACKAGE_PIN AC25 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[7] }]
set_property -dict { PACKAGE_PIN AB27 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[8] }]
set_property -dict { PACKAGE_PIN AB28 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[9] }]
set_property -dict { PACKAGE_PIN AC24 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[10] }]
set_property -dict { PACKAGE_PIN AD24 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[11] }]
set_property -dict { PACKAGE_PIN AC26 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[12] }]
set_property -dict { PACKAGE_PIN AD27 IOSTANDARD LVCMOS18 } [get_ports { saFbDb[13] }]
set_property -dict { PACKAGE_PIN AC27 IOSTANDARD LVCMOS18 } [get_ports { saFbWrt[0] }]
set_property -dict { PACKAGE_PIN AD28 IOSTANDARD LVCMOS18 } [get_ports { saFbWrt[1] }]
set_property -dict { PACKAGE_PIN R23 IOSTANDARD LVCMOS18 } [get_ports { saFbWrt[2] }]
set_property -dict { PACKAGE_PIN R24 IOSTANDARD LVCMOS18 } [get_ports { saFbWrt[3] }]
set_property -dict { PACKAGE_PIN R25 IOSTANDARD LVCMOS18 } [get_ports { saFbClk[0] }]
set_property -dict { PACKAGE_PIN R26 IOSTANDARD LVCMOS18 } [get_ports { saFbClk[1] }]
set_property -dict { PACKAGE_PIN R28 IOSTANDARD LVCMOS18 } [get_ports { saFbClk[2] }]
set_property -dict { PACKAGE_PIN T28 IOSTANDARD LVCMOS18 } [get_ports { saFbClk[3] }]
set_property -dict { PACKAGE_PIN T22 IOSTANDARD LVCMOS18 } [get_ports { saFbSel[0] }]
set_property -dict { PACKAGE_PIN T23 IOSTANDARD LVCMOS18 } [get_ports { saFbSel[1] }]
set_property -dict { PACKAGE_PIN T25 IOSTANDARD LVCMOS18 } [get_ports { saFbSel[2] }]
set_property -dict { PACKAGE_PIN U25 IOSTANDARD LVCMOS18 } [get_ports { saFbSel[3] }]
set_property -dict { PACKAGE_PIN T27 IOSTANDARD LVCMOS18 } [get_ports { saFbReset[0] }]
set_property -dict { PACKAGE_PIN U28 IOSTANDARD LVCMOS18 } [get_ports { saFbReset[1] }]
set_property -dict { PACKAGE_PIN U22 IOSTANDARD LVCMOS18 } [get_ports { saFbReset[2] }]
set_property -dict { PACKAGE_PIN V22 IOSTANDARD LVCMOS18 } [get_ports { saFbReset[3] }]
set_property -dict { PACKAGE_PIN U24 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[0] }]
set_property -dict { PACKAGE_PIN V24 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[1] }]
set_property -dict { PACKAGE_PIN U27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[2] }]
set_property -dict { PACKAGE_PIN V27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[3] }]
set_property -dict { PACKAGE_PIN V25 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[4] }]
set_property -dict { PACKAGE_PIN V26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[5] }]
set_property -dict { PACKAGE_PIN W23 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[6] }]
set_property -dict { PACKAGE_PIN Y23 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[7] }]
set_property -dict { PACKAGE_PIN W24 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[8] }]
set_property -dict { PACKAGE_PIN Y24 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[9] }]
set_property -dict { PACKAGE_PIN W26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[10] }]
set_property -dict { PACKAGE_PIN Y26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[11] }]
set_property -dict { PACKAGE_PIN W27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[12] }]
set_property -dict { PACKAGE_PIN W28 IOSTANDARD LVCMOS18 } [get_ports { sq1FbDb[13] }]
set_property -dict { PACKAGE_PIN Y25 IOSTANDARD LVCMOS18 } [get_ports { sq1FbWrt[0] }]
set_property -dict { PACKAGE_PIN AA25 IOSTANDARD LVCMOS18 } [get_ports { sq1FbWrt[1] }]
set_property -dict { PACKAGE_PIN Y28 IOSTANDARD LVCMOS18 } [get_ports { sq1FbWrt[2] }]
set_property -dict { PACKAGE_PIN AA28 IOSTANDARD LVCMOS18 } [get_ports { sq1FbWrt[3] }]

##############################################################################
## HP Bank 66 (VCCO=1.8V) - SQ1 FB remainder + SQ1 Bias + AUX DAC (no clocks)
##############################################################################
set_property -dict { PACKAGE_PIN A26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbClk[0] }]
set_property -dict { PACKAGE_PIN A27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbClk[1] }]
set_property -dict { PACKAGE_PIN B27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbClk[2] }]
set_property -dict { PACKAGE_PIN B28 IOSTANDARD LVCMOS18 } [get_ports { sq1FbClk[3] }]
set_property -dict { PACKAGE_PIN C26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbSel[0] }]
set_property -dict { PACKAGE_PIN C27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbSel[1] }]
set_property -dict { PACKAGE_PIN D27 IOSTANDARD LVCMOS18 } [get_ports { sq1FbSel[2] }]
set_property -dict { PACKAGE_PIN D28 IOSTANDARD LVCMOS18 } [get_ports { sq1FbSel[3] }]
set_property -dict { PACKAGE_PIN E26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbReset[0] }]
set_property -dict { PACKAGE_PIN D26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbReset[1] }]
set_property -dict { PACKAGE_PIN F25 IOSTANDARD LVCMOS18 } [get_ports { sq1FbReset[2] }]
set_property -dict { PACKAGE_PIN F26 IOSTANDARD LVCMOS18 } [get_ports { sq1FbReset[3] }]
set_property -dict { PACKAGE_PIN F28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[0] }]
set_property -dict { PACKAGE_PIN E28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[1] }]
set_property -dict { PACKAGE_PIN H25 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[2] }]
set_property -dict { PACKAGE_PIN G25 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[3] }]
set_property -dict { PACKAGE_PIN H27 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[4] }]
set_property -dict { PACKAGE_PIN G28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[5] }]
set_property -dict { PACKAGE_PIN J26 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[6] }]
set_property -dict { PACKAGE_PIN H26 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[7] }]
set_property -dict { PACKAGE_PIN J27 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[8] }]
set_property -dict { PACKAGE_PIN J28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[9] }]
set_property -dict { PACKAGE_PIN K24 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[10] }]
set_property -dict { PACKAGE_PIN J24 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[11] }]
set_property -dict { PACKAGE_PIN K25 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[12] }]
set_property -dict { PACKAGE_PIN K26 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasDb[13] }]
set_property -dict { PACKAGE_PIN L23 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasWrt[0] }]
set_property -dict { PACKAGE_PIN K23 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasWrt[1] }]
set_property -dict { PACKAGE_PIN L25 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasWrt[2] }]
set_property -dict { PACKAGE_PIN L26 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasWrt[3] }]
set_property -dict { PACKAGE_PIN L27 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasClk[0] }]
set_property -dict { PACKAGE_PIN K28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasClk[1] }]
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasClk[2] }]
set_property -dict { PACKAGE_PIN L22 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasClk[3] }]
set_property -dict { PACKAGE_PIN M23 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasSel[0] }]
set_property -dict { PACKAGE_PIN M24 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasSel[1] }]
set_property -dict { PACKAGE_PIN M28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasSel[2] }]
set_property -dict { PACKAGE_PIN L28 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasSel[3] }]
set_property -dict { PACKAGE_PIN N27 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasReset[0] }]
set_property -dict { PACKAGE_PIN M27 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasReset[1] }]
set_property -dict { PACKAGE_PIN P22 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasReset[2] }]
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS18 } [get_ports { sq1BiasReset[3] }]

##############################################################################
## HD Bank 84 (VCCO=3.3V) - Thermistors on SYSMON + remaining AUX DAC
##############################################################################
set_property -dict { PACKAGE_PIN AB13 IOSTANDARD ANALOG } [get_ports { localThermistorP[0] }]
set_property -dict { PACKAGE_PIN AB14 IOSTANDARD ANALOG } [get_ports { localThermistorN[0] }]
set_property -dict { PACKAGE_PIN AC14 IOSTANDARD ANALOG } [get_ports { localThermistorP[1] }]
set_property -dict { PACKAGE_PIN AC15 IOSTANDARD ANALOG } [get_ports { localThermistorN[1] }]
set_property -dict { PACKAGE_PIN AB15 IOSTANDARD ANALOG } [get_ports { localThermistorP[2] }]
set_property -dict { PACKAGE_PIN AB16 IOSTANDARD ANALOG } [get_ports { localThermistorN[2] }]
set_property -dict { PACKAGE_PIN AC16 IOSTANDARD ANALOG } [get_ports { localThermistorP[3] }]
set_property -dict { PACKAGE_PIN AD16 IOSTANDARD ANALOG } [get_ports { localThermistorN[3] }]
set_property -dict { PACKAGE_PIN AD13 IOSTANDARD ANALOG } [get_ports { localThermistorP[4] }]
set_property -dict { PACKAGE_PIN AD14 IOSTANDARD ANALOG } [get_ports { localThermistorN[4] }]
set_property -dict { PACKAGE_PIN AE13 IOSTANDARD ANALOG } [get_ports { localThermistorP[5] }]
set_property -dict { PACKAGE_PIN AE14 IOSTANDARD ANALOG } [get_ports { localThermistorN[5] }]
set_property -dict { PACKAGE_PIN AE15 IOSTANDARD ANALOG } [get_ports { feThermistorP[0] }]
set_property -dict { PACKAGE_PIN AF15 IOSTANDARD ANALOG } [get_ports { feThermistorN[0] }]
set_property -dict { PACKAGE_PIN AE16 IOSTANDARD ANALOG } [get_ports { feThermistorP[1] }]
set_property -dict { PACKAGE_PIN AF16 IOSTANDARD ANALOG } [get_ports { feThermistorN[1] }]
##############################################################################
## HD Bank 85 (VCCO=3.3V) - Misc control: boot, I2C, SFP, TES DAC, xbar, power
##############################################################################
set_property -dict { PACKAGE_PIN AA10 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }]
set_property -dict { PACKAGE_PIN AB9 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }]
set_property -dict { PACKAGE_PIN AB10 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }]
set_property -dict { PACKAGE_PIN AC9 IOSTANDARD LVCMOS33 } [get_ports { locScl }]
set_property -dict { PACKAGE_PIN AB12 IOSTANDARD LVCMOS33 } [get_ports { locSda }]
set_property -dict { PACKAGE_PIN AC12 IOSTANDARD LVCMOS33 } [get_ports { tempAlertL }]
set_property -dict { PACKAGE_PIN AC10 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }]
set_property -dict { PACKAGE_PIN AC11 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }]
set_property -dict { PACKAGE_PIN AD11 IOSTANDARD LVCMOS33 } [get_ports { sfpScl[0] }]
set_property -dict { PACKAGE_PIN AE10 IOSTANDARD LVCMOS33 } [get_ports { sfpSda[0] }]
set_property -dict { PACKAGE_PIN AD12 IOSTANDARD LVCMOS33 } [get_ports { sfpScl[1] }]
set_property -dict { PACKAGE_PIN AE11 IOSTANDARD LVCMOS33 } [get_ports { sfpSda[1] }]
set_property -dict { PACKAGE_PIN AD9 IOSTANDARD LVCMOS33 } [get_ports { anaPwrEn }]
set_property -dict { PACKAGE_PIN AE9 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncA }]
set_property -dict { PACKAGE_PIN AF10 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncB }]
set_property -dict { PACKAGE_PIN AF11 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncC }]
set_property -dict { PACKAGE_PIN AF12 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[0] }]
set_property -dict { PACKAGE_PIN AG12 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[1] }]
set_property -dict { PACKAGE_PIN AG10 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[0] }]
set_property -dict { PACKAGE_PIN AG9 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[1] }]
set_property -dict { PACKAGE_PIN AH10 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[0] }]
set_property -dict { PACKAGE_PIN AH9 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[1] }]
set_property -dict { PACKAGE_PIN AH11 IOSTANDARD LVCMOS33 } [get_ports { xbarTimingSel[0] }]
set_property -dict { PACKAGE_PIN AH12 IOSTANDARD LVCMOS33 } [get_ports { xbarTimingSel[1] }]

##############################################################################
## HD Bank 86 (VCCO=3.3V) - TES DAC, FE DAC, lemo, tesDelatch
##############################################################################
set_property -dict { PACKAGE_PIN A11 IOSTANDARD LVCMOS33 } [get_ports { tesDacSclk }]
set_property -dict { PACKAGE_PIN A10 IOSTANDARD LVCMOS33 } [get_ports { tesDacDin }]
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVCMOS33 } [get_ports { tesDacLdacL }]
set_property -dict { PACKAGE_PIN A12 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[0] }]
set_property -dict { PACKAGE_PIN B10 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[1] }]
set_property -dict { PACKAGE_PIN B9 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[2] }]
set_property -dict { PACKAGE_PIN C12 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[3] }]
set_property -dict { PACKAGE_PIN B12 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[4] }]
set_property -dict { PACKAGE_PIN D11 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[5] }]
set_property -dict { PACKAGE_PIN C10 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[6] }]
set_property -dict { PACKAGE_PIN D12 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[7] }]
set_property -dict { PACKAGE_PIN C11 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[0] }]
set_property -dict { PACKAGE_PIN D9 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[1] }]
set_property -dict { PACKAGE_PIN C9 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[2] }]
set_property -dict { PACKAGE_PIN E10 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[3] }]
set_property -dict { PACKAGE_PIN E9 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[4] }]
set_property -dict { PACKAGE_PIN F11 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[5] }]
set_property -dict { PACKAGE_PIN E11 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[6] }]
set_property -dict { PACKAGE_PIN G10 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[7] }]
set_property -dict { PACKAGE_PIN F10 IOSTANDARD LVCMOS33 } [get_ports { feDacSclk }]
set_property -dict { PACKAGE_PIN G12 IOSTANDARD LVCMOS33 } [get_ports { feDacMosi }]
set_property -dict { PACKAGE_PIN F12 IOSTANDARD LVCMOS33 } [get_ports { feDacMiso }]
set_property -dict { PACKAGE_PIN H10 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[0] }]
set_property -dict { PACKAGE_PIN G9 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[1] }]

##############################################################################
## HD Bank 87 (VCCO=3.3V) - LEDs
##############################################################################
set_property -dict { PACKAGE_PIN A15 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }]
set_property -dict { PACKAGE_PIN A16 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }]
set_property -dict { PACKAGE_PIN B13 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }]
set_property -dict { PACKAGE_PIN B14 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }]
set_property -dict { PACKAGE_PIN C14 IOSTANDARD LVCMOS33 } [get_ports { leds[4] }]
set_property -dict { PACKAGE_PIN B15 IOSTANDARD LVCMOS33 } [get_ports { leds[5] }]
set_property -dict { PACKAGE_PIN C15 IOSTANDARD LVCMOS33 } [get_ports { leds[6] }]
set_property -dict { PACKAGE_PIN C16 IOSTANDARD LVCMOS33 } [get_ports { leds[7] }]
set_property -dict { PACKAGE_PIN D13 IOSTANDARD LVCMOS33 } [get_ports { conRxGreenLed }]
set_property -dict { PACKAGE_PIN D14 IOSTANDARD LVCMOS33 } [get_ports { conRxYellowLed }]
set_property -dict { PACKAGE_PIN D16 IOSTANDARD LVCMOS33 } [get_ports { conTxGreenLed }]
set_property -dict { PACKAGE_PIN D17 IOSTANDARD LVCMOS33 } [get_ports { conTxYellowLed }]
set_property -dict { PACKAGE_PIN E13 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[2] }]
set_property -dict { PACKAGE_PIN E14 IOSTANDARD LVCMOS33 } [get_ports { lemoIn[0] }]
set_property -dict { PACKAGE_PIN E15 IOSTANDARD LVCMOS33 } [get_ports { lemoIn[1] }]
set_property -dict { PACKAGE_PIN E16 IOSTANDARD LVCMOS33 } [get_ports { lemoOut[0] }]
set_property -dict { PACKAGE_PIN F13 IOSTANDARD LVCMOS33 } [get_ports { lemoOut[1] }]
set_property -dict { PACKAGE_PIN G13 IOSTANDARD LVCMOS33 } [get_ports { fePwrSyncA }]
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVCMOS33 } [get_ports { fePwrSyncB }]

##############################################################################
## Clock Groups
##############################################################################
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks adcDClk0] \
    -group [get_clocks -include_generated_clocks adcDClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk]

## PGP GT recovered clocks
create_clock -name pgpTxOutClk    -period 6.400 [get_pins -hier -filter {NAME =~ *U_PgpCore_1/*TXOUTCLK}]
create_clock -name pgpTxPcsClk    -period 6.400 [get_pins -hier -filter {NAME =~ *U_PgpCore_1/*txoutclkpcs*}]

set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks fabRefClk0] \
    -group [get_clocks pgpTxOutClk] \
    -group [get_clocks pgpTxPcsClk]

## Timing TX word clock async to axil and timing RX
set_clock_groups -asynchronous \
    -group [get_clocks -quiet wordClk] \
    -group [get_clocks axilClk]

set_clock_groups -asynchronous \
    -group [get_clocks -quiet wordClk] \
    -group [get_clocks -include_generated_clocks timingRxClk]

##############################################################################
## Bitstream Configuration
##############################################################################
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property CONFIG_VOLTAGE 1.8 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
