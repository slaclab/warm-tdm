# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
# %% [markdown]
# # Cosim register, readout and stop/zero checks
# Run against a dedicated, stopped simulation server. Each cell calls the same
# implementation as the batch check, including cleanup and evidence recording.
# Edit each call for the compiled fixture; a VCS pass is not physical acceptance.

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
controls = runs.run_cosim("verify_cosim_controls", RUN_DIR, connection_args)

# %%
readout = runs.run_cosim("verify_cosim_readout", RUN_DIR,
    connection_args + ["--rows", "2", "--acq", "30", "--start-delay", "5"])

# %%
stop_zero = runs.run_cosim("verify_cosim_stop_zero", RUN_DIR,
    connection_args + ["--cycles", "5", "--settle-sec", "5"])

# %% [markdown]
# Inspect result.json and console.txt under the printed invocation directories.
# Record outcomes and links to modeled DAC traces; register checks alone do not
# establish analog stop/zero behavior.
