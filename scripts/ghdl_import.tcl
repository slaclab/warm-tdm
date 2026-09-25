#!/usr/bin/env tclsh
##############################################################################
## Repo-local wrapper around the ruckus GHDL import flow.
##############################################################################

source $::env(RUCKUS_PROC_TCL)

set ::DIR_PATH ""

if { [file exists $::env(OUT_DIR)] } {
   file delete -force -- $::env(OUT_DIR)
}
file mkdir $::env(OUT_DIR)

# Keep the import flow sandbox-friendly. The upstream ruckus loader shells out
# through `exec` to create `BuildInfoPkg.vhd`, but the current phase-1 cocotb
# benches do not consume that package.
loadRuckusTcl $::env(PROJ_DIR)
