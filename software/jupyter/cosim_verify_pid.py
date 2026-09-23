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
# # Cosim: closed-loop PID behavior + performance (interactive)
#
# Interactive notebook version of `software/cosim/verify_cosim_pid.py`. It locks
# the muxed SQ1-FB servo with **real (nonzero) gains** and measures its behavior
# from the per-visit PID-debug stream — for BOTH the integer `AdcDsp` and
# floating-point `AdcDspFp` controllers (auto-detected). Runs through a
# `VirtualClient` against a live `warmTdmServer --sim`. See
# [`software/cosim/README_cosim.md`](../cosim/README_cosim.md) for the recipe and
# `software/cosim/run_cosim_pid_suite.py` for the turnkey both-builds runner.
#
# Behaviors: **steady** (lock + steady-state residual), **step** (TesBias
# disturbance rejection), **flux** (opt-in TesBias ramp through flux quanta,
# best-effort). The script emits a JSON PASS/FAIL report; this notebook runs the
# same lock recipe + metrics with prints/plots so you can tune by hand. The
# gains/thresholds are model+build specific (23 µA sinusoid-blend build), NOT
# physics. Source-controlled as a percent-format `.py`; a generated `.ipynb` sits
# next to it.

# %% [markdown]
# ## Connect + config

# %%
# %run ../scripts/_setupLibPaths.py
# %matplotlib inline

import os
import time
from types import SimpleNamespace

import numpy as np
import matplotlib.pyplot as plt
import pyrogue.interfaces
import warm_tdm_api.operations as ops
from warm_tdm_api.operations import StreamData
from warm_tdm_api.operations.pid_analysis import pid_metrics

HOST, PORT = "localhost", 9099
COL = 0
ROWS = 8
PATH = 'auto'           # 'auto' | 'integer' | 'float'
BEHAVIORS = ['steady', 'step']   # add 'flux' for the (opt-in) ramp
NUM_PTS = 400           # RowPeriodCycles
SAMPLE_NUM = 20         # samples per row window
DAQ_READOUT = 1         # RowSequencesPerDaqReadout (frames flush in short cosim runs)
SEED_TUNE_POINTS = True  # SetCosimTunePoints() first (fresh-sim fixture)
SETTLE = 5.0            # start_delay before each capture
ACQ = 20.0              # wall seconds per capture
PRIME = 5.0             # throwaway priming capture after run_mux
LOCK_SETTLE = 15.0      # let the servo converge before the steady-state capture
CAPTURE_RETRIES = 5     # re-take until the PID stream is non-empty
STEP_uA = None          # None => profile default (500 uA)
FLUX_STEPS = 6
FLUX_STEP_uA = 20.0
DEADBAND = None

# Built-in per-path defaults (RAW hardware coefficients, sign included).
# Re-tuned 2026-09-21 via a closed-loop AXI-AccumError sweep at Sq1Bias=50/
# Sq1Fb=2/SaFb=9 (SampleCount=20). See the script's DEFAULTS for the rationale.
DEFAULTS = {
    'integer': dict(
        sq1fb_uA=2.0, sq1bias_uA=50.0, safb_uA=9.0, flux_quantum_uA=23.0,
        gains=dict(p_raw=-0.010, i_raw=0.0, d_raw=0.0, use_group_gain=True),
        step_uA=500.0, thresholds=dict(residual_max=800.0, flux_jump_max=0)),
    'float': dict(
        sq1fb_uA=2.0, sq1bias_uA=50.0, safb_uA=9.0, flux_quantum_uA=23.0,
        gains=dict(p_raw=-0.005, i_raw=-1e-5, d_raw=0.0, use_group_gain=True),
        step_uA=500.0, thresholds=dict(residual_max=700.0, flux_jump_max=1)),
}

# The output dir must exist at this exact absolute path -- DataWriter files are
# created server-side (server + client share the host here). Create it explicitly
# and pass it as the session dir, as _cosim_common.run does for the scripts.
OUTPUT_DIR = "/tmp/cosim_pid"
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = pyrogue.interfaces.VirtualClient(addr=HOST, port=PORT)
sess = ops.Session(client.root.Group,
                   output=SimpleNamespace(sessiondir=OUTPUT_DIR))
