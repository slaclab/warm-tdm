##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file, may be
## copied, modified, propagated, or distributed except according to the terms
## contained in the LICENSE.txt file.
##############################################################################
## Post-route power estimation with realistic switching activity
##############################################################################

source -quiet $::env(RUCKUS_DIR)/vivado/env_var.tcl

puts "==============================================="
puts "Running enhanced power estimation..."
puts "==============================================="

# Reset all switching activity to start clean
reset_switching_activity -all

##############################################################################
# Clock switching activity
# signal_rate for clocks = 2 * frequency_in_MHz (transitions per microsecond)
# static_probability = 0.5 (50% duty cycle)
##############################################################################

# Primary input clocks
# gtRefClk0: 250 MHz
set_switching_activity -static_probability 0.5 -signal_rate 500 [get_clocks gtRefClk0]
# gtRefClk1: 156.25 MHz
set_switching_activity -static_probability 0.5 -signal_rate 312.5 [get_clocks gtRefClk1]
# timingRxClk: 125 MHz
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_clocks timingRxClk]
# adcDClk0/1: 500 MHz (DDR bit clock)
set_switching_activity -static_probability 0.5 -signal_rate 1000 [get_clocks adcDClk0]
set_switching_activity -static_probability 0.5 -signal_rate 1000 [get_clocks adcDClk1]

# Generated clocks from MMCMs/PLLs
# fabRefClk0: 125 MHz (gtRefClk0 / 2)
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_clocks fabRefClk0]
# axilClk: 125 MHz
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_clocks axilClk]
# pgpClk: 62.5 MHz
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_clocks pgpClk]
# ethClk: 125 MHz
catch {set_switching_activity -static_probability 0.5 -signal_rate 250 [get_clocks ethClk]}
# ethClkDiv2: 62.5 MHz
catch {set_switching_activity -static_probability 0.5 -signal_rate 125 [get_clocks ethClkDiv2]}
# ethClk156: 156.25 MHz (only in 10G build)
catch {set_switching_activity -static_probability 0.5 -signal_rate 312.5 [get_clocks ethClk156]}
# idelayClk: 200 MHz
set_switching_activity -static_probability 0.5 -signal_rate 400 [get_clocks idelayClk]
# timingTxBitClk: 625 MHz
set_switching_activity -static_probability 0.5 -signal_rate 1250 [get_clocks timingTxBitClk]
# timingTxWordClk: 125 MHz
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_clocks timingTxWordClk]
# timingRxBitClk: 625 MHz
set_switching_activity -static_probability 0.5 -signal_rate 1250 [get_clocks timingRxBitClk]
# timingRxWordClk: 125 MHz
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_clocks timingRxWordClk]

# Low-frequency utility clocks
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.03 [get_clocks dnaDivClk]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.03 [get_clocks icapClk]}

##############################################################################
# I/O port switching activity
# For differential pairs, only set the P side (Vivado Power 33-294)
##############################################################################

# ADC serial data inputs (16 LVDS lanes)
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

##############################################################################
# Vivado's vectorless propagation derives internal toggle rates from the
# clock and I/O annotations above.
##############################################################################

##############################################################################
# Read SAIF file if available (from VCD-based flow)
# This overrides vectorless estimates for any nodes covered by simulation
##############################################################################
set saif_file "${IMPL_DIR}/${PROJECT}_power.saif"
if {[file exists $saif_file]} {
    puts "Reading SAIF file: $saif_file"
    read_saif $saif_file
    puts "SAIF file loaded successfully"
} else {
    puts "No SAIF file found at $saif_file"
    puts "Using vectorless activity estimates only"
}

##############################################################################
# Generate enhanced power report
##############################################################################
report_power -file ${IMPL_DIR}/${PROJECT}_power_annotated.rpt \
    -rpx ${IMPL_DIR}/${PROJECT}_power_annotated.rpx \
    -advisory

puts "==============================================="
puts "Enhanced power report written to:"
puts "  ${IMPL_DIR}/${PROJECT}_power_annotated.rpt"
puts "==============================================="
