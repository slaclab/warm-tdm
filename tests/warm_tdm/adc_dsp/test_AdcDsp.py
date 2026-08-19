# Test methodology:
# - Sweep: Exercise the fixed-point `AdcDsp` cocotb wrapper across the PID
#   control cases that motivated the regression work: I-disabled operation,
#   state clearing on I writes / start-run / software clear, and positive-rail
#   anti-windup.
# - Interface: fp-pid split the ADC accumulation out into `AdcAccumulator`, so
#   `AdcDsp` now consumes a decoded `accumIn : AdcAccumResultType` qualified by
#   `accumValid` instead of a raw ADC AXI-stream. The bench therefore presents
#   one accumulation result (accumError / rowIndex / sq1FbDac / seqStart) and
#   pulses `accumValid` for a single cycle, rather than feeding ADC samples and
#   row-strobe metadata.
# - Stimulus: Program the live AXI-Lite register bank, then present accumulation
#   results while a flattened `LocalTimingType` input supplies the run-control
#   pulses (startRun) directly.
# - Checks: `sumAccum` (X"18") stays at zero when `I_Coef = 0`, becomes nonzero
#   when I is enabled and the row error is nonzero, clears after `I_Coef`
#   changes, `startRun`, and `clearPidState`, and stays held at zero when the
#   commanded SQ1 feedback is already above the positive rail (anti-windup).
# - Timing: The bench drives `LocalTimingType` and `AdcAccumResultType` directly
#   instead of using the full timing serial path so PID failures stay
#   attributable to `AdcDsp` rather than to a larger integration shell.
# - Simulator: GHDL. `AdcDsp` contains no Xilinx FP IP; the SIMULATION_G generic
#   swaps its AXI-stream FIFOs to inferred logic so GHDL can elaborate it.

from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
from firmware.submodules.surf.tests.axi.utils import axil_read_u32, axil_write_u32
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test


WRAPPER_PATH = "firmware/common/warm_tdm/wrappers/AdcDspCocotbWrapper.vhd"
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
        "AdcDsp.vhd",
        "FixedPkg.vhd",
        "TimingPkg.vhd",
        "WarmTdmPkg.vhd",
    },
}
IMPORT_FILE_EXCLUDES = ("*Tb*.vhd",)

# AdcDsp AXI-Lite register map (see AdcDsp.vhd comb process)
REG_CONTROL = 0x0000  # bit0 = fllEnable, bit8 = outputMode, bit16 = accumShift
REG_P_COEF = 0x0004
REG_I_COEF = 0x0008
REG_D_COEF = 0x000C
REG_ACCUM_ERROR = 0x0010
REG_LAST_ACCUM_ERROR = 0x0014
REG_SUM_ACCUM = 0x0018
REG_CLEAR_PID_STATE = 0x0030

FLL_ENABLE_MASK = 0x00000001
# `sfixed(0 downto -23)` cannot represent +1.0; the top bit is the sign bit.
# Use the largest positive coefficient instead.
UNIT_COEF = (1 << 23) - 1

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


def _encode_sq1fb_offset_binary(value: int) -> int:
    # Inverse of AdcDsp.convOffsetBin with INVERT_SQ1FB_G=true: keep the sign
    # bit, invert the low 13 bits. Maps a 2's-complement feedback value to the
    # inverted offset-binary DAC code AdcDsp expects on accumIn.sq1FbDac.
    raw = value & _mask(14)
    sign = raw & (1 << 13)
    low = (~raw) & _mask(13)
    return sign | low


