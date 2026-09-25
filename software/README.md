# Warm TDM software

Run commands below from the repository root in the configured Rogue environment.

| Task | Entry point |
|---|---|
| Hardware server | `python software/scripts/warmTdmServer.py --ip <board-ip>` |
| Server with local GUI | `python software/scripts/warmTdmGui.py --ip <board-ip>` (or server `--gui`) |
| Remote GUI | `python software/scripts/warmTdmClientGui.py --server localhost:9099` |
| Interactive Python client | `python software/scripts/warmTdmClientCmd.py --host localhost --port 9099` |
| PROM programming/reload | `software/scripts/PromLoader --help` |
| Inspect recorded data, integer/FP PID, waveform and config | `python software/scripts/inspect_stream.py capture.dat` |
| Start a measurement notebook | [Notebook run workflow](../docs/notebook-runs.md) |
| Physical bench checks / targeted reproducers | [hwtest](hwtest/README.md) |
| Batch simulation checks and harness | [cosim](cosim/README_cosim.md) |
| Software unit tests / explicit Rogue smoke checks | [Regression guide](../tests/README.md) |

`python/warm_tdm_api/` holds device, operations, tuning and GUI code;
`python/warm_tdm_run/` provides offline run-directory management without
importing Rogue. `notebooks/` contains reusable templates, not measurement
results. `examples/cpp_extension/` is an unmaintained native-extension reference.
The root `conda.yml` is the environment definition; generated data belongs on
experiment storage or in ignored root `runs/`.

## Changed paths and retired tools

- Bench checks moved from `software/scripts/hwtest/` to `software/hwtest/`.
- Templates moved from `software/jupyter/` to [notebooks](notebooks/README.md).
  The historical DMM/Testing notebooks and saved outputs from the old template
  and latency exploration are preserved under
  [measurement references](../docs/reference/measurements/README.md).
- `DataFileReader.py`, `PidDebugFileReader.py` and `PidDebugFileReaderFp.py`
  are replaced by `inspect_stream.py`; Python analysis uses `ops.StreamReader`.
- `Jupyter.py`, `callSubroutines.py` and `interactivetest.py` were removed.
  Use an operations Session from a measurement notebook or the interactive client.
- `warmTdmClientCmd.py` now opens a Python prompt with `client`, `group`, `sess`
  and `ops`. Pass `--run-dir` for an existing measurement record; otherwise it
  connects without creating an output directory. It is no longer a `%run`
  bootstrap. Use `ops.connect(run_dir=...)` in notebooks.
- Cosim controls/readout/stop-zero notebooks are combined into `cosim/checks`;
  `cosim/pid`, `cosim/tuning` and `cosim/pid_lock` use batch implementations.

The checkout-based notebook helpers/templates are not added to release script
packaging. Operator launchers and the stream inspector remain packaged. See
[Software guide](SOFTWARE_GUIDE.md) for architecture and the
[Operations API](../docs/operations-api.md) for reusable calls.
