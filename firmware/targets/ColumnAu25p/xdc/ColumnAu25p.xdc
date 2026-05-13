##############################################################################
## Pin constraints for XAU25P-SFVB784 power evaluation target
## These are PLACEHOLDER assignments for synthesis/implementation power analysis.
## They are valid pins for the package but do NOT correspond to a real board.
##############################################################################

## GT Reference Clocks (MGTREFCLK pins on the GTY quad)
create_clock -name gtRefClk0 -period 4.000 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 6.400 [get_ports {gtRefClk1P}]

set_property PACKAGE_PIN T8 [get_ports {gtRefClk0P}]
set_property PACKAGE_PIN T7 [get_ports {gtRefClk0N}]
set_property PACKAGE_PIN R10 [get_ports {gtRefClk1P}]
set_property PACKAGE_PIN R9 [get_ports {gtRefClk1N}]

## GTY Transceivers (Quad 224)
# PGP
set_property PACKAGE_PIN U4 [get_ports {pgpTxP}]
set_property PACKAGE_PIN U3 [get_ports {pgpTxN}]
set_property PACKAGE_PIN V2 [get_ports {pgpRxP}]
set_property PACKAGE_PIN V1 [get_ports {pgpRxN}]

# SFP (10G Ethernet)
set_property PACKAGE_PIN T4 [get_ports {sfp0TxP}]
set_property PACKAGE_PIN T3 [get_ports {sfp0TxN}]
set_property PACKAGE_PIN R2 [get_ports {sfp0RxP}]
set_property PACKAGE_PIN R1 [get_ports {sfp0RxN}]

##############################################################################
## HP Bank 24 (VCCO = 1.8V) - LVDS Timing and ADC
##############################################################################

## ADC Clocks
create_clock -name adcDClk0 -period 2.00 [get_ports {adcDClkP[0]}]
create_clock -name adcDClk1 -period 2.00 [get_ports {adcDClkP[1]}]
set_input_jitter adcDClk0 .35
set_input_jitter adcDClk1 .35

## Timing RX (LVDS with internal termination)
set_property -dict { PACKAGE_PIN D12 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkP }]
set_property -dict { PACKAGE_PIN C12 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxClkN }]
set_property -dict { PACKAGE_PIN E13 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataP }]
set_property -dict { PACKAGE_PIN D13 IOSTANDARD LVDS DIFF_TERM TRUE } [get_ports { timingRxDataN }]

create_clock -name timingRxClk -period 8.000 [get_ports {timingRxClkP}]

## Timing TX (LVDS output)
set_property -dict { PACKAGE_PIN B13 IOSTANDARD LVDS } [get_ports { timingTxClkP }]
set_property -dict { PACKAGE_PIN A13 IOSTANDARD LVDS } [get_ports { timingTxClkN }]
set_property -dict { PACKAGE_PIN B12 IOSTANDARD LVDS } [get_ports { timingTxDataP }]
set_property -dict { PACKAGE_PIN A12 IOSTANDARD LVDS } [get_ports { timingTxDataN }]

## ADC Clock Output (LVDS)
set_property -dict { PACKAGE_PIN F14 IOSTANDARD LVDS } [get_ports { adcClkP }]
set_property -dict { PACKAGE_PIN E14 IOSTANDARD LVDS } [get_ports { adcClkN }]

## ADC 0 (HP Bank 24)
set_property -dict { PACKAGE_PIN H14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[0] }]
set_property -dict { PACKAGE_PIN G14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[0] }]
set_property -dict { PACKAGE_PIN H13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[0] }]
set_property -dict { PACKAGE_PIN G13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[0] }]

