# Historical whole-path stimulus regression, STAGE B (compare).
#
# Replays the shared scripted raw-ADC + timing stimulus into the CURRENT
# post-split datapath (AdcAccumulator -> AdcDsp, wired as in DataPath.vhd) and
# checks its mAxil SQ1-FB-DAC write transactions against the frozen pre-split
# golden plus explicit changes required by retained full-precision feedback.
# The first visit to each row and overflow rails still match the old golden.
# Later visits use saved feedback rather than adopting the stimulus's forced
# per-visit DAC changes. The old golden is preserved, never regenerated from
# the modified RTL. See test_AdcDsp_fractional.py for actual-write feedback tests.
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
async def compare_historical_stimulus_with_retained_feedback(dut):
    golden = read_golden()
    driver = BitExactDriver(dut)
    writes = await driver.run(STIMULUS)

    # Independent exact-rational calculation of the six later, non-rail
    # commands: start each row at its FIRST applied DAC, then retain
    # F_next = F + p*E + i*S_old. Gains are raw Q1.23 values from STIMULUS.
    # For example, row 0 starts at -292; its first two corrections sum to
    # 973208925/1048576, giving F=667024733/1048576 -> q=636 -> DAC=7555.
    expected = golden[:3] + [
        (0, 7555), (1, 9648), (2, 9266),
        (0, 7049), (1, 9985), (2, 9097),
    ] + golden[9:]
    assert writes == expected, (
        "current AdcAccumulator+AdcDsp writes differ from the retained-feedback "
        "expectations for the historical stimulus.\n"
        f"  expected ({len(expected)}): {expected}\n"
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
