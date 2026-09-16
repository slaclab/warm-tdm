# Warm TDM; subject to LICENSE.txt in the repository root.
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl
loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm
# The common ruckus loads the real Int2Fp/Fp2Int/FpMac XCIs. Never load
# tests/common/vhdl/FpPidModels.vhd in this vendor qualification target.
loadSource -lib warm_tdm -sim_only -fileType "VHDL 2008" \
   -path $::env(TOP_DIR)/common/warm_tdm/wrappers/AdcDspFpCocotbWrapper.vhd
loadSource -lib xil_defaultlib -sim_only -fileType "VHDL 2008" -dir "$::DIR_PATH/tb"
set_property top {AdcDspFp} [get_filesets sources_1]
set_property top {AdcDspFpTb} [get_filesets sim_1]
set_property top_lib xil_defaultlib [get_filesets sim_1]