group = sess.group
cb = sess.coordinator_cb
tx = cb.WarmTdmCore.Timing.TimingTx
dsp = cb.DataPath.AdcDsp[COL]
rows = list(range(ROWS))
sess.status()

# %% [markdown]
# ## Detect the controller path + resolve the profile

# %%
def detect_path(dsp):
    if hasattr(dsp, 'D_Coef') and hasattr(dsp, 'Sq1FbFullValid'):
        return 'integer'
    if hasattr(dsp, 'P_Coef') and hasattr(dsp, 'I_Coef') and not hasattr(dsp, 'D_Coef'):
        return 'float'
    raise AssertionError('Cannot classify AdcDsp path (unexpected coefficient set)')

path = detect_path(dsp) if PATH == 'auto' else PATH
cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULTS[path].items()}
if STEP_uA is not None:
    cfg['step_uA'] = STEP_uA
print(f"controller path: {path}; gains {cfg['gains']}; thresholds {cfg['thresholds']}")

# %% [markdown]
# ## Lock helpers
#
# `apply_gains` writes the raw coefficients via the right interface for the path;
# `apply_lock` is the full recipe (seed op point → FluxQuantum → SA null →
# setup_mux → gains → run → prime → settle). `capture_data` re-takes until the
# PID-debug stream is non-empty (the cosim DataWriter tees data only
# intermittently).

# %%
def apply_gains(gains):
    n = int(tx.SampleCount.get())            # normalized = raw * SampleCount
    if path == 'integer':
        sess.set_pid(p=gains['p_raw'] * n, i=gains['i_raw'] * n,
                     d=gains['d_raw'] * n, cols=[COL])
        return dict(interface='set_pid', p_norm=gains['p_raw'] * n, i_norm=gains['i_raw'] * n)
    if gains.get('use_group_gain', True) and hasattr(group, 'PidP_Gain'):
        group.PidP_Gain.set(value=gains['p_raw'] * n, index=COL)
        group.PidI_Gain.set(value=gains['i_raw'] * n, index=COL)
        return dict(interface='group_gain', p_norm=gains['p_raw'] * n, i_norm=gains['i_raw'] * n)
    dsp.P_Coef.set(float(gains['p_raw']))
    dsp.I_Coef.set(float(gains['i_raw']))
    return dict(interface='raw_coef', p_raw=gains['p_raw'], i_raw=gains['i_raw'])


def apply_lock():
    if SEED_TUNE_POINTS:
        group.SetCosimTunePoints()
    dsp.PidEnable.set(False)
    dsp.FluxQuantum.set(cfg['flux_quantum_uA'])
    group.RowReadoutOrder.set(list(range(ROWS)))
    for r in range(ROWS):
        group.Sq1BiasCurrent.set(index=(COL, r), value=cfg.get('sq1bias_uA', 50.0))
        group.Sq1FbCurrent.set(index=(COL, r), value=cfg['sq1fb_uA'])
        group.SaFbCurrent.set(index=(COL, r), value=cfg.get('safb_uA', 9.0))
    sess.sa_offset()
    sess.setup_mux(num_pts=NUM_PTS, sample_num=SAMPLE_NUM,
                   enable_pid=True, enable_pid_debug=True)
    tx.RowSequencesPerDaqReadout.set(DAQ_READOUT)
    applied = apply_gains(cfg['gains'])
    sess.run_mux()
    # Prime one throwaway capture (DataWriter tees the data streams only after its
    # first Open/Close on a run) + settle.
    import os
    sess.root.DataWriter.DataFile.set(os.path.join(sess._require_output(), 'prime.dat'))
    sess.take_data(PRIME, start_delay_sec=SETTLE)
    if LOCK_SETTLE > 0:
        time.sleep(LOCK_SETTLE)
    return applied


def capture_data(deadband=None, acq=None, on_open=None):
    """take_data within the running MUX, retry until PID stream non-empty."""
    import os
    path_, metrics = None, {}
    for _ in range(max(1, CAPTURE_RETRIES)):
        sess.root.DataWriter.DataFile.set(os.path.join(sess._require_output(), 'pid.dat'))
        if on_open is not None:
            on_open()
        path_ = sess.take_data(acq if acq is not None else ACQ, start_delay_sec=SETTLE)
        sd = StreamData(path_)
        metrics = {r: pid_metrics(sd, COL, r, deadband=deadband) for r in rows}
        if any((m.get('n_visits') or 0) > 0 for m in metrics.values()):
            return str(path_), metrics, True
    return str(path_), metrics, False


