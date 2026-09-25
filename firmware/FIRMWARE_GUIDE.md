# Firmware Deep-Dive Guide

Supplementary reference for AI agents working on warm-tdm firmware. For the project overview, see the root [`AGENTS.md`](../AGENTS.md).

## Timing Protocol

The timing system distributes synchronization across all boards via a dedicated SelectIO LVDS link (not MGT). The protocol is defined in `common/warm_tdm/rtl/TimingPkg.vhd`. For the full protocol specification — control character semantics, row-boundary sequencing, `pwrSync` hold/release behavior, and the `LocalTimingType` record contract — see [`common/TimingProtocol.md`](common/TimingProtocol.md).

### Frame Structure

- Frame width: 259 bits (`TIMING_NUM_BITS_C`)
- Encoding: 8B/10B with K-character framing
- Carrier clock: 125 MHz (timingRxClk/timingTxClk)
- Serialization: bit-serial via `TimingSerializer*.vhd` / `TimingDeserializer*.vhd`

### K-Character Commands

| Constant | Value | K-Code | Meaning |
|----------|-------|--------|---------|
| `IDLE_C` | 0xBC | K28.5 | Link idle |
| `START_RUN_C` | 0x1C | K28.0 | Begin data acquisition run |
| `END_RUN_C` | 0x3C | K28.1 | End run |
| `ROW_SEQ_START_C` | 0x5C | K28.2 | Start of row sequence loop |
| `ROW_STROBE_C` | 0x7C | K28.3 | Commit pending row (row boundary) |
| `SAMPLE_START_C` | 0x9C | K28.4 | ADC sampling begins |
| `SAMPLE_END_C` | 0xDC | K28.6 | ADC sampling ends |
| `PWR_SYNC_WAIT_C` | 0xFC | K28.7 | Power synchronization pause |
| `STAGE_NEXT_ROW_C` | 0xF7 | K23.7 | Preload next logical row |
| `DAQ_READOUT_START_C` | 0xFD | K29.7 | DAQ readout trigger |
| `WAVEFORM_CAPTURE_C` | 0xFE | K30.7 | Trigger waveform capture |

### LocalTimingType Record

The decoded timing frame produces a `LocalTimingType` record with these fields:

| Field | Width | Description |
|-------|-------|-------------|
| `startRun` | 1 | Strobed at start of run |
| `endRun` | 1 | Strobed at end of run |
| `running` | 1 | High during active run |
| `runTime` | 64 | Clock counts since start of run |
| `rowStrobe` | 1 | Commit pending row on row-boundary |
| `rowSeqStart` | 1 | Start of row sequence loop |
| `daqReadoutStart` | 1 | DAQ readout trigger |
| `sample` | 1 | Currently in sample window |
| `firstSample` | 1 | First sample of window |
| `lastSample` | 1 | Last sample of window |
| `stageNextRow` | 1 | Preload next row |
| `rowSeq` | 8 | Sequence index in row-order list |
| `logicalRow` | 8 | Active logical row |
| `nextLogicalRow` | 8 | Pending row for next strobe |
| `rowTime` | 32 | Clocks since last row strobe |
| `rowSeqCount` | 64 | Full loops through all rows |
| `daqReadoutCount` | 64 | Number of DAQ readouts |
| `waveformCapture` | 1 | Trigger waveform capture flag |

Serialization uses SURF's `assignSlv`/`assignRecord` helpers for bit-packing.

## AXI-Lite Address Map

`WarmTdmCore` uses a 4-port crossbar defined via `AxiLiteCrossbarMasterConfigArray`:

| Index | Constant | Base Address | Size | Content |
|-------|----------|-------------|------|---------|
| 0 | `AXIL_COMMON_C` | 0x0000_0000 | 24-bit (16 MB) | XADC, boot PROM, power monitor, EEPROM, SFP I2C |
| 1 | `AXIL_TIMING_C` | 0x0100_0000 | 24-bit (16 MB) | TimingTx/Rx registers |
| 2 | `AXIL_COM_C` | 0xA000_0000 | 24-bit (16 MB) | PGP, Ethernet, RSSI status |
| 3 | `AXIL_APP_C` | 0xC000_0000 | 28-bit (256 MB) | Application registers (DataPath, DSP, DACs) |

The application crossbar (port 3) is further subdivided by each target's top-level entity.

### Pattern for Sub-Crossbars

```vhdl
constant NUM_AXIL_MASTERS_C : integer := 4;
constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(...) := (
   INDEX_A => (baseAddr => X"...", addrBits => N, connectivity => X"FFFF"),
   ...);

U_XBAR : entity surf.AxiLiteCrossbar
   generic map (
      NUM_SLAVE_SLOTS_G  => 1,
      NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
      MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C)
   port map (...);
```

