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
# # Cosim: reduced SA / SQ1 tuning (interactive)
#
# Interactive notebook version of `software/cosim/verify_cosim_tuning.py`. It
# exercises the reduced SA-offset / SA-tune / SQ1-tune processes on a configured
# sensor fixture through a `VirtualClient` against a running
# `warmTdmServer --sim`, validating that each produces complete, finite,
# non-flat modeled curves with a selected operating point. See
# [`software/cosim/README_cosim.md`](../cosim/README_cosim.md).
#
# The script emits a JSON PASS/FAIL report; this notebook runs the same processes
# and **plots** the reduced curves so you can eyeball the modeled response.
# Model convergence only — real SQUID gain/noise/stability remain on Issue #68.
# Source-controlled as a percent-format `.py`; a generated `.ipynb` sits next to
# it.

# %% [markdown]
# ## Connect + profile
#
# The profile is the same JSON the script takes (`--profile`), inlined here as an
# editable dict. It names the columns/rows and the reduced sweep parameters for
# each process. Edit for your fixture; `cosim_tuning.example.json` in
# `software/cosim/` is a worked example.

# %%
# %run ../scripts/_setupLibPaths.py
# %matplotlib inline

import time
from types import SimpleNamespace

import numpy as np
import matplotlib.pyplot as plt
import pyrogue.interfaces
import warm_tdm_api.operations as ops

HOST, PORT = "localhost", 9099
PROCESS_TIMEOUT = 600.0
TIMING_TIMEOUT = 120.0

# Reduced tuning profile (mirror software/cosim/cosim_tuning.example.json).
PROFILE = {
    "columns": [0],
    "rows": [0, 1],
    "sa_offset": {},
    "sa_tune": {"SaFbNumSteps": 32, "SaBiasNumSteps": 1,
                "SaFbLowOffset": 0.0, "SaFbHighOffset": 100.0},
    "sq1_tune": {"Sq1FbNumSteps": 32, "Sq1BiasNumSteps": 1,
                 "Sq1FbLowOffset": -30.0, "Sq1FbHighOffset": 30.0,
                 "ServoDisable": False},
    "minimum_curve_span": {"sa": 0.05, "sq1": 0.05},
}

client = pyrogue.interfaces.VirtualClient(addr=HOST, port=PORT)
sess = ops.Session(client.root.Group,
                   output=SimpleNamespace(sessiondir="/tmp/cosim_tuning"))
group = sess.group
sess.status()

# %% [markdown]
# ## Validate the profile + set the enabled set
#
# Bound the sweeps (feedback 5..64 steps, bias 1..4) and pick the columns/rows.

# %%
cols, rows = PROFILE['columns'], PROFILE['rows']
assert cols and len(set(cols)) == len(cols) and all(
    isinstance(c, int) and 0 <= c < sess.chans_per_board for c in cols), 'Invalid columns'
assert rows and len(set(rows)) == len(rows) and all(
    isinstance(r, int) and 0 <= r < int(group.MaxRows.get()) for r in rows), 'Invalid rows'
assert len(cols) <= 2 and len(rows) <= 2, 'Use at most two columns and rows for reduced sweeps'
for params, prefix in [(PROFILE['sa_tune'], 'Sa'), (PROFILE['sq1_tune'], 'Sq1')]:
    assert 5 <= params[prefix+'FbNumSteps'] <= 64 and 1 <= params[prefix+'BiasNumSteps'] <= 4, \
        'Profile must bound feedback (5..64) and bias (1..4) steps'
assert PROFILE['sq1_tune'].get('ServoDisable', False) is False, \
    'ServoDisable must be false for the closed-loop SQ1 check'
spans = PROFILE['minimum_curve_span']

# Save the enabled-set vars for restore at the end.
_saved = [(v, v.get()) for v in (group.ColEnableMask, group.RowReadoutOrder)]
group.ColEnableMask.set(sum(1 << c for c in cols if 0 <= c < sess.chans_per_board))
group.RowReadoutOrder.set(rows)
print(f"cols {cols} rows {rows} enabled")


def check_curve(curve, points, biases, minimum_span):
    """Assert one reduced sweep is complete, finite, non-flat, with an op point."""
    x = np.asarray(curve['xValues'], dtype=float)
    y = np.asarray(curve['curves'], dtype=float)
    bias = np.asarray(curve['biasValues'], dtype=float)
    assert x.shape == (points,) and y.shape == (biases, points) and bias.shape == (biases,), \
        f'Incomplete sweep: x={x.shape}, curves={y.shape}, biases={bias.shape}'
    assert np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and np.all(np.isfinite(bias)), \
        'Non-finite sweep data'
    assert np.any(np.ptp(y, axis=1) > minimum_span), 'Sweep lacks required modeled response'
    assert all(curve.get(k) is not None and np.isfinite(float(curve[k]))
               for k in ['xOut', 'yOut', 'biasOut']), 'Missing/non-finite operating point'
    idx = curve.get('bestIndex')
    assert isinstance(idx, (int, np.integer)) and 0 <= idx < biases, 'Invalid best-curve selection'

