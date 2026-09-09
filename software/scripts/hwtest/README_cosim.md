# VirtualClient checks against VCS

These scripts connect to an already-running `warmTdmServer --sim` using an
actual `pyrogue.interfaces.VirtualClient` and an explicit operations `Session`.
They do not start a simulator, flash an FPGA, or automatically identify whether
an endpoint is VCS. Use a dedicated simulation server, with timing stopped,
writer closed and tuning/waveform processes idle. One column board and one row
board are required by these checks.

Build/start GroupTb using [the VCS setup](../../../firmware/simulations/GroupTb/README_cosim.md).
Simulation uses Vivado 2025.1 + VCS X-2025.06; physical bitfiles use Vivado 2024.1.
Use a compatible Rogue Python/native pair and configure its client/transport
timeouts for slow simulated register transactions. These scripts' timing waits
and process execution deadlines do not impose a hard deadline on an in-flight
Rogue transaction or cooperative Process.Stop.

## What a VCS result establishes

| Check | Script / observable | Acceptance still requiring hardware |
|---|---|---|
| Group broadcasts | `verify_cosim_controls.py`: LED/power-sync register fanout and cable-resistance model leaves, then restoration | Visible LEDs, electrical supply synchronization and physical calibration |
| AllFastDacs | Same script: all 24 override registers receive each code; final verified zeroing | Actual analog outputs; raw command does not promise all overrides are serviced |
| ADC FIR writes | Same script with `--fir`: cache-only versus committed coefficients on all eight channels | Physical filter response; even modeled response requires a separate stimulus/trace check |
| Readout / masks / PID / units | `verify_cosim_readout.py`: complete finite channel sets, exact masks, intact frames, config-derived units, repeated acquisitions | Real-link throughput/recovery and calibrated gains/noise |
| Acquisition ownership / interruption | Same script: owned-run cleanup, preservation of a pre-existing run, injected startup interruption and successful restart | Real transport faults and wall-time performance on hardware |
| Raw ADC capture | Same script with `--raw`: nonempty finite saved ADC samples | Physical ADC response, gain and noise |
| Stop/zero | `verify_cosim_stop_zero.py`: shared nonzero → running → stopped/zero register sequence | Physical fast/slow column-output measurements. Also retain modeled DAC traces for #86's full VCS requirement |
| SA offset / SA tune / SQ1 tune | `verify_cosim_tuning.py`: finite complete reduced curves, non-flat response, selected operating points; explicit fixture profile | Real SQUID convergence, stability, gain and noise |
| Process timeout/Stop/restart | Same script with `--cancel-only`: two immediate timeout/Stop attempts | Real-link error recovery and physical stop latency |
| Fiber health, PROM reboot and waveform update rate | Current VirtualClient/VCS scripts cannot establish these | Real fiber/RSSI path, running image/reconnection, measured waveform rates and levels |

Digital criteria can be completed with a recorded VCS pass on the matching
candidate. Hardware criteria remain open on #68/#86/#55. A script's availability
or a MemEmulate test is not a VCS pass. Completed #50/#60 evidence remains valid
for its recorded setup; a new combined-candidate run is recorded on #68.