set_property -dict { PACKAGE_PIN J12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][0] }]
set_property -dict { PACKAGE_PIN H12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][0] }]
set_property -dict { PACKAGE_PIN K13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][1] }]
set_property -dict { PACKAGE_PIN J13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][1] }]
set_property -dict { PACKAGE_PIN L12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][2] }]
set_property -dict { PACKAGE_PIN K12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][2] }]
set_property -dict { PACKAGE_PIN L14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][3] }]
set_property -dict { PACKAGE_PIN L13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][3] }]
set_property -dict { PACKAGE_PIN M12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][4] }]
set_property -dict { PACKAGE_PIN M11 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][4] }]
set_property -dict { PACKAGE_PIN N13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][5] }]
set_property -dict { PACKAGE_PIN N12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][5] }]
set_property -dict { PACKAGE_PIN P12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][6] }]
set_property -dict { PACKAGE_PIN P11 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][6] }]
set_property -dict { PACKAGE_PIN R13 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[0][7] }]
set_property -dict { PACKAGE_PIN R12 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[0][7] }]

##############################################################################
## HP Bank 25 (VCCO = 1.8V) - ADC 1
##############################################################################
set_property -dict { PACKAGE_PIN B15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkP[1] }]
set_property -dict { PACKAGE_PIN A15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcFClkN[1] }]
set_property -dict { PACKAGE_PIN C14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkP[1] }]
set_property -dict { PACKAGE_PIN B14 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcDClkN[1] }]

set_property -dict { PACKAGE_PIN D15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][0] }]
set_property -dict { PACKAGE_PIN C15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][0] }]
set_property -dict { PACKAGE_PIN F15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][1] }]
set_property -dict { PACKAGE_PIN E15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][1] }]
set_property -dict { PACKAGE_PIN G16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][2] }]
set_property -dict { PACKAGE_PIN F16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][2] }]
set_property -dict { PACKAGE_PIN H16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][3] }]
set_property -dict { PACKAGE_PIN G15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][3] }]
set_property -dict { PACKAGE_PIN J16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][4] }]
set_property -dict { PACKAGE_PIN J15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][4] }]
set_property -dict { PACKAGE_PIN K16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][5] }]
set_property -dict { PACKAGE_PIN K15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][5] }]
set_property -dict { PACKAGE_PIN L16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][6] }]
set_property -dict { PACKAGE_PIN L15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][6] }]
set_property -dict { PACKAGE_PIN M16 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChP[1][7] }]
set_property -dict { PACKAGE_PIN M15 IOSTANDARD LVDS DIFF_TERM TRUE} [get_ports { adcChN[1][7] }]

## ADC control (LVCMOS18 in HP bank)
set_property -dict { PACKAGE_PIN N16 IOSTANDARD LVCMOS18 } [get_ports { adcSclk }]
set_property -dict { PACKAGE_PIN P16 IOSTANDARD LVCMOS18 } [get_ports { adcSdio }]
set_property -dict { PACKAGE_PIN N15 IOSTANDARD LVCMOS18 } [get_ports { adcCsb }]
set_property -dict { PACKAGE_PIN P15 IOSTANDARD LVCMOS18 } [get_ports { adcSync }]
set_property -dict { PACKAGE_PIN R16 IOSTANDARD LVCMOS18 } [get_ports { adcPdwn }]

##############################################################################
## HD Bank 64 (VCCO = 3.3V) - Fast DAC SA FB
##############################################################################
set_property -dict { PACKAGE_PIN AB21 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[0] }]
set_property -dict { PACKAGE_PIN AC21 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[1] }]
set_property -dict { PACKAGE_PIN AB22 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[2] }]
set_property -dict { PACKAGE_PIN AC22 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[3] }]
set_property -dict { PACKAGE_PIN AA22 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[4] }]
set_property -dict { PACKAGE_PIN AA23 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[5] }]
set_property -dict { PACKAGE_PIN AB23 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[6] }]
set_property -dict { PACKAGE_PIN AC23 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[7] }]
set_property -dict { PACKAGE_PIN AB24 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[8] }]
set_property -dict { PACKAGE_PIN AC24 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[9] }]
set_property -dict { PACKAGE_PIN AA24 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[10] }]
set_property -dict { PACKAGE_PIN AA25 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[11] }]
set_property -dict { PACKAGE_PIN AB25 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[12] }]
set_property -dict { PACKAGE_PIN AC25 IOSTANDARD LVCMOS33 } [get_ports { saFbDb[13] }]

