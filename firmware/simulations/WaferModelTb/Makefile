GHDL ?= ghdl
GHDL_FLAGS := --std=08
BUILD_DIR := $(abspath ../../build/WaferModelTb/ghdl)
SIM_DIR := ../../common/warm_tdm/sim
SURF_RTL_DIR := ../../submodules/surf/base/general/rtl

SURF_SOURCES := \
	$(SURF_RTL_DIR)/StdRtlPkg.vhd

MODEL_SOURCES := \
	$(SIM_DIR)/SimPkg.vhd \
	$(SIM_DIR)/WaferSimPkg.vhd \
	$(SIM_DIR)/SquidModel.vhd \
	$(SIM_DIR)/SsaModel.vhd \
	$(SIM_DIR)/Sq1Model.vhd \
	$(SIM_DIR)/RowFasModel.vhd \
	$(SIM_DIR)/ChipFasModel.vhd \
	$(SIM_DIR)/TdmMuxColumnModel.vhd \
	$(SIM_DIR)/DetectorModuleSim.vhd \
	$(SIM_DIR)/GroupDetectorHarnessSim.vhd \
	$(SIM_DIR)/WaferSim.vhd

.PHONY: test analyze clean

test: analyze
	$(GHDL) -e $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) -o $(BUILD_DIR)/wafermodeltb WaferModelTb
	$(BUILD_DIR)/wafermodeltb --assert-level=error
	$(GHDL) -e $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) -o $(BUILD_DIR)/wafercompatibilitytb WaferCompatibilityTb
	$(BUILD_DIR)/wafercompatibilitytb --assert-level=error
	$(GHDL) -e $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) -o $(BUILD_DIR)/detectorscaletb DetectorScaleTb
	$(BUILD_DIR)/detectorscaletb --assert-level=error
	$(GHDL) -e $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) -o $(BUILD_DIR)/detectorprofiletb DetectorProfileTb
	$(BUILD_DIR)/detectorprofiletb --assert-level=error
	$(GHDL) -e $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) -o $(BUILD_DIR)/groupdetectorharnesstb GroupDetectorHarnessTb
	$(BUILD_DIR)/groupdetectorharnesstb --assert-level=error

analyze:
	mkdir -p $(BUILD_DIR)
	$(GHDL) -a $(GHDL_FLAGS) --work=surf --workdir=$(BUILD_DIR) $(SURF_SOURCES)
	$(GHDL) -a $(GHDL_FLAGS) --work=warm_tdm --workdir=$(BUILD_DIR) -P$(BUILD_DIR) $(MODEL_SOURCES)
	$(GHDL) -a $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) tb/WaferModelTb.vhd
	$(GHDL) -a $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) tb/WaferCompatibilityTb.vhd
	$(GHDL) -a $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) tb/DetectorScaleTb.vhd
	$(GHDL) -a $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) tb/DetectorProfileTb.vhd
	$(GHDL) -a $(GHDL_FLAGS) --workdir=$(BUILD_DIR) -P$(BUILD_DIR) tb/GroupDetectorHarnessTb.vhd

clean:
	rm -rf $(BUILD_DIR)
