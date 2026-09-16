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
