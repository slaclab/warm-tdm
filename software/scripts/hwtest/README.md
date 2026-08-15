# Hardware-test helper scripts

Runnable bench scripts that automate the *software-observable* parts of the
[Hardware Verification](https://github.com/slaclab/warm-tdm/wiki/Hardware-Verification)
wiki procedures. Each script maps 1:1 to a wiki subpage, runs the steps that a
host can judge on its own (register reads, file comparisons), and prints a
`PASS`/`FAIL` checklist against that page's pass criteria.

These do **not** replace the wiki pages — anything needing an instrument (a DMM
on a load board, a scope trace) stays a manual step on the page. The scripts
cover the parts where the verdict is a number the software already has.

## Scripts

| Script | Wiki page | What it checks automatically | Still manual |
|---|---|---|---|
| `verify_dead_masks.py` | HW-Verify-Issue-60 | Masked channels are exactly the channels that drop out of the stream file | — (fully software) |
| `check_link_health.py` | HW-Verify-Issue-50 | RSSI (and PGP) link counters; baseline + poll-for-deltas | inducing a real fiber fault |
| `verify_stop_and_zero.py` | HW-Verify-Issue-86 | `stop_and_zero` drives fast-DAC readbacks to ~0 across N run/stop cycles | load-board DMM confirmation |

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
version — paste that block into the wiki page's **Record** section and the issue.
