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
# # Cosim: closed-loop SQ1-FB PID lock (interactive)
#
# Interactive notebook version of `software/cosim/cosim_pid_lock.py`. Brings up
# (and monitors) a closed-loop muxed SQ1-FB PID lock in the **GroupTb cosim**,
# then optionally ramps `TesBias` to walk the servo through flux jumps. Run
# against a live `warmTdmServer --sim` (see
# [`software/cosim/README_cosim.md`](../cosim/README_cosim.md) for the sim
# recipe). The script stays the batch/CI form; this notebook is for chasing a
# lock by hand and plotting the descent.
#
# The lock recipe (order matters — see `docs/plans/tes-scaling/` and
# `docs/plans/pid-cosim-verification/cosim-tuning-settings.md`):
#
# 0. `SetCosimTunePoints()` for a fresh sim (RowMap + FAS-on + SA/SQ1 seed).
# 1. Write the **coherent** per-row operating point — Sq1Bias AND Sq1Fb AND SaFb.
# 2. `FluxQuantum = Phi0`; the multi-flux-wrap RTL rejects the write unless PID
#    is disabled + not busy, so disable PID first.
# 3. `sa_offset()` AFTER the operating-point tables are applied.
# 4. `setup_mux()` — small `sample_num` keeps the per-visit error small.
# 5. `set_pid()` — P is the stable single-integrator knob; NEGATIVE at the
#    Sq1Bias=50 / 23 µA point. P-only (I=0) locks cleanly.
# 6. `run_mux()`, poll per-row `AccumError`.
# 7. (optional) ramp `TesBias` and read the `FluxJumps` register at each step.
#
# This notebook is source-controlled as a percent-format `.py`; a generated
# `.ipynb` sits next to it. Edit the config cell for your sim, then run top to
# bottom.

# %% [markdown]
# ## Connect
#
# Build a `VirtualClient` to the running sim and wrap its `Group` in an
# operations `Session` (the same handle the batch script uses, minus the JSON
# provenance machinery).

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

client = pyrogue.interfaces.VirtualClient(addr=HOST, port=PORT)
sess = ops.Session(client.root.Group,
                   output=SimpleNamespace(sessiondir="/tmp/cosim_pid_lock"))
group = sess.group
cb = sess.coordinator_cb
tx = cb.WarmTdmCore.Timing.TimingTx

sess.status()

# %% [markdown]
# ## Lock configuration
#
# The defaults are the fitted 23 µA sinusoid-blend model operating point. The
# stable P sign is **negative** at Sq1Bias=50 (Sq1Bias=100 clips the DAC and will
# not lock at any gain).

# %%
COL = 0                 # global column index to servo
ROWS = 8                # rows to monitor
P, I, D = -0.05, 0.0, 0.0   # normalized gains (P is the stable knob; NEGATIVE here)
SAMPLE_NUM = 20         # samples per row window
NUM_PTS = 400           # RowPeriodCycles
SQ1FB_uA = 2.0          # SQ1 FB mid-slope operating point at Sq1Bias=50
SQ1BIAS_uA = 50.0       # SQ1 bias (100 clips the DAC and will not lock)
SAFB_uA = 9.0           # SA FB (must be applied before sa_offset)
FLUX_QUANTUM_uA = 23.0  # FluxQuantum = SQ1 flux period Phi0
SECS = 20               # monitor duration (seconds; polled once/sec)
SEED_TUNE_POINTS = True  # SetCosimTunePoints() first (fresh-sim fixture)
SEED_TUNE = True        # write the coherent per-row operating point

# TES flux-jump ramp (after locking); set TES_STEPS > 0 to enable.
TES_STEPS = 0
TES_STEP_uA = 4.0       # keep < one Phi0 so the servo tracks continuously
TES_SETTLE = 5.0        # seconds to settle after each TesBias step

dsp = cb.DataPath.AdcDsp[COL]


def mae(rows):
    """Per-row mean |AccumError| (the loop residual)."""
    return int(np.mean(np.abs(np.asarray(dsp.AccumError.get())[:rows])))


# Start from a stopped run (the notebook may be re-run against a live server).
if bool(tx.Running.get()):
    tx.EndRun()
    time.sleep(0.4)

# %% [markdown]
# ## 0. Seed the fixture + 1. coherent per-row operating point
#
# `SetCosimTunePoints()` seeds a fresh sim; then write Sq1Bias AND Sq1Fb AND SaFb
# for every row under test. Also set `RowReadoutOrder` — a fresh sim defaults it
# to `[0]`, so without this only row 0 is ever visited.

