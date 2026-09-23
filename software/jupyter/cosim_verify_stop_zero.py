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
# # Cosim: stop-and-zero register sequence (interactive)
#
# Interactive notebook version of `software/cosim/verify_cosim_stop_zero.py`. It
# drives the shared **nonzero → confirmed MUX run → stopped/zero** register
# sequence (Issue #86 acceptance, software-visible portion) through a
# `VirtualClient` against a running `warmTdmServer --sim`. See
# [`software/cosim/README_cosim.md`](../cosim/README_cosim.md).
#
# Like the script, this reuses `run_cycles` from the hardware-bench helper
# `software/scripts/hwtest/verify_stop_and_zero.py` (the logic is identical on
# cosim and hardware) rather than reimplementing it. Register verification only —
# a physical DAC-voltage (DMM/scope) measurement still owns final #86 acceptance.
# Source-controlled as a percent-format `.py`; a generated `.ipynb` sits next to
# it.

# %% [markdown]
# ## Connect + config

# %%
# %run ../scripts/_setupLibPaths.py

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pyrogue.interfaces
import warm_tdm_api.operations as ops

HOST, PORT = "localhost", 9099
CYCLES = 5
FORCE_uA = 50.0
TOL_uA = 0.5
SETTLE_SEC = 5.0
NUM_PTS = 512
# The output dir must exist at this exact absolute path -- run_cycles takes data
# server-side (server + client share the host here). Create it explicitly and
# pass it as the session dir, as _cosim_common.run does for the scripts.
OUTPUT_DIR = "/tmp/cosim_stop_zero"
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = pyrogue.interfaces.VirtualClient(addr=HOST, port=PORT)
sess = ops.Session(client.root.Group,
                   output=SimpleNamespace(sessiondir=OUTPUT_DIR))
group = sess.group
sess.status()

# %% [markdown]
# ## Reach the shared `run_cycles` helper
#
# `run_cycles` lives in the hardware-bench script, which stays in
# `software/scripts/hwtest/`. Put that directory on `sys.path` (via the repo
# root) and import it — the same bridge the cosim script uses.

# %%
ROOT = Path.cwd()
while ROOT != ROOT.parent and not (ROOT / 'software/scripts/hwtest').is_dir():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / 'software/scripts/hwtest'))
from verify_stop_and_zero import run_cycles

# %% [markdown]
# ## Run the nonzero → MUX → stop/zero cycles
#
# Enable all columns, run the cycle sequence, then restore the column mask. Each
# cycle forces the fast DACs nonzero, confirms a MUX run, then stops and checks
# the outputs read back zero.

# %%
args = SimpleNamespace(cycles=CYCLES, force_uA=FORCE_uA, tol_uA=TOL_uA,
                       settle_sec=SETTLE_SEC, num_pts=NUM_PTS,
                       skip_cols='', diagnose=False)

_saved_mask = group.ColEnableMask.get()
try:
    group.ColEnableMask.set((1 << sess.chans_per_board) - 1)
    run_cycles(sess, args)
    print(f"PASS: nonzero -> confirmed mux run -> stopped/zero registers "
          f"across {CYCLES} cycles")
finally:
    group.ColEnableMask.set(_saved_mask)

print("final state: timing stopped, PID disabled, column outputs zeroed; "
      "per-row currents and column selection restored")
print("limitation: register verification only; DMM/scope DAC-voltage acceptance "
      "remains open on #86")
