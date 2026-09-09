set impl_dir "/u1/bareese/build/ColumnFpgaBoard325Coordinator/ColumnFpgaBoard325Coordinator_project.runs/impl_1"
set dcp_file "${impl_dir}/ColumnFpgaBoard_routed.dcp"
set saif_file "/sdf/home/b/bareese/projects/warm-tdm/firmware/build/GroupTb/GroupTb_project.sim/sim_1/behav/GroupTb_column.saif"

puts "Opening checkpoint..."
open_checkpoint $dcp_file

puts "Reading SAIF file..."
read_saif $saif_file -strip_path {GROUPTB/GEN_COL_BOARDS(0).U_COLUMNFPGABOARDSIM/U_COLUMNFPGABOARD/U_COLUMNFPGABOARD_1}

puts "Generating power report..."
report_power -file ${impl_dir}/ColumnFpgaBoard325Coordinator_power_saif.rpt -advisory

puts "Done. Report: ${impl_dir}/ColumnFpgaBoard325Coordinator_power_saif.rpt"
close_design
exit 0
