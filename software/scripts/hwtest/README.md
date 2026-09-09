# Hardware-test helper scripts

Runnable bench scripts automate the software-observable portions of issue
acceptance: register reads, file comparisons and explicit pass/fail checks.
The owning issue holds the remaining checklist and test results. Reusable setup
instructions live on the [Hardware Verification wiki](https://github.com/slaclab/warm-tdm/wiki/Hardware-Verification).
Physical measurements and real-link tests remain manual acceptance steps.

## Scripts

| Script | Owning issue | What it checks automatically | Still manual |
|---|---|---|---|
| `verify_dead_masks.py` | [#60](https://github.com/slaclab/warm-tdm/issues/60) | Masked channels are exactly the channels that drop out of the stream file | — (fully software) |
| `check_link_health.py` | [#50](https://github.com/slaclab/warm-tdm/issues/50) | RSSI (and PGP) link counters; baseline + poll-for-deltas | inducing a real fiber fault |
| `verify_stop_and_zero.py` | [#86](https://github.com/slaclab/warm-tdm/issues/86) | Complete finite nonzero → confirmed mux run → stopped/zero fast-DAC readbacks across N cycles | load-board DMM confirmation |

## Running

Start a `warmTdmServer` (real hardware or `--emulate` for a smoke test — note
emulate does **not** exercise the analog path, so a `PASS` in emulate only means
the script and register plumbing work, not that the hardware behaves). Then:

```bash
conda activate warm-tdm-r615
cd software/scripts/hwtest
python verify_dead_masks.py     --host localhost --port 9099 --cols c4r3,c4r19,c5r58
python check_link_health.py     --host localhost --port 9099 --seconds 30
python verify_stop_and_zero.py  --host localhost --port 9099 --cycles 5
```

All three share the connection flags `--host` (default `localhost`) and `--port`
(default `9099`) and connect via `warm_tdm_api.operations.connect`. Each exits
non-zero on `FAIL` so they can be chained or run under CI against a live rig.

Every run prints the firmware build stamps + git hashes (via
`ops.print_hardware()`) so a result is pinned to a specific firmware/software
version. Add the software commit, tool versions, configuration and outcome to a
result comment on the owning issue; do not duplicate a status record on the wiki.

`verify_stop_and_zero.py` requires one column board and one row board for its
normal acceptance path. It programs nonzero per-row currents with PID disabled,
verifies every output at idle and during a confirmed run, then requires complete
zero readbacks after timing stops. It restores saved per-row current settings
and attempts stop/zero on failure; timing is left stopped and PID disabled.
`--skip-cols` is diagnostic-only. A missing/non-finite readback or zero-only
baseline fails the test. MemEmulate does not run the DAC FSM and is not expected
to pass this sequence; use GroupTb cosimulation or hardware and record which.
The `--diagnose` matrix explains override behavior; it is not the full acceptance
sequence. Scope/DMM measurements remain on #86.
