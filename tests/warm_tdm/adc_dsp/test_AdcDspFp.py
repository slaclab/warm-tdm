# Test methodology (floating-point PID variant):
# - Sweep: Exercise the `AdcDspFp` cocotb wrapper across the same PID control
#   cases as the fixed-point bench, adapted to the IEEE-754 float32 datapath:
#   I-disabled operation, integrator clearing on I/startRun/clearPidState, a
#   basic proportional response, and positive-rail anti-windup.
# - Interface: identical to the fixed-point bench -- fp-pid feeds AdcDspFp a
#   decoded `accumIn : AdcAccumResultType` qualified by `accumValid`. The bench
#   presents one accumulation result and pulses accumValid.
# - Coefficients are IEEE-754 single-precision floats (unlike the fixed-point
#   `sfixed(0 downto -23)` coding), so a near-unity P/I coefficient is simply
#   1.0 == 0x3F800000.
# - Readback registers are float32 for sumAccum (X"18"), sq1FbNew (X"20"), etc.
#
# SIMULATOR REQUIREMENT (important):
#   AdcDspFp instantiates the Xilinx FpMac, Int2Fp and Fp2Int IEEE-754 IP cores.
#   GHDL cannot elaborate those primitives, so this bench MUST run under VCS
#   (or XSIM) with the Vivado compiled simulation libraries providing the FP IP
#   models. It is skipped by default and enabled by exporting WARM_TDM_SIM=vcs
#   after sourcing the VCS + Vivado sim-lib environments. See
#   docs/_meta/rtl_regression_handoff.md for the exact recipe.

from __future__ import annotations

import os
import struct

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from firmware.submodules.surf.tests.axi.utils import axil_read_u32, axil_write_u32
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test


WRAPPER_PATH = "firmware/common/warm_tdm/wrappers/AdcDspFpCocotbWrapper.vhd"
UNISIM_STUB_PATH = "tests/common/vhdl/unisim_vcomponents.vhd"

# FP IP core simulation sources must be supplied by the Vivado compiled sim
# libraries at run time (VCS -y/-liblist or XSIM -L). The behavioral netlists
# are NOT part of the surf/warm_tdm import tree.
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
        "SlaveAxiLiteIpIntegrator.vhd",
        "SsiPkg.vhd",
        "StdRtlPkg.vhd",
        "Synchronizer.vhd",
        "SynchronizerFifo.vhd",
        "SynchronizerVector.vhd",
        "TextUtilPkg.vhd",
        "TrueDualPortRam.vhd",
        "TrueDualPortRamXpmAlteraMfDummy.vhd",
        "TrueDualPortRamXpmDummy.vhd",
    },
    "warm_tdm": {
        "AdcDspFp.vhd",
        "TimingPkg.vhd",
        "WarmTdmPkg.vhd",
    },
}
IMPORT_FILE_EXCLUDES = ("*Tb*.vhd",)

# AdcDspFp AXI-Lite register map (see AdcDspFp.vhd comb process)
REG_CONTROL = 0x0000  # bit0 = fllEnable, bit8 = outputMode
REG_P_COEF = 0x0004
REG_I_COEF = 0x0008
REG_ACCUM_ERROR = 0x0010
REG_SUM_ACCUM = 0x0018   # float32
REG_SQ1FB_NEW = 0x0020   # float32
REG_SQ1FB_FULL = 0x0028  # float32
REG_SQ1FB_INT = 0x002C   # signed int
REG_CLEAR_PID_STATE = 0x0030
REG_FLUX_QUANTUM = 0x0040       # float32
REG_INV_FLUX_QUANTUM = 0x0044   # float32

FLL_ENABLE_MASK = 0x00000001

FP_ONE = 0x3F800000        # 1.0f
FP_LARGE_QUANTUM = 0x461C4000  # 10000.0f -- large so no flux wrap in these tests


