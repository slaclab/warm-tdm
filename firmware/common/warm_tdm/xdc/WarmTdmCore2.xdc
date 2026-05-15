##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

## MMCM-derived clocks (master: fabRefClk0 defined in family-specific XDC)
create_generated_clock -name axilClk   [get_pins -hier -filter {NAME =~ *U_PgpCore_1*U_Phy*U_Mmcm/CLKOUT0}]
create_generated_clock -name pgpClk    [get_pins -hier -filter {NAME =~ *U_PgpCore_1*U_Phy*U_Mmcm/CLKOUT1}]
create_generated_clock -name idelayClk [get_pins -hier -filter {NAME =~ *U_MMCM_IDELAY*U_Mmcm/CLKOUT0}]

## Clock groups - asynchronous domains
set_clock_groups -asynchronous \
    -group [get_clocks -include_generated_clocks gtRefClk0] \
    -group [get_clocks -include_generated_clocks gtRefClk1] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks pgpClk] \
    -group [get_clocks gtRefClk0]

set_clock_groups -asynchronous \
    -group [get_clocks fabRefClk0] \
    -group [get_clocks axilClk]

set_clock_groups -asynchronous \
    -group [get_clocks fabRefClk0] \
    -group [get_clocks pgpClk]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks -include_generated_clocks timingRxClk]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk]