class AdcDspBench:
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
        sq1fb_value: int = 0,
        num_samples: int = 2,
        seq_start: bool = False,
        settle_cycles: int = 24,
    ) -> None:
        """Present one AdcAccumulator result and pulse accumValid for a cycle.

        This is the fp-pid replacement for the old raw-ADC `drive_row` helper:
        the accumulation now lives in AdcAccumulator, so the bench simply hands
        AdcDsp a completed AdcAccumResultType and lets the PID state machine run
        to completion before the caller reads back registers.
        """
        self.dut.ACCUM_ERROR.value = error & _mask(32)
        self.dut.ACCUM_NUM_SAMPLES.value = num_samples & _mask(8)
        self.dut.ACCUM_ROW_INDEX.value = row & _mask(8)
        self.dut.ACCUM_SQ1FB_DAC.value = _encode_sq1fb_offset_binary(sq1fb_value)
        self.dut.ACCUM_SEQ_START.value = 1 if seq_start else 0
        self.dut.ACCUM_DAQ_READOUT_START.value = 0
        self.dut.ACCUM_VALID.value = 1
        await RisingEdge(self.dut.clk)
        # Deassert valid and let the PID pipeline complete (IDLE -> ... -> IDLE).
        await self.idle_cycles(settle_cycles)

    async def wait_for_pid_clear(self, cycles: int = 300) -> None:
        await self.idle_cycles(cycles)


async def setup_bench(dut) -> AdcDspBench:
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

    bench = AdcDspBench(dut)
    await bench.set_timing(running=1)
    await axil_write_u32(bench.axil, REG_P_COEF, 0)
    await axil_write_u32(bench.axil, REG_D_COEF, 0)
    return bench


@cocotb.test()
async def i_coef_zero_does_not_accumulate(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, 0)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=12)

    accum_error = await axil_read_u32(bench.axil, REG_ACCUM_ERROR)
    sum_accum = await axil_read_u32(bench.axil, REG_SUM_ACCUM)

    assert accum_error != 0
    assert sum_accum == 0


@cocotb.test()
async def i_coef_write_clears_integrator_state(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, 1)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=10)
    sum_accum_before = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_before != 0

    await axil_write_u32(bench.axil, REG_I_COEF, 2)
    await bench.wait_for_pid_clear()

    sum_accum_after = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    last_accum_after = await axil_read_u32(bench.axil, REG_LAST_ACCUM_ERROR)

    assert sum_accum_after == 0
    assert last_accum_after == 0


@cocotb.test()
async def start_run_clears_integrator_state(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, 1)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=9)
    sum_accum_before = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_before != 0

    await bench.pulse_start_run()
    await bench.wait_for_pid_clear()

    sum_accum_after = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    accum_error_after = await axil_read_u32(bench.axil, REG_ACCUM_ERROR)

    assert sum_accum_after == 0
    assert accum_error_after == 0


@cocotb.test()
async def clear_pid_state_register_clears_integrator_state(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, 1)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    await bench.drive_accum(error=9)
    sum_accum_before = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_before != 0

    await axil_write_u32(bench.axil, REG_CLEAR_PID_STATE, 1)
    await bench.wait_for_pid_clear()

    sum_accum_after = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    accum_error_after = await axil_read_u32(bench.axil, REG_ACCUM_ERROR)

    assert sum_accum_after == 0
    assert accum_error_after == 0


@cocotb.test()
async def anti_windup_holds_integrator_at_positive_rail(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, UNIT_COEF)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()

    # Nominal integration with feedback near mid-scale: integrator moves.
    await bench.drive_accum(error=11, sq1fb_value=0)
    sum_accum_nominal = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_nominal != 0

    # Clear the integrator and add a proportional term.
    await bench.pulse_start_run()
    await bench.wait_for_pid_clear()
    sum_accum_cleared = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_cleared == 0
    await axil_write_u32(bench.axil, REG_P_COEF, UNIT_COEF)

    # Commanded SQ1 feedback already above the positive rail with a positive
    # error: the anti-windup clamp must block integration (sumAccum stays 0).
    await bench.drive_accum(error=11, sq1fb_value=8188)
    sum_accum_saturated = await axil_read_u32(bench.axil, REG_SUM_ACCUM)

    assert sum_accum_saturated == 0


@pytest.mark.parametrize("parameters", [pytest.param({}, id="adcdsp_cocotb_wrapper")])
def test_AdcDsp(parameters):
    run_warm_tdm_vhdl_test(
        test_file=__file__,
        toplevel="warm_tdm.adcdspcocotbwrapper",
        parameters=parameters,
        extra_env=parameters,
        extra_vhdl_sources={
            "unisim": [UNISIM_STUB_PATH],
            "warm_tdm": [WRAPPER_PATH],
        },
        sim_build_key="adcdsp_accum_pid_v1",
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
    )