set_property -dict { PACKAGE_PIN AB26 IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[0] }]
set_property -dict { PACKAGE_PIN AC26 IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[1] }]
set_property -dict { PACKAGE_PIN AA26 IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[2] }]
set_property -dict { PACKAGE_PIN Y25 IOSTANDARD LVCMOS33 } [get_ports { saFbWrt[3] }]
set_property -dict { PACKAGE_PIN Y26 IOSTANDARD LVCMOS33 } [get_ports { saFbClk[0] }]
set_property -dict { PACKAGE_PIN W25 IOSTANDARD LVCMOS33 } [get_ports { saFbClk[1] }]
set_property -dict { PACKAGE_PIN W26 IOSTANDARD LVCMOS33 } [get_ports { saFbClk[2] }]
set_property -dict { PACKAGE_PIN V26 IOSTANDARD LVCMOS33 } [get_ports { saFbClk[3] }]
set_property -dict { PACKAGE_PIN V25 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[0] }]
set_property -dict { PACKAGE_PIN U25 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[1] }]
set_property -dict { PACKAGE_PIN U26 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[2] }]
set_property -dict { PACKAGE_PIN T25 IOSTANDARD LVCMOS33 } [get_ports { saFbSel[3] }]
set_property -dict { PACKAGE_PIN T26 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[0] }]
set_property -dict { PACKAGE_PIN R26 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[1] }]
set_property -dict { PACKAGE_PIN R25 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[2] }]
set_property -dict { PACKAGE_PIN P25 IOSTANDARD LVCMOS33 } [get_ports { saFbReset[3] }]

##############################################################################
## HD Bank 65 (VCCO = 3.3V) - Fast DAC SQ1 FB
##############################################################################
set_property -dict { PACKAGE_PIN P26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[0] }]
set_property -dict { PACKAGE_PIN N26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[1] }]
set_property -dict { PACKAGE_PIN N24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[2] }]
set_property -dict { PACKAGE_PIN N25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[3] }]
set_property -dict { PACKAGE_PIN M24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[4] }]
set_property -dict { PACKAGE_PIN M25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[5] }]
set_property -dict { PACKAGE_PIN M26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[6] }]
set_property -dict { PACKAGE_PIN L24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[7] }]
set_property -dict { PACKAGE_PIN L25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[8] }]
set_property -dict { PACKAGE_PIN L26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[9] }]
set_property -dict { PACKAGE_PIN K25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[10] }]
set_property -dict { PACKAGE_PIN K26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[11] }]
set_property -dict { PACKAGE_PIN J25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[12] }]
set_property -dict { PACKAGE_PIN J26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbDb[13] }]

set_property -dict { PACKAGE_PIN H25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[0] }]
set_property -dict { PACKAGE_PIN H26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[1] }]
set_property -dict { PACKAGE_PIN G25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[2] }]
set_property -dict { PACKAGE_PIN G26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbWrt[3] }]
set_property -dict { PACKAGE_PIN F25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[0] }]
set_property -dict { PACKAGE_PIN E25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[1] }]
set_property -dict { PACKAGE_PIN E26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[2] }]
set_property -dict { PACKAGE_PIN D25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbClk[3] }]
set_property -dict { PACKAGE_PIN D26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[0] }]
set_property -dict { PACKAGE_PIN C24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[1] }]
set_property -dict { PACKAGE_PIN B24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[2] }]
set_property -dict { PACKAGE_PIN A24 IOSTANDARD LVCMOS33 } [get_ports { sq1FbSel[3] }]
set_property -dict { PACKAGE_PIN C25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[0] }]
set_property -dict { PACKAGE_PIN B25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[1] }]
set_property -dict { PACKAGE_PIN A25 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[2] }]
set_property -dict { PACKAGE_PIN B26 IOSTANDARD LVCMOS33 } [get_ports { sq1FbReset[3] }]

