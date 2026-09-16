# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Flux wrapping: saved feedback/count, actual DAC, debug and unwrapped output."""
import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
import numpy as np
import pytest

from firmware.submodules.surf.tests.axi.utils import axil_read_u32
from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp.test_AdcDsp_fractional import FeedbackLoop
from tests.warm_tdm.adc_dsp._pid_bitexact import REG_FLUX_QUANTUM, REG_P_COEF
from tests.warm_tdm.adc_dsp.test_AdcDsp_bitexact_compare import (
    IMPORT_LIBRARY_ALLOWLIST, IMPORT_FILE_ALLOWLISTS, IMPORT_FILE_EXCLUDES,
    WRAPPER_PATH, UNISIM_STUB_PATH,
)


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


class FluxLoop(FeedbackLoop):
    async def start(self, **kwargs):
        await super().start(**kwargs)
        spec = importlib.util.spec_from_file_location(
            'flux_data_formats', Path(__file__).resolve().parents[3] /
            'firmware/python/warm_tdm/_DataFormats.py')
        self.formats = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.formats
        spec.loader.exec_module(self.formats)
        self.frames, self.samples, self.samples32 = [], [], []
        cocotb.start_soon(self.monitor())
        await self.write(0x50, 1)

    async def monitor(self):
        frame = bytearray()
        while True:
            await RisingEdge(self.driver.dut.clk)
            await ReadOnly()
            d = self.driver.dut
            if int(d.DEBUG_TVALID.value):
                assert int(d.DEBUG_TKEEP.value) == 0xff
                frame.extend(int(d.DEBUG_TDATA.value).to_bytes(8, 'little'))
                if int(d.DEBUG_TLAST.value):
                    self.frames.append(self.formats.PidDebug.from_numpy(
                        np.frombuffer(bytes(frame), dtype=np.uint8)))
                    frame.clear()
            if int(d.PID_TVALID.value) and int(d.PID_TKEEP.value):
                assert int(d.PID_TKEEP.value) == 0xf
                self.samples.append((int(d.PID_TID.value), signed(int(d.PID_TDATA.value), 32)))
                self.samples32.append(signed(int(d.PID_TDATA.value), 32))

    async def full(self, row):
        lo = await axil_read_u32(self.driver.axil, 0x7000 + 8 * row)
        hi = await axil_read_u32(self.driver.axil, 0x7004 + 8 * row)
        raw = lo | (hi << 32)
        return Fraction(signed(raw, 38), 1 << 23), bool(raw & (1 << 38))

    async def count(self, row):
        # User chose to retain the signed nine-bit range.
        return signed(await axil_read_u32(self.driver.axil, 0x6000 + 4 * row), 9)

    async def seed(self, row, full, count=0):
        word = (int(full * (1 << 23)) & ((1 << 38) - 1)) | (1 << 38)
        await self.write(0x7000 + 8 * row, word)
        await self.write(0x7004 + 8 * row, word >> 32)
        await self.write(0x6000 + 4 * row, count)
        self.feedback[row] = self.encode(round(full))

    async def check(self, row, error, full, count, quantum, enabled=True):
        before_frames, before_samples = len(self.frames), len(self.samples)
        actual = await self.visit(error, row, enabled=enabled)
        saved, valid = await self.full(row)  # Also allow output FIFOs to drain.
        assert valid and saved == full, (saved, full)
        assert await self.count(row) == count
        assert len(self.frames) == before_frames + 1
        msg = self.frames[-1]
        assert msg.row == row
        if enabled:
            assert msg.fields['numFluxJumps'] == count
            assert actual == round(full)
            assert msg.fields['sq1FbFull'] == full
            assert self.samples[before_samples:] == [(row, round(full) + count * quantum)]
        else:
            assert self.samples[before_samples:] == []


@cocotb.test()
async def flux_direction_and_continuity(dut):
    loop = FluxLoop(dut)
    await loop.start()
    for q in (1, 2000, 2001, 8191):
        await loop.write(REG_FLUX_QUANTUM, q)
        for row, sign in ((0, 1), (loop.last_row, -1)):
            # Both signs and a nonzero existing count; strict threshold and
            # a fractional threshold crossing, followed by a real wrap.
            full = Fraction(sign * 7862)
            count = sign * 7
            await loop.seed(row, full, count)
            await loop.check(row, 0, full, count, q)
            for error in (sign, sign, -sign, -sign):
                unwrapped = full + count * q + Fraction(error, 4)
                candidate = full + Fraction(error, 4)
                jump = int(candidate > 7862) - int(candidate < -7862)
                full, count = candidate - jump * q, count + jump
                assert full + count * q == unwrapped
                await loop.check(row, error, full, count, q)