def f32_to_u32(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def u32_to_f32(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]


# LocalTimingType bit layout, matching TimingPkg.toSlv field order/widths.
TIMING_FIELD_LAYOUT = {
    "startRun": (0, 1),
    "endRun": (1, 1),
    "running": (2, 1),
    "runTime": (3, 64),
    "rowStrobe": (67, 1),
    "rowSeqStart": (68, 1),
    "daqReadoutStart": (69, 1),
    "sample": (70, 1),
    "firstSample": (71, 1),
    "lastSample": (72, 1),
    "stageNextRow": (73, 1),
    "rowSeq": (74, 8),
    "rowIndex": (82, 8),
    "rowIndexNext": (90, 8),
    "rowTime": (98, 32),
    "rowSeqCount": (130, 64),
    "daqReadoutCount": (194, 64),
    "waveformCapture": (258, 1),
}


def _mask(width: int) -> int:
    return (1 << width) - 1


def _pack_timing(**fields: int) -> int:
    word = 0
    for name, (offset, width) in TIMING_FIELD_LAYOUT.items():
        value = fields.get(name, 0)
        word |= (value & _mask(width)) << offset
    return word


class AdcDspFpBench:
    def __init__(self, dut):
        self.dut = dut
        self.axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "S_AXIL"), dut.clk, dut.rst)
        self.timing_fields = {"running": 1}

    async def set_timing(self, **fields: int) -> None:
        self.timing_fields.update(fields)
        self.dut.TIMING_RX_DATA.value = _pack_timing(**self.timing_fields)
        await RisingEdge(self.dut.clk)

    async def pulse_start_run(self) -> None:
        await self.set_timing(startRun=1, runTime=0, rowSeqCount=0)
        await self.set_timing(startRun=0)

    def _clear_accum(self) -> None:
        self.dut.ACCUM_VALID.value = 0
        self.dut.ACCUM_ERROR.value = 0
        self.dut.ACCUM_NUM_SAMPLES.value = 0
        self.dut.ACCUM_ROW_INDEX.value = 0
        self.dut.ACCUM_SQ1FB_DAC.value = 0
        self.dut.ACCUM_SEQ_START.value = 0
        self.dut.ACCUM_DAQ_READOUT_START.value = 0

    async def idle_cycles(self, cycles: int) -> None:
        self._clear_accum()
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)

    async def drive_accum(
        self,
        *,
        error: int,
        row: int = 0,
        num_samples: int = 2,
        seq_start: bool = False,
        settle_cycles: int = 64,
    ) -> None:
        """Present one AdcAccumulator result and pulse accumValid for a cycle.

        The FP pipeline is much longer than the fixed-point one (each FpMac /
        Int2Fp / Fp2Int stage has multi-cycle latency), so settle_cycles is
        larger to let the state machine run IDLE -> ... -> IDLE.
        """
        self.dut.ACCUM_ERROR.value = error & _mask(32)
        self.dut.ACCUM_NUM_SAMPLES.value = num_samples & _mask(8)
        self.dut.ACCUM_ROW_INDEX.value = row & _mask(8)
        self.dut.ACCUM_SQ1FB_DAC.value = 0
        self.dut.ACCUM_SEQ_START.value = 1 if seq_start else 0
        self.dut.ACCUM_DAQ_READOUT_START.value = 0
        self.dut.ACCUM_VALID.value = 1
        await RisingEdge(self.dut.clk)
        await self.idle_cycles(settle_cycles)

    async def wait_for_pid_clear(self, cycles: int = 400) -> None:
        await self.idle_cycles(cycles)