##############################################################################
## HD Bank 66 (VCCO = 3.3V) - Fast DAC SQ1 Bias + AUX
##############################################################################
set_property -dict { PACKAGE_PIN A21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[0] }]
set_property -dict { PACKAGE_PIN A22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[1] }]
set_property -dict { PACKAGE_PIN B21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[2] }]
set_property -dict { PACKAGE_PIN B22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[3] }]
set_property -dict { PACKAGE_PIN C21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[4] }]
set_property -dict { PACKAGE_PIN C22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[5] }]
set_property -dict { PACKAGE_PIN D21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[6] }]
set_property -dict { PACKAGE_PIN D22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[7] }]
set_property -dict { PACKAGE_PIN E21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[8] }]
set_property -dict { PACKAGE_PIN E22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[9] }]
set_property -dict { PACKAGE_PIN F21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[10] }]
set_property -dict { PACKAGE_PIN F22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[11] }]
set_property -dict { PACKAGE_PIN G21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[12] }]
set_property -dict { PACKAGE_PIN G22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasDb[13] }]

set_property -dict { PACKAGE_PIN H21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[0] }]
set_property -dict { PACKAGE_PIN H22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[1] }]
set_property -dict { PACKAGE_PIN J21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[2] }]
set_property -dict { PACKAGE_PIN J22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasWrt[3] }]
set_property -dict { PACKAGE_PIN K21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[0] }]
set_property -dict { PACKAGE_PIN K22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[1] }]
set_property -dict { PACKAGE_PIN L21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[2] }]
set_property -dict { PACKAGE_PIN L22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasClk[3] }]
set_property -dict { PACKAGE_PIN M21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[0] }]
set_property -dict { PACKAGE_PIN M22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[1] }]
set_property -dict { PACKAGE_PIN N21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[2] }]
set_property -dict { PACKAGE_PIN N22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasSel[3] }]
set_property -dict { PACKAGE_PIN P21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[0] }]
set_property -dict { PACKAGE_PIN P22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[1] }]
set_property -dict { PACKAGE_PIN R21 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[2] }]
set_property -dict { PACKAGE_PIN R22 IOSTANDARD LVCMOS33 } [get_ports { sq1BiasReset[3] }]

## AUX DAC (also in HD bank 66)
set_property -dict { PACKAGE_PIN T21 IOSTANDARD LVCMOS33 } [get_ports { auxDb[0] }]
set_property -dict { PACKAGE_PIN T22 IOSTANDARD LVCMOS33 } [get_ports { auxDb[1] }]
set_property -dict { PACKAGE_PIN U21 IOSTANDARD LVCMOS33 } [get_ports { auxDb[2] }]
set_property -dict { PACKAGE_PIN U22 IOSTANDARD LVCMOS33 } [get_ports { auxDb[3] }]
set_property -dict { PACKAGE_PIN V21 IOSTANDARD LVCMOS33 } [get_ports { auxDb[4] }]
set_property -dict { PACKAGE_PIN V22 IOSTANDARD LVCMOS33 } [get_ports { auxDb[5] }]
set_property -dict { PACKAGE_PIN W21 IOSTANDARD LVCMOS33 } [get_ports { auxDb[6] }]
set_property -dict { PACKAGE_PIN W22 IOSTANDARD LVCMOS33 } [get_ports { auxDb[7] }]
set_property -dict { PACKAGE_PIN Y21 IOSTANDARD LVCMOS33 } [get_ports { auxDb[8] }]
set_property -dict { PACKAGE_PIN Y22 IOSTANDARD LVCMOS33 } [get_ports { auxDb[9] }]
set_property -dict { PACKAGE_PIN AA21 IOSTANDARD LVCMOS33 } [get_ports { auxDb[10] }]
set_property -dict { PACKAGE_PIN AA22 IOSTANDARD LVCMOS33 } [get_ports { auxDb[11] }]
set_property -dict { PACKAGE_PIN A23 IOSTANDARD LVCMOS33 } [get_ports { auxDb[12] }]
set_property -dict { PACKAGE_PIN B23 IOSTANDARD LVCMOS33 } [get_ports { auxDb[13] }]

