##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

## Primary clocks (from ports)
create_clock -name timingRxClk -period 8.000 [get_ports {timingRxClkP}]
create_clock -name gtRefClk0 -period 4.000 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 6.400 [get_ports {gtRefClk1P}]

## Generated clocks - use wildcards to survive hierarchy changes
create_generated_clock -name fabRefClk0 [get_pins -hier -filter {NAME =~ */U_ClockDist_1/*/ODIV2}]

create_generated_clock -name axilClk [get_pins -hier -filter {NAME =~ */U_PgpEthCore_1/*/U_Phy/*/CLKOUT0}]
create_generated_clock -name pgpClk  [get_pins -hier -filter {NAME =~ */U_PgpEthCore_1/*/U_Phy/*/CLKOUT1}]

create_generated_clock -name idelayClk [get_pins -hier -filter {NAME =~ */U_Timing_1/*MMCM*/*/CLKOUT0}]

create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingTx_1/*/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingTx_1/*/CLKOUT1}]

create_generated_clock -name timingRxBitClk  [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingRx_1/*/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ */U_Timing_1/U_TimingRx_1/*/CLKOUT1}]

## Clock groups - asynchronous domains
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks pgpClk]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk]
