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
# # Warm TDM tune + PID gain sweep (hardware)
#
# A worked, runnable bench notebook that does a **real** end-to-end tune (connect
# → manual-FAS → SA/SQ1 tune → mux setup) and then, on top of that tune, runs a
# **closed-loop PID gain sweep** and a **readout-health / flux-jump check**.
#
# It follows the muxed-run bring-up model (`docs/design/muxed-run-bringup.md`) and
# the operations API (`docs/operations-api.md`): the three configuration layers
# are **A — enabled set** (which cols/rows), **B — tune point** (the servo
# setpoints a tune produces), **C — run settings** (how the muxed run is
# clocked/servoed). **A is the anchor**; B is tuned against it; C runs over it.
#
# The gain sweep here is the same closed-loop **AXI-`AccumError`** method the
# cosim harness uses (see `software/scripts/hwtest/cosim_pid_lock.py` and the
# tuning notes in `software/scripts/hwtest/verify_cosim_pid.py`): for each
# candidate gain, run the MUX and poll the per-row `mean|AccumError|` register
# until it floors. The stream capture yields too few PID-debug visits to see the
# loop floor, so the register poll is the right instrument for picking a gain.
# Everything is inline in this notebook (no helper module) so it can be edited at
# the prompt. This notebook is source-controlled as a percent-format `.py`
# (clean diffs); a generated `.ipynb` sits next to it.
#
# The marked values below are a worked example for one bench setup — edit them
# for your hardware. Cells run top to bottom.

# %% [markdown]
# ## 0. Connect
#
# `ops.connect()` builds a client to the running `warmTdmServer` and caches a
# default `Session`, so the free-function shims (`ops.take_raw(...)`, etc.)
# work without a `session.` prefix. Here we also hold the explicit `sess` so the
# gain-sweep cells can reach board nodes (`sess.cbs`, `sess.coordinator_cb`)
# directly.

# %%
# Register the in-repo library paths, then enable inline plots.
# (jupytext comments notebook magics in the .py; they run in the .ipynb.)
# %run ../scripts/_setupLibPaths.py
# %matplotlib inline

import time
import numpy as np
import matplotlib.pyplot as plt
import warm_tdm_api.operations as ops

sess = ops.connect(host="localhost", port=9099)   # returns the default Session
group = sess.group
r = sess.root                                      # the pyrogue tree (client mirror)

ops.status()                                       # one-shot state summary
ops.print_hardware()                               # firmware/build info per board

# %% [markdown]
# Optional one-time analog setup (front-end dependent — set for your cryostat):

# %%
ops.set_cryo_resistance(Rcryo_Ohm=116.0)         # roundtrip cable R on all AFE amps
ops.set_ps_synch(1)                              # synchronize board power supplies
ops.disable_leds()

# %% [markdown]
# ## A. Enabled set (the anchor)
#
# Choose which columns and rows are read out **before** tuning. Everything below
# is indexed against this. `ColEnableMask` is an integer bitmask (bit c set =
# column c enabled, e.g. 0x0F = columns 0-3); `RowReadoutOrder` is the logical
# readout order (see docs/design/row-mapping.md).

# %%
group.ColEnableMask.set(0x0F)                       # <-- which columns participate (bits 0-3)
group.RowMap6x10()                                  # <-- pick a row map for your array
group.RowReadoutOrder.set([10, 11, 12, 13])       # <-- logical rows to read out

print("cols enabled:", hex(group.ColEnableMask.get()))
print("row order    :", group.RowReadoutOrder.get())

# %% [markdown]
# ## B. Tune point
#
# Tune in stages against the enabled set. Each wrapper starts the corresponding
# `pr.Process`, blocks until it finishes, and returns its output. Zero the
# setpoints first for repeatability across tunes. **The gain sweep below runs on
# top of this tune** — do not skip it.

# %%
ncol = int(group.NumColumns.get())
group.Sq1FbForceCurrent.set([0.0] * ncol)
group.Sq1BiasForceCurrent.set([0.0] * ncol)
group.SaFbForceCurrent.set([0.0] * ncol)

# %% [markdown]
# ### B.1 SA offset + SA tune
#
# `SetAfterFinish=True` programs the fitted SA operating point onto the tree.
# `sa_tune` runs an SA offset servo internally at the end; a standalone
# `ops.sa_offset()` first is optional.

