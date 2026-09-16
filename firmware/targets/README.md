# Firmware targets

Active targets are thin build configurations over shared board sources. The
authoritative target catalog is [`../releases.yaml`](../releases.yaml); keep
the aggregate [Makefile](Makefile) aligned with it. Release procedure and branch
policy are in [`docs/RELEASE.md`](../../docs/RELEASE.md).

## Naming and source ownership

Names use `Function·FpgaBoard·Part·[FrontEnd]·[Coord]·[10G]`:

- `160` and `325` identify XC7K160T and XC7K325T parts.
- `Coord` selects `RING_ADDR_0_G=true`, replacing the old `0`/`Coordinator`
  suffixes.
- `AwaXe` identifies the front end; `10G` identifies the Ethernet option.

| Target | RTL top |
|---|---|
| `ColumnFpgaBoard160` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard160Coord` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Coord` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Coord10G` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325AwaXeCoord10G` | `ColumnFpgaBoardAwaXe` |
| `RowFpgaBoard160` | `RowFpgaBoard` |
| `RowFpgaBoard160Coord` | `RowFpgaBoard` |
| `RowFpgaBoard325` | `RowFpgaBoard` |

The board tops live in `../common/warm_tdm/rtl/`, board simulation sources in
`../common/warm_tdm/sim/`, and pinouts in `../common/warm_tdm/xdc/`. Targets
select a top, generics, constraints, and build hooks. Active variants must not
load shared RTL from sibling target directories.

This removes the old dependency on a specially named canonical target that
owned every variant's sources. Target names can then change without renaming
RTL entities or the PyRogue device hierarchy. A broader `Dev/Bicep` naming
scheme was rejected because it added churn without fixing that dependency.

## Constraint selection

Each active target explicitly loads `WarmTdmCore2.xdc` and exactly its own board
pinout (`ColumnFpgaBoard.xdc`, `ColumnFpgaBoardAwaXe.xdc`, or `RowFpgaBoard.xdc`).
The common `ruckus.tcl` must keep `loadConstraints -dir .../xdc` disabled:
loading the directory would combine incompatible board pinouts. Common RTL and
simulation directories can be loaded as VHDL 2008.

When moving sources, also check `firmware/simulations/*/ruckus.tcl`, release
image paths, and build hooks. Simulation targets were consumers of the old
target-local source paths too.

## Building and release coverage

Use **Vivado 2024.1**. Later versions have caused hold-time closure problems in
this project. From the repository root:

```bash
source /sdf/group/faders/tools/xilinx/2024.1/Vivado/2024.1/settings64.sh
make -C firmware/targets list
make -C firmware/targets ColumnFpgaBoard325Coord
```

The aggregate build defaults to `prom`; `SUBTARGET` selects another supported
make target. Build products are under the `firmware/build/` symlink, and final
images under each target's `images/` directory. Inspect that symlink directly
when locating logs.

The `warmTdm` release selects `ColumnFpgaBoard325Coord`,
`ColumnFpgaBoard325Coord10G`, `RowFpgaBoard160`, and `RowFpgaBoard325`.
`build_release.sh -r warmTdm --list` checks release resolution without building.
Catalog consistency and source-path checks do not establish synthesis or
timing closure. Current candidate build/resource obligations are on
[#70](https://github.com/slaclab/warm-tdm/issues/70), with context in the
[resource integration handoff](../../docs/plans/resource-integration/README.md).

## Legacy targets

`legacy/` retains `ColumnModule`, `ColumnModule0`, `RowModule`, `RowModule0`, and
`RowModuleC00` for reference and legacy simulations. They are excluded from the
active aggregate/release catalog and may retain local sibling-source
dependencies. Keeping those sources does not imply current hardware or Python
support.
