# Bit-exact re-qualification, STAGE B (compare).
#
# Replays the shared scripted raw-ADC + timing stimulus into the CURRENT
# post-split datapath (AdcAccumulator -> AdcDsp, wired as in DataPath.vhd) and
# asserts its mAxil SQ1-FB-DAC write transactions match, bit-for-bit, the golden
# captured from the pre-split AdcDsp (test_AdcDsp_bitexact_capture.py). A match
# proves the accumulator split preserved the integer PID behavior end-to-end.
#
# This is the model-free Tier-1 check the closed-loop cosim cannot provide.

from __future__ import annotations

import cocotb
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp._pid_bitexact import BitExactDriver, STIMULUS, read_golden


WRAPPER_PATH = "firmware/common/warm_tdm/wrappers/AdcDspAccumCompareWrapper.vhd"
UNISIM_STUB_PATH = "tests/common/vhdl/unisim_vcomponents.vhd"

IMPORT_LIBRARY_ALLOWLIST = {"surf", "warm_tdm"}
IMPORT_FILE_ALLOWLISTS = {
    "surf": {
        "ArbiterPkg.vhd",
        "AxiLiteCrossbar.vhd",
        "AxiLiteMaster.vhd",
        "AxiLitePkg.vhd",
        "AxiPkg.vhd",
        "AxiDualPortRam.vhd",
        "AxiStreamFifoV2.vhd",
        "AxiStreamGearbox.vhd",
        "AxiStreamPipeline.vhd",
        "AxiStreamPkg.vhd",
        "AxiStreamResize.vhd",
        "DualPortRam.vhd",
        "Fifo.vhd",
        "FifoAlteraMfDummy.vhd",
        "FifoAsync.vhd",
        "FifoCascade.vhd",
        "FifoOutputPipeline.vhd",
        "FifoRdFsm.vhd",
        "FifoSync.vhd",
        "FifoWrFsm.vhd",
        "FifoXpmDummy.vhd",
        "LutRam.vhd",
        "RstSync.vhd",
        "SimpleDualPortRam.vhd",
        "SimpleDualPortRamInferred.vhd",
        "SlaveAxiLiteIpIntegrator.vhd",
        "SsiPkg.vhd",
        "StdRtlPkg.vhd",
        "Synchronizer.vhd",
        "SynchronizerFifo.vhd",
        "SynchronizerVector.vhd",
        "TextUtilPkg.vhd",
        "TrueDualPortRam.vhd",
        "TrueDualPortRamInferred.vhd",
        "TrueDualPortRamXpmAlteraMfDummy.vhd",
        "TrueDualPortRamXpmDummy.vhd",
    },
    "warm_tdm": {
        "AdcAccumulator.vhd",
        "AdcDsp.vhd",
        "FixedPkg.vhd",
        "FrameHeaderPkg.vhd",
        "TimingPkg.vhd",
        "WarmTdmPkg.vhd",
    },
}
IMPORT_FILE_EXCLUDES = ("*Tb*.vhd",)


@cocotb.test()
async def compare_to_presplit_golden(dut):
    golden = read_golden()
    driver = BitExactDriver(dut)
    writes = await driver.run(STIMULUS)

    assert writes == golden, (
        "current AdcAccumulator+AdcDsp mAxil SQ1-FB-DAC writes differ from the "
        "pre-split golden (accumulator split is NOT bit-exact).\n"
        f"  golden ({len(golden)}): {golden}\n"
        f"  actual ({len(writes)}): {writes}"
    )


@pytest.mark.parametrize("parameters", [pytest.param({}, id="accum_compare")])
def test_AdcDsp_bitexact_compare(parameters):
    run_warm_tdm_vhdl_test(
        test_file=__file__,
        toplevel="warm_tdm.adcdspaccumcomparewrapper",
        parameters=parameters,
        extra_env=parameters,
        extra_vhdl_sources={
            "unisim": [UNISIM_STUB_PATH],
            "warm_tdm": [WRAPPER_PATH],
        },
        sim_build_key="adcdsp_bitexact_compare_v1",
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
    )
