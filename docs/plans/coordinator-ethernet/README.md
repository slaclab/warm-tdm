# Coordinator-only Ethernet

## Goal and implementation

Generate `PgpEthCore.U_EthCore_1` only when the existing boolean
`RING_ADDR_0_G` is true. Non-coordinators retain PGP data/register access;
the absent Ethernet AXI-Lite window returns DECERR, its master stays idle,
and its stream/status outputs have defined tie-offs.

The shared `WarmTdmCore.xdc` holds non-Ethernet constraints. Coordinator
targets explicitly load `WarmTdmCore_1g.xdc` or `WarmTdmCore_10g.xdc` after
it, matching `ETH_10G_G`. Non-coordinators load neither Ethernet XDC. These
files use the new `GEN_ETH.U_EthCore_1` hierarchy.
All constraints are managed XDC; target ruckus files select them without
conditional netlist queries or unmanaged constraint scripts. HardwareGroup
disables the Ethernet device subtree for ring addresses other than zero so
startup/configuration reads do not access the absent batcher registers.

## Validation and remaining work

- Implemented locally, including the core/common naming cleanup.
- GHDL 6.0 analysis/elaboration and four focused simulations passed for
  `RING_ADDR_0_G` true/false crossed with `ETH_10G_G` true/false. The harness
  used the real PgpEthCore, SURF crossbars and reset logic, with PgpCore and
  EthCore interface stubs. It checked conditional Ethernet presence, status
  tie-offs, idle masters, stream routing/backpressure, PGP register responses,
  and Ethernet-window read/write OKAY versus DECERR responses. This does not
  qualify the internal Ethernet/PGP cores or their physical links.
- After the rename, final XDC checks passed all three clock configurations
  (no Ethernet, 1G, 10G). All selected XDC files were evaluated
  with mocked Vivado queries in an interpreter with `if`, `llength`, loops,
  `proc`, and `eval` hidden; expected clocks and nonempty clock groups passed.
  The real ruckus `loadConstraints` procedure, with mocked Vivado file
  commands, passed all eight active targets. Three 1G coordinators and two
  10G coordinators select the matching Ethernet XDC; three non-coordinators
  load none. File order, board pinouts and consistency with target generics
  were checked. This does not replace Vivado constraint validation.
- Python syntax and `git diff --check` passed. PyRogue is unavailable in the
  default local Python, so the device-tree change has no runtime validation.
- Software regression: `.venv/bin/python -m pytest software/tests -q` passed
  127 tests and 54 subtests. Removed a stale AllFastDacs test case for the
  already-deleted ColumnModule Python driver; both maintained column-board
  variants remain covered. Package-export paths and renamed class declarations
  passed static checks. Core/common RTL and Python bodies were compared with
  the pre-rename maintained sources to confirm only names/comments/whitespace
  changed. No active code references the superseded `*2` core/common names.
- Vivado 2024.1 is unavailable on this workstation. Synthesis, timing,
  resource savings, and physical ring/host operation remain unverified.
- Before integration, record affected coordinator/non-coordinator builds
  and hardware acceptance on an owning issue. No new issue has been created;
  #70 is related resource work, not an explicit owner for this change yet.

## Clock and reset dependency audit (2026-09-16)

Source review of commit `316b112` found no shared hardware clock or reset
supplied by EthCore. All EthCore clock/reset ports are inputs; its generated
clocks, MMCM resets and 10G QPLL signals stay inside that entity.

| Clock / consumer | Source retained on non-coordinators |
| --- | --- |
| 125 MHz fabric reference | ClockDist buffers/divides the external 250 MHz reference |
| 125 MHz AXI-Lite and application AXI-stream clocks | PgpCore.ClockManager7, fed by the fabric reference |
| 62.5 MHz PGP fabric clock | Second output of that same PgpCore MMCM |
| PGP serial link | PGP channel CPLL using the 250 MHz GT reference; its QPLL inputs are unused |
| Timing TX bit/word clocks | TimingTx MMCM using the 125 MHz fabric reference |
| Timing RX bit/word clocks | TimingRx MMCM using the incoming differential timing clock |
| ADC output clock, column timing/DSP and row DAC timing | Timing RX word clock exported as timingRxClk125 |
| 200 MHz IDELAYCTRL reference | Separate Timing.U_MMCM_IDELAY using the 125 MHz fabric reference |
| Device DNA and ICAP clocks | WarmTdmCommon/AxiVersion logic retained by the naming cleanup |
| 156.25 MHz reference heartbeat | ClockDist's second reference buffer, outside EthCore |

