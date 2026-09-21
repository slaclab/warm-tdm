# GroupTb PyRogue ↔ VCS co-simulation

`GroupTb` simulates a full Warm-TDM **Group** (1 column board + 1 row board, a
configurable WAFER/SQUID device model — see the generics at the top of
`tb/GroupTb.vhd`) in VCS, with the **real RTL**, and bridges it to a PyRogue
server over TCP sockets. Because it clocks the real FSMs at real timing, it can
exercise things `--emulate` cannot (e.g. the FastDacDriver override/`IDLE`
timing behind Issue #86/#32).

The RTL under test is **whatever is checked out** in the working tree, so
`git checkout <branch>` before building to test a specific RTL.

`LOAD_G` selects the complete cold-load preset. The available values are:

```text
LOAD_BOARD  # simple resistive electronics load
WAFER       # legacy alias for the synthetic 32-row, one-level wafer
WAFER_32    # explicit spelling of the synthetic 32-row wafer
BICEP3      # 22-row, 12-column physical profile; eight columns instantiated here
NIST_50R    # 50-row, 12-column physical profile; provisional 5x10 banks
BA4         # 60-row, 12-column physical profile; 6x10 banks
```

Each named profile owns separate SSA, SQ1, row-FAS, and chip-FAS parameter
records. The checked-in values are explicitly synthetic until measured values
are available. Custom parameters and direct per-pixel TES stimulus remain
available on the lower-level `DetectorModuleSim`, `GroupDetectorHarnessSim`,
and `WaferSim` interfaces without expanding the top-level `GroupTb` generic
list.

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

# 3. Compile + elaborate, then launch the sim (opens TCP bridges and free-runs)
cd $(git rev-parse --show-toplevel)/firmware/build/GroupTb/GroupTb_project.sim/sim_1/behav
./sim_vcs_mx.sh                # builds ./simv; the ruckus script does not launch it
source setup_env.sh
./simv -licqueue -l simulate.log  # leave this running

# 4. PyRogue server, --sim (new shell)
conda activate warm-tdm-r615
cd software/scripts
python warmTdmServer.py --sim --simPgpRing --columnBoards 1 --rowBoards 1 --rowAddrBits 5 --maxRows 32

# 5. Client (new shell) — operations / hwtest against localhost:9099
conda activate warm-tdm-r615
python -c "import warm_tdm_api.operations as ops; sess = ops.connect(); ops.status()"
```

## Comms mode: direct-SRP bypass vs simulated PGP ring

`GroupTb` has a master toggle, `SIM_PGP_GT_C` (top of `tb/GroupTb.vhd`), that
selects how the host reaches the boards. **The `warmTdmServer.py --simPgpRing`
flag MUST be set to match** — the RTL toggle decides which TCP ports get bound,
and the software toggle decides which ports the client connects to; a mismatch
means the client dials a port nothing is listening on.

| | `SIM_PGP_GT_C := false` (bypass) | `SIM_PGP_GT_C := true` (ring) |
|---|---|---|
| MGT ring | not driven | real `Pgp2bGtx7VarLat` GTX model, board-to-board |
| SRP bridge | every board has its own | **coordinator only** |
| Row board reached | direct socket | over the ring, through the coordinator |
| Client flag | `warmTdmServer.py --sim` | `warmTdmServer.py --sim --simPgpRing` |
| Exercises the ring-routing path | no | **yes** (matches real hardware) |

The ring mode is the one that reproduces the SRP-over-ring path used on real
hardware; use it to catch ring/coordinator regressions. The bypass mode is
faster (no GTX to simulate). The checked-in toggle currently selects ring mode.
Ring mode adds GTX CDR-lock + PGP handshake time, so give the client extra settle time before the
first row-board register access (the row's ring address is only valid after
link-up).

### RX buffering and ReadAll stress

Real GTX mode uses an unthrottled receive FIFO in simulation, as on hardware.
`ROGUE_SIM_EN_G` must be false when `SIM_PORT_NUM_G=0`: GTX cannot honor the
FIFO's `tReady`, and enabling that handshake can discard data without reporting
RAM overflow. The simulation-only ready handshake is for a Rogue stream model.
Ring mode still bypasses the Ethernet/RSSI stack, so inject downstream stalls
explicitly when testing the coordinator's receive capacity.

Use the [RX buffer characterization](../../../tests/warm_tdm/pgp_ring/test_rx_buffer.py)
for an isolated GHDL test of queued replies and framing after overflow. Width 10
does not by itself bound outstanding response bytes. Waiting between PyRogue
blocks also does not serialize the 4 KiB transactions within a larger block.
See the [ReadAll investigation](../../../docs/plans/register-timeout/README.md#width-10-bound-investigation)
for the capacity calculation and remaining full-ring checks.

A watchdog expiring around a VirtualClient ReadAll does not cancel that RPC.
A second request through the same serialized client/server path can wait behind
it without reaching FPGA SRP. Establish column responsiveness with an independent
server-side probe or RTL observation before calling that result a column lockup.

### Checking simulation progress and GTX startup

The ICAP initialization message near 1.272 us can be the last timestamp printed
by a normally advancing simulation. High CPU use during free-running VCS is
also expected; neither observation establishes a delta-cycle loop.

To inspect progress, launch `./simv -licqueue -ucli -l simulate.log` instead of
the free-running command above. At the UCLI prompt:

```tcl
run 100us
puts "Reached 100 us"
```

This pauses at 100 us. Resume with `run` before making client reads; a paused
simulation cannot service SRP. For a minimal communication check, disable
startup bulk reads/writes and polling, then read AxiVersion and PGP status on
ports 10000 (column) and 10002 (row). Allow seconds of wall time per transaction;
the full simulation roots already use an extended timeout. Confirm PGP local
and remote link-ready before attempting row access.

For deeper startup debugging, inspect `pgpClk`, `pgpRst`, and `pgpRxOut(0)` in
each `PgpCore`, and `cPllLock`, `cPllRefClkLost`, `gtTxReset`, `gtRxReset`,
`txResetDone`, `rxResetDone`, `txFsmResetDone`, and `rxFsmResetDone` in its
`Gtx7Core`. Both GTX user clocks come from the free-running MMCM `pgpClk`;
recovered clock outputs are open at `PgpCore`. An unknown recovered RX clock
therefore does not feed back into the fabric RX clock here.

## TCP ports (sim side ↔ `--sim` client)

Set by generics in `tb/GroupTb.vhd` and matched by `_HardwareGroup.py`'s
simulation branch. The port layout depends on the comms mode:

**Bypass (`SIM_PGP_GT_C := false`, `--sim` without `--simPgpRing`)** — each board
binds its own sockets:

| Path | Column board (i=0) | Row board (i=1) |
|------|--------------------|-----------------|
| SRP (register) | `10000` | `11000` |
| Data stream | `20000` | `21000` |

**Ring (`SIM_PGP_GT_C := true`, `--sim --simPgpRing`)** — only the coordinator
binds sockets; each ring address is reached at `base + ringAddr*2` on the
coordinator (`RogueTcpStreamWrap` `PORT_NUM + code*2` layout):

| Path | Coordinator (addr 0) | Row board (addr 1) |
|------|----------------------|--------------------|
| SRP (register) | `10000` | `10002` |
| Data stream | `20000` | `20002` |

In both modes `SIM_PGP_PORT_NUM_G` is `0` for the real GTX ring and nonzero
(`7000`/`70000`) to keep the bypass.

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
  the GroupTb topology. A 60-row profile needs at least six row-address bits;
  the eventual dual-BA4 120-slot schedule needs seven.
