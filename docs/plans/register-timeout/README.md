# Register timeout after the September 18 image

## Goal and reported behavior

Compare working firmware/software `1045236eecac9719092883b78dee6e850c63698b`
(`ColumnFpgaBoard325Coord10G`) with the loaded image
`ColumnFpgaBoard325Int10G-0x00000000-20260918115303-bareese-d0bedaa.mcs.gz`.
The board responds to ping and RSSI appears to link, but register reads time out.
Determine the likely regression and the smallest discriminating hardware test.

## Status

Initial source comparison complete; root cause remains unconfirmed on hardware.
The image revision exists locally as
`d0bedaae8b65e648d6cec101c39564f5bcbb2b9a`; the working tree is at `dd46689`
with unrelated uncommitted work. Compare committed revisions explicitly.
No hardware access or build reports have been supplied. Local `firmware/build/`
contains simulation directories, not this target's synthesis/implementation.

## Findings so far

- Both target configurations enable `RING_ADDR_0_G=true` and `ETH_10G_G=true`.
  The new target explicitly selects the integer PID path. Its default RSSI
  window is still 3 and segment size still 1024 bytes.
- Host SRP remains UDP 8192, packetizer v2, SRPv3, application destination
  equal to board index. EthCore's local SRP route and bridge are unchanged.
- Commit `857a104` changed both RSSI cores from the default inferred backend
  to `SYNTH_MODE_G => "xpm"`. This selects different RSSI payload RAM and output
  FIFO implementations. Handshake success alone does not validate payloads.
- That commit also changed local data and remote-ring bridge FIFOs to XPM,
  using `MEMORY_TYPE_G => "bram"`. The SURF FIFO wrapper documents `block`,
  `distributed`, `auto`, and `ultra`, and passes the string directly to XPM.
  Investigate separately from the coordinator's direct SRP path.
- SURF changed from `4acecf9` to `70191c1`. Its AXI, RAM/FIFO, RSSI, SRP,
  Ethernet MAC, IP/UDP, and 10G core sources have no diff between those pins.
- The core/common rename preserves the maintained AXI address map. Ethernet
  gating still includes the coordinator. Ethernet XDC was split and hierarchy
  paths updated; actual synthesized constraints/timing remain unverified.
- Target `vivado/project_setup.tcl` now enables both `POWER_OPT_DESIGN` and
  `POST_PLACE_POWER_OPT_DESIGN`; both were commented out for the working target.
- The new target inherits `ROW_ADDR_BITS_G=7` (128 rows), versus 8 (256 rows)
  in the working image. Host defaults remain `--rowAddrBits 8 --maxRows 256`.
  Use `--rowAddrBits 7 --maxRows 128` (or fewer mapped rows) with this image.
  This mismatch does not change the coordinator AxiVersion address.
- EthCore simulation replaces the physical Ethernet/RSSI stack with a TCP
  bridge. Passing ordinary group co-simulation does not exercise the RSSI
  backend change.

## Ranked suspects

1. **RSSI implementation selection (`857a104`)**: the most direct changed
   logic on the coordinator register transport. The backend generic affects
   RSSI RX/TX segment RAMs and application/transport output FIFOs. Connection
   control traffic can succeed without validating stored application payloads.
   No specific defect in the RSSI XPM implementation was proven by this review.
2. **Implementation/constraints**: newly enabled power optimization and the
   Ethernet hierarchy/XDC split need the actual candidate reports. The selected
   10G constraints preserve the prior clock-group intent with updated paths;
   source review cannot establish that Vivado resolved every object or met
   timing. PGP's AXI clock/reset generation itself has no functional diff.
3. **Remote-board transport**: remote Ethernet/PGP FIFOs also changed backend,
   and PGP FIFO address width dropped from 10 to 8. Investigate these first
   instead if coordinator reads succeed and only remote boards fail.

The new `"bram"` XPM selections deserve a separate build-log check. SURF's
`Fifo` and `FifoXpm` pass that string through without translating it to
`"block"`. They are not the segment RAM setting inside the RSSI instances,
which retains the default `"block"`. One local-data XPM/`"bram"` FIFO already
existed in the working image, so merely finding that spelling is not proof
of the newly reported global failure.

## Discriminating next checks

