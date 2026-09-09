##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file, may be
## copied, modified, propagated, or distributed except according to the terms
## contained in the LICENSE.txt file.
##############################################################################
## Standalone vectorless power analysis script
##
## Usage:
##   vivado -mode batch -source run_power_analysis.tcl
##
## Runs against the existing routed DCP without rebuilding.
## Output: ColumnFpgaBoard325Coordinator_power_annotated.rpt in impl_1/
##############################################################################

set script_dir [file dirname [file normalize [info script]]]
set target_dir [file dirname $script_dir]
set target_name [file tail $target_dir]
set build_dir [file normalize "${target_dir}/../../build/${target_name}"]
set impl_dir "${build_dir}/${target_name}_project.runs/impl_1"
set dcp_file "${impl_dir}/ColumnFpgaBoard_routed.dcp"

if {![file exists $dcp_file]} {
    puts "ERROR: Routed DCP not found: $dcp_file"
    exit 1
}

puts "Opening routed checkpoint: $dcp_file"
open_checkpoint $dcp_file

puts "==============================================="
puts "Setting switching activity..."
puts "==============================================="

# Reset all switching activity
reset_switching_activity -all

##############################################################################
# Clock switching activity
# signal_rate = 2 * frequency_in_MHz (transitions per us)
##############################################################################

# Primary input clocks
set_switching_activity -static_probability 0.5 -signal_rate 500   [get_clocks gtRefClk0]
set_switching_activity -static_probability 0.5 -signal_rate 312.5 [get_clocks gtRefClk1]
set_switching_activity -static_probability 0.5 -signal_rate 250   [get_clocks timingRxClk]
set_switching_activity -static_probability 0.5 -signal_rate 1000  [get_clocks adcDClk0]
set_switching_activity -static_probability 0.5 -signal_rate 1000  [get_clocks adcDClk1]

# Generated clocks from MMCMs/PLLs
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

# Low-frequency utility clocks
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.03 [get_clocks dnaDivClk]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.03 [get_clocks icapClk]}

##############################################################################
# I/O port switching activity
# signal_rate in MHz (transitions per us)
# For differential pairs, only set the P side per Vivado Power 33-294
##############################################################################

# ADC serial data inputs - toggling at ~half the bit clock rate for random data
# adcChP[0][0..7] and adcChP[1][0..7]: 16 LVDS data lanes
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_ports {adcChP[*][*]}]
# ADC frame clocks
set_switching_activity -static_probability 0.5 -signal_rate 250 [get_ports {adcFClkP[*]}]

# Fast DAC outputs (AD9767 parallel interface)
# saFbDb[13:0], sq1FbDb[13:0], sq1BiasDb[13:0] - 14-bit data buses
# Updated at ~125 MHz / 32 rows = ~3.9 MHz row rate, but data bits toggle ~50%
set_switching_activity -static_probability 0.5 -signal_rate 50 [get_ports {saFbDb[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 50 [get_ports {sq1FbDb[*]}]
set_switching_activity -static_probability 0.5 -signal_rate 50 [get_ports {sq1BiasDb[*]}]
# DAC clock/control (saFbClk, sq1FbClk, sq1BiasClk, *Wrt, *Sel, *Reset)
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

# TES bias DAC (SPI): slow updates
set_switching_activity -static_probability 0.5 -signal_rate 5  [get_ports {tesDacSclk}]
set_switching_activity -static_probability 0.5 -signal_rate 5  [get_ports {tesDacDin}]
set_switching_activity -static_probability 0.1 -signal_rate 1  [get_ports {tesDacCsL[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 0.1 [get_ports {tesDacLdacL}]

# Front-end DAC SPI
set_switching_activity -static_probability 0.5 -signal_rate 5  [get_ports {feDacSclk}]
set_switching_activity -static_probability 0.5 -signal_rate 5  [get_ports {feDacMosi}]
set_switching_activity -static_probability 0.1 -signal_rate 1  [get_ports {feDacSyncB[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 0.1 [get_ports {feDacLdacB[*]}]
set_switching_activity -static_probability 0.1 -signal_rate 0.1 [get_ports {feDacResetB[*]}]

# Boot flash SPI
set_switching_activity -static_probability 0.5 -signal_rate 0.1 [get_ports {bootCsL}]
set_switching_activity -static_probability 0.5 -signal_rate 0.1 [get_ports {bootMosi}]

# Timing interface data (not the clock port - that's handled by clock constraints)
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_ports {timingRxDataP}]
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_ports {timingTxDataP}]
set_switching_activity -static_probability 0.5 -signal_rate 125 [get_ports {timingTxClkP}]

# I2C - very low toggle
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {locScl}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {locSda}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {pwrScl}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {pwrSda}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {sfpScl[*]}]}
catch {set_switching_activity -static_probability 0.5 -signal_rate 0.4 [get_ports {sfpSda[*]}]}

##############################################################################
# Vivado's vectorless propagation engine will derive internal toggle rates
# from the clock and I/O annotations set above.
##############################################################################

##############################################################################
# Generate power report
##############################################################################
set out_file "${impl_dir}/${target_name}_power_annotated.rpt"

puts "==============================================="
puts "Generating power report..."
puts "==============================================="

report_power -file $out_file -advisory

puts "==============================================="
puts "Done. Report written to:"
puts "  $out_file"
puts "==============================================="

close_design
exit 0
