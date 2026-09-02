# Warm TDM — Agent Orientation

## Project Summary

Warm TDM is a time-division multiplexing detector readout system for TES (Transition-Edge Sensor) bolometric detector arrays using SQUID multiplexing, developed at SLAC National Accelerator Laboratory.

The system has two board types:
- **Row boards** — Drive row-select DAC signals for TDM switching (sequentially addressing detector rows)
- **Column boards** — Digitize SQUID amplifier signals via ADC, apply real-time DSP (PID loops, filtering, flux-jump detection), and drive bias/feedback DACs

Boards communicate via a **PGP ring topology** with Ethernet bridge for host access, and synchronize via a **custom serialized timing protocol** (259-bit frames, 8B/10B encoded). A "**Group**" is a set of Row + Column boards managed as a single unit (typically 2 Row + 4 Column boards).

## Repository Layout

```
warm-tdm/
├── firmware/
│   ├── targets/                # 14 FPGA build targets (Row/Column variants)
│   │   ├── ColumnFpgaBoard/    #   Kintex-7, prom output
│   │   ├── ColumnAu25p/        #   Artix UltraScale+, bit output, 10G Ethernet
│   │   ├── RowFpgaBoard/       #   Kintex-7, prom output
│   │   ├── RowModule/          #   Compact row module
│   │   ├── ColumnModule/       #   Compact column module
│   │   ├── Makefile            #   Aggregate build (all targets)
│   │   └── ...                 #   Numbered/feature variants (0, 325, AwaXe, 10G)
│   ├── common/warm_tdm/        # Shared RTL library
│   │   ├── rtl/                #   ~44 VHDL entities (production logic)
│   │   ├── sim/                #   Device simulation models
│   │   ├── xdc/                #   Shared timing constraints
│   │   ├── ip/                 #   Xilinx IP cores (Int2Fp, FpMac)
│   │   └── ruckus.tcl          #   Loads common sources into build
│   ├── python/warm_tdm/        # PyRogue device drivers (~47 files)
│   ├── simulations/            # Testbenches (GroupTb, RowTb, StackTb)
│   ├── submodules/             # surf + ruckus (git submodules)
│   └── releases.yaml           # Release and packaging config
├── software/
│   ├── python/warm_tdm_api/    # High-level API (tuning, data, GUI logic)
│   │   ├── widgets/            #   PyDM UI components
│   │   └── operations/         #   Client-side operational layer (acquisition,
│   │                           #   setup, analysis); import explicitly
│   ├── scripts/                # Executable entry points (server, GUI, client)
│   ├── cfg/                    # YAML hardware configuration files
│   ├── lib/                    # C/C++ shared library
│   └── jupyter/                # Analysis notebooks
├── docs/
│   ├── RELEASE.md              # Release process + git workflow
│   └── src/                    # Sphinx documentation source
├── conda.yml                   # Conda environment definition
├── .gitmodules                 # Submodule declarations (surf, ruckus)
└── releases.yaml               # Top-level release config
```

## Architecture Overview

### Data Flow (Column Board)

```
AD9681 ADC → DataPath → AdcDsp (PID + baseline + flux-jump) → EventBuilder → PGP Stream → Host
                                    ↕
                          FastDacDriver (SQ1 feedback)
                          RowDacDriver (SA feedback)
```

### Timing System

A dedicated serialized link distributes synchronization across all boards:
- 259-bit timing frame (`TIMING_NUM_BITS_C`) with 8B/10B encoding
- K-character framing: IDLE, START_RUN, ROW_STROBE, SAMPLE_START/END, PWR_SYNC_WAIT, etc.
- `LocalTimingType` record decodes timing into: runTime, rowStrobe, sample, rowSeq, daqReadout signals
- Coordinator board (RING_ADDR_0) generates timing; other boards receive and decode
- See `firmware/common/warm_tdm/rtl/TimingPkg.vhd` for all protocol constants
- For the full protocol specification (control characters, row-boundary sequences, pwrSync behavior), see [`firmware/common/TimingProtocol.md`](firmware/common/TimingProtocol.md)

