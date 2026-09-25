#!/usr/bin/env tclsh
##############################################################################
## Repo-local wrapper around the ruckus GHDL proc layer.
##############################################################################

source $::env(RUCKUS_DIR)/ghdl/proc.tcl

# Replace the upstream shell-based source staging with Tcl-native filesystem
# calls so local macOS sandboxing does not block `make rtl_import`.
proc UpdateSrcFileLists {filepath lib} {
   set path [file normalize ${filepath}]
   set fileExt [file extension ${path}]
   set fbasename [file tail ${path}]

   if { ${fileExt} eq {.vhd} || ${fileExt} eq {.vhdl} } {
      set SRC_TYPE "SRC_VHDL"
   } elseif { ${fileExt} eq {.v} || ${fileExt} eq {.vh} } {
      set SRC_TYPE "SRC_VERILOG"
   } else {
      set SRC_TYPE "SRC_SVERILOG"
   }

   set dstDir "$::env(OUT_DIR)/${SRC_TYPE}/${lib}"
   file mkdir $dstDir

   set dstPath "${dstDir}/${fbasename}"
   if { [file exists $dstPath] } {
      file delete -force -- $dstPath
   }
   file link -symbolic $dstPath $path
}
