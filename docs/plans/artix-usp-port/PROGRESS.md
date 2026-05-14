# Artix UltraScale+ Port — Progress

## 2026-05-14

**Status: Timing closure not yet achieved.**

Latest attempt: manual PLL placement constraint (`PLL_X0Y6`) to put the
timing TX PLL near the OSERDESE3 bank and reduce clock skew.

### Completed

- [x] Platform split: all major subsystems have 7s/Usp variants
- [x] New target directory (`ColumnAu25p`) with top entity and pin map
- [x] XDC constraint refactoring (common + platform + config files)
- [x] All existing targets updated for new XDC structure
- [x] Clock distribution working (IBUFDS_GTE4 ODIV2 → BUFG_GT)
- [x] Timing RX: ISERDESE3 + BUFGCE_DIV + MMCM for bit/word clocks
- [x] Timing TX: OSERDESE3 + PLL for bit/word clocks
- [x] PGP: GTY instantiation compiles
- [x] 10G Ethernet PHY instantiation compiles
- [x] Surf submodule updated to support UltraScale+ primitives
- [x] Resolved clock declaration circular references
- [x] Switched from MMCM to PLL for timing TX (better for OSERDESE3)

### Active Problem

Timing closure. The clock tree is structurally correct but timing analysis
reports violations. Areas of concern:

- CLK/CLKDIV skew between PLL output and OSERDESE3 inputs
- Async clock domain crossings between timing clocks and AXI-Lite domain
- Possible need for additional `set_clock_groups` or `set_false_path` on
  recovered timing clocks

### Remaining

- [ ] Achieve timing closure on `ColumnAu25p`
- [ ] Verify 7-Series targets still build clean (regression check)
- [ ] Hardware bring-up and link testing
- [ ] Resolve ruckus submodule to a release (currently special branch)
