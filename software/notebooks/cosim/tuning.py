# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
# %% [markdown]
# # Cosim tuning: run and inspect
# The batch implementation owns setup, checks and cleanup. Edit the arguments
# and fixture profile before running; keep comparisons tied to the same model.

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

# %%
HOST, PORT = "localhost", 9099
MANIFEST = RUN_DIR / "config" / "simulation.json"
# Copy the manifest for the actual running simulator/server here first.
# See software/cosim/README_cosim.md for required source/build/fixture fields.
connection_args = ["--host", HOST, "--port", str(PORT), "--manifest", str(MANIFEST)]

# %%
result_dir = runs.run_cosim("verify_cosim_tuning", RUN_DIR, connection_args + ["--profile", str(RUN_DIR / "config" / "cosim_tuning.example.json")])

# %%
import json
reports = [json.loads(path.read_text()) for path in result_dir.rglob("result.json")]
reports

# %% [markdown]
# ## Explore recorded data
# Use the recorded .dat files with operations.plot_stream_data or plot_pid_debug.
# Add plots and observations here; leave the original capture files intact.

# %%
list(result_dir.rglob("*.dat"))

# %%
import matplotlib.pyplot as plt
curve_files = list(result_dir.rglob("tuning-results.json"))
if curve_files:
    curves = json.loads(curve_files[0].read_text())
    for col, curve in enumerate(curves.get("SaTuneProcess", [])):
        if curve and "xValues" in curve:
            for values in curve["curves"]:
                plt.plot(curve["xValues"], values, label=f"SA col {col}")
    plt.xlabel("SA feedback (uA)")
    plt.ylabel("Measured response")
    plt.legend()