def mean_over_rows(metrics, key):
    vals = [m[key] for m in metrics.values() if m.get(key) is not None]
    return float(np.mean(vals)) if vals else None


def locked(metrics):
    fr = mean_over_rows(metrics, 'final_residual')
    return fr is not None and fr <= cfg['thresholds']['residual_max']

# %% [markdown]
# ## Lock the servo
#
# Save the registers we touch (the script's `restore()` set), then run the lock
# recipe. Everything below runs inside this locked run; the final cell restores.

# %%
_vars = [dsp.PidEnable, dsp.PidDebugEnable, dsp.RowEnableMask, dsp.FluxQuantum,
         group.RowReadoutOrder, tx.Mode, tx.RowPeriodCycles, tx.SampleStartTime,
         tx.SampleEndTime, tx.RowSequencesPerDaqReadout,
         group.Sq1FbCurrent, group.TesBias, dsp.P_Coef, dsp.I_Coef]
if path == 'integer':
    _vars += [dsp.D_Coef]
for gname in ['PidP_Gain', 'PidI_Gain', 'PidD_Gain']:
    if hasattr(group, gname):
        _vars.append(getattr(group, gname))
_saved = [(v, v.get()) for v in _vars]

applied = apply_lock()
print(f"applied gains: {applied}")

# %% [markdown]
# ## steady — lock + steady-state residual
#
# Judge lock on the converged-tail residual (`final_residual`); report the
# second-half mean alongside.

# %%
if 'steady' in BEHAVIORS:
    path_, metrics, got = capture_data(deadband=DEADBAND)
    final_res = mean_over_rows(metrics, 'final_residual')
    mean_res = mean_over_rows(metrics, 'steady_residual')
    max_fj = max((abs(m['flux_jump_delta']) for m in metrics.values()
                  if m.get('flux_jump_delta') is not None), default=None)
    th = cfg['thresholds']
    ok = (got and final_res is not None and final_res <= th['residual_max']
          and (max_fj is None or max_fj <= th['flux_jump_max']))
    print(f"{'PASS' if ok else 'FAIL'}: steady-state lock -- final_residual={final_res} "
          f"(<= {th['residual_max']}), mean_residual={mean_res}, max_flux_jump={max_fj}")

    # Plot the per-row error timeseries from the capture.
    sd = StreamData(path_)
    plt.figure(figsize=(9, 5))
    for r in rows:
        slot = sd.pid.get(COL, {}).get(r, {})
        err = slot.get('accumError') or slot.get('accumErrorFp')
        if err:
            plt.plot(err, marker='.', alpha=0.7, label=f"r{r}")
    plt.axhline(th['residual_max'], color='k', ls='--', alpha=0.5, label='residual_max')
    plt.axhline(-th['residual_max'], color='k', ls='--', alpha=0.5)
    plt.xlabel("PID-debug visit"); plt.ylabel("accumError")
    plt.title(f"steady-state error, col {COL}, {path}"); plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8); plt.tight_layout()

# %% [markdown]
# ## step — TesBias disturbance rejection
#
# Confirm locked, apply a DC `TesBias` step, let the loop re-settle, then require:
# was locked, feedback moved, no spurious flux jumps, and the error recovered from
# its post-step peak. (The weak synthetic TES→SQ1 coupling makes this a
# lock-retention check, not a large-signal transient measurement.)

