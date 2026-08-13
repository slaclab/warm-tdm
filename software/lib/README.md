# software/lib — dead prototype, kept as a C++-module skeleton

**None of this code is live.** It is not built by any target, no `.so` is
produced from it, and nothing in the running software imports it. It is retained
on purpose as a *reference skeleton* for the day we want to add a real C++
extension to the warm-tdm software tree — the directory layout and Boost.Python
glue are the tedious parts to reconstruct, so we keep a working copy rather than
rederive them.

If you are looking for **no-hardware operation**, this is not it — see
[Running without hardware](#running-without-hardware) below.

## What it was

An early, abandoned attempt at a **high-rate data-stream emulator**: synthesize
column data frames in native code, push them through the Rogue stream stack, and
tally throughput at the receiver. Two classes:

- `TdmGroupEmulate` (`ris::Master`) — a data *source*. `start()` spins a
  `std::thread` that synthesizes fake column frames on request and sends them
  downstream (`reqFrame`/`toFrame`/`sendFrame`).
- `TdmDataReceiver` (`ris::Slave`) — a data *sink*. `acceptFrame()` does
  `rogue::GilRelease noGil;`, locks, and counts frames/bytes.

It was never finished: the frame payload is filled with loop indices (`row`,
`col`, `groupId`) rather than emulated ADC/SQUID data, `reqFrames()` is a no-op
(`timestampA = timestampA;`), and the receiver only counts bytes. The topology it
models (12 groups, fixed 4-col/32-row, `uint8_t` row counts) predates the
tree-derived topology, `maxRows`/`rowAddrBits`, `Session`, the TDEST channel
scheme, and PID-debug streams. Reviving it as an emulator is not worth it.

Removed alongside this stub (see git history for the full island):
`software/scripts/warmTdmEmulate.py` and the PyRogue wrappers
`warm_tdm_api/_TdmDataReceiver.py`, `_TdmGroupEmulate.py`, `_RunEmulate.py`.
(Retired under issue #72.)

## Why it's C++ at all

Rogue projects are normally pure Python; the C++ hook is Rogue's escape hatch
for **stream endpoints that must not take the Python GIL per frame**. A Python
`ris.Slave.acceptFrame` holds the GIL on every frame, which throttles a
high-rate stream. Writing the hot path in C++ (`rogue::GilRelease noGil;`) lets
frame production/consumption run on a native thread at line rate, with Python
kept only for the cold path — the `FrameCount`/`ByteCount` counters surfaced as
`pr.LocalVariable`s. That GIL-release streaming pattern is the reason to reach
for a C++ module, and the reason to keep this as an example.

## The skeleton (what to copy for a real module)

```
software/lib/
├── CMakeLists.txt          # standalone project; finds rogue/boost, sets the
│                           #   .so name (PREFIX "" SUFFIX ".so") and points
│                           #   LIBRARY_OUTPUT_DIRECTORY back into ../python so
│                           #   pyrogue.addLibraryPath() can find the module
├── include/                # class headers (subclass ris::Master / ris::Slave)
└── src/
    ├── <Class>.cpp         # implementation
    └── warm_tdm_lib.cpp    # BOOST_PYTHON_MODULE(warm_tdm_lib) — registers
                            #   each class's setup_python() into one module
```

The other half of the pattern — how a Boost.Python class is wrapped as a
`pr.Device` with `pr.LocalVariable` counters and `_getStreamMaster`/
`_getStreamSlave` + `__rshift__`/`__lshift__` stream hooks — lived in the deleted
`_Tdm*.py` wrappers. Recover it from git history if you need it:

```bash
git show f8c1586:software/python/warm_tdm_api/_TdmGroupEmulate.py
git show f8c1586:software/python/warm_tdm_api/_TdmDataReceiver.py
```

Note the CMake project is still named `ucusc_hn_lib` (copied from an upstream
template and never renamed) — rename it if you promote this to a real build.

## Running without hardware

The dead script here is **not** the way. Use the register-memory emulation built
into the live tree, which swaps the real SRP for
`pyrogue.interfaces.simulation.MemEmulate` (see
`firmware/python/warm_tdm/_HardwareGroup.py`):

```bash
cd software/scripts && python Jupyter.py --emulate
```
