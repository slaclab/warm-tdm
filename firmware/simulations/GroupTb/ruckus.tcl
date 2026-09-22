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
set useFloatPid "false"
if { [info exists ::env(USE_FLOAT_PID)] } {
   set req [string tolower $::env(USE_FLOAT_PID)]
   if { $req eq "0" || $req eq "false" || $req eq "no" } {
      set useFloatPid "false"
   }
}
set_property generic "[get_property generic [get_filesets {sim_1}]] USE_FLOAT_PID_G=$useFloatPid" [get_filesets {sim_1}]
puts "GroupTb: USE_FLOAT_PID_G=$useFloatPid"

# Select the Ethernet clock and simulated payload bandwidth together. Keep the
# historical 10G column coordinator default; reject typos instead of silently
# running a bandwidth test with the wrong configuration.
set eth10g "true"
if { [info exists ::env(ETH_10G)] } {
   switch -- [string tolower $::env(ETH_10G)] {
      0 - false - no { set eth10g "false" }
      1 - true - yes { set eth10g "true" }
      default { error "ETH_10G must be 0/1, false/true, or no/yes" }
   }
}
set_property generic "[get_property generic [get_filesets {sim_1}]] ETH_10G_G=$eth10g" [get_filesets {sim_1}]
puts "GroupTb: ETH_10G_G=$eth10g (shared Ethernet payload pacing per direction)"

# Comms mode: fully simulate the board-to-board PGP GTX ring vs. the historical
# direct-SRP bypass. Keep ring mode as the checked-in default (matches real
# hardware routing); reject typos instead of silently running the wrong mode.
# The software side (warmTdmServer.py --simPgpRing) MUST be set to match.
set simPgpRing "false"
if { [info exists ::env(SIM_PGP_RING)] } {
   switch -- [string tolower $::env(SIM_PGP_RING)] {
      0 - false - no { set simPgpRing "false" }
      1 - true - yes { set simPgpRing "true" }
      default { error "SIM_PGP_RING must be 0/1, false/true, or no/yes" }
   }
}
set_property generic "[get_property generic [get_filesets {sim_1}]] SIM_PGP_GT_G=$simPgpRing" [get_filesets {sim_1}]
puts "GroupTb: SIM_PGP_GT_G=$simPgpRing (true=simulate PGP GTX ring, false=direct-SRP bypass)"

# Per-device wafer variation seed. Defaults to 0 (no variation: every device
# identical), which matches the single no-variation cosim tune point
# (SetCosimTunePoints) so the servo can lock. Set VARIATION_SEED in the
# environment to a nonzero value to spread tunings channel-to-channel.
set variationSeed "0"
if { [info exists ::env(VARIATION_SEED)] } {
   set variationSeed $::env(VARIATION_SEED)
}
set_property generic "[get_property generic [get_filesets {sim_1}]] VARIATION_SEED_G=$variationSeed" [get_filesets {sim_1}]
puts "GroupTb: VARIATION_SEED_G=$variationSeed"

# TES-bias -> SQ1-input coupling scale (wafer model). Defaults to 1.0 (nominal).
# After the wafer recalibration the coupling is ~1 Phi0 per 10 uA of TES current,
# so the default TES flux ramp already sweeps several Phi0 and exercises the servo
# flux-jump handling without a scale-up -- this is a vestigial test aid, left at
# 1.0 everywhere. Set TES_CURRENT_SCALE only if you deliberately want to amplify
# the coupling beyond the recalibrated physical value.
if { [info exists ::env(TES_CURRENT_SCALE)] } {
   set tesCurrentScale $::env(TES_CURRENT_SCALE)
   set_property generic "[get_property generic [get_filesets {sim_1}]] TES_CURRENT_SCALE_G=$tesCurrentScale" [get_filesets {sim_1}]
   puts "GroupTb: TES_CURRENT_SCALE_G=$tesCurrentScale"
}
