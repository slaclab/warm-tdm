# Artix UltraScale+ Port (ColumnAu25p Target)

## Goal

Port the Column board firmware to an Artix UltraScale+ (xcau25p-sfvb784-1-e)
FPGA, adding 10G Ethernet support. New target: `ColumnAu25p`.

## Approach

### Platform abstraction

Split existing monolithic entities into platform-specific variants so the
same common RTL supports both 7-Series and UltraScale+:

| Subsystem | Wrapper | 7-Series | UltraScale+ |
|-----------|---------|----------|-------------|
| Clock distribution | `ClockDist.vhd` | `ClockDist7s.vhd` | `ClockDistUsp.vhd` |
| Timing RX PHY | `TimingRx.vhd` | `TimingRxPhy7s.vhd` | `TimingRxPhyUsp.vhd` |
| Timing TX PHY | `TimingTx.vhd` | `TimingTxPhy7s.vhd` | `TimingTxPhyUsp.vhd` |
| Timing deserializer | — | `TimingDeserializer7s.vhd` | `TimingDeserializerUsp.vhd` |
| Timing serializer | — | `TimingSerializer7s.vhd` | `TimingSerializerUsp.vhd` |
| PGP PHY | `PgpCore.vhd` | `PgpPhy7s.vhd` | `PgpPhyUsp.vhd` |
| Ethernet PHY | `EthCore.vhd` | `EthPhy7s.vhd` | `EthPhyUsp.vhd` |

Also added `PgpRingRouter.vhd` (factored out of `PgpCore.vhd`).

### New target: `ColumnAu25p`

- Top entity: `firmware/targets/ColumnAu25p/rtl/ColumnAu25p.vhd`
- Pin map: `firmware/targets/ColumnAu25p/xdc/ColumnAu25p.xdc`
- Build: `make bit` (not prom)
- Generics: `RING_ADDR_0_G=true`, `ETH_10G_G=true`, `GEN_ADC_FILTER_G=false`
- GTY Quad 225 for PGP + 10G SFP
- Bank 64 (HP 1.8V): ADC LVDS with ISERDESE3
- Bank 67 (HP 1.8V): Timing LVDS with PLL-based serialization

### Constraint refactoring

Split `WarmTdmCore2.xdc` into platform/config-specific files:
- `WarmTdmCore2.xdc` — Common async clock groups and false paths
- `WarmTdmCore2_7s.xdc` — 7-Series MMCM clock definitions
- `WarmTdmCore2_usp.xdc` — UltraScale+ clock definitions (PLL, BUFGCE_DIV)
- `WarmTdmCore2_1g.xdc` — 1G Ethernet clock groups
- `WarmTdmCore2_10g.xdc` — 10G Ethernet clock groups

All existing 7-Series targets updated their `ruckus.tcl` to load the
appropriate subset of these constraint files.

### Key differences from 7-Series

- ISERDES → ISERDESE3 (with BUFGCE_DIV for divided clock)
- OSERDES → OSERDESE3
- PLL replaces MMCM for timing TX serialization
- IBUFDS_GTE4 with ODIV2 for fabric reference clocks
- GTY transceivers (vs GTX/GTP)

## Current Status

**Timing closure is the active problem.** The clock tree compiles but timing
is not met. Recent work:

- Switched timing TX from PLL to MMCM and back — PLL works better
- Tried manual PLL placement (`PLL_X0Y6`) to reduce CLK/CLKDIV skew to
  OSERDESE3
- Clock generation had broken circular references that were resolved
- XDC clock definitions have been iterated several times

## Files Modified (relative to pydm-widgets base)

New files:
- `firmware/targets/ColumnAu25p/` (entire target directory)
- `firmware/common/warm_tdm/rtl/ClockDist7s.vhd`
- `firmware/common/warm_tdm/rtl/ClockDistUsp.vhd`
- `firmware/common/warm_tdm/rtl/EthPhy7s.vhd`
- `firmware/common/warm_tdm/rtl/EthPhyUsp.vhd`
- `firmware/common/warm_tdm/rtl/PgpPhy7s.vhd`
- `firmware/common/warm_tdm/rtl/PgpPhyUsp.vhd`
- `firmware/common/warm_tdm/rtl/PgpRingRouter.vhd`
- `firmware/common/warm_tdm/rtl/TimingDeserializerUsp.vhd`
- `firmware/common/warm_tdm/rtl/TimingSerializerUsp.vhd`
- `firmware/common/warm_tdm/rtl/TimingRxPhyUsp.vhd`
- `firmware/common/warm_tdm/rtl/TimingTxPhyUsp.vhd`
- `firmware/common/warm_tdm/rtl/TimingRxPhy7s.vhd`
- `firmware/common/warm_tdm/rtl/TimingTxPhy7s.vhd`
- `firmware/common/warm_tdm/xdc/WarmTdmCore2_7s.xdc`
- `firmware/common/warm_tdm/xdc/WarmTdmCore2_usp.xdc`
- `firmware/common/warm_tdm/xdc/WarmTdmCore2_1g.xdc`
- `firmware/common/warm_tdm/xdc/WarmTdmCore2_10g.xdc`

Significantly refactored:
- `ClockDist.vhd`, `EthCore.vhd`, `PgpCore.vhd`
- `Timing.vhd`, `TimingRx.vhd`, `TimingTx.vhd`
- `WarmTdmCommon2.vhd`, `WarmTdmCore2.vhd`
- `WarmTdmCore2.xdc`
- All existing target `ruckus.tcl` files (to load new XDC split)

## Validation

- [ ] `ColumnAu25p` builds clean (`make bit`)
- [ ] Timing closure met (no setup/hold violations)
- [ ] Existing 7-Series targets still build (regression)
- [ ] Hardware test: timing link locks between boards
- [ ] Hardware test: 10G Ethernet RSSI link establishes
- [ ] Hardware test: PGP ring routes frames correctly

## Dependencies

- Branch is based on `pydm-widgets` (see `docs/plans/pydm-widgets/`)
- Uses updated `surf` submodule
- Requires special `ruckus` branch (submodule pointer)
