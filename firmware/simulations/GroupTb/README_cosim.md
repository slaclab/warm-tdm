# GroupTb PyRogue ↔ VCS co-simulation

`GroupTb` simulates a full Warm-TDM **Group** (1 column board + 1 row board, 32
rows, a WAFER/SQUID device model — see the constants at the top of
`tb/GroupTb.vhd`) in VCS, with the **real RTL**, and bridges it to a PyRogue
server over TCP sockets. Because it clocks the real FSMs at real timing, it can
exercise things `--emulate` cannot (e.g. the FastDacDriver override/`IDLE`
timing behind Issue #86/#32).

The RTL under test is **whatever is checked out** in the working tree, so
`git checkout <branch>` before building to test a specific RTL.

## Toolchain (important version split)

| Use | Tool | Source command |
|-----|------|----------------|
| **Simulation** | Vivado **2025.1** | `source /sdf/group/faders/tools/xilinx/2025.1/Vivado/2025.1/settings64.sh` |
| Bitfile builds | Vivado **2024.1** | `source /sdf/group/faders/tools/xilinx/2024.1/Vivado/2024.1/settings64.sh` |
| VCS | X-2025.06 | `source /sdf/group/faders/tools/synopsys/vcs/X-2025.06/settings.sh` |

Use **2025.1 for simulation** — 2024.1 fails to simulate the floating-point IP
(`FpMac`/`Int2Fp`). Use **2024.1 for bitfiles** — later Vivado causes hold-time
errors in timing closure. (Source directly, not through a pipe — piping `source`
runs it in a subshell and the env won't stick.)

## Steps

```bash
# 1. Environment (simulation)
source /sdf/group/faders/tools/xilinx/2025.1/Vivado/2025.1/settings64.sh
source /sdf/group/faders/tools/synopsys/vcs/X-2025.06/settings.sh

# 2. Generate the VCS scripts (Vivado export; post_vcs.tcl patches for VHDL-2008)
cd firmware/simulations/GroupTb
make vcs                       # ~5-7 min

# 3. Compile + elaborate + launch the sim (opens the TCP bridges, then free-runs)
cd $(git rev-parse --show-toplevel)/firmware/build/GroupTb/GroupTb_project.sim/sim_1/behav
./sim_vcs_mx.sh                # builds ./simv and runs it; leave it running

# 4. PyRogue server, --sim (new shell)
conda activate warm-tdm-r615
cd software/scripts
python warmTdmServer.py --sim --columnBoards 1 --rowBoards 1 --rowAddrBits 5 --maxRows 32

# 5. Client (new shell) — operations / hwtest against localhost:9099
conda activate warm-tdm-r615
python -c "import warm_tdm_api.operations as ops; sess = ops.connect(); ops.status()"
```

## TCP ports (sim side ↔ `--sim` client)

Set by generics in `tb/GroupTb.vhd` and matched by `_HardwareGroup.py`'s
simulation branch:

| Path | Column board (i=0) | Row board (i=1) |
|------|--------------------|-----------------|
| SRP (register) | `10000` | `11000` |
| Data stream | `20000` | `21000` |
| PGP ring | `7000` | `70000` |

## Gotchas

- **`ERROR: [Project 1-228] Project '..._project' is read-only`** — the build dir
  holds a project created by a *different* Vivado version (e.g. a prior 2024.1
  run). Fix: `rm -rf $(git rev-parse --show-toplevel)/firmware/build/GroupTb` and
  re-run `make vcs`. (`firmware/build` is a symlink to `/u1/<user>/build`.)
- **Cosim is slow** — every clock is simulated. Give client scripts generous
  settle/sleep (seconds), and prefer minimal checks over long sweeps.
- **The override is a stopped-state operation** — during a MUX run the per-row
  RAM overwrites the fast-DAC output every row, so a force set *while running*
  reads back 0 regardless. Test override/zeroing with the run stopped.
- Match `warmTdmServer.py --sim` board counts / `--rowAddrBits` / `--maxRows` to
  the GroupTb constants (1 col, 1 row, 5-bit row addr, 32 rows).