# %%
# ops.sa_offset()                                   # optional: PID SA offset to null SA bias

sa_out = ops.sa_tune(                               # sweep SA bias/fb, pick lock points
    SaFbLowOffset=0.0,
    SaFbHighOffset=100.0,
    SaFbNumSteps=300,
    SaBiasLowOffset=47.4,
    SaBiasHighOffset=50.0,
    SaBiasNumSteps=1,
    SetAfterFinish=True,
)

# %%
# Inspect the per-column SA curves (needs an in-process root; see the plotting
# note in the docs if a bare .get() prints "<Figure ...>" instead of rendering).
group.SaTuneProcess.MultiPlot.get()

# %% [markdown]
# ### B.2 FAS tune (manual set)
#
# The scripted `ops.fas_tune` (commented at the end of this cell) sweeps each
# active row's physical FAS line and picks its on-current. On this bench we
# instead set the FAS on-currents directly to half a flux quantum, computed from
# the measured mutual inductance — a reliable bypass when the sweep is not yet
# trustworthy. `FasOff` is driven to 0 so unselected rows are off.

# %%
import scipy.constants as sc

# Half a flux quantum through the FAS mutual inductance (NIST mux21_s4, 2-level).
magnetic_flux_quantum = sc.h / (2 * sc.e)
Mfas_Henry = 6.3e-12
fas_phi0_uA = 1.0e6 * magnetic_flux_quantum / Mfas_Henry
print(f"FAS Phi0 = {fas_phi0_uA:.1f} uA")
i_fas = fas_phi0_uA / 2.0

rdd = sess.rdds[0]
rdd.Mode.setDisp("MANUAL")                          # drive each FAS line individually
for line in range(17):                              # row-select 0-9, chip-select 10-16
    rdd.FasOn.Current_[line].set(i_fas)             # ON current, driven to the DAC
    rdd.FasOff.Current_[line].set(0.0)              # OFF current (0 = line off)

# Scripted alternative (bypassed here):
# fas_out = ops.fas_tune(FasFluxHighOffset=310.0, FasFluxNumSteps=21,
#                        Sq1BiasCurrent=40.0, SetAfterFinish=True)

# %% [markdown]
# ### B.3 SQ1 tune
#
# Run after the FAS on-currents are set (they select each row for the sweep).
# `SetAfterFinish=True` programs the fitted per-(col,row) lock point
# (Sq1Fb/Sq1Bias/SaFb) into the readout tables — the same apply the manual
# "set the fitted values" loop used to do by hand. **The gain sweep depends on
# this real lock point** (a wrong operating point will not lock at any gain — see
# the Sq1Bias clipping note in the cosim tuning docs).

# %%
sq1_out = ops.sq1_tune(
    Sq1FbLowOffset=-30.0,
    Sq1FbHighOffset=30.0,
    Sq1FbNumSteps=120,
    Sq1BiasLowOffset=50.0,
    Sq1BiasHighOffset=50.0,
    Sq1BiasNumSteps=1,
    ServoPrecision=0.0015,
    ServoKp=-6.4,
    ServoKi=-0.2,
    SetAfterFinish=True,
)

# %%
# One compact 4x2 figure (all columns) per tuned row -- the SQ1 analogue of
# SaTuneProcess.MultiPlot. Cheaper than plot_sq1curves, which draws one plot per
# (col, row).
sq1 = group.Sq1TuneProcess
for rowpos in range(len(group.RowReadoutOrder.get())):
    sq1.PlotRow.set(rowpos)
    display(sq1.MultiPlot.get())

# %% [markdown]
# ## C. Run settings
#
# `setup_mux` configures the coordinator timing (row period + sample window),
# puts the row DACs in timing mode, and enables SQ1 PID for the active columns.
# It does **not** start the run unless `run_now=True`. `set_pid` sets the
# sample-count-normalized per-column gains. We enable PID-debug here so the final
# capture carries the per-(col,row) PID stream for offline analysis.

# %%
ops.setup_mux(
    num_pts=512,              # row period in ADC cycles (visit rate = 125 MHz / num_pts / nrows)
    sample_end_offset=100,
    sample_num=25,
    enable_pid=True,
    enable_pid_debug=True,    # populate the PID-debug stream in the final capture
    # run_now=True,           # optionally start the MUX right here instead of run_mux()
)

