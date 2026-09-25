#-----------------------------------------------------------------------------
# Warm-TDM repo-local GHDL import surface for cocotb regressions.
#-----------------------------------------------------------------------------

# Default to the source import step because the cocotb flow consumes the
# generated `build/SRC_VHDL/` tree directly.
target: rtl_import

ifndef PROJECT
export PROJECT = warm_tdm_regress
endif

export TOP_DIR  = $(abspath $(PWD))
export PROJ_DIR = $(abspath $(PWD))
export OUT_DIR  = $(PROJ_DIR)/build

ifeq ($(wildcard $(TOP_DIR)/ruckus/system_ghdl.mk),$(TOP_DIR)/ruckus/system_ghdl.mk)
export RUCKUS_DIR = $(TOP_DIR)/ruckus
else ifeq ($(wildcard $(TOP_DIR)/firmware/submodules/ruckus/system_ghdl.mk),$(TOP_DIR)/firmware/submodules/ruckus/system_ghdl.mk)
export RUCKUS_DIR = $(TOP_DIR)/firmware/submodules/ruckus
else ifeq ($(wildcard $(HOME)/ruckus/system_ghdl.mk),$(HOME)/ruckus/system_ghdl.mk)
export RUCKUS_DIR = $(HOME)/ruckus
else
$(error Could not find system_ghdl.mk in ./ruckus, firmware/submodules/ruckus, or ~/ruckus)
endif

ifndef GHDL_CMD
export GHDL_CMD = ghdl
endif

export GHDL_BASE_FLAGS = \
	--workdir=$(OUT_DIR) \
	--std=08 \
	--ieee=synopsys \
	-frelaxed-rules \
	-fexplicit

export GHDL_OPTIONAL_WARNINGS = elaboration hide specs shared
export GHDL_SUPPORTED_WARNING_NAMES := $(shell $(GHDL_CMD) --help-warnings 2>/dev/null | awk '/^[[:space:]]*-W/ {name=$$1; sub(/^-W/, "", name); sub(/\*$$/, "", name); if (name != "all") print name}')
export GHDL_WARNING_FLAGS := $(strip $(foreach warn,$(GHDL_OPTIONAL_WARNINGS),$(if $(filter $(warn),$(GHDL_SUPPORTED_WARNING_NAMES)),-Wno-$(warn))))
export GHDLFLAGS = $(GHDL_BASE_FLAGS) $(GHDL_WARNING_FLAGS)

# External `~/ruckus` is a supported local fallback for the regression flow,
# so skip repo-specific submodule lock enforcement in this Makefile.
export OVERRIDE_SUBMODULE_LOCKS = 1

include $(RUCKUS_DIR)/system_ghdl.mk

# Route all downstream `source $::env(RUCKUS_PROC_TCL)` calls through a
# repo-local wrapper so the SURF import tree can run inside the local sandbox.
override export RUCKUS_PROC_TCL = $(TOP_DIR)/scripts/ghdl_proc_override.tcl

# The upstream `ghdl/import.tcl` path uses `exec rm -rf`, which triggers a
# macOS sandbox ownership error in this environment. Keep the upstream target
# untouched and add a repo-local import target that uses Tcl's file APIs.
.PHONY : rtl_import
rtl_import :
	$(call ACTION_HEADER,"GHDL: Import (ghdl -i)")
	@env RUCKUS_PROC_TCL=$(TOP_DIR)/scripts/ghdl_proc_override.tcl tclsh scripts/ghdl_import.tcl
