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
# # Cosim: Group broadcast + DAC/FIR control checks (interactive)
#
# Interactive notebook version of `software/cosim/verify_cosim_controls.py`. It
# checks that Group broadcast leaves (LEDs, power-sync, cable resistance) fan out
# to every board, that `AllFastDacs` writes all override registers, and
# (optionally) the ADC FIR coefficient bank — all through a `VirtualClient`
# against a running `warmTdmServer --sim`. See
# [`software/cosim/README_cosim.md`](../cosim/README_cosim.md).
#
# The script emits a JSON PASS/FAIL report for CI; this notebook runs the same
# checks with `assert` + prints so you can inspect state between steps. Register
# values only — LED light, supply phase and analog filter response still need
# hardware. Source-controlled as a percent-format `.py`; a generated `.ipynb`
# sits next to it.

# %% [markdown]
# ## Connect + config

# %%
# %run ../scripts/_setupLibPaths.py
# %matplotlib inline

from types import SimpleNamespace

import numpy as np
import pyrogue.interfaces
import warm_tdm_api.operations as ops

HOST, PORT = "localhost", 9099
BROADCASTS_ONLY = False   # only test the Group broadcast controls
TEST_FIR = False          # also test the compiled-in ADC FIR bank (needs GEN_ADC_FILTER_G=true)
TIMING_TIMEOUT = 120.0

client = pyrogue.interfaces.VirtualClient(addr=HOST, port=PORT)
sess = ops.Session(client.root.Group,
                   output=SimpleNamespace(sessiondir="/tmp/cosim_controls"))
group = sess.group
sess.status()

# %% [markdown]
# ## Group broadcast leaves
#
# Drive `LedEnable`, `PowerSupplySynchronized` and `CableResistance`, and confirm
# each fans out to every board's leaves. Values are saved and restored around the
# checks (the notebook re-implements the script's `restore()` context manager
# with an explicit save/restore).

# %%
boards = list(sess.boards().values())
leds = [b.WarmTdmCore.WarmTdmCommon.WarmTdmConfig.LedEn for b in boards]
timing = [b.WarmTdmCore.Timing.TimingTx for b in boards]
ps = [getattr(tx, name) for tx in timing
      for name in ['PwrSyncA', 'PwrSyncB', 'PwrSyncC', 'PwrSyncEn']]
cables = sess.hwg.find(name='CableR$')
assert cables, 'No amplifier cable-resistance leaves found'

# Save for restore at the end of this cell.
_saved = [(v, v.get()) for v in leds + ps + cables]
try:
    for state in [False, True]:
        group.LedEnable.set(state)
        assert all(int(v.get()) == int(state) for v in leds), 'LED register fanout mismatch'
        group.PowerSupplySynchronized.set(state)
        for tx in timing:
            assert all(int(getattr(tx, n).get()) == (2 if state else 0)
                       for n in ['PwrSyncA', 'PwrSyncB', 'PwrSyncC']), 'Power-sync fanout mismatch'
            assert bool(tx.PwrSyncEn.get()) == state, 'Power-sync enable mismatch'
    for resistance in [120.0, 250.0]:
        group.CableResistance.set(resistance)
        assert all(float(v.get()) == resistance for v in cables), 'Cable resistance fanout mismatch'
    print(f"PASS: Group broadcast leaf writes fan out to {len(boards)} boards, "
          f"{len(cables)} cable leaves")
finally:
    for v, val in reversed(_saved):
        v.set(val)

# %% [markdown]
# ## AllFastDacs override registers
#
# `AllFastDacs(code)` should write the same code into every SQ1Fb / SAFb / SQ1Bias
# override register. Enable all columns first, then zero the DACs afterward.
# (Skipped if `BROADCASTS_ONLY`.)

# %%
if BROADCASTS_ONLY:
    print("skipped (BROADCASTS_ONLY): DAC override/zeroing and FIR registers")
else:
    cb = sess.coordinator_cb
    _saved_mask = (group.ColEnableMask, group.ColEnableMask.get())
    try:
        group.ColEnableMask.set((1 << sess.chans_per_board) - 1)
        try:
            for code in [8192, 9000]:
                cb.AllFastDacs(code)
                for name in ['SQ1Fb', 'SAFb', 'SQ1Bias']:
                    dev = getattr(cb, name)
                    actual = [int(dev.OverrideRaw[ch].get()) for ch in range(sess.chans_per_board)]
                    assert actual == [code] * sess.chans_per_board, f'{name} override RAM mismatch'
            print("PASS: AllFastDacs writes all override registers")
        finally:
            assert sess.stop_and_zero(settle_sec=TIMING_TIMEOUT), 'Final DAC zeroing failed'
    finally:
        _saved_mask[0].set(_saved_mask[1])
    print("final state: timing stopped, column DACs zeroed; broadcast settings restored")

# %% [markdown]
# ## (Optional) ADC FIR coefficient bank
#
# Only for a fixture built with `GEN_ADC_FILTER_G=true`. Sets the informational
# cutoff and checks cache-only vs committed coefficients on all channels against
# a `firwin` reference. Set `TEST_FIR = True` above to run.

# %%
if not TEST_FIR:
    print("skipped (TEST_FIR=False): FIR registers require GEN_ADC_FILTER_G=true")
else:
    cb = sess.coordinator_cb
    dev = cb.DataPath.AdcFilters
    from scipy.signal import firwin
    enabled = dev.enable.get()
    old_cutoff = dev.FilterCuttoffFreq.get()
    try:
        dev.enable.set(True)
        taps = [dev.FirFilter[ch].Taps for ch in range(sess.chans_per_board)]
        _saved_taps = [(v, np.asarray(v.get()).copy()) for v in taps]
        try:
            original = [np.asarray(v.get()).copy() for v in taps]
            for cutoff in [1e6, 5e6]:
                expected = firwin(len(original[0]), cutoff, fs=125e6, window='hamming')
                dev.FilterCuttoffFreq.set(cutoff, write=False)
                for v, previous in zip(taps, original):
                    np.testing.assert_allclose(v.get(read=False), expected, rtol=0, atol=5e-7)
                    np.testing.assert_allclose(v.get(), previous, rtol=0, atol=5e-7)
                dev.FilterCuttoffFreq.set(cutoff)
                for v in taps:
                    np.testing.assert_allclose(v.get(), expected, rtol=0, atol=5e-7)
                original = [np.asarray(v.get()).copy() for v in taps]
            print("PASS: FIR cache-only and committed coefficients on all channels")
        finally:
            for v, val in reversed(_saved_taps):
                v.set(val)
    finally:
        dev.FilterCuttoffFreq.set(old_cutoff, write=False)
        dev.enable.set(enabled)
