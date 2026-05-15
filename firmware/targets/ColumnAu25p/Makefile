export GIT_BYPASS = 1

# Define target part
export PRJ_PART = xcau25p-sfvb784-1-e

# Using a non-standard target name
export TARGET = ColumnAu25p

target: bit

export TOP_DIR = $(abspath $(PWD)/../..)
export PRJ_VERSION = 0x00000001

include $(TOP_DIR)/submodules/ruckus/system_vivado.mk

###############################################################
#### Power Strategy Exploration ###############################
###############################################################
.PHONY : power_explore
power_explore : $(SOURCE_DEPEND)
	$(call ACTION_HEADER,"Power Strategy Exploration")
	@cd $(OUT_DIR); vivado -mode batch -source $(PROJ_DIR)/vivado/power_explore.tcl
