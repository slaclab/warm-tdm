# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Wire-format compatibility for retained integer SQ1 feedback diagnostics."""
import importlib.util
import math
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


formats = load('pid_data_formats', 'firmware/python/warm_tdm/_DataFormats.py')


def frame(version, full=-100.25):
    header = struct.pack('<4BIQ', 1, version, 0, 2, 0, 123456789)
    # Pack independently of the production dtype. Low 32-bit signed PID inputs
    # have zero padding; full feedback alone is sign-extended across its word.
    words = [3 | (255 << 8), (-17) & 0xffffffff, 8000,
             21, (-5) & 0xffffffff, 3 << 21,
             0xff, 8100 | (7 << 32), 16 | (99 << 32)]
    if version == 3:
        words[6] = 0xffffffff  # V3 sign-extends numFluxJumps to int32.
    if version >= 2:
        words.insert(6, int(full * (1 << 23)) & ((1 << 64) - 1))
    return header + struct.pack('<' + 'Q' * len(words), *words)


@pytest.mark.parametrize('version', [1, 2, 3])
def test_layout_versions_preserve_existing_fields(version):
    msg = formats.PidDebug.from_numpy(np.frombuffer(frame(version), dtype=np.uint8))
    assert msg.header.formatVersion == version
    assert (msg.header.boardId, msg.header.timestampNs, msg.col, msg.row) == (2, 123456789, 3, 255)
    expected = dict(accumError=-17, sumAccumError=21, diffAccumError=-5,
                    pidResult=3 << 21, sq1FbStart=8000, sq1FbEnd=8100,
                    numFluxJumps=-1, dropCount=7, numSamples=16, readoutCount=99)
    if version >= 2:
        expected['sq1FbFull'] = -100.25
    assert msg.fields == expected


@pytest.mark.parametrize('full', [-8192, 8191, -100.25, 100.25, -2**-23, 2**-23])
@pytest.mark.parametrize('version', [2, 3])
def test_full_feedback_sign_and_fraction(full, version):
    msg = formats.PidDebug.from_numpy(np.frombuffer(frame(version, full), dtype=np.uint8))
    assert msg.fields['sq1FbFull'] == full


@pytest.mark.parametrize('count', [-262144, -131073, -256, -129, -128, 127, 128, 255, 131072, 262143])
def test_v3_flux_count_preserves_expanded_range(count):
    raw = bytearray(frame(3))
    raw[72:76] = count.to_bytes(4, 'little', signed=True)
    msg = formats.PidDebug.from_numpy(np.frombuffer(raw, dtype=np.uint8))
    assert msg.fields['numFluxJumps'] == count


@pytest.mark.parametrize('raw', [
    frame(2)[:-8], frame(1) + bytes(8), frame(2) + frame(2), bytes(8),
    frame(2)[:1] + b'\x04' + frame(2)[2:],
    b'\x02' + frame(2)[1:],
])
def test_rejects_wrong_type_version_and_size(raw):
    with pytest.raises((ValueError, IndexError)):
        formats.PidDebug.from_numpy(np.frombuffer(raw, dtype=np.uint8))


def test_float_debug_layout_unchanged():
    raw = (struct.pack('<4BIQ', 2, 1, 0, 2, 0, 1000) +
           struct.pack('<QfffffiHBBI', 3 | (255 << 8), 1.5, -100.25, 2.5,
                       3.5, -101.75, -1, 8191, 16, 0, 7))
    assert len(raw) == formats.PID_DEBUG_FP_FRAME_BYTES == 56
    msg = formats.PidDebugFp.from_numpy(np.frombuffer(raw, dtype=np.uint8))
    assert msg.fields['sq1FbFullFp'] == -100.25
    assert msg.fields['numFluxJumps'] == -1
    assert msg.fields['sq1FbInt'] == 8191


def test_live_receiver_normalizes_all_versions_and_clears_missing_full():
    # Exercise the production process() using a memory-store fake; PyRogue is
    # not required on hosts running these offline format checks.
    pr = ModuleType('pyrogue')
    pr.Device = pr.DataReceiver = object
    pr.interfaces = ModuleType('pyrogue.interfaces')
    pr.interfaces.simulation = ModuleType('pyrogue.interfaces.simulation')
    with patch.dict(sys.modules, {
        'pyrogue': pr, 'pyrogue.interfaces': pr.interfaces,
        'pyrogue.interfaces.simulation': pr.interfaces.simulation,
        'warm_tdm': formats,
    }):
        debugger = load('pid_debugger', 'firmware/python/warm_tdm/_PidDebugger.py')
    row = SimpleNamespace(updateFromParser=Mock(), throttled=Mock(return_value=False))
    receiver = SimpleNamespace(
        col=3, mem=SimpleNamespace(_data={}), Sq1FbFull=SimpleNamespace(set=Mock()),
        LogicalRow=SimpleNamespace(get=Mock(return_value=255)),
        RowPids=SimpleNamespace(PID={255: row}), readBlocks=Mock(), checkBlocks=Mock())
    for version in (3, 2, 1):
        # process() now only enqueues; the synchronous decode/normalize path is
        # _handleRaw (run on the worker thread in production).
        debugger.PidDebugger._handleRaw(receiver, bytearray(frame(version)))
        normalized = bytearray(frame(1)[16:])
        normalized[48:52] = (-1).to_bytes(4, 'little', signed=True)
        assert bytes(receiver.mem._data[i] for i in range(72)) == normalized
        full = receiver.Sq1FbFull.set.call_args.args[0]
        assert full == -100.25 if version >= 2 else math.isnan(full)
    assert row.updateFromParser.call_count == 3
