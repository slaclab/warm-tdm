# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
# %% [markdown]
# # Warm TDM operations template
#
# A worked, runnable outline of the standard bench workflow using the
# `warm_tdm_api.operations` API. It follows the muxed-run bring-up model
# (`docs/design/muxed-run-bringup.md`): the three configuration layers are
#
# * **A — enabled set**: which columns/rows participate (`ColEnableMask`, row map)
# * **B — tune point**: the servo setpoints a tune produces (SA/SQ1 bias & fb, ...)
# * **C — run settings**: how the muxed run is clocked/servoed (`setup_mux`)
#
# **A is the anchor** — set it first; tuning (B) is performed against it, and the
# run settings (C) are expressed over it. This template is source-controlled as a
# percent-format `.py` (clean diffs); a generated `.ipynb` sits next to it.
#
# The marked values below are a worked example for one bench setup — edit them
# for your hardware. Cells run top to bottom.

# %% [markdown]
# ## Open a measurement copy
# Create this copy with `software/scripts/new_run.py`. Select the Rogue-enabled
# kernel. Set `WARM_TDM_PATH` in that kernel's environment when using a checkout.
# Start Jupyter in the run directory, or set RUN_DIR to its explicit path.

# %%
import os
import sys
from pathlib import Path

if os.environ.get("WARM_TDM_PATH"):
    checkout = Path(os.environ["WARM_TDM_PATH"]).expanduser().resolve()
    for relative in ["software/python", "firmware/python", "firmware/submodules/surf/python"]:
        sys.path.insert(0, str(checkout / relative))

import warm_tdm_run as runs
RUN_DIR = runs.find_run()  # Or: runs.validate_run("/shared/path/to/run")
print("Measurement directory:", RUN_DIR)

# %% [markdown]
# ## Connect to the server
# DataWriter writes on the server: this run must exist at the same absolute path
# on the client and server. Reconnecting reuses it; no new directory is created.

# %%
import numpy as np
import warm_tdm_api.operations as ops

HOST, PORT = "localhost", 9099
SERVER_REVISION = None  # Fill in the actual server revision if known.
sess = ops.connect(host=HOST, port=PORT, run_dir=RUN_DIR)
group = sess.group
r = sess.root
runs.record_connection(sess, RUN_DIR, HOST, PORT, server_revision=SERVER_REVISION)
sess.status()
initial_config = sess.save_config()

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
# Fixture-specific example; edit before running setup/tuning cells.
ROW_MAP = "RowMap8x10"
FAS_LINES = list(range(18))  # RS 0-9, CS 10-17 for this map
COLUMN_MASK = 0x0F
LOGICAL_ROWS = [10, 11, 12, 13]
group.ColEnableMask.set(COLUMN_MASK)                       # <-- which columns participate (bits 0-3)
getattr(group, ROW_MAP)()                                  # <-- pick a row map for your array
group.RowReadoutOrder.set(LOGICAL_ROWS)       # <-- logical rows to read out

print("cols enabled:", hex(group.ColEnableMask.get()))
print("row order    :", group.RowReadoutOrder.get())

# %% [markdown]
# ## B. Tune point
#
# Tune in stages against the enabled set. Each wrapper starts the corresponding
# `pr.Process`, blocks until it finishes, and returns its output. Zero the
# setpoints first for repeatability across tunes.

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
for line in FAS_LINES:
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
# "set the fitted values" loop used to do by hand.

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

# Per-(col,row) curves instead (a lot of plots):
# ops.plot_sq1curves(sq1_out, cols=[c for c, e in enumerate(group.colEnableBools) if e],
#                    rows=range(len(group.RowReadoutOrder.get())))

# %% [markdown]
# ### (Optional) save / restore the working point
#
# `save_config` writes all RW+WO variables (a recallable config); `save_state`
# adds RO (a full snapshot). Layer-scoped "just the tune point" save/restore is a
# planned helper (see docs/design/muxed-run-bringup.md) — for now these broad
# snapshots are what exist.

# %%
tuned_config = sess.save_config()                   # saved under RUN_DIR/config/
# ops.load_config(cfg)                              # restore later

# %% [markdown]
# ## C. Run settings + acquire
#
# `setup_mux` configures the coordinator timing (row period + sample window),
# puts the row DACs in timing mode, and enables SQ1 PID for the active columns.
# It does **not** start the run unless `run_now=True`. `set_pid` then sets the
# sample-count-normalized per-column gains (final say over the same normalized
# gains setup_mux rescales), so its value stays valid if the sample window
# changes. `run_mux` starts the free-running MUX; `take_data` captures within it
# without stopping it, so the run persists until `stop_and_zero`.

# %%
ops.setup_mux(
    num_pts=512,              # row period in ADC cycles (visit rate = 125 MHz / num_pts / nrows)
    sample_end_offset=100,
    sample_num=25,
    enable_pid=True,
    # run_now=True,           # optionally start the MUX right here instead of run_mux()
)

ops.set_pid(p=-0.015, i=0.0, debug=False)           # sample-count-normalized gains (=-0.0006 raw x 25 samples)

ops.run_mux()                                       # start the free-running MUX
try:
    data_file = ops.take_data(acq_time_sec=10.0)
    print("wrote", Path(data_file).relative_to(RUN_DIR))
finally:
    # End this acquisition run even when a capture is interrupted.
    sess.coordinator_cb.WarmTdmCore.Timing.TimingTx.EndRun()

# %% [markdown]
# ## Analyze
#
# `plot_stream_data` reads the readout stream (channel 9) from the `.dat` and
# plots time-domain + ASD for the requested channels. Calibration (sample rate,
# SQ1FB→pA) is derived from the file's embedded config automatically.

# %%
res = ops.plot_stream_data("c*r10", stream_data_id=data_file)   # path is first-class
# analyze a pair with a noise-model fit:
# ops.analyze_pair("c0r10", "c1r10", stream_data_id=data_file, do_fit=True)

# %% [markdown]
# ### (Debug) raw waveforms and PID-debug
#
# Raw ADC captures and the per-(col,row) PID-debug stream are debugging aids, not
# part of normal operation. PID-debug is only populated when the run had
# `PidDebugEnable` set — pass `debug=True` to `set_pid` (or `enable_pid_debug=True`
# to `setup_mux`) before the acquisition.

# %%
raw_idx = ops.multi_raw(col=0, nraw=10)             # .npy captures -> index file
freqs, mean_asd, rms = ops.get_mean_raw_asd(col=0, idxpath=raw_idx)

# ops.plot_pid_debug("c*r10", field="accumError", pid_data_id=data_file)

# %% [markdown]
# ## Safe state
#
# `stop_and_zero` ends the run and zeros the column outputs (all columns, incl.
# tune-disabled ones). It is **not** a hardware interlock — row DACs are left
# untouched — see its docstring.

# %%
ops.stop_and_zero()

# %%
final_config = sess.save_config()

# %% [markdown]
# ## Observations and outcome
# Record what changed, failed/interrupted attempts, and the relevant data files.
