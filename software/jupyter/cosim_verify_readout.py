# ---
# jupyter:
#   jupytext:
#     text_representation:
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     name: python3
# ---

# %% [markdown]
# # Cosim: readout / PID-debug / masks / units (interactive)
#
# Interactive notebook version of `software/cosim/verify_cosim_readout.py`. It
# checks, through a `VirtualClient` against a running `warmTdmServer --sim`: a
# complete finite readout channel set, a populated PID-debug stream, exact
# dead-mask effect, config-derived units, repeated acquisitions, and acquisition
# ownership/interruption cleanup. See
# [`software/cosim/README_cosim.md`](../cosim/README_cosim.md).
#
# The script emits a JSON PASS/FAIL report; this notebook runs the same checks
# with `assert` + prints so you can inspect each capture. Real-link throughput /
# recovery and calibrated gains/noise still need hardware. Source-controlled as a
# percent-format `.py`; a generated `.ipynb` sits next to it.

# %% [markdown]
# ## Connect + config

# %%
# %run ../scripts/_setupLibPaths.py
# %matplotlib inline

import _thread
import threading
from types import SimpleNamespace

import numpy as np
import pyrogue.interfaces
import pyrogue.utilities.fileio
import warm_tdm
import warm_tdm_api.operations as ops
from warm_tdm_api.operations import StreamData
from warm_tdm_api.operations.unit_conversions import derive_fs, derive_sq1fb_to_pA

HOST, PORT = "localhost", 9099
ROWS = 2
NUM_PTS = 512
DAQ_READOUT = 1        # RowSequencesPerDaqReadout (1 so frames flush in short cosim runs)
ACQ = 30.0             # wall seconds per capture; increase for slow VCS
START_DELAY = 5.0
INTERRUPT_AFTER = 1.0
TEST_RAW = False       # add a raw ADC capture (can be slow in VCS)
RAW_TIMEOUT = 600.0
TIMING_TIMEOUT = 120.0

client = pyrogue.interfaces.VirtualClient(addr=HOST, port=PORT)
sess = ops.Session(client.root.Group,
                   output=SimpleNamespace(sessiondir="/tmp/cosim_readout"))
group = sess.group
cb = sess.coordinator_cb
tx = cb.WarmTdmCore.Timing.TimingTx
sess.status()


def wait_running(expected, timeout=TIMING_TIMEOUT):
    import time as _t
    end = _t.monotonic() + timeout
    while bool(tx.Running.get()) != expected:
        assert _t.monotonic() < end, f'Running did not become {expected} within {timeout}s'
        _t.sleep(0.1)

# %% [markdown]
# ## File inspector
#
# Decode a capture's frames (readout=ch9, PID-debug=ch0-7, config=ch255), being
# strict about corruption but tolerant of benign capture-boundary fragments, then
# validate the decoded channel set, PID channels and config-derived units.

# %%
def require_samples(data, expected):
    actual = {(int(col), int(row)) for col, rows in data.items()
              for row, values in rows.items() if len(values)}
    assert actual == expected, f'Channel mismatch: missing={expected-actual}, unexpected={actual-expected}'
    for col, row in expected:
        values = np.asarray(data[col][row])
        assert values.size > 0 and np.all(np.isfinite(values)), f'Invalid samples c{col}r{row}'


def inspect_file(path, expected, pid_expected, live_fs, live_scales):
    counts = dict(readout=0, readout_populated=0, pid=0, config=0)
    pid_offsize = {}
    with pyrogue.utilities.fileio.FileReader(files=[path]) as reader:
        for header, payload in reader.records():
            if header.channel == 9:
                assert len(payload) >= 32 and len(payload) % 8 == 0, 'Malformed readout frame'
                counts['readout'] += 1
                if len(payload) >= 40:
                    counts['readout_populated'] += 1
            elif header.channel in range(8):
                assert len(payload) % 8 == 0, 'Misaligned PID-debug frame'
                try:
                    warm_tdm.PidDebug.from_numpy(payload)
                except (ValueError, IndexError):
                    pid_offsize[header.channel] = pid_offsize.get(header.channel, 0) + 1
                    assert pid_offsize[header.channel] <= 2, 'Excess off-size PID-debug frames'
                else:
                    counts['pid'] += 1
            elif header.channel == 255:
                counts['config'] += 1
    assert all(counts.values()), f'Missing frame types: {counts}'
    stream = StreamData(path)
    require_samples(stream.data, expected)
    pid_pairs = {(int(c), int(r)) for c, rows in stream.pid.items() for r, fields in rows.items()
                 if fields and all(len(v) for v in fields.values())}
    assert pid_pairs == pid_expected, f'PID channel mismatch: {pid_pairs} vs {pid_expected}'
    for c, r in pid_pairs:
        assert all(np.all(np.isfinite(v)) for v in stream.pid[c][r].values()), 'Non-finite PID fields'
    assert bool(stream.config), 'No decodable embedded configuration'
    for col in live_scales:
        fs = derive_fs(stream.config, col)
        scale = derive_sq1fb_to_pA(stream.config, col)
        assert fs is not None and np.isfinite(fs) and fs > 0, 'Missing/invalid file sample rate'
        assert scale is not None and np.isfinite(scale) and scale != 0, 'Missing/invalid file calibration'
        np.testing.assert_allclose(fs, live_fs, rtol=1e-3)
        np.testing.assert_allclose(scale, live_scales[col], rtol=1e-3)
    return counts

