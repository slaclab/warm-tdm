# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Exact multiple-wrap contract using real state RAM, streams and DAC writes."""
import copy
from fractions import Fraction
import random

import cocotb
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp.test_AdcDsp import IMPORT_FILE_ALLOWLISTS
from tests.warm_tdm.adc_dsp.test_AdcDspFp import WRAPPER
from tests.warm_tdm.adc_dsp.test_AdcDsp_lifecycle import setup

LSB = Fraction(1, 1 << 23)
COUNT_MIN, COUNT_MAX = -(1 << 18), (1 << 18) - 1


def reciprocal(q):
    shift = 16 + (q - 1).bit_length() if q else 0
    return ((1 << shift) // q, shift) if q else (0, 0)


def reference(candidate, count, q):
    excess = max(abs(candidate) - 7862, 0)
    # Exact rational ceiling, independent of the reciprocal approximation.
    n = -((-excess) // q) if q else 0
    jumps = n if candidate >= 0 else -n
    local = max(-8192, min(8191, candidate - jumps * q))
    total = max(COUNT_MIN, min(COUNT_MAX, count + jumps))
    return local, total


async def period(b, q):
    inverse, shift = reciprocal(q)
    await b.write(0x48, inverse)
    await b.write(0x4c, shift)
    await b.write(0x40, q)
    await b.idle()
    assert await b.read(0x40) == q
    assert await b.read(0x48) == inverse
    assert await b.read(0x4c) == shift


async def seed(b, row, full, count=0, integral=0):
    word = (int(full * (1 << 23)) & ((1 << 38)-1)) | (1 << 38)
    await b.write(0x7000 + 8*row, word & 0xffffffff)
    await b.write(0x7004 + 8*row, word >> 32)
    await b.write(0x6000 + 4*row, count & 0x7ffff)
    await b.write(0x2000 + 4*row, integral & 0x3ffff)


async def check(b, row, error, before, count, q, *, masked=False):
    nw, no, nf = len(b.writes), len(b.outputs), len(b.frames)
    start = await b.visit(error=error, row=row)
    correction = await b.correction(row)
    local, total = reference(before + correction, count, q)
    assert await b.feedback(row) == ((before if masked else local), True)
    assert await b.count(row) == (count if masked else total)
    assert len(b.frames) == nf + 1
    msg = b.frames[-1]
    assert msg.fields['sq1FbFull'] == local
    assert msg.fields['numFluxJumps'] == total
    if masked:
        assert len(b.writes) == nw and len(b.outputs) == no
    else:
        assert b.writes[nw:] == [(row, round(local))]
        assert b.outputs[no:] == [(row, round(local) + total*q)]
        # Includes the real command FIFO and AXI write master, with no stall.
        assert b.write_cycles[-1] - start <= 32
    return local, total


@cocotb.test()
async def exact_boundaries_and_wide_candidates(dut):
    b = await setup(dut, p=-1, i=0, q=1239)
    await b.write(0x50, 1)
    rng = random.Random(20260917)
    for q in (0, 1, 2, 3, 5, 107, 1005, 1239, 2000, 2001, 4096, 8191):
        await period(b, q)
        candidates = [Fraction(7862), Fraction(131072)]
        if q:
            candidates += [Fraction(7862+k*q) + offset
                           for k in (2, 17)
                           for offset in (-LSB, 0, LSB, Fraction(1, 2))
                           if 7862+k*q < 147000]
        candidates += [Fraction(rng.randrange(8000, 147000)) + LSB for _ in range(1)]
        for c in candidates:
            if c > 147455:
                continue  # Full MAC extrema are covered below.
            for row, sign in ((0, 1), (b.rows-1, -1)):
                candidate = sign*c
                # Make candidate using -error and a legal 38-bit feedback seed.
                error = -sign*min(131071, int(c))
                before = candidate + error
                await seed(b, row, before, sign*300)
                local, total = await check(b, row, error, before, sign*300, q)
                if q:
                    assert abs(local) <= 7862
                    assert local + total*q == candidate + sign*300*q

@cocotb.test()
async def full_mac_and_retained_ram_extrema(dut):
    b = await setup(dut, p=-1, i=0, q=1239)
    await b.write(0x50, 1)
    # Exercise pidResult and sq1FbFull extrema with 18-bit error/integral.
    await b.write(8, 0x800000)  # activeI=-1
    await b.idle()
    await b.write(12, 0x7fffff)  # activeD near +1 reaches both pidResult limits.
    for q in (1, 3, 1005, 1239, 8191):
        await period(b, q)
        for row, sign in ((0, 1), (b.rows-1, -1)):
            error = -131072 if sign > 0 else 131071
            before = 16384-LSB if sign > 0 else Fraction(-16384)
            await seed(b, row, before, 0, error)
            await b.write(0x1000 + 4*row, 0)  # lastAccumError=0
            await check(b, row, error, before, 0, q)
            expected_delta = 262144-LSB if sign > 0 else -262144
            assert await b.correction(row) == expected_delta


@cocotb.test()
async def correction_count_overflow_and_mask(dut):
    b = await setup(dut, p=-1, i=-1, q=1005)
    await b.write(0x50, 1)
    # Known reciprocal underestimate: excess=270349 leaves fluxCandidate=7867
    # before cleanup. The one correction restores the exact trigger window.
    for row, sign in ((0, 1), (b.rows-1, -1)):
        error = -131000 if sign > 0 else 131000
        before = sign*Fraction(16212)
        await seed(b, row, before, sign*1000, error)
        await check(b, row, error, before, sign*1000, 1005)

    await period(b, 1)
    for row, sign, count in ((0, 1, COUNT_MAX), (b.rows-1, -1, COUNT_MIN)):
        await b.write(0x30, 1)
        await b.idle()
        before = sign*Fraction(16000)
        error = -131000 if sign > 0 else 131000
        await seed(b, row, before, count, error)
        await b.mask(((1 << b.rows)-1) ^ (1 << row))
        for _ in range(3):
            await check(b, row, error, before, count, 1, masked=True)
            assert await b.integral(row) == error
            assert await b.read(0x54) & 1 == 0
        await b.mask((1 << b.rows)-1)
        await check(b, row, error, before, count, 1)
        assert await b.read(0x54) & 1 == 1
        await b.change_i(Fraction(-1, 2))
        assert await b.read(0x54) & 1 == 1  # Clearing sumAccum preserves the diagnostic.
        await b.change_i(-1)

    # Products near the signed int32 limits, using all 19 count bits.
    await b.write(8, 0)
    await b.idle()
    await period(b, 8191)
    for row, sign, count in ((0, 1, COUNT_MAX), (b.rows-1, -1, COUNT_MIN)):
        await seed(b, row, sign*7000, count)
        await check(b, row, 0, sign*7000, count, 8191)


@cocotb.test()
async def ordinary_wrap_registers_and_visit_snapshot(dut):
    b = await setup(dut, p=-1, i=0, q=1239)
    await b.write(0x50, 1)
    before = Fraction(123, 4)
    count = 1000
    await seed(b, 0, before, count)
    no, nw = len(b.outputs), len(b.writes)
    # An accepted visit keeps activeReciprocal even if axiReciprocal changes.
    # Raw writes are ordinary storage: no validation, staging or commit.
    await b.visit(error=-100000, settle=0)
    await b.write(0x48, 0)
    await b.idle()
    await b.clocks(50)
    local, total = reference(before + 100000, count, 1239)
    assert b.outputs[no:] == [(0, round(local) + total*1239)]
    assert b.writes[nw:] == [(0, round(local))]
    assert await b.read(0x48) == 0
    assert await b.read(0x40) == 1239
    # Configure the ordinary registers while stopped. A changed quantum
    # clears the old flux reference; an unchanged quantum preserves it.
    await b.write(0, 0)
    await b.idle()
    await period(b, 2000)
    assert await b.feedback() == (0, False)
    assert await b.count() == 0
    await b.write(0, 1)
    await b.idle()
    await b.visit(error=0, seed=101)
    saved = await b.feedback()
    await period(b, 2000)
    assert await b.feedback() == saved


@cocotb.test()
async def bounded_visit_schedule_and_dac_latency(dut):
    b = await setup(dut, p=0, i=0, q=1239)
    # The optional debug FIFO can pause diagnostics independently of control.
    # Measure accepted visits from DAC writes and the PID readout stream.
    await b.write(0x50, 0)
    for p, minimum in ((0, 16), (-1, 21)):
        await b.write(4, round(p*(1 << 23)) & 0xffffff)
        for spacing, accepted in ((minimum, 10), (minimum-1, 5)):
            await b.write(0x30, 1)
            await b.idle()
            await seed(b, 0, Fraction(0))
            nw, no, nf = len(b.writes), len(b.outputs), len(b.frames)
            starts = []
            for _ in range(10):
                starts.append(await b.visit(error=-100000, settle=spacing-1))
            await b.clocks(60)
            assert len(b.writes)-nw == accepted
            assert len(b.outputs)-no == accepted
            assert len(b.frames) == nf
            # visit() records the drive cycle; accumulation is accepted on
            # the next rising edge. Measure from that acceptance edge.
            latencies = [cycle-start-1 for cycle, start in
                         zip(b.write_cycles[nw:], starts[::10//accepted])]
            assert latencies == [minimum+4]*accepted
            dut._log.info('Integer P=%s spacing=%d accepted=%d/10 DAC latency=%s',
                          p, spacing, accepted, latencies)


@pytest.mark.parametrize('parameters', [
    {'ROW_ADDR_BITS_G': 3, 'INVERT_SQ1FB_G': True, 'USE_FLOAT_PID_G': False},
    {'ROW_ADDR_BITS_G': 8, 'INVERT_SQ1FB_G': False, 'USE_FLOAT_PID_G': False},
])
def test_AdcDsp_multi_flux(parameters):
    allowlists = copy.deepcopy(IMPORT_FILE_ALLOWLISTS)
    allowlists['warm_tdm'].add('AdcDspFp.vhd')
    run_warm_tdm_vhdl_test(
        test_file=__file__, toplevel='warm_tdm.adcdspfpcocotbwrapper',
        parameters=parameters, extra_env=parameters,
        extra_vhdl_sources={'unisim': ['tests/common/vhdl/unisim_vcomponents.vhd'],
                            'warm_tdm': [WRAPPER, 'tests/common/vhdl/FpPidModels.vhd']},
        import_library_allowlist={'surf', 'warm_tdm'},
        import_file_allowlists=allowlists, import_file_excludes=('*Tb*.vhd',))