### Communication

- **PGP ring**: Boards connected in a ring via MGT links; `RingRouter` routes frames by address and tags each board's data with its ring address in `tDest[6:4]` (stream type in `tDest[3:0]`)
- **Ethernet bridge**: Coordinator board bridges Ethernet↔PGP ring for host access
- **Host protocol**: RSSI/SRP over UDP (register access on port 8192, data on port 8193)
- **Data channelization**: the full TDEST scheme — per-board stream tags, the ring board tag, host demux, file-channel layout (readout=9, PID-debug=0–7, config=255), the multi-board caveat, and the migration plan — is documented in [`firmware/common/DataChannelization.md`](firmware/common/DataChannelization.md)

### Platform Support

| Platform | Part | Transceiver | Targets |
|----------|------|-------------|---------|
| Kintex-7 | XC7K160T | GTX/GTP | ColumnFpgaBoard, RowFpgaBoard, *Module variants |
| Artix UltraScale+ | xcau25p | GTY | ColumnAu25p |

Platform-specific files use suffixes: `*7s.vhd` (7-Series), `*Usp.vhd` (UltraScale+)

### Clock Domains

- **125 MHz** — AXI-Lite bus (`axilClk`), derived from 250 MHz GT ref via MMCM
- **250 MHz** — GT reference clock (`gtRefClk0`)
- **156.25 MHz** — Secondary GT reference for Ethernet (`gtRefClk1`)
- **Variable** — Timing clocks (timingRxClk, timingTxClk) and ADC clocks (500 MHz data clock on Column)

## Key Entities

| Entity | Path (under `firmware/common/warm_tdm/rtl/`) | Role |
|--------|----------------------------------------------|------|
| WarmTdmCore2 | `WarmTdmCore2.vhd` | Top integration: timing + comms + AXI crossbar + app |
| DataPath | `DataPath.vhd` | ADC interface + DSP pipeline instantiation |
| AdcDsp | `AdcDsp.vhd` | Per-column PID loop, baseline tracking, flux-jump |
| Timing | `Timing.vhd` | Top timing module (instantiates Tx + Rx) |
| TimingTx | `TimingTx.vhd` | Timing frame generation (coordinator only) |
| TimingRx | `TimingRx.vhd` | Timing frame receive and decode |
| TimingPkg | `TimingPkg.vhd` | Protocol constants and LocalTimingType record |
| PgpEthCore | `PgpEthCore.vhd` | PGP ring + Ethernet bridge |
| RingRouter | `RingRouter.vhd` | Frame routing/depacketization in PGP ring |
| EventBuilder | `EventBuilder.vhd` | Packs 8-channel DSP output into data frames |
| RowDacDriver2 | `RowDacDriver2.vhd` | Row-select DAC sequencing |
| FastDacDriver | `FastDacDriver.vhd` | SQ1 feedback fast DAC driver |
| WarmTdmPkg | `WarmTdmPkg.vhd` | Package constants and AXI stream configs |

## Firmware Conventions

- **Library**: All RTL loaded as `-lib warm_tdm`
- **VHDL standard**: 2008 (`-fileType "VHDL 2008"`)
- **Naming**: Entity names match filenames (`AdcDsp` → `AdcDsp.vhd`)
- **Generics**: Suffixed `_G` (e.g., `TPD_G`, `SIMULATION_G`, `RING_ADDR_0_G`, `ETH_10G_G`, `GEN_ADC_FILTER_G`)
- **Constants**: Suffixed `_C` (e.g., `AXIL_CLK_FREQ_C`, `APP_BASE_ADDR_C`)
- **Signal style**: camelCase (`axilClk`, `timingRxData`)
- **Architecture**: Always named `rtl`
- **SURF library usage**: Import `surf.StdRtlPkg`, `surf.AxiLitePkg`, `surf.AxiStreamPkg`, `surf.SsiPkg`
- **XDC split**: Common timing constraints AND board pinouts live in `common/warm_tdm/xdc/`; each target loads its own pinout by explicit `loadConstraints -path` (the common `xdc` `-dir` auto-load stays disabled so a target pulls in only its own pinout)
- **Platform abstraction**: Wrapper entities instantiate `*7s` or `*Usp` variants based on `FPGA_FAMILY_G` or target context
- **License**: SLAC proprietary header required on all source files

