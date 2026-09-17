##############################################################################
## This file is part of 'Warm TDM'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'Warm TDM', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################

# SFP transceiver serial pins.
#
# These are dedicated GT (MGT) sites, so they are only valid when the Ethernet
# GT actually drives them -- i.e. coordinator builds (RING_ADDR_0_G=true), which
# instantiate PgpEthCore's GEN_ETH. In non-Ethernet builds the NO_ETH branch
# drives sfp0Tx* from fabric logic, and LOC-ing a fabric OBUF onto a GT site
# fails place_design (Vivado 12-1411). Load this only from Ethernet targets,
# alongside WarmTdmCore_1g.xdc / WarmTdmCore_10g.xdc.

set_property PACKAGE_PIN K2 [get_ports {sfp0TxP}]
set_property PACKAGE_PIN K1 [get_ports {sfp0TxN}]
set_property PACKAGE_PIN L4 [get_ports {sfp0RxP}]
set_property PACKAGE_PIN L3 [get_ports {sfp0RxN}]
# set_property PACKAGE_PIN H2 [get_ports {sfp1TxP}]
# set_property PACKAGE_PIN H1 [get_ports {sfp1TxN}]
# set_property PACKAGE_PIN J4 [get_ports {sfp1RxP}]
# set_property PACKAGE_PIN J3 [get_ports {sfp1RxN}]
