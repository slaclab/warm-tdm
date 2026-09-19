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
  Non-coordinators carry no Ethernet: `PgpEthCore` gates the Ethernet core on ring
  address zero (`GEN_ETH`), so `RING_ADDR_0_G=false` ties off the Ethernet
  interfaces and instantiates no core.
- Other targets retain the legacy `Coord` suffix for `RING_ADDR_0_G=true`
  (e.g. `RowFpgaBoard160Coord`, `ColumnFpgaBoard325AwaXeCoord10G`), which replaced
  the even older `0`/`Coordinator` suffixes.

Each `ColumnFpgaBoard325` target's `ruckus.tcl` is self-contained: it sets its own
generics (including `USE_FLOAT_PID_G`) and loads its own constraints directly. The
`Fp`/`Int` siblings differ only in `USE_FLOAT_PID_G`, and the `1G`/`10G`/bare
variants only in `RING_ADDR_0_G`/`ETH_10G_G` and the Ethernet XDC; keep the
matching families in sync by hand when editing shared generics.

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
Each target's `ruckus.tcl` must keep `loadConstraints -dir .../xdc` disabled:
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

`make all` builds every target but, under `-j`, a single failure is easy to lose
in interleaved output. For a parallel build with a clear pass/fail summary and
per-target logs, use `make report` (optionally `make report JOBS=N` to cap
concurrency): it delegates to `build_release.sh` over the aggregate target list,
keeps going past failures, and prints an `OK`/`FAILED` table under
`build_logs/<git-hash>/`. Each `FAILED` line is followed by the tail of that
target's log (the error itself; override the line count with `FAIL_TAIL=N`), plus
the full log path. It exits non-zero if any target failed.

The `warmTdm` release selects the six split `ColumnFpgaBoard325` targets
(`Fp`/`Int` × non-coord/`1G`/`10G`), `RowFpgaBoard160`, and `RowFpgaBoard325`.
`build_release.sh -r warmTdm --list` checks release resolution without building.
Catalog consistency and source-path checks do not establish synthesis or
timing closure. Current candidate build/resource obligations are on
[#70](https://github.com/slaclab/warm-tdm/issues/70), with context in the
[resource integration handoff](../../docs/plans/resource-integration/README.md).

## Retired targets

`ColumnModule`, `ColumnModule0`, `RowModule`, `RowModule0`, and `RowModuleC00`
are retired, along with their `RowTb`/`StackTb` benches and exclusive support
modules. Use Git history for those sources and their matching dependencies.
The current `WarmTdmCore`/`WarmTdmCommon` names identify the former `*2`
implementations used by active boards, not the original legacy interfaces.
