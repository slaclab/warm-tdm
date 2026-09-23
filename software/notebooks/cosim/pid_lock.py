# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
# %% [markdown]
# # Cosim PID lock exploration
# Uses the batch lock recipe and cleanup. This is a diagnostic, not a pass/fail
# acceptance check. Defaults describe the documented 23-uA model fixture.

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
result_dir = runs.run_cosim("cosim_pid_lock", RUN_DIR,
    ["--host", HOST, "--port", str(PORT), "--rows", "8",
     "--seed-tune-points", "--seed-tune", "--secs", "20"])

# %%
import json
import matplotlib.pyplot as plt
trace_path = max((RUN_DIR / "data").glob("pid-lock-*.json"), key=lambda p: p.stat().st_mtime_ns)
trace = json.loads(trace_path.read_text())
plt.plot(range(1, len(trace["trajectory"]) + 1), trace["trajectory"])
plt.xlabel("Time (s)")
plt.ylabel("Mean absolute accumulated error (counts)")

# %% [markdown]
# Record operating point, gain changes and observations here. A failed attempt's
# console remains under data/ even if no completed trajectory was produced.
