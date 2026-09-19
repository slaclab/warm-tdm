# Bit-exact re-qualification, STAGE A (capture).
#
# Drives the shared scripted raw-ADC + timing stimulus into the PRE-SPLIT AdcDsp
# (snapshot at golden_refs/presplit_rtl/, commit 5645f7e) and records its mAxil
# SQ1-FB-DAC write transactions as the model-free golden reference. The compare
# bench (test_AdcDsp_bitexact_compare.py) replays the identical stimulus into the
# current AdcAccumulator+AdcDsp and asserts the same write sequence.
#
# The DUT here is built from the pre-split snapshot, NOT the current RTL: the
# warm_tdm library is supplied entirely via extra_vhdl_sources (snapshot packages
# + AdcDsp + capture wrapper), and the surf import allowlist is used only for
# surf. This keeps the old warm_tdm out of the current-RTL compare run's library.

from __future__ import annotations

from pathlib import Path

import cocotb
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp._pid_bitexact import BitExactDriver, STIMULUS, write_golden


SNAPSHOT_DIR = Path("tests/warm_tdm/adc_dsp/golden_refs/presplit_rtl")
UNISIM_STUB_PATH = "tests/common/vhdl/unisim_vcomponents.vhd"

# Pre-split snapshot sources, compiled into the warm_tdm library. FrameHeaderPkg
# did not exist at the reference commit; the old AdcDsp needs only these three
# packages plus (current) surf.
SNAPSHOT_WARM_TDM_SOURCES = [
    str(SNAPSHOT_DIR / "FixedPkg.vhd"),
    str(SNAPSHOT_DIR / "WarmTdmPkg.vhd"),
    str(SNAPSHOT_DIR / "TimingPkg.vhd"),
    str(SNAPSHOT_DIR / "AdcDsp.vhd"),
    str(SNAPSHOT_DIR / "AdcDspPresplitCaptureWrapper.vhd"),
]

# surf import allowlist (same building blocks as the current AdcDsp bench).
IMPORT_LIBRARY_ALLOWLIST = {"surf"}
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
}
IMPORT_FILE_EXCLUDES = ("*Tb*.vhd",)


@cocotb.test()
async def capture_presplit_golden(dut):
    driver = BitExactDriver(dut)
    writes = await driver.run(STIMULUS)

    # The stimulus enables three rows and visits each three times, so every
    # enabled visit must produce a mAxil write; anything less means the golden
    # would under-constrain the compare.
    assert len(writes) == len(STIMULUS.visits), (
        f"expected one mAxil DAC write per row visit "
        f"({len(STIMULUS.visits)}), captured {len(writes)}: {writes}"
    )
    write_golden(writes)


@pytest.mark.parametrize("parameters", [pytest.param({}, id="presplit_capture")])
def test_AdcDsp_bitexact_capture(parameters):
    run_warm_tdm_vhdl_test(
        test_file=__file__,
        toplevel="warm_tdm.adcdsppresplitcapturewrapper",
        parameters=parameters,
        extra_env=parameters,
        extra_vhdl_sources={
            "unisim": [UNISIM_STUB_PATH],
            "warm_tdm": SNAPSHOT_WARM_TDM_SOURCES,
        },
        sim_build_key="adcdsp_bitexact_capture_v1",
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
    )
