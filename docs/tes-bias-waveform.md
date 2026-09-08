# Software TES bias waveforms

`Group.TesBiasWaveformProcess` generates sine and square waveforms by writing
the TES bias vector from the server. There is one `TesBiasWaveformGenerator[i]`
per configured TES bias line, created before clients connect.

For example, using a connected Group:

```python
proc = group.TesBiasWaveformProcess
gen = proc.TesBiasWaveformGenerator[0]
gen.Mode.setDisp('Square')
gen.Frequency.set(1.0)        # waveform frequency, Hz
gen.TESBiasLow.set(0.0)      # microamps
gen.TESBiasHigh.set(25.0)    # microamps
proc.UpdateRate.set(100.0)   # host updates per second
proc.Start()
# Later:
proc.Stop()
```

Settings are sampled when the process starts. Stop and restart to apply changed
settings. Each line can use `None`, `Square`, or `Sine`; `None` holds that line's
original bias while other lines play. If all lines are `None`, or no bias lines
exist, the process returns without writing anything.

`UpdateRate` is a requested host update rate. It must be finite and positive;
waveform frequencies must be finite and nonnegative, and bias levels must be
finite. Zero waveform frequency produces a constant value: the midpoint for
sine and the low level for square. Fractional bias settings are supported.
The process warns once if writes fall more than one update interval behind.
Measure the sustainable rate on the actual host/link; it is not a hardware clock.

## Stop and error behavior

The process uses monotonic time and waits in intervals of at most 50 ms while
checking Stop. It checks again before issuing a waveform write. Stop no longer
waits for a whole update period; thread scheduling, an in-flight transaction and
the restoration writes still take their normal completion/timeout time.

Before playback it copies the original bias vector. Once any waveform write
has been attempted, it attempts to restore that entire vector on every exit,
including a normal Stop, a failed or partially completed write, or interruption.
Invalid settings are rejected before the first write.

If restoration fails, the process logs the failure and does not claim that the
outputs were restored. On normal Stop, the restoration exception is raised to
the process framework. If playback also failed, the original playback exception
is preserved and the restoration failure is logged separately. A successful
software write is not independent physical verification of the DAC outputs.

## Compatibility with the earlier implementation

The numeric mode mapping preserves the original `wtj-refactor` implementation:

| Value | Mode |
|---|---|
| 0 | None |
| 1 | Square |
| 2 | Sine |

Earlier revisions of PR #79 temporarily used `1 = Sine`, `2 = Square`.
Check saved numeric settings made with those revisions. Use `Mode.setDisp()`
with the mode name when writing new scripts.

The newer API intentionally uses these names; legacy aliases are not installed:

| Earlier name | Current name |
|---|---|
| `SoftwareClock` | `UpdateRate` |
| `tesBiasWaveformGenerator[i]` | `TesBiasWaveformGenerator[i]` |
| `wfstep` Python helper | `wfsquare` |

Update notebook references and saved configuration paths accordingly. Code
constructing `TesBiasWaveformProcess` directly must now supply `config`; Group
already passes it. The generator tree is fixed from `config.numColumns` rather
than expanded when playback starts.

## Validation

From the repository root, with NumPy installed:

```bash
python -m unittest discover -s software/tests -v
```

These regression tests use real NumPy calculations with fake device nodes and
a deterministic clock. They cover Stop, write/restore failures, invalid inputs,
multiple waveform modes, configuration sizing, timing-lag warnings and restart.
They do not exercise Rogue's process threads, transport, or physical outputs.
The same command runs in CI.

For the process/thread and client checks, activate a real Rogue environment and
run:

```bash
python software/tests/rogue_tes_bias_waveform_smoke.py
```

This test starts a localhost ZMQ server and client with 16 generators and a
simulated bias vector. It exercises Start/Stop/restart, partial-write and
restoration errors, client discovery, and YAML configuration migration. It
does not connect to boards or validate the full hardware Group tree. Allow
localhost sockets when running it in a sandbox. It runs separately from CI,
which does not install Rogue.

[Issue #55](https://github.com/slaclab/warm-tdm/issues/55) owns the acceptance
criteria, outstanding checks and candidate-specific test results. This includes
physical waveform shape, restoration and sustainable update rate. Consult the
issue for current verification status; merging PR #79 does not complete hardware
acceptance.
