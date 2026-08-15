##############################################################################
## Vectorless power activity script for use in an open Vivado GUI session.
## Source this from the Tcl console after opening the routed design:
##   source .../set_power_activity.tcl
##############################################################################

reset_switching_activity -all

# Primary input clocks
set_switching_activity -static_probability 0.5 -signal_rate 500   [get_clocks gtRefClk0]
set_switching_activity -static_probability 0.5 -signal_rate 312.5 [get_clocks gtRefClk1]
set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks timingRxClk]
set_switching_activity -static_probability 0.5 -signal_rate 1000  [get_clocks adcDClk0]
set_switching_activity -static_probability 0.5 -signal_rate 1000  [get_clocks adcDClk1]

# Generated clocks
set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks fabRefClk0]
set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks axilClk]
set_switching_activity -static_probability 0.5 -signal_rate 125   [get_clocks pgpClk]
catch {set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks ethClk]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 125   [get_clocks ethClkDiv2]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 312.5 [get_clocks ethClk156]}
set_switching_activity -static_probability 0.5 -signal_rate 400   [get_clocks idelayClk]
set_switching_activity -static_probability 0.5 -signal_rate 1250  [get_clocks timingTxBitClk]
set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks timingTxWordClk]
set_switching_activity -static_probability 0.5 -signal_rate 1250  [get_clocks timingRxBitClk]
set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks timingRxWordClk]
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.03 [get_clocks dnaDivClk]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.03 [get_clocks icapClk]}

# ADC serial data inputs (P side only for differential)
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_ports {adcChP[*][*]}]
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_ports {adcFClkP[*]}]

# Fast DAC outputs (AD9767 parallel: 14-bit data, clk, wrt, sel, reset)
set_switching_activity -static_probability 0.5 -signal_rate 50 [get_ports {saFbDb[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 50 [get_ports {sq1FbDb[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 50 [get_ports {sq1BiasDb[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {saFbClk[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {saFbWrt[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {saFbSel[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 1  [get_ports {saFbReset[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {sq1FbClk[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {sq1FbWrt[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {sq1FbSel[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 1  [get_ports {sq1FbReset[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {sq1BiasClk[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {sq1BiasWrt[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 8  [get_ports {sq1BiasSel[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 1  [get_ports {sq1BiasReset[*]}]

# TES bias DAC (SPI)
set_switching_activity -static_probability 0.5 -signal_rate 5   [get_ports {tesDacSclk}]
set_switching_activity -static_probability 0.5 -signal_rate 5   [get_ports {tesDacDin}]
set_switching_activity -static_probability 0.1 -signal_rate 1   [get_ports {tesDacCsL[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 0.1 [get_ports {tesDacLdacL}]

# Front-end DAC SPI
set_switching_activity -static_probability 0.5 -signal_rate 5   [get_ports {feDacSclk}]
set_switching_activity -static_probability 0.5 -signal_rate 5   [get_ports {feDacMosi}]
set_switching_activity -static_probability 0.1 -signal_rate 1   [get_ports {feDacSyncB[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 0.1 [get_ports {feDacLdacB[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 0.1 [get_ports {feDacResetB[*]}]

# Boot flash SPI
set_switching_activity -static_probability 0.5 -signal_rate 0.1 [get_ports {bootCsL}]
set_switching_activity -static_probability 0.5 -signal_rate 0.1 [get_ports {bootMosi}]

# Timing interface data
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_ports {timingRxDataP}]
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_ports {timingTxDataP}]
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_ports {timingTxClkP}]

# I2C
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {locScl}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {locSda}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {pwrScl}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {pwrSda}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {sfpScl[*]}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {sfpSda[*]}]}

# Vivado derives internal toggle rates from clock and I/O annotations above.

puts "Switching activity set. Now run: Report > Report Power (or report_power)"