For detailed firmware conventions, see [`firmware/FIRMWARE_GUIDE.md`](firmware/FIRMWARE_GUIDE.md).

## Software Conventions

- **Two Python packages**:
  - `warm_tdm` (in `firmware/python/`) — Low-level PyRogue device drivers mapping FPGA registers
  - `warm_tdm_api` (in `software/python/`) — High-level control, tuning algorithms, GUI logic
- **`warm_tdm_api.operations` subpackage**: client-side operational layer
  (acquisition, hardware setup, analysis/plotting) driving the rogue tree
  remotely; kept distinct from the tree device modules. Not auto-imported — use
  `import warm_tdm_api.operations`. Hardware-coupled ops are methods on a
  `Session` object (`ops.connect()`/`ops.use()` establish a cached default for
  the notebook shims; tests/scripts construct their own `Session`). Pure helpers
  live in `formats.py`. (Formerly the `warm_tdm_jupyter` package.)
- **Device file naming**: Underscore prefix (`_AdcDsp.py`), exported via `__init__.py`
- **Device pattern**: Classes inherit `pr.Device`, registers defined as `pr.RemoteVariable(offset=..., bitSize=..., bitOffset=...)`
- **Commands**: `pr.RemoteCommand` with function callbacks
- **Hierarchy**: `GroupRoot` → `Group` → `HardwareGroup` → board devices → sub-devices
- **Tuning**: Long-running algorithms implemented as `pr.Process` devices (start/stop/status)
- **GUI**: PyDM-based widgets in `software/python/warm_tdm_api/widgets/`
- **Client-server**: ZMQ-based PyRogue server; clients connect remotely

For detailed software conventions, see [`software/SOFTWARE_GUIDE.md`](software/SOFTWARE_GUIDE.md).

## Build System

Uses SLAC **ruckus** build system wrapping Xilinx Vivado.

### Vivado version (important)

Firmware builds **must use Vivado 2024.1**. Later versions have a bug that
causes hold-time errors in timing closure. Vivado is not on PATH by default;
source it before building:

```bash
source /sdf/group/faders/tools/xilinx/2024.1/Vivado/2024.1/settings64.sh
```

### Target Makefile Pattern
```makefile
target: prom                    # 'prom' for 7-series, 'bit' for AU25P
export PRJ_PART = XC7K160TFFG676-1
export RUCKUS_DIR = $(abspath $(PWD)/../../submodules/ruckus)
export PRJ_VERSION = 0x00000001
export GIT_BYPASS = 1
export GZIP_BUILD_IMAGE = 1
include $(RUCKUS_DIR)/system_vivado.mk
```

### Target ruckus.tcl Pattern
```tcl
source -quiet $::env(RUCKUS_DIR)/vivado_proc.tcl
loadRuckusTcl $::env(TOP_DIR)/submodules/surf
loadRuckusTcl $::env(TOP_DIR)/common/warm_tdm
loadSource -lib warm_tdm -dir "$::DIR_PATH/rtl" -fileType "VHDL 2008"
loadConstraints -path $::env(TOP_DIR)/common/warm_tdm/xdc/WarmTdmCore2.xdc
loadConstraints -dir "$::DIR_PATH/xdc"
# Feature generics set via:
set_property generic "RING_ADDR_0_G=true ETH_10G_G=true" [current_fileset]
```

### Build Commands
```bash
# Single target
cd firmware/targets/ColumnFpgaBoard && make prom

# All targets
cd firmware/targets && make

# Specific target via aggregate Makefile
cd firmware/targets && make ColumnAu25p

# Open Vivado GUI for a target
cd firmware/targets/ColumnFpgaBoard && make gui
```

### Build Output Location

