##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

# Integer (AdcDsp) PID datapath.
set useFloatPid false
source $::env(PROJ_DIR)/../common/ColumnFpgaBoard3251G.tcl
