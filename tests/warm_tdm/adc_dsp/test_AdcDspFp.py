# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""FP controller regressions with real RAMs, DAC AXI writes and stream FIFOs.

Default: GHDL plus explicit test-only finite binary32 arithmetic models. This
qualifies control/state/transport, NOT generated Xilinx arithmetic or timing.
See docs/plans/pid-cosim-verification/FP_FIX_PLAN.md for vendor acceptance.
"""
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import struct
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotbext.axi import AxiLiteBus, AxiLiteMaster
import numpy as np
import pytest

from firmware.submodules.surf.tests.axi.utils import axil_read_u32, axil_write_u32
from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp.test_AdcDsp import IMPORT_FILE_ALLOWLISTS, _pack_timing

ROOT = Path(__file__).resolve().parents[3]
WRAPPER = 'firmware/common/warm_tdm/wrappers/AdcDspFpCocotbWrapper.vhd'


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def fp(value):
    return struct.unpack('<f', struct.pack('<I', value))[0]


def signed(value, width=32):
    value &= (1 << width) - 1
    return value - (1 << width) if value & (1 << (width - 1)) else value


class Bench:
    def __init__(self, dut):
        self.d = dut
        self.rows = 1 << int(os.environ.get('ROW_ADDR_BITS_G', 3))
        self.inverted = os.environ.get('INVERT_SQ1FB_G', 'True').lower() == 'true'
        self.axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, 'S_AXIL'), dut.clk, dut.rst)
        self.writes = []
        self.frames = []
        self.outputs = []
        self.frame = bytearray()
        self.cycles = 0
        self.write_cycles = []
        spec = importlib.util.spec_from_file_location('fp_test_formats', ROOT/'firmware/python/warm_tdm/_DataFormats.py')
        self.formats = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.formats
        spec.loader.exec_module(self.formats)

    def encode(self, value):
        return (int(value) & 0x3fff) ^ (0x1fff if self.inverted else 0x2000)

    def decode(self, code):
        return signed(code ^ (0x1fff if self.inverted else 0x2000), 14)

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
                    self.frames.append(self.formats.PidDebugFp.from_numpy(np.frombuffer(bytes(self.frame), dtype=np.uint8)))
                    self.frame.clear()
            if int(self.d.PID_TVALID.value) and int(self.d.PID_TKEEP.value):
                self.outputs.append((int(self.d.PID_TID.value), fp(int(self.d.PID_TDATA.value))))

    async def clocks(self, n):
        for _ in range(n):
            await RisingEdge(self.d.clk)
            await Timer(2, unit='ns')

    async def read(self, address):
        return await axil_read_u32(self.axil, address)

    async def write(self, address, value):
        await axil_write_u32(self.axil, address, value)

    async def write_fp(self, address, value):
        await self.write(address, bits(value))

    async def read_fp(self, address):
        return fp(await self.read(address))

    async def idle(self, *, dac=True):
        for _ in range(100):
            if (await self.read(0x34)) & (3 if dac else 1) == 0:
                return
        raise AssertionError('controller/DAC queue did not drain')

    async def gains(self, p=0.0, i=0.0):
        await self.write_fp(4, p)
        await self.write_fp(8, i)
        await self.idle()

    async def period(self, q):
        await self.write_fp(0x40, q)
        await self.write_fp(0x44, 1/q if q else 0)

    async def enable(self):
        await self.write(0, 1)
        await self.idle()

    async def visit(self, error=0, row=0, seed=0, settle=85):
        self.d.ACCUM_ERROR.value = error & 0xffffffff
        self.d.ACCUM_NUM_SAMPLES.value = 1
        self.d.ACCUM_ROW_INDEX.value = row
        self.d.ACCUM_SQ1FB_DAC.value = self.encode(seed)
        self.d.ACCUM_VALID.value = 1
        start = self.cycles
        await self.clocks(1)
        self.d.ACCUM_VALID.value = 0
        await self.clocks(settle)
        return start

    async def full(self, row=0):
        return await self.read_fp(0x3000 + 4*row)

    async def integral(self, row=0):
        return await self.read_fp(0x2000 + 4*row)

    async def count(self, row=0):
        return signed(await self.read(0x4000 + 4*row))

    async def mask(self, value):
        for offset in range(8):
            await self.write(0x60 + 4*offset, (value >> (32*offset)) & 0xffffffff)


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk, 8, unit='ns').start())
    dut.rst.value = 1
    for name in ('TIMING_RX_DATA', 'ACCUM_VALID', 'ACCUM_ERROR', 'ACCUM_NUM_SAMPLES',
                 'ACCUM_ROW_INDEX', 'ACCUM_SQ1FB_DAC', 'ACCUM_SEQ_START',
                 'ACCUM_DAQ_READOUT_START', 'DAC_STALL', 'DAC_FAIL'):
        getattr(dut, name).value = 0
    b = Bench(dut)
    cocotb.start_soon(b.monitor())
    await b.clocks(5)
    dut.rst.value = 0
    dut.TIMING_RX_DATA.value = _pack_timing(running=1)
    await b.clocks(5)
    await b.period(0)
    await b.write(0x50, 1)
    await b.enable()
    return b


@cocotb.test()
async def seeds_and_retains_fractional_feedback_per_row(dut):
    b = await setup(dut)
    await b.period(1024)
    for row, seed in ((0, 377), (b.rows-1, -1234)):
        start = await b.visit(row=row, seed=seed)
        assert await b.full(row) == seed
        assert b.outputs[-1] == (row, float(seed))
        j = round(seed/1024)
        assert await b.count(row) == j
        assert b.writes[-1] == (row, seed-j*1024)
        dut._log.info('Seed input-to-DAC latency: %d clocks', b.write_cycles[-1]-start)
        await b.visit(row=row, seed=55)
        assert await b.full(row) == seed
    await b.gains(p=.25)
    for n in range(1, 9):
        start = await b.visit(error=1, seed=0)
        assert await b.full() == 377+n*.25
        assert b.writes[-1] == (0, round(377+n*.25))
        assert b.frames[-1].fields['sq1FbNewFp'] == 377+n*.25
    dut._log.info('Steady input-to-DAC latency: %d clocks', b.write_cycles[-1]-start)
    assert await b.full(b.rows-1) == -1234


@cocotb.test()
async def masked_rows_hold_state_and_remain_unseeded(dut):
    b = await setup(dut)
    await b.gains(p=.25, i=.125)
    await b.mask(((1 << b.rows)-1) ^ 1)
    for _ in range(3):
        await b.visit(error=4, seed=123)
    assert await b.read(0x3000) == 0x7fc00000
    assert await b.integral() == 0
    assert await b.count() == 0
    assert b.writes == []
    assert await b.read_fp(0x1000) == 4
    await b.visit(error=4, row=b.rows-1, seed=50)
    assert await b.full(b.rows-1) == 51
    await b.mask((1 << b.rows)-1)
    await b.visit(error=4, seed=100)
    assert await b.full() == 101
    assert await b.integral() == 4
    await b.mask(((1 << b.rows)-1) ^ 1)
    saved_writes = len(b.writes)
    await b.visit(error=1000, seed=-100)
    assert await b.full() == 101
    assert await b.integral() == 4
    assert len(b.writes) == saved_writes
    await b.mask((1 << b.rows)-1)
    await b.visit(error=0, seed=-100)
    assert await b.full() == 101.5  # held I history, no masked corrections


@cocotb.test()
async def rounding_multi_quantum_and_large_excursion(dut):
    b = await setup(dut)
    await b.period(1024)
    for value in (511.5, 512, 512.5, 1536, -511.5, -512, -512.5, -1536, 10000, -10000):
        await b.write_fp(0x3000, value)
        await b.visit()
        j = round(value/1024)
        assert await b.full() == value
        assert await b.count() == j
        assert b.writes[-1] == (0, round(value-j*1024))
    for sign in (1, -1):
        base = sign * 256 * 1024
        await b.write_fp(0x3000, base)
        await b.gains(p=.25)
        for n in range(1, 9):
            await b.visit(error=sign)
            assert await b.full() == base + sign*n*.25
    # Q=0 must override even a stale reciprocal left by a raw client.
    await b.gains()
    await b.write_fp(0x40, 0)
    await b.write_fp(0x3000, 377)
    await b.visit()
    assert await b.count() == 0
    assert b.writes[-1] == (0, 377)


@cocotb.test()
async def clipping_tracks_applied_feedback_and_preserves_fraction(dut):
    b = await setup(dut)
    for sign, rail in ((1, 8191), (-1, -8192)):
        await b.gains(p=1)
        await b.write_fp(0x3000, sign*8100)
        for _ in range(3):
            start = await b.visit(error=sign*1000)
            assert await b.full() == rail
            assert b.outputs[-1] == (0, float(rail))
            assert b.frames[-1].fields['sq1FbNewFp'] == rail
            assert b.writes[-1] == (0, rail)
        dut._log.info('Clipped input-to-DAC latency: %d clocks', b.write_cycles[-1]-start)
        await b.visit(error=-sign*10)
        assert await b.full() == rail-sign*10
    await b.gains(p=.25)
    await b.write_fp(0x3000, 8190)
    await b.visit(error=1)
    assert await b.full() == 8190.25
    assert b.writes[-1] == (0, 8190)
    # Deliberately oversized raw period tests J*Q preservation during clipping.
    await b.gains()
    await b.period(32768)
    for value, expected, j in ((41768, 40959, 1), (-41768, -40960, -1)):
        await b.write_fp(0x3000, value)
        await b.visit()
        assert await b.full() == expected
        assert await b.count() == j
        assert b.outputs[-1] == (0, float(expected))


@cocotb.test()
async def integral_antiwindup_and_gain_change_lifecycle(dut):
    b = await setup(dut)
    await b.gains(p=1, i=.25)
    await b.visit(error=1000, seed=8100)
    assert await b.full() == 8191
    assert await b.integral() == 0
    await b.visit(error=-10)
    assert await b.full() == 8181
    assert await b.integral() == -10
    await b.gains(i=.125)
    await b.period(1024)
    await b.write_fp(0x3000, 1500.25)
    await b.visit(error=4)
    assert await b.integral() == 4
    assert await b.full() == 1500.25
    await b.visit(error=4, row=b.rows-1, seed=300)
    assert await b.integral(b.rows-1) == 4
    await b.write_fp(8, .125)  # identical writes do not reset
    await b.idle()
    assert await b.integral() == 4
    await b.visit(error=4, settle=0)
    await b.write_fp(8, .5)  # accepted visit uses its old coefficient snapshot
    await b.idle()
    assert await b.full() == 1500.75
    assert await b.count() == 1
    assert await b.integral() == 0
    assert await b.integral(b.rows-1) == 0
    await b.visit(error=4)
    assert await b.full() == 1500.75
    assert await b.integral() == 4
    await b.write(8, 0x80000000)  # -0 canonicalizes to disabled +0
    await b.idle()
    assert await b.read(8) == 0
    assert await b.integral() == 0
    await b.visit(error=200)
    assert await b.full() == 1500.75
    assert await b.integral() == 0


@cocotb.test()
async def full_clears_reseed_all_rows(dut):
    b = await setup(dut)
    for trigger in ('explicit', 'start', 'enable'):
        await b.visit(row=b.rows-1, seed=50)
        if trigger == 'explicit':
            await b.write(0x30, 1)
        elif trigger == 'start':
            dut.TIMING_RX_DATA.value = _pack_timing(running=1, startRun=1)
            await b.clocks(1)
            dut.TIMING_RX_DATA.value = _pack_timing(running=1)
        else:
            await b.write(0, 0)
            await b.idle()
            await b.write(0, 1)
        await b.idle()
        assert await b.read(0x3000+4*(b.rows-1)) == 0x7fc00000
        await b.visit(row=b.rows-1, seed=-77)
        assert await b.full(b.rows-1) == -77
        assert await b.integral(b.rows-1) == 0


@cocotb.test()
async def stalled_dac_writes_are_delivered_once_in_order(dut):
    b = await setup(dut)
    await b.gains(p=1)
    dut.DAC_STALL.value = 1
    for row in range(5):
        await b.visit(error=row+1, row=row, seed=row*100)
    assert not b.writes
    assert (await b.read(0x34)) & 2
    dut.DAC_STALL.value = 0
    await b.idle()
    assert b.writes == [(row, row*100+row+1) for row in range(5)]
    assert await b.read(0x88) == 0
    assert await b.read(0x8c) == 0
    dut.DAC_FAIL.value = 1
    await b.visit(error=1)
    await b.idle()
    assert await b.read(0x8c) == 1
    dut.DAC_FAIL.value = 0


@cocotb.test()
async def fifo_overflow_is_counted_and_busy_drains(dut):
    b = await setup(dut)
    await b.gains(p=1)
    dut.DAC_STALL.value = 1
    for _ in range(24):
        await b.visit(error=1)
    lost = await b.read(0x88)
    assert lost > 0
    assert await b.read(0x34) == 2
    dut.DAC_STALL.value = 0
    await b.idle()
    assert len(b.writes) + lost == 24
    assert b.writes == [(0, n) for n in range(1, len(b.writes)+1)]
    await b.write(0x38, 1)
    assert await b.read(0x88) == 0
    assert await b.read(0x34) == 0


@cocotb.test()
async def visit_loss_and_disable_drain_are_distinct(dut):
    b = await setup(dut)
    await b.gains(p=1)
    await b.visit(error=7, seed=100, settle=1)
    await b.visit(error=99, row=1, settle=0)
    await b.write(0, 0)
    await b.idle()
    assert b.writes == [(0, 107)]
    assert await b.read(0x80) == 1
    await b.visit(error=123)
    assert await b.read(0x84) == 1
    assert b.writes == [(0, 107)]
    await b.write(0x38, 1)
    assert await b.read(0x80) == 0
    assert await b.read(0x84) == 0


@pytest.mark.parametrize('parameters', [
    {'ROW_ADDR_BITS_G': 3, 'INVERT_SQ1FB_G': True},
    {'ROW_ADDR_BITS_G': 8, 'INVERT_SQ1FB_G': False},
])
def test_AdcDspFp(parameters):
    allowlists = copy.deepcopy(IMPORT_FILE_ALLOWLISTS)
    allowlists['warm_tdm'].add('AdcDspFp.vhd')
    if os.environ.get('WARM_TDM_SIM', 'ghdl') != 'ghdl':
        raise RuntimeError('Use firmware/simulations/AdcDspFpTb for generated-IP tests; the GHDL test models '
                           'must not be mistaken for Xilinx qualification.')
    run_warm_tdm_vhdl_test(
        test_file=__file__, toplevel='warm_tdm.adcdspfpcocotbwrapper',
        parameters=parameters, extra_env=parameters,
        extra_vhdl_sources={
            'unisim': ['tests/common/vhdl/unisim_vcomponents.vhd'],
            'warm_tdm': [WRAPPER, 'tests/common/vhdl/FpPidModels.vhd'],
        },
        import_library_allowlist={'surf', 'warm_tdm'},
        import_file_allowlists=allowlists, import_file_excludes=('*Tb*.vhd',),
    )