Vivado project and run outputs are at:
```
firmware/build/<TargetName>/
├── <TargetName>_project.xpr         # Vivado project file
├── <TargetName>_project.runs/
│   ├── synth_1/runme.log            # Synthesis log (check for ERRORs here)
│   ├── impl_1/runme.log             # Implementation log
│   └── <IpName>_synth_1/runme.log   # Per-IP synthesis logs
```

Final images (`.bit`, `.mcs`) go to:
```
firmware/targets/<TargetName>/images/
```

To diagnose a failed build, check:
```bash
grep "ERROR" firmware/build/<TargetName>/<TargetName>_project.runs/synth_1/runme.log
```

## Running the Software

```bash
# Create conda environment
conda env create -f conda.yml

# Start hardware server
cd software/scripts && python warmTdmServer.py --ip <board-ip>

# Start GUI
python warmTdmGui.py

# Command-line client
python warmTdmClientCmd.py

# Emulation mode (no hardware — fakes register memory via MemEmulate)
python warmTdmGui.py --emulate       # or warmTdmServer.py --emulate (headless)
```

## Releases

WarmTDM uses a surf-style branch model: feature branches merge into
`pre-release`, which is promoted to `main`, and releases are cut by tagging
`main` with `vX.Y.Z`. Pushing a version tag triggers the `gen_release` CI job,
and firmware `.mcs` images are attached to the GitHub Release via
`ruckus/scripts/firmwareRelease.py`.

**Merge, do not rebase.** This repo's workflow is merge-based throughout. To
bring an upstream branch (e.g. `pre-release`) into a feature branch, `git merge`
it and resolve conflicts in the merge commit — never `git rebase`. Rebase is not
the workflow we use, even for a local-only branch that has never been pushed.