# %% [markdown]
# ## SA offset
#
# Runs the SA-offset servo and confirms it nulls the modeled SA ADC output below
# the process precision.

# %%
sa_off = sess.run_process('SaOffsetProcess', timeout_sec=PROCESS_TIMEOUT, poll_sec=0.5,
                          **PROFILE['sa_offset'])
values = np.asarray(sa_off)
assert values.shape == (sess.chans_per_board,) and np.all(np.isfinite(values[cols])), \
    'Invalid SA offset result'
residual = np.asarray(group.SaOutAdc.get())[cols]
precision = float(group.SaOffsetProcess.Precision.get())
assert np.all(np.isfinite(residual)) and np.all(np.abs(residual) < precision), \
    'SA offset did not null modeled ADC output'
print(f"PASS: SA offset nulled; residual {residual} < precision {precision}")

# %% [markdown]
# ## SA tune
#
# Sweeps SA bias/feedback and picks a lock point per column. Validate then plot.

# %%
sa_tune = sess.run_process('SaTuneProcess', timeout_sec=PROCESS_TIMEOUT, poll_sec=0.5,
                           **PROFILE['sa_tune'])
p = PROFILE['sa_tune']
assert len(sa_tune) == sess.chans_per_board, 'Missing SA column results'
for c in cols:
    check_curve(sa_tune[c], p['SaFbNumSteps'], p['SaBiasNumSteps'], spans['sa'])
print(f"PASS: SA tune curves complete for cols {cols}")

plt.figure(figsize=(9, 5))
for c in cols:
    x = np.asarray(sa_tune[c]['xValues'], dtype=float)
    for row_curve in np.asarray(sa_tune[c]['curves'], dtype=float):
        plt.plot(x, row_curve, alpha=0.8, label=f"col {c}")
plt.xlabel("SA FB"); plt.ylabel("SA out"); plt.title("SA tune (reduced)")
plt.grid(True, alpha=0.3); plt.legend(); plt.tight_layout()

# %% [markdown]
# ## SQ1 tune
#
# Runs after the SA lock. Sweeps SQ1 feedback per row; validate then plot.

# %%
sq1_tune = sess.run_process('Sq1TuneProcess', timeout_sec=PROCESS_TIMEOUT, poll_sec=0.5,
                            **PROFILE['sq1_tune'])
p = PROFILE['sq1_tune']
assert len(sq1_tune) == len(rows), 'Missing SQ1 row results'
for row_result in sq1_tune:  # stored in requested row-list order
    assert len(row_result) == sess.chans_per_board, 'Missing SQ1 column results'
    for c in cols:
        check_curve(row_result[c], p['Sq1FbNumSteps'], p['Sq1BiasNumSteps'], spans['sq1'])
print(f"PASS: SQ1 tune curves complete for {len(rows)} row(s), cols {cols}")

plt.figure(figsize=(9, 5))
for ri, row_result in enumerate(sq1_tune):
    for c in cols:
        x = np.asarray(row_result[c]['xValues'], dtype=float)
        for row_curve in np.asarray(row_result[c]['curves'], dtype=float):
            plt.plot(x, row_curve, alpha=0.8, label=f"c{c} r{rows[ri]}")
plt.xlabel("SQ1 FB"); plt.ylabel("SA out"); plt.title("SQ1 tune (reduced)")
plt.grid(True, alpha=0.3); plt.legend(); plt.tight_layout()

# %% [markdown]
# ## Safe state
#
# Deactivate rows, stop/zero, and restore the enabled set.

# %%
for name in ['SaOffsetProcess', 'SaTuneProcess', 'Sq1TuneProcess']:
    proc = getattr(group, name)
    if proc.Running.get():
        proc.Stop()
for row in rows:
    group.ManualRowOff(row)
group.ColEnableMask.set((1 << sess.chans_per_board) - 1)
assert sess.stop_and_zero(settle_sec=TIMING_TIMEOUT), 'Final stop/zero failed'
for v, val in reversed(_saved):
    v.set(val)
print("final state: rows deactivated, timing stopped, column outputs zeroed; settings restored")