1. Stop other clients to the same RSSI port. Start from a fresh FPGA reset or
   power cycle, before any normal full-tree startup (see the sticky-timeout
   mechanism below). Establish that **UDP 8192** links,
   independently of data-port 8193 status. Read a single 32-bit coordinator
   AxiVersion word at **address 0, packetizer destination 0**, with initial
   full-tree reads and polling disabled. A returned value of zero is valid
   for this target's firmware version. Record the host revision, failing
   device/address, and whether the host receives any SRP response frame.
2. If that single read times out, make a diagnostic build changing only
   `U_RssiServer_SRP`'s generic in `EthCore.vhd` (currently line 512):

   ```diff
   -            SYNTH_MODE_G          => "xpm",
   +            SYNTH_MODE_G          => "inferred",
   ```

   Leave `U_RssiServer_DATA` and the other FIFO settings unchanged for this
   experiment. Build `ColumnFpgaBoard325Int10G` with Vivado **2024.1** and repeat
   the same single read. Recovery would implicate the SRP RSSI implementation
   selection or its physical implementation, not yet identify an exact XPM
   primitive defect. A failed experiment does not eliminate the other XPM
   FIFO changes.
3. Inspect the actual candidate's synthesis/implementation logs and timing
   reports under `firmware/build/ColumnFpgaBoard325Int10G/` on the build host:
   Vivado version, resolved generics, XPM memory-type warnings, missing XDC
   objects, unconstrained endpoints, setup and hold slack, and power optimization
   messages. If needed, compare an otherwise identical build with both power
   optimization steps explicitly disabled.
4. If address zero works, use the matching row-capacity options above and
   identify the first failing full-tree access before blaming global SRP.

## Follow-up: alternatives to an RSSI backend defect

The backend change is a candidate, not a demonstrated XPM bug. Two other
mechanisms fit a working network link with failed register access:

### Latched SRP hardware bus lock

SURF `protocols/srp/rtl/SrpV3AxiLite.vhd` deliberately retains `r.timeout`
across requests (line 343). With its request timeout enabled, an AXI transaction
that never completes sets this flag (read path line 671). Subsequent requests
skip AXI execution and return a timeout footer (lines 513 and 580/585), until
the bridge's `axilRst` resets its state. An RSSI reconnect does not reset this
AXI-domain state in EthCore.

This means "all registers now fail" does not prove that the very first access
failed: a startup read to one nonresponding endpoint can spoil later access
through the same SRP bridge. When the transport works, the expected symptom is
an SRP error response with timeout bits 8 and 13 (`0x2100` if no other flags),
not necessarily a host timeout from receiving no response. With a zero timeout
field in the request, the bridge can remain waiting instead of latching that
error. The exact first error message or packet trace distinguishes these.

DataPath's bus crosses into `timingRxClk125` through `AxiLiteAsync`; however,
this SURF bridge has a local error responder while its remote reset is asserted.
Do not equate any timing-reset condition with a bus hang: a stopped clock with
reset not properly reported, or a nonresponding endpoint, is a different case.
No particular new endpoint has been proven to cause such a hang.

### AXI clock/reset failure with live Ethernet

For 10G, EthCore's Ethernet/RSSI clock is derived from the 156.25 MHz reference.
The register bus uses PgpCore's separate MMCM, fed by the fabric reference
derived from the 250 MHz reference. Therefore ping and RSSI link-up do not
establish that `axilClk` runs or that `axilRst` is released. The clock-generation
RTL is unchanged across the compared revisions, so this is a physical/build
or board-state alternative, not an identified source-level regression.

`WarmTdmCore.vhd` exposes useful indications without register reads (provided
the LEDs are enabled, which is the reset default):

| HDL LED index | Signal | Expected meaning |
|---|---|---|
| `leds[0]` | Fabric reference 0 heartbeat | Reference feeding PGP/AXI is running |
| `leds[1]` | Fabric reference 1 heartbeat | Reference feeding 10G is running |
| `leds[2]` | AXI clock heartbeat | AXI clock is running; does not prove reset release |
| `leds[3]` | Timing RX clock heartbeat | Timing clock is running; does not prove link lock |
| `leds[4]` | `rssiStatus(0)(0)` | Register RSSI connection, UDP 8192 |
| `leds[5]` | `rssiStatus(1)(0)` | Data RSSI connection, UDP 8193 |
| `leds[6]` | `ethPhyReady` | Ethernet PHY ready |

These are HDL indices, not verified silkscreen labels. JTAG/ILA inspection of
`axilRst` and the SRP AXI handshake would separate reset/clock issues from an
unanswered transaction if a suitable instrumented image is available.

### Host/network and build-state checks