set_property -dict { PACKAGE_PIN C23 IOSTANDARD LVCMOS33 } [get_ports { auxWrt[0] }]
set_property -dict { PACKAGE_PIN D23 IOSTANDARD LVCMOS33 } [get_ports { auxWrt[1] }]
set_property -dict { PACKAGE_PIN E23 IOSTANDARD LVCMOS33 } [get_ports { auxWrt[2] }]
set_property -dict { PACKAGE_PIN F23 IOSTANDARD LVCMOS33 } [get_ports { auxWrt[3] }]
set_property -dict { PACKAGE_PIN G23 IOSTANDARD LVCMOS33 } [get_ports { auxClk[0] }]
set_property -dict { PACKAGE_PIN H23 IOSTANDARD LVCMOS33 } [get_ports { auxClk[1] }]
set_property -dict { PACKAGE_PIN J23 IOSTANDARD LVCMOS33 } [get_ports { auxClk[2] }]
set_property -dict { PACKAGE_PIN K23 IOSTANDARD LVCMOS33 } [get_ports { auxClk[3] }]
set_property -dict { PACKAGE_PIN L23 IOSTANDARD LVCMOS33 } [get_ports { auxSel[0] }]
set_property -dict { PACKAGE_PIN M23 IOSTANDARD LVCMOS33 } [get_ports { auxSel[1] }]
set_property -dict { PACKAGE_PIN N23 IOSTANDARD LVCMOS33 } [get_ports { auxSel[2] }]
set_property -dict { PACKAGE_PIN P23 IOSTANDARD LVCMOS33 } [get_ports { auxSel[3] }]
set_property -dict { PACKAGE_PIN R23 IOSTANDARD LVCMOS33 } [get_ports { auxReset[0] }]
set_property -dict { PACKAGE_PIN T23 IOSTANDARD LVCMOS33 } [get_ports { auxReset[1] }]
set_property -dict { PACKAGE_PIN U23 IOSTANDARD LVCMOS33 } [get_ports { auxReset[2] }]
set_property -dict { PACKAGE_PIN V23 IOSTANDARD LVCMOS33 } [get_ports { auxReset[3] }]

##############################################################################
## HD Bank 67 (VCCO = 3.3V) - Slow DACs, LEDs, Misc
##############################################################################

## Slow DACs (FE TES DACs)
set_property -dict { PACKAGE_PIN A17 IOSTANDARD LVCMOS33 } [get_ports { feDacSclk }]
set_property -dict { PACKAGE_PIN B17 IOSTANDARD LVCMOS33 } [get_ports { feDacMosi }]
set_property -dict { PACKAGE_PIN C17 IOSTANDARD LVCMOS33 } [get_ports { feDacMiso }]
set_property -dict { PACKAGE_PIN D17 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[0] }]
set_property -dict { PACKAGE_PIN E17 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[1] }]
set_property -dict { PACKAGE_PIN F17 IOSTANDARD LVCMOS33 } [get_ports { feDacSyncB[2] }]
set_property -dict { PACKAGE_PIN A18 IOSTANDARD LVCMOS33 } [get_ports { feDacLdacB[0] }]
set_property -dict { PACKAGE_PIN B18 IOSTANDARD LVCMOS33 } [get_ports { feDacLdacB[1] }]
set_property -dict { PACKAGE_PIN C18 IOSTANDARD LVCMOS33 } [get_ports { feDacLdacB[2] }]
set_property -dict { PACKAGE_PIN D18 IOSTANDARD LVCMOS33 } [get_ports { feDacResetB[0] }]
set_property -dict { PACKAGE_PIN E18 IOSTANDARD LVCMOS33 } [get_ports { feDacResetB[1] }]
set_property -dict { PACKAGE_PIN F18 IOSTANDARD LVCMOS33 } [get_ports { feDacResetB[2] }]

## TES DACs
set_property -dict { PACKAGE_PIN G17 IOSTANDARD LVCMOS33 } [get_ports { tesDacSclk }]
set_property -dict { PACKAGE_PIN H17 IOSTANDARD LVCMOS33 } [get_ports { tesDacDin }]
set_property -dict { PACKAGE_PIN J17 IOSTANDARD LVCMOS33 } [get_ports { tesDacLdacL }]
set_property -dict { PACKAGE_PIN K17 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[0] }]
set_property -dict { PACKAGE_PIN L17 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[1] }]
set_property -dict { PACKAGE_PIN M17 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[2] }]
set_property -dict { PACKAGE_PIN N17 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[3] }]
set_property -dict { PACKAGE_PIN A19 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[4] }]
set_property -dict { PACKAGE_PIN B19 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[5] }]
set_property -dict { PACKAGE_PIN C19 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[6] }]
set_property -dict { PACKAGE_PIN D19 IOSTANDARD LVCMOS33 } [get_ports { tesDacCsL[7] }]

