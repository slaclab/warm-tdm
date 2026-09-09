# VCS UCLI script to dump FSDB for Vivado power estimation
#
# Usage (requires simv linked with Verdi, which this build already is):
#   ./simv_debug -ucli -do dump_vcd.do
#
# This dumps switching activity for the ColumnFpgaBoard instance only.
#
# After running, convert FSDB to VCD:
#   fsdb2vcd GroupTb_column.fsdb -o GroupTb_column.vcd

# Use FSDB (Verdi native format - works without -debug_access on compile)
fsdbDumpfile "GroupTb_column.fsdb"
fsdbDumpvars 0 /GROUPTB/GEN_COL_BOARDS(0)/U_COLUMNFPGABOARDSIM/U_COLUMNFPGABOARD/U_COLUMNFPGABOARD_1

# Run for 3ms of steady-state activity (reset releases at ~6us)
run 3ms