@cocotb.test()
async def masked_wrap_holds_feedback_and_count(dut):
    loop = FluxLoop(dut)
    await loop.start()
    await loop.write(REG_FLUX_QUANTUM, 2000)
    for row, sign in ((0, 1), (loop.last_row, -1)):
        await loop.seed(row, sign * 7862, sign * 7)
        await loop.mask(row, False)
        for _ in range(3):
            await loop.check(row, sign, sign * 7862, sign * 7, 2000, enabled=False)
            # Debug reports the hypothetical command; neither half of that
            # feedback/count pair may be committed on a masked visit.
            assert loop.frames[-1].fields['numFluxJumps'] == sign * 8
            assert loop.frames[-1].fields['sq1FbFull'] == sign * Fraction(23449, 4)
        await loop.mask(row, True)
        await loop.check(row, sign, sign * Fraction(23449, 4), sign * 8, 2000)


@cocotb.test()
async def zero_quantum_does_not_count_jumps(dut):
    loop = FluxLoop(dut)
    await loop.start(p=0)
    for row, sign in ((0, 1), (loop.last_row, -1)):
        await loop.seed(row, sign * 8000)
        for _ in range(3):
            await loop.check(row, 0, sign * 8000, 0, 0)


@cocotb.test()
async def flux_count_debug_crosses_eight_bit_boundary(dut):
    loop = FluxLoop(dut)
    await loop.start()
    await loop.write(REG_FLUX_QUANTUM, 2000)
    for row, sign, start in ((0, 1, 127), (loop.last_row, -1, -128),
                             (0, 1, 254), (loop.last_row, -1, -255)):
        await loop.seed(row, sign * 7862, start)
        await loop.check(row, sign, sign * Fraction(23449, 4), start + sign, 2000)


@cocotb.test()
async def flux_count_saturation_limit_is_explicit(dut):
    loop = FluxLoop(dut)
    await loop.start()
    await loop.write(REG_FLUX_QUANTUM, 2000)
    for row, sign, start in ((0, 1, 255), (loop.last_row, -1, -256)):
        await loop.seed(row, sign * 7862, start)
        full = sign * Fraction(23449, 4)
        await loop.check(row, sign, full, start, 2000)
        # This is the documented limit, not lossless reconstruction: the DAC
        # still wraps after the count saturates, losing one quantum of history.
        wanted = sign * Fraction(31449, 4) + start * 2000
        assert full + start * 2000 - wanted == -sign * 2000


@cocotb.test()
async def readout_preserves_negative_sign_for_int32_converter(dut):
    loop = FluxLoop(dut)
    await loop.start()
    await loop.write(REG_FLUX_QUANTUM, 2000)
    await loop.seed(0, -7862, -7)
    await loop.check(0, -1, Fraction(-23449, 4), -8, 2000)
    # BiquadFilter passes tData(31:0) directly to its Int32-to-float core.
    # A three-byte FIFO discards the sign-extension byte and corrupts negatives.
    assert loop.samples32[-1] == -21862, loop.samples32[-1]


@cocotb.test()
async def one_wrap_recovery_and_slew_limit(dut):
    loop = FluxLoop(dut)
    await loop.start()
    await loop.write(REG_FLUX_QUANTUM, 2000)
    for row, sign in ((0, 1), (loop.last_row, -1)):
        await loop.seed(row, sign * 8000)
        await loop.check(row, sign * 2001, sign * Fraction(26001, 4), sign, 2000)
    await loop.write(REG_P_COEF, 1 << 22)
    for row, sign, rail in ((0, 1, 8191), (loop.last_row, -1, -8192)):
        await loop.seed(row, sign * 8000)
        # 8000 + 4000 - 2000 = 10000: one quantum cannot recover this step.
        # It clips, updates the count once, and the readout reflects clipping.
        await loop.check(row, sign * 8000, rail, sign, 2000)


@cocotb.test()
async def prewrap_anti_windup_policy_is_explicit(dut):
    loop = FluxLoop(dut)
    await loop.start(i=1 << 20)
    await loop.write(REG_FLUX_QUANTUM, 2000)
    await loop.seed(0, 8000)
    await loop.check(0, 2001, Fraction(26001, 4), 1, 2000)
    # Existing I-state admission uses the pre-wrap candidate (8500.25), so it
    # holds even though wrapping successfully recovers a non-clipped command.
    assert await axil_read_u32(loop.driver.axil, 0x2000) == 0


@pytest.mark.parametrize('parameters', [
    pytest.param({'ROW_ADDR_BITS_G': 3, 'INVERT_SQ1FB_G': True}, id='8rows_inverted'),
    pytest.param({'ROW_ADDR_BITS_G': 8, 'INVERT_SQ1FB_G': False}, id='256rows_normal'),
])
def test_AdcDsp_flux(parameters):
    run_warm_tdm_vhdl_test(
        test_file=__file__, toplevel='warm_tdm.adcdspaccumcomparewrapper',
        parameters=parameters, extra_env=parameters,
        extra_vhdl_sources={'unisim': [UNISIM_STUB_PATH], 'warm_tdm': [WRAPPER_PATH]},
        import_library_allowlist=IMPORT_LIBRARY_ALLOWLIST,
        import_file_allowlists=IMPORT_FILE_ALLOWLISTS,
        import_file_excludes=IMPORT_FILE_EXCLUDES,
    )