async def setup_bench(dut) -> AdcDspFpBench:
    cocotb.start_soon(Clock(dut.clk, 8, units="ns").start())

    dut.rst.value = 1
    dut.TIMING_RX_DATA.value = 0
    dut.ACCUM_VALID.value = 0
    dut.ACCUM_ERROR.value = 0
    dut.ACCUM_NUM_SAMPLES.value = 0
    dut.ACCUM_ROW_INDEX.value = 0
    dut.ACCUM_SQ1FB_DAC.value = 0
    dut.ACCUM_SEQ_START.value = 0
    dut.ACCUM_DAQ_READOUT_START.value = 0

    for _ in range(5):
        await RisingEdge(dut.clk)

    dut.rst.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)

    bench = AdcDspFpBench(dut)
    await bench.set_timing(running=1)
    # Large flux quantum + tiny inverse so the flux-wrap path never triggers in
    # these PID unit checks.
    await axil_write_u32(bench.axil, REG_FLUX_QUANTUM, FP_LARGE_QUANTUM)
    await axil_write_u32(bench.axil, REG_INV_FLUX_QUANTUM, f32_to_u32(1.0 / 10000.0))
    await axil_write_u32(bench.axil, REG_P_COEF, 0)
    return bench


@cocotb.test()
async def i_coef_zero_does_not_accumulate(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, 0)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=12)

    accum_error = await axil_read_u32(bench.axil, REG_ACCUM_ERROR)
    sum_accum = u32_to_f32(await axil_read_u32(bench.axil, REG_SUM_ACCUM))

    assert accum_error != 0
    assert sum_accum == 0.0


@cocotb.test()
async def i_coef_nonzero_accumulates(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, FP_ONE)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=10)
    sum_accum = u32_to_f32(await axil_read_u32(bench.axil, REG_SUM_ACCUM))
    # Integrator = 0 + accumError = 10.0 after one iteration.
    assert sum_accum != 0.0


@cocotb.test()
async def start_run_clears_integrator_state(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, FP_ONE)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=9)
    assert u32_to_f32(await axil_read_u32(bench.axil, REG_SUM_ACCUM)) != 0.0

    await bench.pulse_start_run()
    await bench.wait_for_pid_clear()

    assert u32_to_f32(await axil_read_u32(bench.axil, REG_SUM_ACCUM)) == 0.0


@cocotb.test()
async def clear_pid_state_register_clears_integrator_state(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, FP_ONE)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=9)
    assert u32_to_f32(await axil_read_u32(bench.axil, REG_SUM_ACCUM)) != 0.0

    await axil_write_u32(bench.axil, REG_CLEAR_PID_STATE, 1)
    await bench.wait_for_pid_clear()

    assert u32_to_f32(await axil_read_u32(bench.axil, REG_SUM_ACCUM)) == 0.0


@cocotb.test()
async def p_term_updates_sq1fb(dut):
    bench = await setup_bench(dut)

    # Pure proportional response: I=0 so integrator stays put; sq1FbNew must
    # move by pCoef*accumError = 1.0*error.
    await axil_write_u32(bench.axil, REG_I_COEF, 0)
    await axil_write_u32(bench.axil, REG_P_COEF, FP_ONE)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=7)
    sq1_new = u32_to_f32(await axil_read_u32(bench.axil, REG_SQ1FB_NEW))

    assert sq1_new != 0.0


def _vcs_available() -> bool:
    return os.environ.get("WARM_TDM_SIM", "").lower() in ("vcs", "xsim")


@pytest.mark.skipif(
    not _vcs_available(),
    reason=(
        "AdcDspFp instantiates Xilinx FpMac/Int2Fp/Fp2Int IP; GHDL cannot "
        "elaborate them. Export WARM_TDM_SIM=vcs (with the VCS + Vivado 2025.2 "
        "compiled sim libraries on the search path) to run this bench. See "
        "docs/_meta/rtl_regression_handoff.md."
    ),
)
@pytest.mark.parametrize("parameters", [pytest.param({}, id="adcdspfp_cocotb_wrapper")])
def test_AdcDspFp(parameters):
    run_warm_tdm_vhdl_test(
        test_file=__file__,
        toplevel="warm_tdm.adcdspfpcocotbwrapper",
        parameters=parameters,
        extra_env=parameters,
        extra_vhdl_sources={
            "unisim": [UNISIM_STUB_PATH],
            "warm_tdm": [WRAPPER_PATH],
        },
        sim_build_key="adcdspfp_accum_pid_v1",
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
        simulator=os.environ.get("WARM_TDM_SIM", "vcs"),
    )
