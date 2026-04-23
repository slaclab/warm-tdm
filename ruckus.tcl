##############################################################################
## Repo-local GHDL import surface for Warm TDM cocotb regressions.
##############################################################################

# Load the GHDL-capable ruckus procedures.
source $::env(RUCKUS_PROC_TCL)

# Reuse the checked-out SURF tree for the common SLAC libraries.
loadRuckusTcl "$::DIR_PATH/firmware/submodules/surf"

# Load the simulator-friendly Warm TDM RTL directly. Keep this import surface
# narrow and avoid Vivado-specific IP handling so `make import` stays usable
# for the cocotb/GHDL flow.
loadSource -lib warm_tdm -dir "$::DIR_PATH/firmware/common/warm_tdm/rtl"
