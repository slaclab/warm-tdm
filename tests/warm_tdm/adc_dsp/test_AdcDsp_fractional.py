# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Whole-path tests: return actual DAC writes as the next visit's feedback."""

import os
import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
import numpy as np
import pytest

from firmware.submodules.surf.tests.axi.utils import axil_read_u32, axil_write_u32
from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp._pid_bitexact import (
    BitExactDriver, RowVisit, Stimulus, REG_CONTROL, REG_P_COEF, REG_I_COEF,
    REG_ROW_ENABLE, REG_FLUX_QUANTUM,
)
from tests.warm_tdm.adc_dsp.test_AdcDsp_bitexact_compare import (
    IMPORT_LIBRARY_ALLOWLIST, IMPORT_FILE_ALLOWLISTS, IMPORT_FILE_EXCLUDES,
    WRAPPER_PATH, UNISIM_STUB_PATH,
)


class FeedbackLoop:
    def __init__(self, dut):
        self.driver = BitExactDriver(dut)
        self.invert = os.environ["INVERT_SQ1FB_G"].lower() == "true"
        self.last_row = (1 << int(os.environ["ROW_ADDR_BITS_G"])) - 1
        self.feedback = {}

    def encode(self, signed):
        return (signed & 0x3fff) ^ (0x1fff if self.invert else 0x2000)

    def decode(self, raw):
        signed = raw ^ (0x1fff if self.invert else 0x2000)
        return signed - 0x4000 if signed & 0x2000 else signed

    async def write(self, addr, value):
        await axil_write_u32(self.driver.axil, addr, value & 0xffffffff)

    async def settle_clear(self):
        for _ in range(300):
            await self.driver._tick()

    async def clear(self):
        await self.write(0x30, 1)
        await self.settle_clear()

    async def mask(self, row, enabled):
        # Each test masks only this one row in its mask word.
        await self.write(REG_ROW_ENABLE + 4 * (row // 32),
                         0xffffffff if enabled else 0xffffffff ^ (1 << (row % 32)))

    async def start(self, p=1 << 21, i=0, d=0):
        await self.driver.reset()
        await self.driver.configure(Stimulus(p, i, d, 0xffffffff, self.encode(0)))
        # The high row exercises the last address of the clear sweep, including
        # the upper mask words for the 256-row configuration.
        await self.write(REG_ROW_ENABLE + 4 * (self.last_row // 32), 0xffffffff)

    async def visit(self, error=1, row=0, seed=None, enabled=True, samples=2):
        if seed is not None:
            self.feedback[row] = self.encode(seed)
        before = len(self.driver.writes)
        await self.driver.visit(RowVisit(
            row, error, num_samples=samples,
            sq1fb_dac=self.feedback.get(row, self.encode(0))))
        writes = self.driver.writes[before:]
        if not enabled:
            assert writes == [], f"disabled row {row} wrote {writes}"
            return None
        assert len(writes) == 1 and writes[0][0] == row, writes
        self.feedback[row] = writes[0][1]
        return self.decode(writes[0][1])


@cocotb.test()
async def fractional_carry_and_rounding(dut):
    loop = FeedbackLoop(dut)
    await loop.start()
    # +/- quarter-code corrections, interleaved rows and independent seeds.
    pos, neg = [], []
    for n in range(8):
        pos.append(await loop.visit(1, 0, seed=100 if n == 0 else None))
        neg.append(await loop.visit(-1, loop.last_row, seed=-100 if n == 0 else None))
    assert pos == [100, 100, 101, 101, 101, 102, 102, 102]
    assert neg == [-100, -100, -101, -101, -101, -102, -102, -102]

    # Half-code ties on odd as well as even bases; fractions of both signs.
    await loop.write(REG_P_COEF, 1 << 22)
    assert [await loop.visit(1, 1, seed=101 if n == 0 else None)
            for n in range(4)] == [102, 102, 102, 103]
    assert [await loop.visit(-1, 2, seed=-101 if n == 0 else None)
            for n in range(4)] == [-102, -102, -102, -103]

    # Small correction from the quantitative design note: 1/64 code/visit.
    await loop.write(REG_P_COEF, 1 << 10)
    tiny = [await loop.visit(128, 3) for _ in range(33)]
    assert tiny == [0] * 32 + [1]
    # Whole-code updates remain exact and do not accumulate an extra term.
    await loop.write(REG_P_COEF, 1 << 22)
    assert [await loop.visit(2, 4) for _ in range(4)] == [1, 2, 3, 4]


@cocotb.test()
async def least_significant_fraction_bit(dut):
    loop = FeedbackLoop(dut)
    await loop.start(p=1 << 22)
    for sign, row in ((1, 0), (-1, loop.last_row)):
        await loop.write(REG_P_COEF, sign * (1 << 22))
        assert await loop.visit(row=row, seed=sign * 100) == sign * 100
        # Stored residue is exactly +/-0.5. One Q1.23 LSB must cross the tie.
        await loop.write(REG_P_COEF, sign)
        assert await loop.visit(row=row) == sign * 101
        # Cross back by two LSBs: the low bit must survive the negative residue
        # as well. These gain changes intentionally preserve feedback state.
        await loop.write(REG_P_COEF, -2 * sign)
        assert await loop.visit(row=row) == sign * 100


@cocotb.test()
async def feedback_state_lifecycle(dut):
    loop = FeedbackLoop(dut)
    await loop.start()
    for row in (0, loop.last_row):
        assert await loop.visit(row=row, seed=200) == 200
        assert await loop.visit(row=row) == 200  # residue +0.5
        await loop.mask(row, False)
        for _ in range(3):
            await loop.visit(row=row, enabled=False)
        await loop.mask(row, True)
        assert await loop.visit(row=row) == 201  # old residue held, not cleared

    for trigger in ("clear", "start_run", "enable", "i_change", "reset"):
        await loop.clear()
        for row in (0, loop.last_row):
            assert await loop.visit(row=row, seed=200) == 200
            assert await loop.visit(row=row) == 200
        if trigger == "clear":
            await loop.clear()
        elif trigger == "start_run":
            loop.driver._apply_timing(startRun=1)
            await loop.driver._tick()
            loop.driver._apply_timing()
        elif trigger == "enable":
            await loop.write(REG_CONTROL, 0)
            await loop.visit(row=loop.last_row, enabled=False)
            await loop.write(REG_CONTROL, 1)
        elif trigger == "i_change":
            # Raw coefficient changes clear, even a one-bit change.
            await loop.write(REG_I_COEF, 1)
            await loop.settle_clear()
            await loop.write(REG_I_COEF, 0)
        else:
            dut.rst.value = 1
            for _ in range(5):
                await loop.driver._tick()
            dut.rst.value = 0
            await loop.settle_clear()
            await loop.write(REG_P_COEF, 1 << 21)
            await loop.write(REG_CONTROL, 1)
        await loop.settle_clear()
        for row in (0, loop.last_row):
            assert [await loop.visit(row=row) for _ in range(3)] == [200, 200, 201], trigger


@cocotb.test()
async def flux_wraps_and_clipping(dut):
    loop = FeedbackLoop(dut)
    await loop.start()
    for quantum in (2000, 2001):
        await loop.clear()
        await loop.write(REG_FLUX_QUANTUM, quantum)
        for sign, row in ((1, 0), (-1, loop.last_row)):
            assert await loop.visit(0, row, seed=sign * 7862) == sign * 7862
            assert (await axil_read_u32(loop.driver.axil, 0x6000 + 4 * row)) & 0x1ff == 0
            actual = [await loop.visit(sign, row) for _ in range(8)]
            # Compare/wrap the fractional feedback, then quantize the output.
            # A quarter-code excursion past the exact threshold wraps at once.
            feedback = Fraction(sign * 7862)
            expected = []
            for _ in range(8):
                feedback += Fraction(sign, 4)
                feedback -= quantum if feedback > 7862 else -quantum if feedback < -7862 else 0
                expected.append(round(feedback))
            assert actual == expected
            jumps = await axil_read_u32(loop.driver.axil, 0x6000 + 4 * row)
            assert jumps & 0x1ff == sign & 0x1ff

        # Half ties with an odd Q distinguish rounding AFTER the flux shift
        # from independently wrapping an already-rounded integer DAC command.
        await loop.clear()
        for sign, row in ((1, 0), (-1, loop.last_row)):
            expected = sign * (5864 if quantum == 2000 else 5862)
            assert await loop.visit(sign * 2, row, seed=sign * 7863) == expected
            assert await loop.visit(0, row) == expected

    await loop.write(REG_FLUX_QUANTUM, 0)
    await loop.clear()
    for sign, rail, row, reverse in (
        (1, 8191, 0, [8191, 8190, 8190]),
        (-1, -8192, loop.last_row, [-8192, -8192, -8191]),
    ):
        # Discard both fractional and large overrange excursions.
        for error in (sign, sign * 4000, sign):
            assert await loop.visit(error, row, seed=rail) == rail
        assert [await loop.visit(-sign, row) for _ in range(3)] == reverse

    # Preserve the existing signed-quantum behavior, including a wrap that
    # saturates. Its fractional residue must be discarded at that second clamp.
    for sign, row, reverse in (
        (1, 0, [8191, 8190, 8190]),
        (-1, loop.last_row, [-8192, -8192, -8191]),
    ):
        await loop.clear()
        await loop.write(REG_FLUX_QUANTUM, (-2000) & 0x3fff)
        assert await loop.visit(sign, row, seed=sign * 8100) == (8191 if sign > 0 else -8192)
        await loop.write(REG_FLUX_QUANTUM, 0)
        assert [await loop.visit(-sign, row) for _ in range(3)] == reverse


@cocotb.test()
async def feedback_width_boundaries(dut):
    loop = FeedbackLoop(dut)
    await loop.start()
    # Keep commands beyond the DAC rails until the flux shift: 8500.25 - 2000
    # must recover to 6500.25, with the fraction retained on subsequent visits.
    # A 14-bit integer coordinate would saturate prematurely before the wrap.
    for sign, row in ((1, 0), (-1, loop.last_row)):
        await loop.clear()
        await loop.write(REG_FLUX_QUANTUM, 2000)
        assert await loop.visit(sign * 2001, row, seed=sign * 8000) == sign * 6500
        await loop.write(REG_FLUX_QUANTUM, 0)
        assert [await loop.visit(sign, row) for _ in range(2)] == [sign * 6500, sign * 6501]

    # A flux shift that still exceeds a rail discards its overrange fraction.
    # Saved feedback is bounded to the DAC range before the one conversion.
    for row, seed, error, quantum, rail, recovery in (
        (0, -7863, -1, -329, -8192, [-8192, -8192, -8191, -8191]),
        (loop.last_row, 7863, 1, -328, 8191, [8191, 8190, 8190, 8190]),
    ):
        await loop.clear()
        await loop.write(REG_FLUX_QUANTUM, quantum & 0x3fff)
        assert await loop.visit(error, row, seed=seed) == rail
        await loop.write(REG_FLUX_QUANTUM, 0)
        assert [await loop.visit(-error, row) for _ in range(4)] == recovery

    # Most-negative signed Q reaches the full pre-clipping wrap extrema:
    # -8192 + (-8192) = -16384 and 8191 - (-8192) = 16383.
    # DAC clipping must replace that excursion with the clipped integer state.
    for row, rail, reverse, recovery in (
        (0, -8192, 1, [-8192, -8192, -8191]),
        (loop.last_row, 8191, -1, [8191, 8190, 8190]),
    ):
        await loop.clear()
        await loop.write(REG_FLUX_QUANTUM, 0x2000)  # signed -8192
        assert await loop.visit(0, row, seed=rail) == rail
        await loop.write(REG_FLUX_QUANTUM, 0)
        assert [await loop.visit(reverse, row) for _ in range(3)] == recovery

    # Commands beyond the guard-bit range cannot be recovered by even the
    # largest positive quantum in a single wrap; final clipping is required.
    for sign, row, rail in ((1, 0, 8191), (-1, loop.last_row, -8192)):
        await loop.clear()
        await loop.write(REG_FLUX_QUANTUM, 8191)
        assert await loop.visit(sign * 1000, row, seed=0, samples=250) == rail


@cocotb.test()
async def fractional_anti_windup(dut):
    loop = FeedbackLoop(dut)
    await loop.start(i=1 << 20)  # I=1/8; P=1/4
    for sign, seed, row, rail in ((1, 8190, 0, 8191), (-1, -8191, loop.last_row, -8192)):
        await loop.write(REG_P_COEF, 1 << 21)
        assert await loop.visit(sign, row, seed=seed) == seed
        assert await loop.visit(0, row) == seed
        assert await loop.visit(sign, row) == rail
        # At the rail the residue is -sign/4 and I*S_old is +sign/4.
        # They cancel exactly: integration is allowed, unlike a check that
        # omits the residue and incorrectly sees an overrange command.
        await loop.write(REG_P_COEF, 0)
        assert await loop.visit(sign, row) == rail
        isum = await axil_read_u32(loop.driver.axil, 0x2000 + 4 * row)
        assert isum & 0x3ffff == (sign * 3) & 0x3ffff
        # The following command really exceeds the rail: hold SumAccum.
        assert await loop.visit(sign, row) == rail
        isum = await axil_read_u32(loop.driver.axil, 0x2000 + 4 * row)
        assert isum & 0x3ffff == (sign * 3) & 0x3ffff


@cocotb.test()
async def feedback_seed_and_reseed(dut):
    loop = FeedbackLoop(dut)
    await loop.start()
    # A masked visit cannot initialize a row's authoritative feedback state.
    await loop.mask(0, False)
    await loop.visit(seed=100, enabled=False)
    await loop.mask(0, True)
    assert await loop.visit(seed=200) == 200
    # Once initialized, saved full-precision feedback is the next loop's base.
    # An external DAC change alone is intentionally not a feedback-state reset.
    assert await loop.visit(seed=500) == 200
    assert await loop.visit() == 201
    # Explicitly clear, then adopt the newly applied seed, retaining its fraction
    # on subsequent visits. This is also the startup/manual-reseed procedure.
    await loop.clear()
    assert await loop.visit(seed=500) == 500
    assert [await loop.visit() for _ in range(2)] == [500, 501]


@cocotb.test()
async def combined_pid_fractional_state(dut):
    loop = FeedbackLoop(dut)
    await loop.start(p=1 << 21, i=1 << 18, d=1 << 20)
    # An exact rational oracle for mixed P/I/D updates, with interleaved rows.
    # Stay far from arithmetic limits here; the dedicated rail tests exercise
    # clamp/anti-windup and the historical golden exercises ADC overflow.
    states = {0: [100, Fraction(0), 0, 0], loop.last_row: [-101, Fraction(0), 0, 0]}
    for n, error in enumerate([1, -3, 7, 0, -9, 2, 1, 1, 0, 8, -2, -1] * 2):
        row = (0, loop.last_row)[n % 2]
        base, residue, isum, last_error = states[row]
        delta = Fraction(error, 4) + Fraction(isum, 32) + Fraction(last_error - error, 8)
        command = base + residue + delta
        expected = round(command)
        actual = await loop.visit(error, row, seed=base if n < 2 else None)
        assert actual == expected, (n, row, command, actual)
        states[row] = [actual, command - expected, isum + error, error]
        # PidResults retains the correction alone, with all 23 fraction bits.
        low = await axil_read_u32(loop.driver.axil, 0x3000 + 8 * row)
        high = await axil_read_u32(loop.driver.axil, 0x3004 + 8 * row)
        assert ((high << 32) | low) & ((1 << 42) - 1) == int(delta * (1 << 23)) & ((1 << 42) - 1)


@cocotb.test()
async def full_feedback_axil_and_debug(dut):
    # Load the production decoder without importing the PyRogue device tree.
    path = Path(__file__).resolve().parents[3] / 'firmware/python/warm_tdm/_DataFormats.py'
    spec = importlib.util.spec_from_file_location('fractional_data_formats', path)
    formats = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = formats
    spec.loader.exec_module(formats)
    loop = FeedbackLoop(dut)
    await loop.start()
    frames = []

    async def monitor_debug():
        frame = bytearray()
        while True:
            await RisingEdge(dut.clk)
            await ReadOnly()
            if int(dut.DEBUG_TVALID.value):
                assert int(dut.DEBUG_TKEEP.value) == 0xff
                frame.extend(int(dut.DEBUG_TDATA.value).to_bytes(8, 'little'))
                if int(dut.DEBUG_TLAST.value):
                    frames.append(bytes(frame))
                    frame.clear()

    cocotb.start_soon(monitor_debug())
    await loop.write(0x50, 1)  # PID-debug enable

    async def read_state(row):
        lo = await axil_read_u32(loop.driver.axil, 0x7000 + 8 * row)
        hi = await axil_read_u32(loop.driver.axil, 0x7004 + 8 * row)
        return lo | (hi << 32)

    def packed(value, valid=True):
        return (int(value * (1 << 23)) & ((1 << 38) - 1)) | (int(valid) << 38)

    async def check_visit(row, error, expected, seed=None, enabled=True, saved=None):
        before = len(frames)
        dac = await loop.visit(error, row, seed=seed, enabled=enabled)
        assert await read_state(row) == packed(expected if saved is None else saved)
        assert len(frames) == before + 1, (before, len(frames))
        raw = frames[-1]
        assert len(raw) == 96 and raw[:2] == b'\x01\x03'
        msg = formats.PidDebug.from_numpy(np.frombuffer(raw, dtype=np.uint8))
        assert msg.col == 0 and msg.row == row
        assert msg.fields['sq1FbFull'] == expected
        # Check wire sign-extension independently of the production decoder.
        assert int.from_bytes(raw[64:72], 'little', signed=True) == int(expected * (1 << 23))
        assert msg.fields['accumError'] == error
        assert msg.fields['sq1FbEnd'] == loop.encode(round(expected))
        assert msg.fields['dropCount'] == 0
        assert msg.fields['numSamples'] > 0
        if enabled:
            assert dac == round(expected)
        return msg

    for row in (0, loop.last_row):
        assert await read_state(row) == 0
    for n in range(1, 5):
        await check_visit(0, 1, 100 + n / 4, seed=100 if n == 1 else None)
        await check_visit(loop.last_row, -1, -100 - n / 4, seed=-100 if n == 1 else None)
    await loop.mask(0, False)
    await check_visit(0, 1, 101.25, enabled=False, saved=101)
    await loop.mask(0, True)

    # AXI writes, both 32-bit halves, must be used by the next visit. Row
    # sequencing is idle and the enable-triggered clear has already completed.
    for value, valid in ((Fraction(-401, 4), True), (Fraction(495, 4), False)):
        word = packed(value, valid)
        await loop.write(0x7000 + 8 * loop.last_row, word)
        await loop.write(0x7004 + 8 * loop.last_row, word >> 32)
        assert await read_state(loop.last_row) == word
        expected = -100 if valid else 300.25
        await check_visit(loop.last_row, 1, expected, seed=300)

    await loop.clear()
    for row in (0, loop.last_row):
        assert await read_state(row) == 0
    await loop.write(REG_FLUX_QUANTUM, 2000)
    for row, sign in ((0, 1), (loop.last_row, -1)):
        msg = await check_visit(row, sign, sign * 5862.25, seed=sign * 7862)
        assert msg.fields['numFluxJumps'] == sign
    await loop.clear()
    await loop.write(REG_FLUX_QUANTUM, 0)
    for row, sign, seed in ((0, 1, 8191), (loop.last_row, -1, -8192)):
        await check_visit(row, sign, seed, seed=seed)
    await loop.clear()
    await loop.write(REG_P_COEF, 1)
    for row, sign in ((0, 1), (loop.last_row, -1)):
        await check_visit(row, sign, sign / (1 << 23), seed=0)


@pytest.mark.parametrize("parameters", [
    pytest.param({"ROW_ADDR_BITS_G": 3, "INVERT_SQ1FB_G": True}, id="8rows_inverted"),
    pytest.param({"ROW_ADDR_BITS_G": 8, "INVERT_SQ1FB_G": False}, id="256rows_normal"),
])
def test_AdcDsp_fractional(parameters):
    run_warm_tdm_vhdl_test(
        test_file=__file__, toplevel="warm_tdm.adcdspaccumcomparewrapper",
        parameters=parameters, extra_env=parameters,
        extra_vhdl_sources={"unisim": [UNISIM_STUB_PATH], "warm_tdm": [WRAPPER_PATH]},
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
    )
