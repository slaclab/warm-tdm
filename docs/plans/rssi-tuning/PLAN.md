# RSSI Segment Size Tuning for 10GbE

## Scope

Increase `MAX_SEG_SIZE_G` on both RssiCoreWrapper instances in EthCore.vhd when
`ETH_10G_G = true` to better utilize jumbo frames that are already enabled at
the MAC layer.

## Background

Both GigEthGtx7 and TenGigEthGtx7 default `JUMBO_G => true`, giving a 9000-byte
Ethernet frame (~8958-byte max UDP payload). The current RSSI config uses
`MAX_SEG_SIZE_G => 1024` regardless of link speed, leaving significant per-segment
overhead on the 10G path.

`WINDOW_ADDR_SIZE_G => 3` (8 segments in flight) is appropriate for both instances
because both carry ring-forwarded streams in addition to their local function.

`SEGMENT_ADDR_SIZE_G` is auto-calculated internally by RssiCoreWrapper and can be
removed from the port map.

## Changes

| File | Change |
|------|--------|
| `firmware/common/warm_tdm/rtl/EthCore.vhd` | Make MAX_SEG_SIZE_G conditional: 1024 for 1GbE, 8192 for 10GbE |
| `firmware/common/warm_tdm/rtl/EthCore.vhd` | Remove SEGMENT_ADDR_SIZE_G from both instantiations (no-op generic) |
| `firmware/common/warm_tdm/rtl/EthCore.vhd` | Keep WINDOW_ADDR_SIZE_G => 3 unchanged |

## BRAM Impact

| Config | Buffer per direction | Total (2 RSSI × TX+RX) |
|--------|---------------------|------------------------|
| 1024 / window=3 (1GbE, unchanged) | 8 KB | 32 KB |
| 8192 / window=3 (10GbE, proposed) | 64 KB | 256 KB |

## Verification

- Synthesize both ColumnFpgaBoard (1GbE) and ColumnFpgaBoardAwaXe (10GbE) targets
- Compare BRAM utilization reports before/after
- Run rogue SRP register read/write tests in simulation at 10G
- Verify streaming data throughput doesn't regress at 1G
