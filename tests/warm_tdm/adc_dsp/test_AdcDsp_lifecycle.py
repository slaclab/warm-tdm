# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Masked state and boundary-safe I changes, using real RAMs and DAC writes."""
import copy
from fractions import Fraction
import numpy as np

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp.test_AdcDsp import IMPORT_FILE_ALLOWLISTS, _pack_timing
from tests.warm_tdm.adc_dsp.test_AdcDspFp import Bench, WRAPPER, signed


class IntegerBench(Bench):
    async def monitor(self):
        while True:
            await RisingEdge(self.d.clk)
            await Timer(2, unit='ns')
            self.cycles += 1
            if int(self.d.rst.value):
                continue
            if int(self.d.DAC_WR_VALID.value):
                self.writes.append((int(self.d.DAC_WR_ADDR.value), self.decode(int(self.d.DAC_WR_DATA.value))))
                self.write_cycles.append(self.cycles)
            if int(self.d.DEBUG_TVALID.value):
                self.frame.extend(int(self.d.DEBUG_TDATA.value).to_bytes(8, 'little'))
                if int(self.d.DEBUG_TLAST.value):
                    self.frames.append(self.formats.PidDebug.from_numpy(np.frombuffer(bytes(self.frame), dtype=np.uint8)))
                    self.frame.clear()
            if int(self.d.PID_TVALID.value) and int(self.d.PID_TKEEP.value):
                self.outputs.append((int(self.d.PID_TID.value), signed(int(self.d.PID_TDATA.value))))

    async def idle(self, **kwargs):
        for _ in range(self.rows + 40):
            if await self.read(0x34) == 0:
                return
        raise AssertionError('integer controller did not finish its visit/clear')

    async def integral(self, row=0):
        return signed(await self.read(0x2000 + 4*row), 18)

    async def count(self, row=0):
        return signed(await self.read(0x6000 + 4*row), 19)

    async def feedback(self, row=0):
        raw = await self.read(0x7000 + 8*row)
        raw |= (await self.read(0x7004 + 8*row)) << 32
        return Fraction(signed(raw, 38), 1 << 23), bool(raw & (1 << 38))

    async def error(self, row=0):
        return signed(await self.read(0x1000 + 4*row), 18)

    async def correction(self, row=0):
        raw = await self.read(0x3000 + 8*row)
        raw |= (await self.read(0x3004 + 8*row)) << 32
        return Fraction(signed(raw, 42), 1 << 23)

    async def change_i(self, value):
        await self.write(8, round(value * (1 << 23)) & 0xffffff)
        await self.idle()


