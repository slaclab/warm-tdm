# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Exercise the integer controller's shared DAC delivery fix under AXI stalls."""
import copy

import cocotb
from cocotb.clock import Clock
import pytest

from tests.common.regression_utils import run_warm_tdm_vhdl_test
from tests.warm_tdm.adc_dsp.test_AdcDsp import IMPORT_FILE_ALLOWLISTS, _pack_timing
from tests.warm_tdm.adc_dsp.test_AdcDspFp import Bench, WRAPPER


@cocotb.test()
async def queued_integer_dac_writes_survive_stalls(dut):
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
    await b.write(4, 1 << 22)  # exact +0.5 in Q1.23
    await b.write(8, 0)
    await b.write(12, 0)
    await b.write(0x40, 0)
    await b.write(0x50, 0)
    await b.write(0, 1)
    await b.clocks(b.rows+40)
    dut.DAC_STALL.value = 1
    for row in range(5):
        await b.visit(error=2*(row+1), row=row, seed=100*row)
    assert not b.writes
    dut.DAC_STALL.value = 0
    await b.clocks(150)
    assert b.writes == [(row, 100*row+row+1) for row in range(5)]


@pytest.mark.parametrize('parameters', [
    {'ROW_ADDR_BITS_G': 3, 'INVERT_SQ1FB_G': True, 'USE_FLOAT_PID_G': False},
    {'ROW_ADDR_BITS_G': 8, 'INVERT_SQ1FB_G': False, 'USE_FLOAT_PID_G': False},
])
def test_AdcDsp_delivery(parameters):
    allowlists = copy.deepcopy(IMPORT_FILE_ALLOWLISTS)
    allowlists['warm_tdm'].add('AdcDspFp.vhd')
    run_warm_tdm_vhdl_test(
        test_file=__file__, toplevel='warm_tdm.adcdspfpcocotbwrapper',
        parameters=parameters, extra_env=parameters,
        extra_vhdl_sources={'unisim': ['tests/common/vhdl/unisim_vcomponents.vhd'],
                            'warm_tdm': [WRAPPER, 'tests/common/vhdl/FpPidModels.vhd']},
        import_library_allowlist={'surf', 'warm_tdm'},
        import_file_allowlists=allowlists, import_file_excludes=('*Tb*.vhd',))