The stock GroupTb can exercise timing/register/data checks. Rich sensor-model
tuning needs an initialized and validated sensor fixture (#98), suitable row
select currents and amplifier settings. Do not import the sensor branch's
additional production tuning/setup changes into #78 solely to obtain a passing
fixture. Identify the exact DUT, server, model and any patches. FAS autotuning
and multi-board file identity remain separate work.

## Manifest and artifacts

Run clients on the server host, or use a filesystem shared at the **same absolute
path**: DataWriter and waveform files are created by the server and inspected
by the client. `--output` contains a unique `cosim-*` directory per invocation.
Each result includes source revisions, script copies/checksums, the local tracked
patch, build stamps, arguments, measured values/counts and failures. The manifest
is operator-supplied provenance, not proof that the loaded sim matches it.
Save server/model patches and VCS compile/run logs with these artifacts too.

Create a manifest **in the checkout used to build the simulator**, then update
`server_software_commit` if the running Python server uses another revision:

```bash
python3 - <<'PY' > /tmp/wtj-cosim-manifest.json
import json, subprocess

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

print(json.dumps({
    'firmware_commit': git('rev-parse', 'HEAD'),
    'server_software_commit': git('rev-parse', 'HEAD'),
    'surf_commit': git('rev-parse', 'HEAD:firmware/submodules/surf'),
    'ruckus_commit': git('rev-parse', 'HEAD:firmware/submodules/ruckus'),
    'fixture': 'GroupTb, WAFER, 1 column + 1 row board, 32 rows; record model patches/generics here',
    'toolchain': 'Vivado 2025.1; VCS X-2025.06'
}, indent=2))
PY
```

Use full 40-character revision IDs. The manifest describes the actual running
build, not whichever branch happens to be open in the client terminal. Add
fixture revision, generics, model parameters and log paths as extra JSON fields.
Record uncommitted server/model changes explicitly.

## Run the checks

Activate the Rogue environment, use the server's printed ZMQ port, and run from
the repository root. The examples assume that port is 9099:

```bash
python software/scripts/hwtest/verify_cosim_controls.py \
  --manifest /tmp/wtj-cosim-manifest.json --output /tmp/wtj-cosim-results

python software/scripts/hwtest/verify_cosim_readout.py \
  --manifest /tmp/wtj-cosim-manifest.json --output /tmp/wtj-cosim-results \
  --rows 2 --acq 30 --start-delay 5 --timing-timeout 120

python software/scripts/hwtest/verify_cosim_stop_zero.py \
  --manifest /tmp/wtj-cosim-manifest.json --output /tmp/wtj-cosim-results \
  --cycles 5 --settle-sec 5 --timing-timeout 120
```

All scripts accept `--host`/`--port`. Increase wall-time acquisition/settling
intervals if VCS produces too little simulated time. An empty or incomplete
stream fails; shorten the enabled row list or lengthen the run before retesting.
PID gains are set to zero for the readout test: this exercises the digital
pipeline without claiming servo convergence. Masked readout samples disappear;
PID-debug records still describe the enabled DSP's row visits.

`--broadcasts-only` omits DAC/FIR tests. Select `--fir` only when the simulated
RTL includes `GEN_ADC_FILTER_G=true`; the Python device exists even when that
register bank is absent. A selected unavailable bank fails. `--raw` enables the
longer full ADC capture (default timeout 600 wall seconds). Its NumPy dictionary
is loaded from the newly generated trusted server artifact.

Controls finish with column outputs zeroed; broadcasts are restored. The
readout test stops timing and restores row selection, timing/PID parameters and
masks, but PID histories and generated files are not restored. Stop/zero leaves
PID disabled and column outputs zeroed, restores per-row currents and the column
enable selection, and leaves row DAC behavior to the existing sequence.

For #86, correlate the register sequence with the modeled GroupTb signals
`sq1FbP/N`, `saFbP/N` and `sq1BiasP/N`; retain the nonzero/run/zero trace and the
conversion/tolerances used. These VHDL real-valued signals are not exposed as
VirtualClient nodes, so the script does not claim to inspect them. Physical
load-board DMM/scope acceptance remains independent.

## Optional sensor tuning and cancellation

Copy [cosim_tuning.example.json](cosim_tuning.example.json) into the artifact
area and adjust its ranges, sample delay and nonzero response thresholds for the
initialized sensor fixture. It is a starting profile, **not a validated operating
point**. Set the fixture's row map, FAS currents and analog/model settings before
running. At most two columns/rows, 64 feedback points and four bias values are
allowed to keep these checks small.

```bash
python software/scripts/hwtest/verify_cosim_tuning.py \
  --manifest /tmp/wtj-cosim-manifest.json --output /tmp/wtj-cosim-results \
  --profile /tmp/my-fixture-tuning.json --process-timeout 600

python software/scripts/hwtest/verify_cosim_tuning.py \
  --manifest /tmp/wtj-cosim-manifest.json --output /tmp/wtj-cosim-results \
  --profile /tmp/my-fixture-tuning.json --cancel-only
```

The full sequence saves SA offset, SA and SQ1 results and checks dimensions,
finite data, minimum modeled response and operating-point selection. It uses
SQ1 servo mode; an open-loop sweep does not establish that check. `--cancel-only`
checks two timeout/Stop/restart attempts instead of convergence. Tuning cleanup
attempts process stops, deactivates selected rows and zeros column outputs;
profile parameters and row/column selection are restored. It does not restore a
previous analog tune point, so use a dedicated simulation session.

## Script validation and issue results

```bash
python -m unittest discover -s software/tests -v
# Requires actual Rogue, but no VCS or hardware:
python software/tests/rogue_cosim_client_smoke.py
```

Unit tests check false-pass rejection and cleanup. The Rogue smoke test uses
production GroupRoot/MemEmulate plus a synthetic stream fixture to check the
actual VirtualClient path, report generation, decoding and rejection of malformed
PID frames. Record it as client plumbing only.

Attach `result.json`, its script/source snapshot, relevant data and VCS traces to
a dated result comment on #68 or #86. Record pass/fail separately for digital,
modeled-sensor and physical criteria; do not close the whole issue from a partial
simulation result. Prerequisite GroupTb acceptance remains open until executed.