# %%
if SEED_TUNE_POINTS:
    group.SetCosimTunePoints()
    print("Ran SetCosimTunePoints()")

group.RowReadoutOrder.set(list(range(ROWS)))

if SEED_TUNE:
    for r in range(ROWS):
        group.Sq1BiasCurrent.set(index=(COL, r), value=SQ1BIAS_uA)
        group.Sq1FbCurrent.set(index=(COL, r), value=SQ1FB_uA)
        group.SaFbCurrent.set(index=(COL, r), value=SAFB_uA)
    print(f"Seeded per-row Sq1Bias={SQ1BIAS_uA} Sq1Fb={SQ1FB_uA} SaFb={SAFB_uA} uA "
          f"on col {COL} rows 0..{ROWS-1}")

# %% [markdown]
# ## 2. FluxQuantum + 3. SA null
#
# Disable PID before writing `FluxQuantum` (the multi-flux-wrap RTL guards it),
# then null the SA AFTER the operating-point tables are applied.

# %%
dsp.PidEnable.set(False)
dsp.FluxQuantum.set(FLUX_QUANTUM_uA)
print(f"FluxQuantum = {float(dsp.FluxQuantum.get()):.3f} uA")

sess.sa_offset()
print(f"SaOutAdc after null = {float(np.asarray(group.SaOutAdc.get())[COL]):+.4f} V")

# %% [markdown]
# ## 4. Mux config, 5. gains, 6. run + poll
#
# Configure the MUX, apply the gains, start the run, then poll per-row
# `mean|AccumError|` once per second and watch it descend to its floor.

# %%
sess.setup_mux(num_pts=NUM_PTS, sample_num=SAMPLE_NUM,
               enable_pid=True, enable_pid_debug=True)
sess.set_pid(p=P, i=I, d=D, cols=[COL])
print(f"SampleCount = {int(tx.SampleCount.get())}  gains P={P} I={I} D={D}")
sess.run_mux()

traj = []
for _ in range(int(SECS)):
    time.sleep(1.0)
    traj.append(mae(ROWS))
final = [int(x) for x in np.asarray(dsp.AccumError.get())[:ROWS]]
print(f"mean|AccumError| per second: {traj}")
print(f"final per-row AccumError:    {final}")
print(f"FluxJumps: {[int(x) for x in np.asarray(dsp.FluxJumps.get())[:ROWS]]}")

# %%
plt.figure(figsize=(9, 5))
plt.plot(range(len(traj)), traj, marker='.')
plt.xlabel("poll time (s)")
plt.ylabel(r"mean $|$AccumError$|$ per row (counts)")
plt.title(f"PID lock descent, col {COL}, {ROWS} row(s), P={P}")
plt.yscale("log")
plt.grid(True, which="both", alpha=0.3)
plt.tight_layout()

# %% [markdown]
# ## 7. (Optional) TES flux-jump ramp
#
# Walk `TesBias` and read the `FluxJumps` register (ground truth) at each step. A
# locked servo tracks the TES-induced flux and wraps at ±7862; `FluxJumps` climbs
# monotonically while `Sq1FbFull` stays bounded. P does not gate this — the
# applied TES flux does. Keep `TES_STEP_uA` below one Phi0. Set `TES_STEPS > 0`
# above to run.

# %%
if TES_STEPS > 0:
    fjv = np.asarray(dsp.FluxJumps.get())
    base = float(np.asarray(group.TesBias.get())[COL])
    start = [int(fjv.flat[r]) for r in range(ROWS)]
    print(f"TES flux-jump ramp from TesBias={base:.1f} uA, {TES_STEPS} x {TES_STEP_uA} uA:")
    print(f"  {'dTesBias':>9} {'FluxJumps(net)':>28} {'Sq1FbFull[0]':>13}")
    try:
        for k in range(1, TES_STEPS + 1):
            group.TesBias.set(index=COL, value=base + k * TES_STEP_uA)
            time.sleep(TES_SETTLE)
            fjv = np.asarray(dsp.FluxJumps.get())
            fbv = np.asarray(dsp.Sq1FbFull.get())
            net = [int(fjv.flat[r]) - start[r] for r in range(ROWS)]
            print(f"  {k*TES_STEP_uA:8.1f}u {str(net):>28} {float(fbv.flat[0]):13.1f}")
    finally:
        group.TesBias.set(index=COL, value=base)
        print(f"restored TesBias = {base:.1f} uA")

# %% [markdown]
# ## Safe state
#
# End the run. (The batch script also calls `client.stop()`; leave the client up
# here so the notebook stays interactive.)

# %%
if bool(tx.Running.get()):
    tx.EndRun()
print("run ended.")
