
# Define target output
target: prom

# Must use VHDL 2008 for IEEE floating support
export SIM_CARGS_VHDL = -nc -l +v2k -xlrm -vhdl08

# Define target part
export PRJ_PART = XC7K160TFFG676-1

export RUCKUS_DIR = $(abspath $(PWD)/../../submodules/ruckus)

#export REMOVE_UNUSED_CODE = 1

export PRJ_VERSION = 0x00000000

export GIT_BYPASS = 1

export GZIP_BUILD_IMAGE = 1

# Use top level makefile
include $(RUCKUS_DIR)/system_vivado.mk