# %%
if 'step' in BEHAVIORS:
    th = cfg['thresholds']
    _saved_tes = group.TesBias.get()
    try:
        base = float(np.asarray(group.TesBias.get())[COL])
        _, pre, pre_got = capture_data(deadband=DEADBAND)
        was_locked = pre_got and locked(pre)
        fb_before = mean_over_rows(pre, 'feedback_mean')
        group.TesBias.set(index=COL, value=base + cfg['step_uA'])
        if LOCK_SETTLE > 0:
            time.sleep(LOCK_SETTLE)
        path_, metrics, got = capture_data(deadband=DEADBAND)
    finally:
        group.TesBias.set(_saved_tes)
    fb_after = mean_over_rows(metrics, 'feedback_mean')
    res_after = mean_over_rows(metrics, 'final_residual')
    peak = max((m['peak_abs_error'] for m in metrics.values()
                if m.get('peak_abs_error') is not None), default=None)
    max_fj = max((abs(m['flux_jump_delta']) for m in metrics.values()
                  if m.get('flux_jump_delta') is not None), default=None)
    fb_move = (abs(fb_after - fb_before) if fb_before is not None and fb_after is not None else None)
    recover_frac = th.get('step_recover_frac', 0.25)
    recovered = (res_after is not None and peak is not None and peak > 0
                 and (res_after <= th['residual_max'] or res_after <= recover_frac * peak))
    fb_moved = fb_move is not None and fb_move > 0.0
    ok = (got and was_locked and fb_moved and recovered
          and (max_fj is None or max_fj <= th['flux_jump_max']))
    print(f"{'PASS' if ok else 'FAIL'}: step disturbance rejection -- step={cfg['step_uA']}uA, "
          f"pre_locked={was_locked}, feedback_move={fb_move}, transient_peak={peak}, "
          f"residual_after={res_after}, recovered={recovered}, max_flux_jump={max_fj}")

# %% [markdown]
# ## flux — TesBias ramp through flux quanta (opt-in, best-effort)
#
# Ramp `TesBias` and read the `FluxJumps` register directly (ground truth) at each
# step. Requires only that the loop stays locked and the counts move
# monotonically (never hard-fails on not reaching the rail). Add `'flux'` to
# `BEHAVIORS` above to run.

# %%
if 'flux' in BEHAVIORS:
    def flux_counts():
        vals = np.asarray(dsp.FluxJumps.get())
        return [int(vals.flat[r]) for r in rows]

    traj = []
    _saved_tes = group.TesBias.get()
    try:
        base = float(np.asarray(group.TesBias.get())[COL])
        start_counts = flux_counts()
        for k in range(1, FLUX_STEPS + 1):
            group.TesBias.set(index=COL, value=base + k * FLUX_STEP_uA)
            path_, metrics, _got = capture_data(deadband=DEADBAND)
            counts = flux_counts()
            net = [c - s for c, s in zip(counts, start_counts)]
            traj.append(dict(tesbias=base + k * FLUX_STEP_uA, flux_jump_net=net,
                             locked=locked(metrics)))
    finally:
        group.TesBias.set(_saved_tes)
    total_net = max((abs(n) for t in traj for n in t['flux_jump_net']), default=0)
    monotone_ok = all(
        not any(b < a for a, b in zip(seq, seq[1:]))
        for seq in ([abs(t['flux_jump_net'][r]) for t in traj] for r in range(len(rows))))
    stayed_locked = bool(traj) and traj[-1]['locked']
    ok = stayed_locked and monotone_ok
    print(f"{'PASS' if ok else 'FAIL'}: flux-jump exercise -- total_flux_jumps={total_net}, "
          f"stayed_locked={stayed_locked}, monotonic={monotone_ok}")

    plt.figure(figsize=(9, 5))
    for r in range(len(rows)):
        plt.plot([t['tesbias'] - float(np.asarray(_saved_tes)[COL]) for t in traj],
                 [t['flux_jump_net'][r] for t in traj], marker='.', label=f"r{rows[r]}")
    plt.xlabel("dTesBias (uA)"); plt.ylabel("net FluxJumps")
    plt.title(f"flux-jump ramp, col {COL}"); plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8); plt.tight_layout()

# %% [markdown]
# ## Safe state
#
# End the run, disable PID (the float FluxQuantum restore is guarded behind PID
# disabled), and restore the touched registers.

# %%
tx.EndRun()
import time as _t
_end = _t.monotonic() + 120.0
while bool(tx.Running.get()) and _t.monotonic() < _end:
    _t.sleep(0.1)
dsp.PidEnable.set(False)
for v, val in reversed(_saved):
    v.set(val)
print("final state: run stopped; gains/coefs/masks/FluxQuantum/Sq1FbCurrent/TesBias restored")
