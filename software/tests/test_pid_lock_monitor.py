##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Independent wire fixtures exercise reconstruction, selection and history."""
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from pid_monitor_imports import load_package_exports

ROOT = Path(__file__).resolve().parents[2]


pr = ModuleType('pyrogue')
pr.Device = pr.DataReceiver = object
pr.interfaces = ModuleType('pyrogue.interfaces')
pr.interfaces.simulation = ModuleType('pyrogue.interfaces.simulation')
with patch.dict(sys.modules, {
        'pyrogue': pr, 'pyrogue.interfaces': pr.interfaces,
        'pyrogue.interfaces.simulation': pr.interfaces.simulation}):
    data = receiver = load_package_exports(
        'warm_tdm', ROOT / 'firmware/python/warm_tdm',
        {'_DataFormats', '_PidDebugger', '_PidDebuggerFp', '_PidLockMonitor'})
    history = load_package_exports(
        'warm_tdm_api.widgets', ROOT / 'software/python/warm_tdm_api/widgets', {'_pid_history'})


def decode_frame(raw):
    arr = np.frombuffer(raw, dtype=np.uint8)
    header = data.FrameHeader.from_numpy(arr)
    decoder = data.PidDebugFp if header.formatType == data.FormatType.PID_FLOAT else data.PidDebug
    return decoder.from_numpy(arr)


def sample_from_frame(raw, **kwargs):
    return data.pid_debug_sample(decode_frame(raw), **kwargs)


def fixed(full=100.25, count=0, timestamp=1_000_000_000, board=0, col=0, row=10, version=3, drops=0):
    header = struct.pack('<4BIQ', 1, version, 0, board, 0, timestamp)
    words = [col | row << 8, (-32) & 0xffffffff, 8191, 0, 0, 0,
             int(full * 2**23) & ((1 << 64) - 1), count & 0xffffffff,
             8191 | drops << 32, 16]
    return header + struct.pack('<10Q', *words)


def floating(full=1000.25, dac=-200, count=3, samples=16):
    return (struct.pack('<4BIQ', 2, 1, 0, 1, 0, 2_000_000_000) +
            struct.pack('<QfffffiHBBI', 2 | 12 << 8, 48.0, 987.0, 10.0, 11.0,
                        full, count, dac & 0x3fff, samples, 0, 9))


@pytest.mark.parametrize('count', [-262143, -1000, -256, -1, 0, 1, 255, 1000, 262142])
@pytest.mark.parametrize('wrapped', [-4000.25, 4000.25])
def test_integer_full_uses_net_count_without_gui_integration(count, wrapped):
    sample = sample_from_frame(fixed(wrapped, count), quantum=1200)
    assert sample[data.FULL] == wrapped + count * 1200
    assert sample[data.DAC] == round(wrapped)
    assert sample[data.ERROR] == -2
    assert sample[data.FLAGS] == 0


@pytest.mark.parametrize('direction', [-1, 1])
def test_wrap_boundary_is_continuous(direction):
    before = sample_from_frame(fixed(direction * 4499.75), quantum=2000)
    after = sample_from_frame(fixed(direction * 2500.25, direction), quantum=2000)
    assert after[data.FULL] - before[data.FULL] == direction * 0.5
    assert abs(after[data.DAC] - before[data.DAC]) == 2000


def test_fp_uses_post_visit_full_and_sign_extends_dac():
    sample = sample_from_frame(floating(), quantum=400)
    assert sample[data.FULL] == 1000.25  # Pre-visit full is 987.
    assert sample[data.DAC] == -200
    assert sample[data.JUMPS] == 3
    assert sample[data.ERROR] == 3
    assert sample[data.COLUMN] == 10
    assert sample[data.ROW] == 12


@pytest.mark.parametrize('raw', [fixed(count=-262144), fixed(count=262143), fixed(version=2)])
def test_incomplete_or_saturated_counts_do_not_claim_full_feedback(raw):
    sample = sample_from_frame(raw, quantum=1000)
    assert np.isnan(sample[data.FULL])
    assert np.isfinite(sample[data.DAC])
    assert int(sample[data.FLAGS]) & data.FULL_UNAVAILABLE


