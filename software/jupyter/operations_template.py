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
# # Warm TDM operations template
#
# A worked, runnable outline of the standard bench workflow using the
# `warm_tdm_api.operations` API. It follows the muxed-run bring-up model
# (`docs/design/muxed-run-bringup.md`): the three configuration layers are
#
# * **A — enabled set**: which columns/rows participate (`ColTuneEnable`, row map)
# * **B — tune point**: the servo setpoints a tune produces (SA/SQ1 bias & fb, ...)
# * **C — run settings**: how the muxed run is clocked/servoed (`setup_mux`)
#
# **A is the anchor** — set it first; tuning (B) is performed against it, and the
# run settings (C) are expressed over it. This template is source-controlled as a
# percent-format `.py` (clean diffs); a generated `.ipynb` sits next to it.
#
# Edit the marked values for your hardware. Cells run top to bottom.

# %% [markdown]
# ## 0. Connect
#
# `ops.connect()` builds a client to the running `warmTdmServer` and caches a
# default `Session`, so the free-function shims (`ops.take_raw(...)`, etc.)
# work without a `session.` prefix. Scripts/tests should instead hold an explicit
# `Session` (`sess = ops.connect(...)`) and call methods on it.

# %%
import warm_tdm_api.operations as ops

sess = ops.connect(host="localhost", port=9099)   # returns the default Session
ops.status()                                       # one-shot state summary
ops.print_hardware()                               # firmware/build info per board

# %% [markdown]
# Optional one-time analog setup (front-end dependent — set for your cryostat):

# %%
# ops.set_cryo_resistance(Rcryo_Ohm=250.0)         # roundtrip cable R on all AFE amps
# ops.set_ps_synch(1)                              # synchronize board power supplies
# ops.disable_leds()

# %% [markdown]
# ## A. Enabled set (the anchor)
#
# Choose which columns and rows are read out **before** tuning. Everything below
# is indexed against this. `ColTuneEnable` is a per-column bool list;
# `RowIndexOrderList` is the logical readout order (see docs/design/row-mapping.md).

# %%
r = sess.root                                       # the pyrogue tree (client mirror)
group = sess.group

group.ColTuneEnable.set([True] * 8)                 # <-- which columns participate
group.RowMap1x32()                                  # <-- pick a row map for your array
group.RowIndexOrderList.set([0, 1, 2, 3])           # <-- logical rows to read out

print("cols enabled:", group.ColTuneEnable.get())
print("row order    :", group.RowIndexOrderList.get())

# %% [markdown]
# ## B. Tune point
#
# Tune in stages against the enabled set. Each wrapper starts the corresponding
# `pr.Process`, blocks until it finishes, and returns its output. Zero the
# setpoints first for repeatability across tunes.

# %%
import numpy as np

ncol = len(group.ColTuneEnable.get())
group.Sq1FbForceCurrent.set([0.0] * ncol)
group.Sq1BiasForceCurrent.set([0.0] * ncol)
group.SaFbForceCurrent.set([0.0] * ncol)

# %% [markdown]
# ### B.1 SA offset + SA tune

# %%
ops.sa_offset()                                     # PID the SA offset to null SA bias

sa_out = ops.sa_tune(                               # sweep SA bias/fb, pick lock points
    SaBiasLowOffset=0.0,
    SaBiasHighOffset=1.0,
    SaBiasNumSteps=5,
)
# ops.sa_tune sets the tune result on the tree (SetAfterFinish). Inspect via the
# process node's plots if desired, e.g. group.SaTuneProcess.PlotMulti.get().

# %% [markdown]
# ### B.2 SQ1 tune
#
# (Set the row-select FAS currents on the row DAC driver as your array requires
# before this — see your hardware notes.)

# %%
sq1_out = ops.sq1_tune(
    Sq1BiasNumSteps=20,
    ServoPrecision=0.0015,
)
# Plot the SQ1 V/phi curves for a few channels:
# ops.plot_sq1curves(sq1_out, cols=[c for c,e in enumerate(group.ColTuneEnable.get()) if e],
#                    rows=range(len(group.RowIndexOrderList.get())))

# %% [markdown]
# ### (Optional) save / restore the working point
#
# `save_config` writes all RW+WO variables (a recallable config); `save_state`
# adds RO (a full snapshot). Layer-scoped "just the tune point" save/restore is a
# planned helper (see docs/design/muxed-run-bringup.md) — for now these broad
# snapshots are what exist.

# %%
# cfg = ops.save_config()                           # -> <sessiondir>/config_<ctime>.yml
# ops.load_config(cfg)                              # restore later

# %% [markdown]
# ## C. Run settings + acquire
#
# `setup_mux` configures the coordinator timing (row period + sample window),
# puts the row DACs in timing mode, and enables SQ1 PID for the active columns.
# Then take a timed streaming acquisition.

# %%
ops.setup_mux(
    num_pts=512,              # row period in ADC cycles (visit rate = 125 MHz / num_pts / nrows)
    sample_end_offset=100,
    sample_num=250,
    enable_pid=True,
)

data_file = ops.take_data(acq_time_sec=10.0)        # opens DataWriter, acquires, closes
print("wrote", data_file)

# %% [markdown]
# ## Analyze
#
# `plot_stream_data` reads the readout stream (channel 9) from the `.dat` and
# plots time-domain + ASD for the requested channels. Calibration (sample rate,
# SQ1FB→pA) is derived from the file's embedded config automatically.

# %%
res = ops.plot_stream_data("c*r*", stream_data_id=data_file)   # path is first-class
# analyze a pair with a noise-model fit:
# ops.analyze_pair("c0r0", "c0r1", stream_data_id=data_file, do_fit=True)

# %% [markdown]
# ### (Debug) raw waveforms and PID-debug
#
# Raw ADC captures and the per-(col,row) PID-debug stream are debugging aids, not
# part of normal operation.

# %%
# raw_idx = ops.multi_raw(col=0, nraw=10)           # .npy captures -> index file
# freqs, mean_asd, rms = ops.get_mean_raw_asd(col=0, idxpath=raw_idx)

# PID-debug (only populated if the run had AdcDsp PidDebugEnable set):
# ops.plot_pid_debug("c*r*", field="accumError", pid_data_id=data_file)

# %% [markdown]
# ## Safe state
#
# `stop_and_zero` is a best-effort return to baseline: it zeros the column
# setpoints, ends the run, and drops to manual timing. It is **not** a hardware
# interlock (a firmware bug means biases may not fully zero after MUX, and row
# DACs are left untouched) — see its docstring.

# %%
ops.stop_and_zero()
