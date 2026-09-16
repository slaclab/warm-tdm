##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the 
## top-level directory of this distribution and at: 
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
## No part of 'warm-tdm', including this file, 
## may be copied, modified, propagated, or distributed except according to 
## the terms contained in the LICENSE.txt file.
##############################################################################
# Load RUCKUS environment and library
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl

# SURF
loadRuckusTcl $::env(TOP_DIR)/submodules/surf

# Warm TDM Common
# (board top entities ColumnFpgaBoard/RowFpgaBoard and the Column testbench now
#  live in common/warm_tdm/{rtl,sim} and are loaded by the line below)
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

# Load target's source code and constraints
loadSource -lib warm_tdm -sim_only -dir $::env(PROJ_DIR)/tb

# Set the top level synth_1 and sim_1
set_property top {ColumnFpgaBoard}       [get_filesets {sources_1}]
set_property top {GroupTb} [get_filesets {sim_1}]

# Select the column-board PID datapath for the GroupTb top-level. Defaults to the
# floating-point AdcDspFp (matching the entity default); set USE_FLOAT_PID=0
# (or =false) in the environment to elaborate the integer AdcDsp path instead,
# e.g. `USE_FLOAT_PID=0 make vcs`.
set useFloatPid "true"
if { [info exists ::env(USE_FLOAT_PID)] } {
   set req [string tolower $::env(USE_FLOAT_PID)]
   if { $req eq "0" || $req eq "false" || $req eq "no" } {
      set useFloatPid "false"
   }
}
set_property generic "[get_property generic [get_filesets {sim_1}]] USE_FLOAT_PID_G=$useFloatPid" [get_filesets {sim_1}]
puts "GroupTb: USE_FLOAT_PID_G=$useFloatPid"

# Per-device wafer variation seed. Defaults to the entity default (nonzero, so
# channels differ). Set VARIATION_SEED in the environment to override -- notably
# VARIATION_SEED=0 makes every device identical, which matches the single
# no-variation cosim tune point (SetCosimTunePoints) so the servo can lock.
if { [info exists ::env(VARIATION_SEED)] } {
   set variationSeed $::env(VARIATION_SEED)
   set_property generic "[get_property generic [get_filesets {sim_1}]] VARIATION_SEED_G=$variationSeed" [get_filesets {sim_1}]
   puts "GroupTb: VARIATION_SEED_G=$variationSeed"
}

# TES-bias -> SQ1-input coupling scale (wafer model). Defaults to 1.0 (nominal).
# The synthetic TES-bias amp is weakly coupled, so set TES_CURRENT_SCALE to a
# large value (e.g. 1000) to let a modest TesBias ramp shift the SQ1 flux by
# several Phi0 and exercise the servo flux-jump handling in cosim. Test aid only.
if { [info exists ::env(TES_CURRENT_SCALE)] } {
   set tesCurrentScale $::env(TES_CURRENT_SCALE)
   set_property generic "[get_property generic [get_filesets {sim_1}]] TES_CURRENT_SCALE_G=$tesCurrentScale" [get_filesets {sim_1}]
   puts "GroupTb: TES_CURRENT_SCALE_G=$tesCurrentScale"
}