## LEDs
set_property -dict { PACKAGE_PIN E19 IOSTANDARD LVCMOS33 } [get_ports { leds[0] }]
set_property -dict { PACKAGE_PIN F19 IOSTANDARD LVCMOS33 } [get_ports { leds[1] }]
set_property -dict { PACKAGE_PIN G19 IOSTANDARD LVCMOS33 } [get_ports { leds[2] }]
set_property -dict { PACKAGE_PIN H19 IOSTANDARD LVCMOS33 } [get_ports { leds[3] }]
set_property -dict { PACKAGE_PIN J19 IOSTANDARD LVCMOS33 } [get_ports { leds[4] }]
set_property -dict { PACKAGE_PIN K19 IOSTANDARD LVCMOS33 } [get_ports { leds[5] }]
set_property -dict { PACKAGE_PIN L19 IOSTANDARD LVCMOS33 } [get_ports { leds[6] }]
set_property -dict { PACKAGE_PIN M19 IOSTANDARD LVCMOS33 } [get_ports { leds[7] }]

## I2C and control
set_property -dict { PACKAGE_PIN N19 IOSTANDARD LVCMOS33 } [get_ports { locScl }]
set_property -dict { PACKAGE_PIN P19 IOSTANDARD LVCMOS33 } [get_ports { locSda }]
set_property -dict { PACKAGE_PIN R19 IOSTANDARD LVCMOS33 } [get_ports { pwrScl }]
set_property -dict { PACKAGE_PIN T19 IOSTANDARD LVCMOS33 } [get_ports { pwrSda }]
set_property -dict { PACKAGE_PIN U19 IOSTANDARD LVCMOS33 } [get_ports { tempAlertL }]

set_property -dict { PACKAGE_PIN A20 IOSTANDARD LVCMOS33 } [get_ports { sfpScl[0] }]
set_property -dict { PACKAGE_PIN B20 IOSTANDARD LVCMOS33 } [get_ports { sfpSda[0] }]
set_property -dict { PACKAGE_PIN C20 IOSTANDARD LVCMOS33 } [get_ports { sfpScl[1] }]
set_property -dict { PACKAGE_PIN D20 IOSTANDARD LVCMOS33 } [get_ports { sfpSda[1] }]

set_property -dict { PACKAGE_PIN E20 IOSTANDARD LVCMOS33 } [get_ports { anaPwrEn }]
set_property -dict { PACKAGE_PIN F20 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncA }]
set_property -dict { PACKAGE_PIN G20 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncB }]
set_property -dict { PACKAGE_PIN H20 IOSTANDARD LVCMOS33 } [get_ports { pwrSyncC }]

## Timing source select crossbar
set_property -dict { PACKAGE_PIN J20 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[0] }]
set_property -dict { PACKAGE_PIN K20 IOSTANDARD LVCMOS33 } [get_ports { xbarDataSel[1] }]
set_property -dict { PACKAGE_PIN L20 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[0] }]
set_property -dict { PACKAGE_PIN M20 IOSTANDARD LVCMOS33 } [get_ports { xbarClkSel[1] }]
set_property -dict { PACKAGE_PIN N20 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[0] }]
set_property -dict { PACKAGE_PIN P20 IOSTANDARD LVCMOS33 } [get_ports { xbarMgtSel[1] }]
set_property -dict { PACKAGE_PIN R20 IOSTANDARD LVCMOS33 } [get_ports { xbarTimingSel[0] }]
set_property -dict { PACKAGE_PIN T20 IOSTANDARD LVCMOS33 } [get_ports { xbarTimingSel[1] }]

