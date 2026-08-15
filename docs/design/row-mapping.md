# Row mapping: logical vs physical rows

System-level overview of how rows are addressed in Warm-TDM, and what the
`maxRows` / `rows` / `numRows` sizing parameters actually count. Written to
inform the deferred row-sizing work (see "Current state" below); reconstructed
by reading the RTL + firmware/python + software together.

## Two row spaces

- **Logical row** — a *time slot* in the TDM readout sequence. "Row 0, 1, …,
  N−1" as detectors are visited in time. This is the index the DSP, tuning
  algorithms, and data streams think in.
- **Physical row** — which actual **row-select DAC line** fires, encoded as
  `(rsBoard, rsAddr)` and optionally a chip-select `(csBoard, csAddr)`. This is
  the wire that turns on a SQUID-mux row. The physical hardware is fixed:
  32 row-selects per row board × the number of row boards.

**RowMap is the lookup table from logical → physical.** Logical row `i` (the
array position) maps to a packed physical row-select address.

## How the map is built (software)

`warm_tdm_api/_Group.py:_setRowMap` builds the RAM that the firmware consumes:

```python
ram = [0x8080 for x in range(self.config.maxRows)]   # 0x8080 = "row off"
for i, row in enumerate(value):                       # i = LOGICAL row index
    valueRs = (row['rsBoard'] << 5) | row['rsAddr']   # physical row-select
    valueCs = 0x80
    if 'csAddr' in row:
        valueCs = (row['csBoard'] << 5) | row['csAddr']
    ram[i] = valueCs << 8 | valueRs                   # logical i -> physical (cs,rs)
```

The convenience commands `RowMap1x32`, `RowMap6x10`, `RowMap8x10`, etc. on
`Group` just build different logical→physical `value` lists and push them through
`RowMap`. The list length = number of active logical rows.

## How the hardware uses it (RTL)

In `firmware/common/warm_tdm/rtl/RowDacDriver2.vhd`:

- A `MAP_RAM` (AxiDualPortRam, `ADDR_WIDTH_G => 8` ⇒ 256 deep) holds the
  logical→physical table written above.
- The timing system emits a `rowStrobe` each time slot. On each strobe the state
  machine advances `mapRamAddr` (the **logical** index), reads `mapRamOut`, and
  drives `rowAddr` = the **physical** row-select from that entry
  (RowDacDriver2.vhd ~lines 492–503).

So the MAP_RAM is *indexed by logical row* and *outputs physical address* — the
hardware embodiment of the same table `_setRowMap` builds.

> Note: a separate fixed `REMAP_C` array (RowDacDriver2.vhd:170) maps logical→
> physical *channel within a board* — a static board-routing detail, distinct
> from RowMap. Don't confuse the two.

## What `maxRows` / `rows` / `numRows` count: LOGICAL rows

Every sizing parameter in the chain counts **maximum logical rows** (depth of
the readout sequence / number of time slots) — never physical hardware:

- `FastDacMem.Raw` (`numValues=rows`, `_FastDacDriver.py`) — one SQ1-FB (etc.)
  DAC setpoint **per logical row**.
- `PidDebugger` (`numRows`, `_PidDebugger.py`) — `numRows` per-logical-row debug
  sub-devices × 8 columns. **The dominant tree cost.**
- `MaxRows` variable = `config.maxRows` — reported max logical rows.
- `_setRowMap`'s `ram` list — indexed by logical row.
- RTL `ROW_ADDR_BITS_G` — logical address space width: `maxRows = 2**bits`
  (8 → 256 default; the `ColumnFpgaBoard160Coord` target uses 5 → 32).

Physical addressing (`rsBoard`/`rsAddr`) is the *content/values* of the map,
never the *count*.

## The tree-size point

`maxRows` exists to let the rogue tree allocate **fewer per-row leaves** when a
system uses fewer logical rows. If you only need 80 rows, the SQ1-FB/Bias DAC
value arrays and the PidDebugger sub-devices only need to be 80 deep instead of
256 — a large saving (× columns × DAC drivers × boards, and PidDebugger creates
real sub-devices per row).

## The safety invariant

Because RowMap is logical→physical and indexed by logical row, shrinking
`maxRows` is safe **iff the readout sequence never defines more logical rows
than `maxRows`** (`len(RowMap)` / `ReadoutList` ≤ `maxRows`). The physical
hardware is untouched; you are only declaring "this system uses at most N time
slots." Over-running (defining more logical rows than `maxRows`) is the failure
mode.

## Current state (cleanup-sw / PR #67) — partially wired

`maxRows` is **not** fully connected to tree sizing on this branch. Five things
all mean "max logical rows" but only some track `config.maxRows`:

### Two distinct quantities — do not conflate

- **`rowAddrBits`** = the deployed RTL generic `ROW_ADDR_BITS_G` (range 3..8).
  The firmware row RAMs are `2**rowAddrBits` deep. A property of the **bitfile**,
  not a software choice; software cannot read it back, so it must be told
  (`--rowAddrBits`, default 8 → depth 256; the `ColumnFpgaBoard160Coord` target
  builds with 5 → depth 32).
- **`maxRows`** = how many row slots the **software** maps into Rogue variables
  and sizes the RowMap RAM for. Bounded by the hardware depth:
  `1 <= maxRows <= 2**rowAddrBits`. `GroupConfig` enforces this at construction.

| Thing | sizes to | notes |
|---|---|---|
| `AdcDsp` per-row arrays / `RowDacDriver2.RowMap` (tree cost) | `rows` = `maxRows` | threaded via `HardwareGroup(maxRows=...)` ✅ |
| software RowMap `ram` list (`_Group.py`) | `config.maxRows` | ✅ |
| `MaxRows` variable | `config.maxRows` | ✅ |
| RTL `ROW_ADDR_BITS_G` (hardware depth) | `2**rowAddrBits` | 8→256 (5→32 for 160Coord); set via `--rowAddrBits` |

`maxRows` is threaded through `HardwareGroup` → `ColumnBoard`/`RowBoard`, so it
sizes the mapped Rogue variables (`AdcDsp` per-row state, `RowDacDriver.RowMap`)
as well as the display variable, the software RowMap RAM, and the GUI bounds. It
maps the first `maxRows` strided entries of the `2**rowAddrBits`-deep firmware
address space. It does **not** touch the RTL: `ROW_ADDR_BITS_G` remains a
build-time generic, and reconciling it (e.g. exposing it as a readback register
so software need not be told) is deferred to the FP-PID / row-sizing firmware
track.
</content>
