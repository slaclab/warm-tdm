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
WAFER_32    # explicit spelling of the synthetic 1x32 wafer
WAFER_8X10  # synthetic 80-row wafer: eight chip-select banks of ten rows
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
python warmTdmServer.py --sim --simPgpRing --columnBoards 1 --rowBoards 1 --rowAddrBits 7 --maxRows 32

# 5. Client (new shell) — operations / hwtest against localhost:9099
conda activate warm-tdm-r615
python -c "import warm_tdm_api.operations as ops; sess = ops.connect(); ops.status()"
```

## Wafer configuration

Select the preset when generating the VCS scripts:

```bash
LOAD=WAFER_32 make vcs          # 1x32: 32 rows, no chip select (default)
LOAD=WAFER_8X10 make vcs        # 8x10: 80 rows, two-level selection
```

These dimensions are banks × rows per bank; both presets model eight columns
on one column board and one row board. `LOAD` accepts the preset names above
(case insensitive), defaults to `WAFER`, and sets `GroupTb.LOAD_G`. Invalid
names fail during project generation. It can be combined with `USE_FLOAT_PID`,
`ETH_10G`, `VARIATION_SEED`, and `TES_CURRENT_SCALE`. After changing it,
regenerate the scripts, rebuild `simv`, and restart the simulation and server.

Both board RTL defaults use seven row-address bits (128 RAM entries). Keep
`--rowAddrBits 7` for either preset; `--maxRows` controls the software extent:

| Preset | Server options | Group row-map command | Physical select lines |
|---|---|---|---|
| `WAFER_32` | `--rowAddrBits 7 --maxRows 32` | `RowMap1x32()` | RS 0–31; no CS |
| `WAFER_8X10` | `--rowAddrBits 7 --maxRows 80` | `RowMap8x10()` | RS 0–9; CS 10–17 |

For example, start the 8x10 server with:

```bash
python warmTdmServer.py --sim --simPgpRing --columnBoards 1 --rowBoards 1 --rowAddrBits 7 --maxRows 80
```

Then program the matching map and logical row order from a client before
starting acquisition (use `RowMap1x32()` and `range(32)` for 1x32):

```python
import warm_tdm_api.operations as ops
sess = ops.connect()
sess.group.RowMap8x10()
sess.group.RowReadoutOrder.set(list(range(80)))
```

The 8x10 logical row is `bank * 10 + row`, with chip line `10 + bank`.
The model uses the same synthetic device parameters as `WAFER_32`, with a
chip FAS added for each bank. Operating points still require tuning for the
selected topology.

## Ethernet bandwidth

Select the Ethernet mode when generating the simulation, then compile and
launch the resulting simulator as above:

```bash
ETH_10G=0 make vcs              # 1 Gbit/s payload ceiling
ETH_10G=1 make vcs              # 10 Gbit/s payload ceiling (default)
```

`ETH_10G` accepts `0/1`, `false/true`, or `no/yes` (case insensitive). It sets
`GroupTb.ETH_10G_G`, propagated through both board simulation models to
`EthCore`. Changing it requires regenerating and rebuilding the simulation;
there is no corresponding PyRogue client option. It can be combined with
`USE_FLOAT_PID`, `VARIATION_SEED`, and `TES_CURRENT_SCALE`.

| Mode | Ethernet clock | Stream width | Aggregate payload ceiling per direction |
|------|----------------|--------------|-----------------------------------------|
| 1G | 125 MHz | 8 bytes | 1 Gbit/s = 125 MB/s |
| 10G | 156.25 MHz | 8 bytes | 10 Gbit/s = 1.25 GB/s |

`EthSimBandwidth` uses SURF's simulation-only `RogueTcpStreamPacer` to count
accepted payload bytes in **simulation time**. SRP and data sockets, including
all their local/remote TDEST channels, share one budget per Ethernet port.
Transmit and receive have independent budgets, modeling full duplex. Idle
credit is capped at one eight-byte beat, partial final beats charge only valid
bytes, and backpressure propagates upstream. The TCP port layout is unchanged.
The SimLink wrappers' own per-wrapper pacing stays disabled because the shared
pacer accounts for both wrappers together. This replaces the former one-byte
1G stream and separate SRP/data ceilings.

These are **payload ceilings**, not wire-accurate Ethernet throughput: cosim
bypasses MAC, UDP/IP and RSSI framing, acknowledgments, retransmissions and
interpacket gaps. Real application throughput is lower and depends on packet
sizes and protocol behavior. Arbitration and other simulated paths may also
reduce achieved throughput. Host TCP speed and simulator wall-clock speed do
not define the modeled bandwidth. In ring mode all boards share the
coordinator's Ethernet budget; bypass mode gives each board its own port budget.

The isolated regression checks both rates, concurrent SRP/data, full duplex,
partial beats, ordering/sidebands, backpressure, idle credit and reset:

```bash
# From the repository root; requires the local regression environment and GHDL.
.venv/bin/python -m pytest tests/warm_tdm/ethernet/test_bandwidth.py -q
```

It runs the real bandwidth helper and SURF pacer without TCP or vendor IP;
full `GroupTb` socket/PGP behavior still requires the VCS workflow above.

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
Ring mode models the selected aggregate Ethernet payload ceiling while still
bypassing the Ethernet/RSSI stack. Inject additional downstream stalls when
testing the coordinator's receive capacity under RSSI/host delays.

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
