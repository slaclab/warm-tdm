# Firmware targets

Active targets are thin build configurations over shared board sources. The
authoritative target catalog is [`../releases.yaml`](../releases.yaml); keep
the aggregate [Makefile](Makefile) aligned with it. Release procedure and branch
policy are in [`docs/RELEASE.md`](../../docs/RELEASE.md).

## Naming and source ownership

Names use `Function·FpgaBoard·Part·[FrontEnd]·[Pid]·[Coord|Eth]`:

- `160` and `325` identify XC7K160T and XC7K325T parts.
- `AwaXe` identifies the front end.
- For the split `ColumnFpgaBoard325` family, `Fp`/`Int` select the PID datapath
  (`USE_FLOAT_PID_G` = `true`/`false`), and the Ethernet type doubles as the
  coordinator marker: a `1G`/`10G` suffix = coordinator (`RING_ADDR_0_G=true`),
  while a bare name (no Ethernet suffix) = non-coordinator (`RING_ADDR_0_G=false`).
  Non-coordinators are intended to carry no Ethernet; until `ColumnFpgaBoard` can
  be built without an Ethernet core they still instantiate a 1G core.
- Other targets retain the legacy `Coord` suffix for `RING_ADDR_0_G=true`
  (e.g. `RowFpgaBoard160Coord`, `ColumnFpgaBoard325AwaXeCoord10G`), which replaced
  the even older `0`/`Coordinator` suffixes.

The three `ColumnFpgaBoard325` families share a build body under
[`common/`](common) (`ColumnFpgaBoard325.tcl`, `ColumnFpgaBoard3251G.tcl`,
`ColumnFpgaBoard32510G.tcl`); each target's `ruckus.tcl` only sets `useFloatPid`
and sources its family body, so the `Fp`/`Int` siblings cannot drift.

| Target | RTL top |
|---|---|
| `ColumnFpgaBoard160` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard160Coord` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Fp` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Int` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Fp1G` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Int1G` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Fp10G` | `ColumnFpgaBoard` |
| `ColumnFpgaBoard325Int10G` | `ColumnFpgaBoard` |
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

Each active target explicitly loads `WarmTdmCore.xdc` and exactly its own board
pinout (`ColumnFpgaBoard.xdc`, `ColumnFpgaBoardAwaXe.xdc`, or `RowFpgaBoard.xdc`).
Coordinator targets also explicitly load `WarmTdmCore_1g.xdc` or
`WarmTdmCore_10g.xdc` after the common XDC, matching `ETH_10G_G`.
Non-coordinator targets load neither Ethernet XDC. Keep each target's
constraint selection consistent with `RING_ADDR_0_G` and `ETH_10G_G` when
changing its generics. All constraint files remain managed XDC without Tcl
control flow.
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
make -C firmware/targets ColumnFpgaBoard325Fp1G
```

The aggregate build defaults to `prom`; `SUBTARGET` selects another supported
make target. Build products are under the `firmware/build/` symlink, and final
images under each target's `images/` directory. Inspect that symlink directly
when locating logs.

The `warmTdm` release selects the six split `ColumnFpgaBoard325` targets
(`Fp`/`Int` × non-coord/`1G`/`10G`), `RowFpgaBoard160`, and `RowFpgaBoard325`.
`build_release.sh -r warmTdm --list` checks release resolution without building.
Catalog consistency and source-path checks do not establish synthesis or
timing closure. Current candidate build/resource obligations are on
[#70](https://github.com/slaclab/warm-tdm/issues/70), with context in the
[resource integration handoff](../../docs/plans/resource-integration/README.md).

## Legacy targets

`legacy/` retains `ColumnModule`, `ColumnModule0`, `RowModule`, `RowModule0`, and
`RowModuleC00` for historical reference. They are excluded from the active
aggregate/release catalog. The original WarmTdmCore/WarmTdmCommon implementations
were removed; these names now identify the former `*2` implementations used
by active boards. The archived RowModule sources and RowTb/StackTb simulations
depend on the original interfaces and require a historical checkout. They are
not supported build or simulation targets for the current common library.
