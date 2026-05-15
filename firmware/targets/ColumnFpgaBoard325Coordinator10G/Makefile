
# Define target output
target: prom

# Define target part
export PRJ_PART = XC7K325TFFG676-2

export RUCKUS_DIR = $(abspath $(PWD)/../../submodules/ruckus)

#export REMOVE_UNUSED_CODE = 1

export PRJ_VERSION = 0x00000000

export GIT_BYPASS = 1

export GZIP_BUILD_IMAGE = 1

# Use top level makefile
include $(RUCKUS_DIR)/system_vivado.mk

###############################################################
#### Power Strategy Exploration ###############################
###############################################################
.PHONY : power_explore
power_explore : $(SOURCE_DEPEND)
	$(call ACTION_HEADER,"Power Strategy Exploration")
	@cd $(OUT_DIR); vivado -mode batch -source $(PROJ_DIR)/vivado/power_explore.tcl