- Establish that the observed RSSI connection is the register port, not only
  data port 8193. Keep only one client on the register RSSI endpoint during the
  probe; an old server, notebook, or loader is a possible competing client.
- A duplicate IP or different running image is a lower-priority alternative.
  Successful ping alone does not verify the newly loaded image's identity.
- A clean rebuild with recorded Vivado version, generics, submodule state,
  timing reports, and boot/image identity separates committed-source analysis
  from incremental-build or flash/boot provenance problems.
- If a fresh address-zero read works until normal startup, prioritize the
  first failing peripheral and startup configuration over a global transport
  defect. If only remote-board destinations fail, prioritize the PGP/ring path.

## Follow-up: proposed 312.5-to-250 MHz constraint regression

The proposed `gtRefClk0` period change is **not present in the effective target
comparison**. The old revision contained both a legacy `WarmTdmCore.xdc` and the
maintained `WarmTdmCore2.xdc`. Commit `316b112` replaced the former filename with
the latter implementation. Comparing only the unsuffixed filename conflates
two different designs.

| Revision / target | Explicitly selected common XDC | `gtRefClk0` | `gtRefClk1` |
|---|---|---|---|
| `1045236` / `ColumnFpgaBoard325Coord10G` | `WarmTdmCore2.xdc` | 4.000 ns | 6.400 ns |
| `d0bedaa` / `ColumnFpgaBoard325Int10G` | `WarmTdmCore.xdc` | 4.000 ns | 6.400 ns |

At `1045236`, common `ruckus.tcl` has XDC directory auto-loading commented out;
the working target explicitly loads `WarmTdmCore2.xdc`. The unused legacy file
has 3.200 ns / 4.000 ns, which explains the apparent frequency change.

Both maintained core revisions set `ClockDist.CLK_0_DIV2_G=true` and
`CLK_1_DIV2_G=false`. The actual AXI chain is `gtRefClk0P/N` -> `IBUFDS_GTE2`
`ODIV2` -> `BUFG` -> PgpCore `ClockManager7` -> `iAxiClk`. Both specify input
period 8 ns, input divider 1, feedback multiplier 8, and AXI output divider 8.
SURF passes these generics directly to `MMCME2_ADV`; the GT CPLL configuration
is calculated from the explicit 250 MHz `REF_CLK_FREQ_G`, not the XDC period.
`create_clock` supplies a timing constraint; it is not an instruction to select
new MMCM divider ratios for this directly instantiated primitive.

If the physical reference were instead 312.5 MHz, the same ratios would imply
a 156.25 MHz MMCM input, 1250 MHz VCO, and 156.25 MHz AXI output in **both**
images. Both target Makefiles specify `XC7K325TFFG676-2`. For that -2 grade at
nominal 1.0 V, DS182 Table 41 specifies a 600–1440 MHz MMCM VCO range, so a
1250 MHz VCO alone does not establish an out-of-range/no-lock diagnosis. This
does not qualify operation at an incorrectly declared input frequency or
validate the rest of the system's timing.

Sources: local committed target loaders, core/ClockDist/PgpCore RTL, SURF
`ClockManager7.vhd`, [AMD DS182 Table 41](https://docs.amd.com/api/khub/documents/BhulK6GRrzUpQYw0lzrnMA/content),
and [AMD UG903 primary clocks](https://docs.amd.com/r/2024.2-English/ug903-vivado-using-constraints/Primary-Clocks).
Physical clock/reset and actual implemented constraints remain useful checks;
the claimed source-level period regression is ruled out for these revisions.

## Validation and handoff

- Compared exact committed sources at `1045236` and `d0bedaa`; followed the
  `WarmTdmCore2`/`WarmTdmCommon2` rename in RTL and Python to avoid comparing
  against the removed legacy implementations.
- Verified no source changes between the pinned SURF revisions in `axi`,
  `base`, RSSI, SRP, PGP, Ethernet MAC, IPv4, UDP, and 10G core directories.
- Verified local EthCore, PgpEthCore, and the new target's ruckus configuration
  are byte-identical to the loaded image's named commit.
- Vivado is unavailable locally; candidate implementation reports and the
  actual image's build-state provenance are unavailable. The filename identifies
  a commit but cannot prove the build checkout/submodules were clean.
- No vendor-XPM simulation or hardware read was run. Source inspection cannot
  establish hardware recovery. Current host revision and a concrete timeout
  path/address remain requested information.

No implementation changes, staging, commits, hardware writes, or external
issue updates have been made for this investigation.