## Platform Abstraction

Two FPGA families are supported. Selection is via the `FPGA_FAMILY_G` generic or by target-specific instantiation:

| Generic Value | Family | Transceiver | Files |
|---------------|--------|-------------|-------|
| `"7SERIES"` | Kintex-7 (XC7K160T) | GTX/GTP | `*7s.vhd` |
| `"ULTRASCALE_PLUS"` | Artix UltraScale+ (xcau25p) | GTY | `*Usp.vhd` |

Platform-split entities:
- `ClockDist7s` / `ClockDistUsp` — Reference clock buffering and distribution
- `TimingRxPhy7s` / `TimingRxPhyUsp` — Timing receive SelectIO deserialization
- `TimingTxPhy7s` / `TimingTxPhyUsp` — Timing transmit SelectIO serialization
- `TimingDeserializer7s` / `TimingDeserializerUsp` — Bit-to-word conversion
- `TimingSerializer7s` / `TimingSerializerUsp` — Word-to-bit conversion
- `PgpPhy7s` / `PgpPhyUsp` — PGP MGT wrapper
- `EthPhy7s` / `EthPhyUsp` — Ethernet MGT wrapper

## Constraint Organization

Active targets select shared board sources and explicit pinouts. See the
[targets README](targets/README.md) for naming, source ownership, and release
build guidance.

| File | Location | Content |
|------|----------|---------|
| `WarmTdmCore.xdc` | `common/warm_tdm/xdc/` | Cross-domain false paths, async clock groups |
| `WarmTdmCore_1g.xdc` | `common/warm_tdm/xdc/` | 1G Ethernet clock groups |
| `WarmTdmCore_10g.xdc` | `common/warm_tdm/xdc/` | 10G Ethernet clock groups |
| `ColumnFpgaBoard.xdc`, `ColumnFpgaBoardAwaXe.xdc`, `RowFpgaBoard.xdc` | `common/warm_tdm/xdc/` | Board pin assignments and I/O standards |

Each active target's `ruckus.tcl` explicitly loads its board pinout and
`WarmTdmCore.xdc`. Coordinator targets additionally load `WarmTdmCore_1g.xdc`
or `WarmTdmCore_10g.xdc`, matching `ETH_10G_G`; non-coordinators load neither.
Keep common XDC directory auto-loading disabled so a build does not combine
incompatible pinouts or Ethernet constraints.

## Simulation

Current simulation targets in `firmware/simulations/`:

| Testbench | Scope | Description |
|-----------|-------|-------------|
| `GroupTb` | Group level | Board group with device models |
| `AdcDspFpTb` | Controller | Floating-point controller acceptance bench |
| `WaferModelTb` | Detector models | Focused wafer, profile, scaling and compatibility benches |

### Running Simulation

```bash
cd firmware/simulations/GroupTb && make vcs
```

Device models in `common/warm_tdm/sim/` provide behavioral representations of external ICs (AD5679R, AD9767) and board assemblies (ColumnFpgaBoardModel, RowFpgaBoardModel, SQUID models).

The simulation environment supports PyRogue co-simulation via TCP socket bridges (`SIMULATION_G => true`, `SIM_PGP_PORT_NUM_G`).

The [sensor-wafer model README](common/warm_tdm/sim/README.md) documents detector
topology, warm/cold interfaces, device equations, synthetic-profile limits, and
focused GHDL test entry points.

## IP Cores

| Core | Path | Function |
|------|------|----------|
| Int2Fp | `common/warm_tdm/ip/Int2Fp/` | Integer to floating-point conversion |
| FpMac | `common/warm_tdm/ip/FpMac/` | Floating-point multiply-accumulate |

These are used in `AdcDsp` for PID arithmetic. The FIR filter IP (`FirFilter`) exists but is currently disabled in `ruckus.tcl`.

## Common Generics

| Generic | Type | Default | Purpose |
|---------|------|---------|---------|
| `TPD_G` | time | 1 ns | Simulation propagation delay |
| `SIMULATION_G` | boolean | false | Enable simulation-only paths |
| `RING_ADDR_0_G` | boolean | false | This board is the ring coordinator |
| `ETH_10G_G` | boolean | false | Use 10G Ethernet (vs 1G) |
| `FPGA_FAMILY_G` | string | "7SERIES" | Target FPGA family |
| `GEN_ADC_FILTER_G` | boolean | false | Generate hardware ADC filter |
| `DHCP_G` | boolean | false | Use DHCP for IP assignment |
| `IP_ADDR_G` | slv(31:0) | 192.168.3.11 | Static IP address (little-endian) |
| `ROW_ADDR_BITS_G` | integer | 5 | Number of row address bits |
