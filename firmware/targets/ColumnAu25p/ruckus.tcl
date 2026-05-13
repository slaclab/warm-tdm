source $::env(RUCKUS_DIR)/vivado_proc.tcl

loadRuckusTcl $::env(TOP_DIR)/submodules/surf

loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm

loadSource -lib warm_tdm -dir "$::DIR_PATH/rtl" -fileType "VHDL 2008"
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2_10g.xdc
loadConstraints -dir "$::DIR_PATH/xdc"

set_property top {ColumnAu25p} [get_filesets {sources_1}]
set_property generic "[get_property generic [current_fileset]] RING_ADDR_0_G=true ETH_10G_G=true GEN_ADC_FILTER_G=false" [current_fileset]