## TES Delatch
set_property -dict { PACKAGE_PIN U20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[0] }]
set_property -dict { PACKAGE_PIN V20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[1] }]
set_property -dict { PACKAGE_PIN W20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[2] }]
set_property -dict { PACKAGE_PIN Y20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[3] }]
set_property -dict { PACKAGE_PIN AA20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[4] }]
set_property -dict { PACKAGE_PIN AB20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[5] }]
set_property -dict { PACKAGE_PIN AC20 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[6] }]
set_property -dict { PACKAGE_PIN V19 IOSTANDARD LVCMOS33 } [get_ports { tesDelatch[7] }]

## Boot memory
set_property -dict { PACKAGE_PIN W19 IOSTANDARD LVCMOS33 } [get_ports { bootCsL }]
set_property -dict { PACKAGE_PIN Y19 IOSTANDARD LVCMOS33 } [get_ports { bootMosi }]
set_property -dict { PACKAGE_PIN AA19 IOSTANDARD LVCMOS33 } [get_ports { bootMiso }]

## Lemo / RJ45 / misc
set_property -dict { PACKAGE_PIN AB19 IOSTANDARD LVCMOS33 } [get_ports { lemoIn[0] }]
set_property -dict { PACKAGE_PIN AC19 IOSTANDARD LVCMOS33 } [get_ports { lemoIn[1] }]
set_property -dict { PACKAGE_PIN AB18 IOSTANDARD LVCMOS33 } [get_ports { lemoOut[0] }]
set_property -dict { PACKAGE_PIN AC18 IOSTANDARD LVCMOS33 } [get_ports { lemoOut[1] }]

set_property -dict { PACKAGE_PIN AA18 IOSTANDARD LVCMOS33 } [get_ports { conRxGreenLed }]
set_property -dict { PACKAGE_PIN Y18 IOSTANDARD LVCMOS33 } [get_ports { conRxYellowLed }]
set_property -dict { PACKAGE_PIN W18 IOSTANDARD LVCMOS33 } [get_ports { conTxGreenLed }]
set_property -dict { PACKAGE_PIN V18 IOSTANDARD LVCMOS33 } [get_ports { conTxYellowLed }]

## Thermistors
set_property -dict { PACKAGE_PIN U18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[0] }]
set_property -dict { PACKAGE_PIN T18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[0] }]
set_property -dict { PACKAGE_PIN R18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[1] }]
set_property -dict { PACKAGE_PIN P18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[1] }]
set_property -dict { PACKAGE_PIN N18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[2] }]
set_property -dict { PACKAGE_PIN M18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[2] }]
set_property -dict { PACKAGE_PIN L18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[3] }]
set_property -dict { PACKAGE_PIN K18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[3] }]
set_property -dict { PACKAGE_PIN J18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[4] }]
set_property -dict { PACKAGE_PIN H18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[4] }]
set_property -dict { PACKAGE_PIN G18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorP[5] }]
set_property -dict { PACKAGE_PIN F18 IOSTANDARD LVCMOS33 } [get_ports { localThermistorN[5] }]

set_property -dict { PACKAGE_PIN V17 IOSTANDARD LVCMOS33 } [get_ports { feThermistorP[0] }]
set_property -dict { PACKAGE_PIN U17 IOSTANDARD LVCMOS33 } [get_ports { feThermistorP[1] }]
set_property -dict { PACKAGE_PIN T17 IOSTANDARD LVCMOS33 } [get_ports { feThermistorN[0] }]
set_property -dict { PACKAGE_PIN R17 IOSTANDARD LVCMOS33 } [get_ports { feThermistorN[1] }]

## FE VR Sync
set_property -dict { PACKAGE_PIN P17 IOSTANDARD LVCMOS33 } [get_ports { fePwrSyncA }]
set_property -dict { PACKAGE_PIN W17 IOSTANDARD LVCMOS33 } [get_ports { fePwrSyncB }]

##############################################################################
## Clock Groups
##############################################################################
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk] \
    -group [get_clocks -include_generated_clocks adcDClk0] \
    -group [get_clocks -include_generated_clocks adcDClk1]

##############################################################################
## Bitstream Configuration
##############################################################################
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]
set_property CONFIG_VOLTAGE 1.8 [current_design]
set_property BITSTREAM.CONFIG.CONFIGFALLBACK ENABLE [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