The removed clocks are Ethernet's private 125/62.5 MHz MMCM outputs for 1G,
or its private 156.25 MHz MMCM output and PHY/QPLL clocks for 10G. PgpCore is
always generated when SIMULATION_G=false, regardless of RING_ADDR_0_G.
WarmTdmCore exports PgpCore's AXI clock/reset to the application. Its power-up
reset and the timing subsystem's resets do not depend on Ethernet. Outside
EthCore, phyReady/RSSI status only drive LEDs; tying them low does not hold
another subsystem in reset.

The shared XDC retains the primary references and all non-Ethernet generated
clocks above, with no ethClk references. The speed-specific XDC files only
name Ethernet clocks and add their clock-group exceptions. No active target
XDC references a removed Ethernet clock outside those selected files.
In particular, keep gtRefClk1 and its primary clock constraint even without
Ethernet: fabRefClk1 still clocks Heartbeat_RefClk1. XDC selection describes
the generated hardware; it is the VHDL generate that removes clock circuitry.

An existing simulation-only limitation was also found: setting both
SIMULATION_G=true and SIMULATE_PGP_G=true removes PgpCore without an alternate
driver for PgpEthCore's axilClk/axilRst. This condition already existed before
316b112. The current ColumnFpgaBoardModel and RowFpgaBoardModel explicitly use
SIMULATE_PGP_G=false and retain the PGP MMCM. Also, the new Ethernet generate
applies in simulation: non-coordinators no longer provide direct EthCore TCP
endpoints. Full-system simulation access remains to be qualified.

This is a source/constraint dependency audit, not synthesis sign-off. The
earlier stubbed GHDL and mocked XDC checks do not validate real MMCM/GT
elaboration, synthesized pin paths, clock propagation, placement or timing.
Vivado 2024.1 is unavailable locally. Before acceptance, build the affected
targets and inspect synthesis/implementation clock and timing reports:

- On non-coordinators, confirm Ethernet MMCM/GT resources are absent while
  PGP, AXI, timing and IDELAY clocks remain present at the expected frequencies.
- Check for undriven clock/reset nets, missing XDC objects, unclocked sequential
  endpoints and timing/DRC failures. Review clock interactions and exceptions.
- On both 1G and 10G coordinators, confirm the selected XDC resolves the new
  GEN_ETH hierarchy and preserves Ethernet clocks and crossing constraints.
- Exercise PGP register/data access, timing lock, ADC readout and row DAC
  operation on non-coordinators, plus host Ethernet access on the coordinator.

## Core/common naming cleanup

The maintained `WarmTdmCore2` and `WarmTdmCommon2` replace the original
implementations under the unsuffixed names in both RTL and Python. The active
common and Ethernet XDC files use the unsuffixed core name as well; the original
legacy constraints are removed. Active board instantiations, target loaders,
package exports, host scripts, tests and current guides follow the rename.
RTL instance labels stay the same, preserving constraint hierarchy paths.

The Python common-register subtree becomes `WarmTdmCore.WarmTdmCommon`.
Existing scripts and saved YAML using `WarmTdmCommon2` must migrate their path;
register addresses and logic are unchanged. Other `*2` devices are out of scope.
Archived RowModule consumers and RowTb/StackTb retain their historical sources
and require a historical checkout with the original core/common interfaces.
Commit-specific references in the old verification log retain their original
filenames.

Files: PgpEthCore and WarmTdmCore/WarmTdmCommon RTL, their active board
instantiations, shared XDC files, all active target loaders, renamed Python
drivers/package exports, HardwareGroup, host callers/tests, and current guides.