# The MUX must be running for the gain sweep to servo and for AccumError to
# update. setup_mux (without run_now) leaves it stopped, so start it now.
ops.run_mux()

# %% [markdown]
# ## D. PID gain sweep (closed-loop, live)
#
# For each candidate **normalized** P gain (the units `set_pid` takes — it
# divides by `TimingTx.SampleCount` before writing the raw DSP coefficient), we
# apply the gain to the columns under test, let the loop run, and poll the per-row
# `mean|AccumError|` once per second to watch it descend to its floor. We record:
#
# * **floor** — the settled `mean|AccumError|` (loop residual; smaller = tighter),
# * **settle_s** — seconds until the trajectory first stays within `SETTLE_TOL` of
#   that floor for the rest of the poll window, and
# * **flux_jump_delta** — net change in the `FluxJumps` register over the poll (a
#   good P holds this at 0; a too-hot or windup-prone gain makes it climb).
#
# A good gain floors well under the residual you care about, settles inside the
# poll window, and does not accumulate flux jumps. The stream capture is too
# sparse (a few PID-debug visits) to see this floor — the register poll is the
# instrument. `pid_metrics` (in `warm_tdm_api.operations.pid_analysis`) computes
# the same quantities offline from a PID-debug capture, if you want a cross-check.

# %%
# --- Sweep configuration (edit for your hardware) ---
SWEEP_COL = 0                 # column under test (a global column index)
GAINS = [-0.005, -0.010, -0.020, -0.05]   # NORMALIZED P gains to try (sign matters)
POLL_S = 12                   # seconds to poll each gain (long enough to floor)
SETTLE_TOL = 20.0             # |AccumError| band (counts) that counts as "settled"

nrows = len(group.RowReadoutOrder.get())
tx = sess.coordinator_cb.WarmTdmCore.Timing.TimingTx
board, chan = sess.col_to_board_chan(SWEEP_COL)
dsp = sess.cbs[board].DataPath.AdcDsp[chan]         # the DSP node for this column
sample_count = int(tx.SampleCount.get())
print(f"col {SWEEP_COL} -> board {board} chan {chan}; SampleCount={sample_count}; "
      f"polling {nrows} row(s) over {POLL_S}s per gain")


def mean_abs_accum_error():
    """Per-row mean |AccumError| for the rows under readout (the loop residual)."""
    return float(np.mean(np.abs(np.asarray(dsp.AccumError.get())[:nrows])))


def flux_jumps_total():
    """Sum of the per-row FluxJumps register over the rows under readout."""
    return int(np.sum(np.asarray(dsp.FluxJumps.get())[:nrows]))


def poll_gain(poll_s, tol):
    """Poll mean|AccumError| once/sec; return (trajectory, floor, settle_s)."""
    traj = [mean_abs_accum_error()]
    for _ in range(int(poll_s)):
        time.sleep(1.0)
        traj.append(mean_abs_accum_error())
    floor = float(np.mean(traj[-3:]))               # settled tail, robust to 1 blip
    # settle_s: first second from which every later sample stays within tol of floor.
    settle_s = None
    for i, v in enumerate(traj):
        if abs(v - floor) <= tol and all(abs(x - floor) <= tol for x in traj[i:]):
            settle_s = i
            break
    return traj, floor, settle_s


sweep = {}
for g in GAINS:
    fj0 = flux_jumps_total()
    ops.set_pid(p=g, cols=[SWEEP_COL])              # apply this gain, loop keeps running
    traj, floor, settle_s = poll_gain(POLL_S, SETTLE_TOL)
    fj_delta = flux_jumps_total() - fj0
    sweep[g] = dict(traj=traj, floor=floor, settle_s=settle_s, flux_jump_delta=fj_delta)
    settle_txt = f"{settle_s}s" if settle_s is not None else "did-not-settle"
    print(f"P={g:+.4f}  floor={floor:8.1f}  settle={settle_txt:>16}  "
          f"flux_jumps+={fj_delta}")