async def setup(dut, p=Fraction(1, 4), i=Fraction(1, 8), d=0, q=2000):
    cocotb.start_soon(Clock(dut.clk, 8, unit='ns').start())
    dut.rst.value = 1
    for name in ('TIMING_RX_DATA', 'ACCUM_VALID', 'ACCUM_ERROR', 'ACCUM_NUM_SAMPLES',
                 'ACCUM_ROW_INDEX', 'ACCUM_SQ1FB_DAC', 'ACCUM_SEQ_START',
                 'ACCUM_DAQ_READOUT_START', 'DAC_STALL', 'DAC_FAIL'):
        getattr(dut, name).value = 0
    b = IntegerBench(dut)
    cocotb.start_soon(b.monitor())
    await b.clocks(5)
    dut.rst.value = 0
    dut.TIMING_RX_DATA.value = _pack_timing(running=1)
    await b.clocks(5)
    for address, value in ((4, p), (8, i), (12, d)):
        await b.write(address, round(value * (1 << 23)) & 0xffffff)
    shift = 16 + (q - 1).bit_length() if q else 0
    await b.write(0x48, (1 << shift) // q if q else 0)
    await b.write(0x4c, shift)
    await b.write(0x40, q)
    await b.idle()
    await b.write(0x50, 0)  # Shared monitor decodes FP debug; leave it disabled.
    await b.write(0, 1)
    await b.idle()
    return b


@cocotb.test()
async def masked_rows_hold_integral_feedback_and_count(dut):
    b = await setup(dut)
    all_rows = (1 << b.rows) - 1
    for row in (0, b.rows-1):
        await b.visit(error=1, row=row, seed=7862)
        assert await b.feedback(row) == (Fraction(23449, 4), True)  # 5862.25
        assert await b.integral(row) == 1
        assert await b.count(row) == 1
        await b.mask(all_rows ^ (1 << row))
        before = len(b.writes), len(b.outputs)
        for _ in range(3):
            await b.visit(error=4, row=row, seed=100)
        assert (len(b.writes), len(b.outputs)) == before
        assert await b.integral(row) == 1
        assert await b.feedback(row) == (Fraction(23449, 4), True)
        assert await b.count(row) == 1
        assert await b.error(row) == 4  # Telemetry still tracks masked visits.
        await b.mask(all_rows)
        await b.visit(error=0, row=row, seed=100)
        assert await b.feedback(row) == (Fraction(46899, 8), True)  # 5862.375
        assert b.writes[-1] == (row, 5862)


@cocotb.test()
async def masked_unseeded_rows_do_not_build_integral(dut):
    b = await setup(dut)
    row = b.rows - 1
    await b.mask(((1 << b.rows)-1) ^ (1 << row))
    for _ in range(3):
        await b.visit(error=4, row=row, seed=7862)
    assert not b.writes and not b.outputs
    assert await b.integral(row) == 0
    assert await b.feedback(row) == (0, False)
    assert await b.count(row) == 0
    await b.mask((1 << b.rows)-1)
    await b.visit(error=1, row=row, seed=123)
    assert await b.feedback(row) == (Fraction(493, 4), True)
    assert await b.integral(row) == 1


@cocotb.test()
async def i_changes_clear_only_integrals_and_preserve_unseeded_rows(dut):
    b = await setup(dut)
    for row, seed, error in ((0, 7862, 1), (b.rows-1, -7862, -1)):
        await b.visit(error=error, row=row, seed=seed)
    saved = {row: (await b.feedback(row), await b.count(row),
                   await b.error(row), await b.correction(row)) for row in (0, b.rows-1)}
    for new_i in (Fraction(1, 2), 0, -Fraction(1, 8)):
        await b.change_i(new_i)
        for row in (0, b.rows-1):
            assert await b.integral(row) == 0
            assert (await b.feedback(row), await b.count(row),
                    await b.error(row), await b.correction(row)) == saved[row]
        assert await b.feedback(1) == (0, False)
    # Preserve fractional carry and flux history even if the captured seed
    # changes. The first visit after changing axiI uses sumAccum=0, without reseeding.
    await b.visit(error=1, seed=100)
    assert await b.feedback() == (Fraction(11725, 2), True)  # 5862.5
    assert await b.integral() == 1
    assert await b.count() == 1
    await b.visit(error=1, seed=100)
    assert await b.feedback() == (Fraction(46901, 8), True)  # 5862.625
    assert b.writes[-1] == (0, 5863)
    await b.change_i(0)
    await b.visit(error=4)
    assert await b.integral() == 0
    assert await b.feedback() == (Fraction(46909, 8), True)


@cocotb.test()
async def same_i_preserves_integrals_and_derivative_history(dut):
    b = await setup(dut, p=0, d=Fraction(1, 4), q=0)
    await b.visit(error=4, seed=100)  # activeD*(lastAccumError-accumError)=-1, sumAccum=0
    assert await b.feedback() == (99, True)
    assert await b.integral() == 4
    await b.change_i(Fraction(1, 8))  # Same value must not clear sumAccum.
    assert await b.integral() == 4
    await b.visit(error=4)
    assert await b.feedback() == (Fraction(199, 2), True)  # 99 + .125*4
    await b.change_i(Fraction(1, 2))
    await b.visit(error=4)
    assert await b.feedback() == (Fraction(199, 2), True)  # activeD=0, sumAccum=0
    await b.visit(error=4)
    assert await b.feedback() == (Fraction(203, 2), True)


@cocotb.test()
async def in_flight_i_change_finishes_with_old_gain_then_clears(dut):
    b = await setup(dut, p=0)
    for row in (0, b.rows-1):
        await b.visit(error=4, row=row, seed=7863)
        assert await b.integral(row) == 4
        assert await b.feedback(row) == (5863, True)
        assert await b.count(row) == 1
    before = len(b.writes)
    await b.visit(error=4, settle=0)
    await b.write(8, 1 << 22)  # +.5; active visit must still use old +.125.
    await b.idle()
    await b.clocks(30)
    assert len(b.writes) == before + 1
    assert b.writes[-1] == (0, 5864)  # 5863.5, nearest even
    assert await b.feedback() == (Fraction(11727, 2), True)
    assert await b.count() == 1
    assert await b.integral() == await b.integral(b.rows-1) == 0
    await b.visit(error=4)
    assert await b.feedback() == (Fraction(11727, 2), True)
    await b.visit(error=4)
    assert await b.feedback() == (Fraction(11731, 2), True)


@cocotb.test()
async def disable_drains_visit_and_full_clear_still_reseeds(dut):
    b = await setup(dut, q=0)
    before = len(b.writes)
    await b.visit(error=1, seed=100, settle=0)
    await b.write(0, 0)
    await b.idle()
    await b.clocks(30)
    assert len(b.writes) == before + 1
    assert await b.feedback() == (Fraction(401, 4), True)
    await b.change_i(Fraction(1, 2))
    assert await b.feedback() == (Fraction(401, 4), True)
    assert await b.integral() == 0
    await b.visit(error=8)
    assert len(b.writes) == before + 1
    # Rising enable remains an explicit full-reseed boundary, like FP.
    await b.write(0, 1)
    await b.idle()
    assert await b.feedback() == (0, False)
    await b.visit(error=1, seed=200)
    assert await b.feedback() == (Fraction(801, 4), True)
    await b.write(0, 1)  # Same-value enable must not clear.
    await b.idle()
    assert await b.feedback() == (Fraction(801, 4), True)


@pytest.mark.parametrize('parameters', [
    {'ROW_ADDR_BITS_G': 3, 'INVERT_SQ1FB_G': True, 'USE_FLOAT_PID_G': False},
    {'ROW_ADDR_BITS_G': 8, 'INVERT_SQ1FB_G': False, 'USE_FLOAT_PID_G': False},
])
def test_AdcDsp_lifecycle(parameters):
    allowlists = copy.deepcopy(IMPORT_FILE_ALLOWLISTS)
    allowlists['warm_tdm'].add('AdcDspFp.vhd')
    run_warm_tdm_vhdl_test(
        test_file=__file__, toplevel='warm_tdm.adcdspfpcocotbwrapper',
        parameters=parameters, extra_env=parameters,
        extra_vhdl_sources={'unisim': ['tests/common/vhdl/unisim_vcomponents.vhd'],
                            'warm_tdm': [WRAPPER, 'tests/common/vhdl/FpPidModels.vhd']},
        import_library_allowlist={'surf', 'warm_tdm'},
        import_file_allowlists=allowlists, import_file_excludes=('*Tb*.vhd',))