def test_masked_feedback_is_not_shown_as_applied_and_empty_error_is_nan():
    sample = sample_from_frame(floating(samples=0), quantum=400, committed=False)
    assert np.isnan(sample[[data.DAC, data.FULL, data.ERROR]]).all()
    assert int(sample[data.FLAGS]) & data.NOT_COMMITTED


@pytest.mark.parametrize('raw', [b'', fixed()[:-1], floating()[:-8], floating() + bytes(8),
                                  b'\x02\x02' + floating()[2:], b'\x03' + fixed()[1:]])
def test_rejects_invalid_frame(raw):
    with pytest.raises(ValueError):
        sample_from_frame(raw, quantum=400)


def test_zero_quantum_preserves_fractional_feedback():
    assert sample_from_frame(fixed(count=42), quantum=0)[data.FULL] == 100.25


def test_history_does_not_connect_across_missing_frames_or_clock_reset():
    h = history.PidHistory()
    for stamp, drops in [(1, 0), (1.1, 0), (1.2, 1), (2, 1)]:
        assert h.append(sample_from_frame(fixed(timestamp=int(stamp * 1e9), drops=drops), quantum=100))
    assert len(h.samples) == 6
    assert np.isnan(h.arrays()[2, data.DAC])
    assert np.isnan(h.arrays()[4, data.DAC])
    assert h.append(sample_from_frame(fixed(timestamp=500_000_000), quantum=100))
    assert len(h.samples) == 1
    assert h.arrays()[0, data.TIME] == 0


def test_history_bounded_selection_calibration_duplicates_and_invalid_samples():
    h = history.PidHistory(seconds=1, max_points=5)
    for stamp in range(20):
        h.append(sample_from_frame(fixed(timestamp=stamp * 100_000_000), quantum=100))
    assert len(h.samples) == 5
    assert not h.append(h.last)
    assert not h.append(np.full(data.SAMPLE_SIZE, np.nan))
    h.append(sample_from_frame(fixed(row=11, timestamp=2_000_000_000), quantum=100))
    assert len(h.samples) == 1
    h.append(sample_from_frame(fixed(row=11, timestamp=2_100_000_000), quantum=200))
    assert len(h.samples) == 1
    h.seconds = 0.05
    h.append(sample_from_frame(fixed(row=11, timestamp=2_200_000_000), quantum=200))
    assert len(h.samples) == 1


class Variable:
    def __init__(self, value):
        self.data = value
        self.updates = []

    def value(self):
        return self.data

    def set(self, value):
        self.data = value
        self.updates.append(value)



def row_device(row, dsp):
    return SimpleNamespace(debugDev=SimpleNamespace(_dsp=dsp), row=row,
                           _nextSampleAt=0, _sampleConfig=None, Sample=Variable(None))


def test_existing_rows_publish_independent_coherent_samples_and_throttle():
    dsp = SimpleNamespace(FluxQuantumRaw=Variable(2000), PidEnableRaw=Variable(True),
                          RowEnableMask=Variable((1 << 10) | (1 << 11)))
    rows = [row_device(row, dsp) for row in (10, 11)]
    with patch.object(receiver.time, 'monotonic', return_value=1):
        for row in rows:
            msg = decode_frame(fixed(full=4499.75, row=row.row))
            receiver.PidRowDebuggerBase.updateSample(row, msg)
            # A later frame within the display interval cannot mutate the snapshot.
            msg.fields['sq1FbFull'] = 2500.25
            msg.fields['numFluxJumps'] = 1
            receiver.PidRowDebuggerBase.updateSample(row, msg)
            assert len(row.Sample.updates) == 1
            assert row.Sample.value()[data.FULL] == 4499.75
        # A config change must not leave the plot claiming masked feedback applied.
        dsp.RowEnableMask.set(0)
        receiver.PidRowDebuggerBase.updateSample(rows[1], msg)
        assert int(rows[1].Sample.value()[data.FLAGS]) & data.NOT_COMMITTED
        dsp.RowEnableMask.set(1 << 10)
    with patch.object(receiver.time, 'monotonic', return_value=1.11):
        msg = decode_frame(fixed(full=2500.25, count=1, timestamp=1_110_000_000))
        receiver.PidRowDebuggerBase.updateSample(rows[0], msg)
        assert rows[0].Sample.value()[data.FULL] == 4500.25
        assert rows[0].Sample.value()[data.TIME] == pytest.approx(1.11)
        assert rows[0].Sample.updates[0][data.FULL] == 4499.75


