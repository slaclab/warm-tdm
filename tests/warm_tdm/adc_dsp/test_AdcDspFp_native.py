# Warm TDM; subject to LICENSE.txt in the repository root.
"""Check the native vendor-acceptance bench locally with explicit FP models.

The generated-IP run is a separate Vivado target: firmware/simulations/AdcDspFpTb.
"""
import copy
import os
from pathlib import Path
import subprocess

from tests.common.regression_utils import build_vhdl_sources, COMMON_VHDL_COMPILE_ARGS
from tests.warm_tdm.adc_dsp.test_AdcDsp import IMPORT_FILE_ALLOWLISTS

ROOT = Path(__file__).resolve().parents[3]


def test_native_bench_with_models(tmp_path):
    allowlists = copy.deepcopy(IMPORT_FILE_ALLOWLISTS)
    allowlists['warm_tdm'].add('AdcDspFp.vhd')
    sources = build_vhdl_sources(
        os.environ.get('WARM_TDM_IMPORT_ROOT'), library_allowlist={'surf', 'warm_tdm'},
        file_allowlists=allowlists, file_excludes=('*Tb*.vhd',))
    sources = {'unisim': [str(ROOT/'tests/common/vhdl/unisim_vcomponents.vhd')], **sources}
    sources['warm_tdm'] += [str(ROOT/path) for path in (
        'tests/common/vhdl/FpPidModels.vhd',
        'firmware/common/warm_tdm/wrappers/AdcDspFpCocotbWrapper.vhd',
        'firmware/simulations/AdcDspFpTb/tb/AdcDspFpTb.vhd')]
    commands = [['ghdl', '-i', *COMMON_VHDL_COMPILE_ARGS, f'--work={lib}', *files]
                for lib, files in sources.items()]
    commands += [['ghdl', command, *COMMON_VHDL_COMPILE_ARGS,
                  '--work=warm_tdm', 'AdcDspFpTb'] for command in ('-m', '-r')]
    for command in commands:
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
    assert 'AdcDspFpTb PASSED' in result.stdout
