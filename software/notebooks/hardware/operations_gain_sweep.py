# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
# %% [markdown]
# # PID P-gain sweep on a tuned instrument
# First complete the hardware operations template and preserve its tuned config.
# This notebook uses the current tune and run settings; it does not retune or
# replace the row map. Gains are normalized; their sign/range are fixture-specific.
# Measurement copies retain outputs. See docs/notebook-runs.md in the checkout.

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
# ## Configure the sweep
# Verify the live enabled columns/rows and sample timing before starting.
# I and D remain at their current values. The helper restores the original P
# after every sweep, including exceptions, and measures the actual logical rows.

# %%
import json
import time
import matplotlib.pyplot as plt

COLUMN = 0
GAINS = [-0.005, -0.010, -0.020, -0.05]
SECONDS = 12
TOLERANCE = 20.0
print("Rows:", group.RowReadoutOrder.get())
print("Column mask:", hex(int(group.ColEnableMask.get())))

# %%
tx = sess.coordinator_cb.WarmTdmCore.Timing.TimingTx
if tx.Running.get():
    raise RuntimeError("Stop timing before starting this notebook's sweep")
results = []
result_file = RUN_DIR / "data" / f"gain-sweep-{time.time_ns()}.json"
try:
    sess.run_mux()
    ops.sweep_pid_p(sess, COLUMN, GAINS, seconds=SECONDS,
                    tolerance=TOLERANCE, results=results)
finally:
    try:
        tx.EndRun()
    finally:
        result_file.write_text(json.dumps(results, indent=2) + "\n")
print("Saved:", result_file.relative_to(RUN_DIR))

# %% [markdown]
# ## Inspect before applying
# Flux is sampled once per second; excursions between polls may be missed.
# A small residual alone does not prove physical lock. Candidates without a
# settled tail or with an observed per-row flux excursion are excluded.

# %%
for result in results:
    plt.plot(range(1, len(result["trajectory"]) + 1), result["trajectory"],
             label=f'P={result["p"]}')
plt.xlabel("Time (s)")
plt.ylabel("Mean absolute accumulated error (counts)")
plt.legend()
plt.savefig(RUN_DIR / "figures" / f"gain-sweep-{time.time_ns()}.png")
eligible = [item for item in results if item["settle_s"] is not None
            and item["max_flux_excursion"] == 0]
print("Eligible candidates:", [(x["p"], x["floor"]) for x in eligible])

# %%
BEST_P = None  # Set after reviewing plots and the physical operating point.
if BEST_P is not None:
    if BEST_P not in [item["p"] for item in eligible]:
        raise ValueError("Choose an eligible measured gain")
    sess.set_pid(p=BEST_P, cols=[COLUMN])  # Only the measured column.
    sess.save_config()

# %% [markdown]
# ## Capture and inspect readout health
# Capture at the currently applied gain (the original gain if BEST_P is unset).
# Debug is enabled temporarily on the measured column and restored on failure.
# take_data owns this run and stops it on completion or interruption.

# %%
if tx.Running.get():
    raise RuntimeError("Stop timing before the validation capture")
board, channel = sess.col_to_board_chan(COLUMN)
dsp = sess.cbs[board].DataPath.AdcDsp[channel]
previous_debug = dsp.PidDebugEnable.get()
try:
    dsp.PidDebugEnable.set(True)
    sess.save_config()
    data_file = sess.take_data(acq_time_sec=10.0)
finally:
    dsp.PidDebugEnable.set(previous_debug)
stream = ops.StreamData(data_file)
print("Capture:", Path(data_file).relative_to(RUN_DIR))
print("Dropped readouts:", stream.dropped_readouts)
print("Malformed PID frames:", stream.malformed_pid)
rows = [int(row) for row in group.RowReadoutOrder.get()]
print("Per-row net flux counts:", np.asarray(dsp.FluxJumps.get())[rows])

# %%
from warm_tdm_api.operations.pid_analysis import pid_metrics_all
metrics = pid_metrics_all(stream.pid_data(), cols=[COLUMN], rows=rows)
print(metrics)
channels = ",".join(f"c{COLUMN}r{row}" for row in rows)
ops.plot_stream_data(channels, stream_data_id=stream)

# %% [markdown]
# ## Outcome
# Timing is stopped; the instrument's DAC state is retained. Record the selected
# gain and evidence here. To zero column outputs when finished, run the next cell.

# %%
sess.stop_and_zero()
sess.save_config()