def test_row_without_dsp_preserves_diagnostics_and_still_throttles():
    row = row_device(10, None)
    with patch.object(receiver.time, 'monotonic', return_value=1):
        for _ in range(2):
            receiver.PidRowDebuggerBase.updateSample(row, decode_frame(fixed()))
    assert len(row.Sample.updates) == 1
    sample = row.Sample.value()
    assert np.isnan(sample[data.FULL])
    assert sample[data.ERROR] == -2


def test_selector_forwards_whole_snapshot_and_ignores_other_rows_columns():
    node = SimpleNamespace(ColumnSelect=Variable(11), RowSelect=Variable(10),
                           _selection=(11, 10), Sample=Variable(None), Status=Variable(''))
    node._selectionChanged = lambda *args: receiver.PidLockMonitor._selectionChanged(node, *args)
    for board, col, row in [(0, 3, 10), (1, 2, 10), (1, 3, 11)]:
        sample = sample_from_frame(fixed(board=board, col=col, row=row), quantum=2000)
        receiver.PidLockMonitor._sampleChanged(node, '', SimpleNamespace(value=sample))
    assert not node.Sample.updates
    sample = sample_from_frame(fixed(full=2500.25, count=1, board=1, col=3), quantum=2000)
    receiver.PidLockMonitor._sampleChanged(node, '', SimpleNamespace(value=sample))
    assert node.Sample.value() is sample  # No rebuilding from separately read scalars.
    node.RowSelect.set(11)
    # Even a delayed callback for the old selection cannot restore the old sample.
    receiver.PidLockMonitor._sampleChanged(node, '', SimpleNamespace(value=sample))
    assert np.isnan(node.Sample.value()).all()
    assert node.Status.value() == 'Waiting for PID-debug frames'


def test_v1_preserves_time_error_and_count_without_claiming_feedback():
    raw = fixed(version=1)
    raw = raw[:64] + raw[72:]  # V1 omits the fractional feedback word.
    sample = sample_from_frame(raw, quantum=2000)
    assert np.isnan(sample[[data.DAC, data.FULL]]).all()
    assert sample[data.TIME] == 1
    assert sample[data.ERROR] == -2
    assert int(sample[data.FLAGS]) & data.FULL_UNAVAILABLE


@pytest.mark.parametrize('quantum', [-1, 8192, float('nan')])
def test_invalid_quantum_withholds_integer_full_without_discarding_diagnostics(quantum):
    sample = sample_from_frame(fixed(), quantum=quantum)
    assert np.isnan(sample[data.FULL])
    assert sample[data.DAC] == 100
    assert int(sample[data.FLAGS]) & data.FULL_UNAVAILABLE


def test_history_keeps_diagnostics_when_wrap_period_is_unknown():
    h = history.PidHistory()
    for stamp in (1_000_000_000, 1_100_000_000):
        assert h.append(sample_from_frame(fixed(timestamp=stamp), quantum=float('nan')))
    assert len(h.samples) == 2
    assert np.isnan(h.arrays()[:, data.FULL]).all()
    assert (h.arrays()[:, data.ERROR] == -2).all()


def test_histories_share_a_reference_without_shifting_stale_channels_to_present():
    first = history.PidHistory()
    second = history.PidHistory()
    first.append(sample_from_frame(fixed(timestamp=1_000_000_000), quantum=1200))
    second.append(sample_from_frame(fixed(timestamp=2_000_000_000), quantum=1200))
    assert first.arrays(reference=2.0)[0, data.TIME] == -1.0
    assert second.arrays(reference=2.0)[0, data.TIME] == 0.0
    assert first.last[data.TIME] == 1.0  # Rendering never changes stored hardware time.
