# Test methodology:
# - Sweep: Exercise the first `AdcDsp` cocotb wrapper across the initial PID
#   control cases that motivated the regression work: I-disabled operation,
#   state clearing on I writes, start-run pulses, and software clear requests,
#   plus positive-rail anti-windup.
# - Stimulus: Program the live AXI-Lite register bank, seed row-0 baseline RAM,
#   then drive one-row ADC sample sequences while a flattened `LocalTimingType`
#   input supplies the run-control pulses.
# - Checks: `sumAccum` must stay at zero when `I_Coef = 0`, become nonzero when
#   I is enabled and the row error is nonzero, clear after `I_Coef` changes,
#   `startRun`, and `clearPidState`, and remain held at zero when the current
#   SQ1 feedback value is already above the positive rail.
# - Timing: The bench intentionally drives `LocalTimingType` directly instead of
#   using the full timing serial path so PID failures stay attributable to
#   `AdcDsp` rather than to a larger timing integration shell.

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
    }
}
IMPORT_FILE_EXCLUDES = ("*Tb*.vhd",)

REG_CONTROL = 0x0000
REG_P_COEF = 0x0004
REG_I_COEF = 0x0008
REG_D_COEF = 0x000C
REG_ACCUM_ERROR = 0x0010
REG_LAST_ACCUM_ERROR = 0x0014
REG_SUM_ACCUM = 0x0018
REG_CLEAR_PID_STATE = 0x0030
ADC_BASELINE_RAM = 0x1000

FLL_ENABLE_MASK = 0x00000001
# `sfixed(0 downto -23)` cannot represent +1.0; the top bit is the sign bit.
# Use the largest positive coefficient instead.
UNIT_COEF = (1 << 23) - 1

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
    raw = value & _mask(14)
    sign = raw & (1 << 13)
    low = (~raw) & _mask(13)
    return sign | low


def _adc_word(adc_value: int, sq1fb_value: int) -> int:
    adc_bits = (adc_value & _mask(14)) << 2
    sq1fb_bits = _encode_sq1fb_offset_binary(sq1fb_value) << 16
    return sq1fb_bits | adc_bits

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

    async def idle_cycles(self, cycles: int, *, adc_word: int = 0) -> None:
        self.dut.ADC_AXIS_TVALID.value = 0
        self.dut.ADC_AXIS_TDATA.value = adc_word
        self.dut.ADC_AXIS_TID.value = 0
        self.dut.ADC_AXIS_TUSER.value = 0
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)

    async def drive_adc_cycle(
        self,
        *,
        adc_word: int,
        row: int,
        tuser: int,
        valid: int = 1,
    ) -> None:
        self.dut.ADC_AXIS_TVALID.value = valid
        self.dut.ADC_AXIS_TDATA.value = adc_word
        self.dut.ADC_AXIS_TID.value = row
        self.dut.ADC_AXIS_TUSER.value = tuser
        await RisingEdge(self.dut.clk)

    async def drive_row(
        self,
        *,
        row: int,
        error: int,
        sq1fb_value: int,
        row_seq_start: bool = True,
        samples: int = 2,
    ) -> None:
        sample_word = _adc_word(error, sq1fb_value)
        row_strobe_flags = (1 << 2) | ((1 << 5) if row_seq_start else 0)

        # Start the row with the same row-strobe metadata that the RTL normally
        # expects from the ADC path.
        await self.drive_adc_cycle(adc_word=sample_word, row=row, tuser=row_strobe_flags)

        # The RTL comments call for a few cycles between row strobe and the
        # first sample so the row-indexed RAM lookups settle.
        await self.idle_cycles(3, adc_word=sample_word)

        for index in range(samples):
            flags = 0
            if index == 0:
                flags |= 1 << 0
            if index == samples - 1:
                flags |= 1 << 1
            await self.drive_adc_cycle(adc_word=sample_word, row=row, tuser=flags)

        # Hold the current SQ1 feedback word through the PREP_PID stage, since
        # the RTL samples the current feedback field after accumulation ends.
        await self.drive_adc_cycle(adc_word=sample_word, row=row, tuser=0)
        await self.idle_cycles(12, adc_word=sample_word)

    async def wait_for_pid_clear(self, cycles: int = 300) -> None:
        await self.idle_cycles(cycles)


async def setup_bench(dut) -> AdcDspBench:
    cocotb.start_soon(Clock(dut.clk, 8, units="ns").start())

    dut.rst.value = 1
    dut.TIMING_RX_DATA.value = 0
    dut.ADC_AXIS_TVALID.value = 0
    dut.ADC_AXIS_TDATA.value = 0
    dut.ADC_AXIS_TID.value = 0
    dut.ADC_AXIS_TUSER.value = 0

    for _ in range(5):
        await RisingEdge(dut.clk)

    dut.rst.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)

    bench = AdcDspBench(dut)
    await bench.set_timing(running=1)
    await axil_write_u32(bench.axil, ADC_BASELINE_RAM, 0)
    await axil_write_u32(bench.axil, REG_P_COEF, 0)
    await axil_write_u32(bench.axil, REG_D_COEF, 0)
    return bench


@cocotb.test()
async def i_coef_zero_does_not_accumulate(dut):
    bench = await setup_bench(dut)

    await axil_write_u32(bench.axil, REG_I_COEF, 0)
    await axil_write_u32(bench.axil, REG_CONTROL, FLL_ENABLE_MASK)
    await bench.wait_for_pid_clear()
    await bench.pulse_start_run()
    await bench.wait_for_pid_clear()

    await bench.drive_row(row=0, error=12, sq1fb_value=0)

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

    await bench.drive_row(row=0, error=10, sq1fb_value=0)
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

    await bench.drive_row(row=0, error=9, sq1fb_value=0)
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

    await bench.drive_row(row=0, error=9, sq1fb_value=0)
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

    await bench.drive_row(row=0, error=11, sq1fb_value=0)
    sum_accum_nominal = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_nominal != 0

    await bench.pulse_start_run()
    await bench.wait_for_pid_clear()
    sum_accum_cleared = await axil_read_u32(bench.axil, REG_SUM_ACCUM)
    assert sum_accum_cleared == 0
    await axil_write_u32(bench.axil, REG_P_COEF, UNIT_COEF)

    # Drive the commanded SQ1 feedback near the positive rail and apply a
    # proportional term so the current command exceeds the anti-windup limit.
    await bench.drive_row(row=0, error=11, sq1fb_value=8188)
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
        sim_build_key="adcdsp_direct_pid_v10",
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
    )