# %% [markdown]
# ## Configure the MUX + baseline capture
#
# Enable all columns, set the row list, zero the PID coefficients (so readout is
# passive), and take a baseline capture with a complete channel set.

# %%
assert 2 <= ROWS <= int(group.MaxRows.get()), 'ROWS must be 2..Group.MaxRows'
assert NUM_PTS > 350, 'NUM_PTS must exceed the sample window (350)'
dsp = [cb.DataPath.AdcDsp[ch] for ch in range(sess.chans_per_board)]

# Save-for-restore set (the script's restore() list).
_vars = [group.ColEnableMask, group.RowReadoutOrder,
         tx.Mode, tx.RowPeriodCycles, tx.SampleStartTime, tx.SampleEndTime,
         tx.RowSequencesPerDaqReadout]
_vars += [rdd.Mode for rdd in sess.rdds.values()]
_vars += [getattr(d, name) for d in dsp for name in
          ['PidEnable', 'PidDebugEnable', 'RowEnableMask', 'P_Coef', 'I_Coef', 'D_Coef']]
_saved = [(v, v.get()) for v in _vars]

group.ColEnableMask.set((1 << sess.chans_per_board) - 1)
group.RowReadoutOrder.set(list(range(ROWS)))
sess.setup_mux(num_pts=NUM_PTS, enable_pid=True, enable_pid_debug=True)
# setup_mux leaves RowSequencesPerDaqReadout at 40 (a DAQ readout then never
# completes in a short cosim run). Shrink it BEFORE reading live_fs (DaqReadoutRate
# derives from it).
tx.RowSequencesPerDaqReadout.set(DAQ_READOUT)
for d in dsp:
    for name in ['P_Coef', 'I_Coef', 'D_Coef']:
        getattr(d, name).set(0.0)
    d.ClearPids()
    d.RowEnableMask.set((1 << 256) - 1)

expected = {(c, r) for c in range(sess.chans_per_board) for r in range(ROWS)}
live_fs = float(tx.DaqReadoutRate.get())
scales = {c: float(cb.AnalogFrontEnd.Channel[c].SQ1FbAmp.CurrentPerLsb.get()) * 1e6
          for c in range(sess.chans_per_board)}


def capture(label, channels):
    path = sess.take_data(ACQ, start_delay_sec=START_DELAY)
    wait_running(False)
    assert not sess.root.DataWriter.IsOpen.get(), 'Writer left open'
    counts = inspect_file(path, channels, expected, live_fs, scales)
    print(f"PASS: {label} -- {counts}, {len(channels)} channels")
    return path

# %%
capture('baseline readout, PID-debug and config-derived units', expected)

# %% [markdown]
# ## Exact dead-mask effect
#
# Mask two (col,row) channels and confirm exactly those drop out of the readout
# stream while every other channel remains.

# %%
masked = {(0, 0), (1, ROWS - 1)}
for col, row in masked:
    dsp[col].RowEnableMask.set(((1 << 256) - 1) ^ (1 << row))
    assert int(dsp[col].RowEnableMask.get()) == (((1 << 256) - 1) ^ (1 << row)), 'Mask register mismatch'
capture('exact dead-mask effect', expected - masked)
for d in dsp:
    d.RowEnableMask.set((1 << 256) - 1)
capture('unmasked repeated acquisition', expected)

# %% [markdown]
# ## Acquisition ownership + interruption cleanup
#
# A capture within a pre-existing run must leave that run running; an interrupted
# startup must clean up the writer and stop the run it started.

# %%
tx.StartRun()
wait_running(True)
sess.take_data(ACQ, start_delay_sec=START_DELAY)
assert bool(tx.Running.get()), 'take_data stopped a pre-existing run'
assert not sess.root.DataWriter.IsOpen.get(), 'Writer left open on pre-existing run'
tx.EndRun()
wait_running(False)
print("PASS: acquisition preserves pre-existing run ownership")

timer = threading.Timer(INTERRUPT_AFTER, _thread.interrupt_main)
timer.start()
try:
    try:
        sess.take_data(ACQ, start_delay_sec=INTERRUPT_AFTER + START_DELAY)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError('Injected interruption was not observed')
finally:
    timer.cancel()
    timer.join()
wait_running(False)
assert not sess.root.DataWriter.IsOpen.get(), 'Writer left open after interruption'
print("PASS: startup interruption cleanup through VirtualClient")
capture('acquisition restarts after interruption', expected)

# %% [markdown]
# ## (Optional) raw ADC capture

# %%
if TEST_RAW:
    path = sess.take_raw(0, timeout_sec=RAW_TIMEOUT, check_delay_sec=1.0)
    raw = np.load(path, allow_pickle=True).item()
    values = np.asarray(raw[0]['ADC Counts'][0])
    assert values.size > 0 and np.issubdtype(values.dtype, np.number) and np.all(np.isfinite(values)), \
        'Empty/non-finite raw waveform'
    print(f"PASS: raw ADC capture and decode -- shape {values.shape}")
else:
    print("skipped (TEST_RAW=False): raw capture can be slow in VCS")

# %% [markdown]
# ## Safe state
#
# Stop the run and restore the row list, timing settings, PID controls and masks.

# %%
tx.EndRun()
wait_running(False)
for v, val in reversed(_saved):
    v.set(val)
print("final state: timing stopped; row list, timing settings, PID controls and masks restored")