# %%
# Plot each gain's descent to its floor. A clean gain drops fast to a low, flat
# floor; too-weak sits high, too-hot rings or the floor rises (and flux jumps).
plt.figure(figsize=(9, 5))
for g, res in sweep.items():
    plt.plot(range(len(res['traj'])), res['traj'], marker='.',
             label=f"P={g:+.4f} (floor {res['floor']:.0f}, fj+{res['flux_jump_delta']})")
plt.xlabel("poll time (s)")
plt.ylabel(r"mean $|$AccumError$|$ per row (counts)")
plt.title(f"PID gain sweep, col {SWEEP_COL}, {nrows} row(s)")
plt.yscale("log")
plt.grid(True, which="both", alpha=0.3)
plt.legend()
plt.tight_layout()

# %% [markdown]
# ### Pick the gain
#
# Rank by floor among the gains that settled with no flux jumps, then apply the
# winner to the columns under test. Edit `BEST_P` by hand if you prefer a
# different trade-off (e.g. a slightly higher floor that settles faster).

# %%
ok = {g: res for g, res in sweep.items()
      if res['settle_s'] is not None and res['flux_jump_delta'] == 0}
BEST_P = min(ok, key=lambda g: ok[g]['floor']) if ok else min(sweep, key=lambda g: sweep[g]['floor'])
print(f"chosen P = {BEST_P:+.4f}  (floor {sweep[BEST_P]['floor']:.1f})")

ops.set_pid(p=BEST_P, i=0.0, debug=True)            # apply to all enabled cols; debug on for the capture

# %% [markdown]
# ## E. Acquire + readout-health / flux-jump check
#
# `take_data` captures within the already-running MUX without stopping it. We then
# read two health signals from the capture and the live registers:
#
# * **dropped readouts** — `StreamData.dropped_readouts` is the run-cumulative
#   count of readout frames the firmware dropped to FIFO backpressure (0 = none
#   lost). `malformed_pid` counts PID-debug boundary fragments (a couple per
#   acquisition is normal). The `StreamReader` also `warnings.warn`s on drops.
# * **flux jumps** — the live `FluxJumps` register per row: for a quiet bench with
#   a locked servo this should not be climbing.

# %%
data_file = ops.take_data(acq_time_sec=10.0)        # capture within the running MUX
print("wrote", data_file)

sd = ops.StreamData(data_file)                      # loads + warns on any drops
print(f"dropped readouts : {sd.dropped_readouts}  (0 = none lost to FIFO backpressure)")
print(f"malformed PID    : {sd.malformed_pid}  (a couple = writer-boundary fragments, expected)")
if sd.dropped_readouts:
    print("  !! readout data is INCOMPLETE -- reduce visit rate (raise num_pts) or "
          "channel count, or check the transport.")

fj = np.asarray(dsp.FluxJumps.get())[:nrows]
print(f"FluxJumps per row (col {SWEEP_COL}): {[int(x) for x in fj]}")

# %% [markdown]
# ## Analyze
#
# `plot_stream_data` reads the readout stream (channel 9) from the `.dat` and
# plots time-domain + ASD for the requested channels. Calibration (sample rate,
# SQ1FB→pA) is derived from the file's embedded config automatically. Because we
# enabled PID-debug, `plot_pid_debug` / `pid_metrics` also work on this file.

# %%
res = ops.plot_stream_data("c*r10", stream_data_id=data_file)   # path is first-class
# analyze a pair with a noise-model fit:
# ops.analyze_pair("c0r10", "c1r10", stream_data_id=data_file, do_fit=True)

# %%
# Offline servo metrics from the PID-debug stream, as a cross-check on the live
# sweep's floor (steady_residual / final_residual are the analogue of the poll
# floor; drop_rate / flux_jump_delta corroborate the register reads).
from warm_tdm_api.operations.pid_analysis import pid_metrics
m = pid_metrics(sd.pid_data(), col=SWEEP_COL, row=0)
print({k: m[k] for k in ('format', 'n_visits', 'steady_residual', 'final_residual',
                          'flux_jump_delta', 'drop_rate')})

# ops.plot_pid_debug("c*r10", field="accumError", pid_data_id=data_file)

# %% [markdown]
# ## Safe state
#
# `stop_and_zero` ends the run and zeros the column outputs (all columns, incl.
# tune-disabled ones). It is **not** a hardware interlock — row DACs are left
# untouched — see its docstring.

# %%
ops.stop_and_zero()
