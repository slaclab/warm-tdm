# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
# %% [markdown]
# # Timing-register read latency
# Measure client round-trip register-read latency against a running server.
# This does not measure ADC-to-DAC pipeline latency. It performs no setup or
# timing writes. The older LatencyDebug notebook, including its saved outputs,
# is preserved under docs/reference/measurements/.

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


# %%
import json
import time

COUNT = 20
tx = sess.coordinator_cb.WarmTdmCore.Timing.TimingTx
samples = []
for _ in range(COUNT):
    start = time.perf_counter()
    tx.ReadDevice()
    samples.append(time.perf_counter() - start)
path = RUN_DIR / "data" / f"register-latency-{time.time_ns()}.json"
path.write_text(json.dumps(dict(seconds=samples, operation="TimingTx.ReadDevice"), indent=2))
print("Median / max seconds:", np.median(samples), max(samples))

# %% [markdown]
# ## Observations
# Record transport, polling/load conditions, server revision, and comparison runs.
