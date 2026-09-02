# Sensor-wafer model tests

These focused VHDL-2008 tests exercise the cold TES/SQUID model without the
vendor IP required by the full `GroupTb` simulation.

Run them locally with:

```bash
make test
```

All work-library objects and elaborated executables are written under
`firmware/build/WaferModelTb/ghdl/`. The repository-wide `build*` ignore rule
keeps that generated area out of Git. `make clean` removes only that test's
subdirectory.

The suite checks the literature-derived ideal low-inductance SQUID equation,
independent SSA/SQ1/row-FAS/chip-FAS parameter sets, the exact nested MUX
network, the fast 8-column `6x10` model, the old eight-channel `WaferSim`
interface, and elaboration of the physical BICEP3, NIST-50-row, and BA4
detector dimensions. It also checks a 12-column detector's `8+4` warm-board
mapping, unused-channel termination, and the dual-BA4 `8+8+(4+4)` mapping.
The NIST `5x10` bank factorization remains provisional until it is checked
against the mask schematic.

The full board, ADC, fixed-point PID, and event-builder paths remain VCS
integration tests under `../GroupTb`.