**Base every PR on `pre-release`, never `main`.** When opening a PR (`gh pr
create`), the base branch is `pre-release` — this is a hard default, not a
preference. Feature work, bug fixes, roadmap tracks, submodule bumps: all target
`pre-release`. `main` receives changes *only* through the periodic
`pre-release` → `main` promotion PR, which is the sole PR whose base is `main`.
`gh pr create` guesses a base from the repository default branch (`main` here),
so pass `--base pre-release` explicitly and confirm it before merging — a PR
merged into `main` by mistake bypasses the whole feature → `pre-release` →
`main` flow and forces a recovery merge back into `pre-release` (as happened with
PR #93). If a change ever genuinely needs to reach `main` ahead of a promotion,
raise it with a maintainer rather than retargeting the PR.

For the full workflow, versioning scheme, and release steps, see
[`docs/RELEASE.md`](docs/RELEASE.md). Release packaging config is in
[`firmware/releases.yaml`](firmware/releases.yaml).

## Project Board & Issue Tracking

Cross-branch planning and PR sequencing live on the GitHub Project board
**["Warm-TDM Roadmap"](https://github.com/orgs/slaclab/projects/43)** (org-owned,
linked to this repo — Projects v2 cannot be repo-owned). The board is the single
source of prioritization; the cross-track merge roadmap (branch topology,
landing order, sequencing decisions) lives on the
[wiki](https://github.com/slaclab/warm-tdm/wiki/Branch-Merge-Roadmap) — it
coordinates work across branches, so it is not tied to any one branch of the
code tree.

**Issue vs PR (the model this repo follows):**
- An **Issue** is the durable *what/why* — a goal, feature, or track. It is what
  gets prioritized on the board and can outlive several PRs.
- A **PR** is the *how* — one concrete attempt. It is a review artifact, not a
  planning card. A PR closes its issue with `Closes #<n>` in the body; on merge
  GitHub auto-closes the issue and its board card moves to Done.
- Do **not** add PRs to the board as separate cards when they close a tracked
  issue — the linked issue already tracks the work. (PR #67 is a legacy
  exception, added before this convention.)

**Conventions:**
- **`roadmap` label** — marks epic/planning issues (merge sequencing, multi-PR
  tracks) so they stay out of the normal bug/feature stream. Filter the Issues
  tab with `label:roadmap` (epics only) or `-label:roadmap` (real work only).
- **Board fields:** `Track` (PR sequencing / Software / Firmware / DDR readout /
  Other), `Priority` (P0-now / P1-next / P2-later), `Status` (Todo / In Progress
  / Blocked / Done). Set these on each item, not on the issue body.
- **Branch flow still applies:** roadmap PRs target `pre-release` (see Releases).

**Tooling note:** Projects v2 is GraphQL-only and needs a token with the
`project` (+ `read:org`) scope; the `gh project` subcommand requires gh ≳ 2.20.
Board views (kanban, table) are created in the web UI — the API cannot create
them.

### Hardware Verification wiki (the "hardware test list")

The wiki page
**[Hardware Verification](https://github.com/slaclab/warm-tdm/wiki/Hardware-Verification)**
is the hardware test list: an index of every change that is *code-complete but
still needs a pass on real hardware*, with one subpage per item
(`HW-Verify-Issue-<n>-<slug>`) giving a step-by-step bench procedure and pass
criteria. Like the roadmap, it lives on the wiki because it coordinates work
that spans branches (some items merged, some on feature branches). The
authoritative *status* is still the board field **`Status = Needs HW Test`**;
the wiki holds the *how-to-verify* the board can't.

**Keep it in sync (do this as a matter of course, not only when asked):**
- When an item's board Status moves **to** `Needs HW Test` (a change lands
  code-complete but unproven on hardware), add a subpage from the template shape
  of the existing ones and a row to the index table.
- When an item is verified on the bench and moves **off** `Needs HW Test`
  (→ Done, or back to In Progress on failure), update its subpage outcome and
  the index row to match — don't silently leave a stale "pending" page.
- Keep the links bidirectional: each subpage links its Issue/PR, and each
  Issue/PR body carries a backlink to its subpage (see the "Hardware
  verification procedure" footer). Add the footer when you create a subpage.
- The board is authoritative on *status*; the wiki is authoritative on *how to
  verify*. When they disagree, fix the wiki to match the board.

## Essential Reading by Task

| Task Area | Start With These Files |
|-----------|----------------------|
| Timing protocol | [`TimingProtocol.md`](firmware/common/TimingProtocol.md), `TimingPkg.vhd`, `TimingTx.vhd`, `TimingRx.vhd`, `TimingSerializer*.vhd`, `TimingDeserializer*.vhd` |
| DSP / data path | `DataPath.vhd`, `AdcDsp.vhd`, `BiquadFilter.vhd`, `EventBuilder.vhd` |
| Communication / PGP | `PgpEthCore.vhd`, `RingRouter.vhd`, `PgpRingRouter.vhd`, `EthCore.vhd` |
| Row board firmware | `RowDacDriver2.vhd`, `RowModuleDacs.vhd`, `RowModuleTimingRx.vhd` |
| Clock distribution | `ClockDist.vhd`, `ClockDist7s.vhd`, `ClockDistUsp.vhd`, `TimingMmcm.vhd` |
| Adding a new target | Copy existing target dir; modify `Makefile` (PRJ_PART, target) and `ruckus.tcl` (generics, constraints) |
| PyRogue drivers | `_WarmTdmCore2.py`, `_AdcDsp.py`, `_HardwareGroup.py`, `_TimingTx.py`, `_TimingRx.py` |
| Tuning algorithms | `software/python/warm_tdm_api/_SaTune.py`, `_Sq1Tune.py`, `_FasTune.py` |
| Simulation | `firmware/simulations/StackTb/` (full system), `firmware/common/warm_tdm/sim/` (device models) |
| Constraints / timing closure | `common/warm_tdm/xdc/WarmTdmCore2.xdc` (shared), target-specific `xdc/` dirs |

## Submodules

| Submodule | URL | Purpose |
|-----------|-----|---------|
| surf | github.com/slaclab/surf | SLAC Universal RTL Framework — AXI, protocols, device IP |
| ruckus | github.com/slaclab/ruckus | Build system — Vivado TCL automation, Makefile targets |

```bash
git submodule update --init --recursive
```
