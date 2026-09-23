# Notebook measurement runs

Git owns reusable, output-free [templates](../software/notebooks/README.md).
An executed notebook is a measurement record: copy it first, keep its outputs,
and store it with its data outside Git. A run directory persists across kernel
restarts and connections and may contain multiple acquisitions and analysis
notebooks. It is separate from the operations `Session` connection object.

## Create a run without connecting to hardware

Choose an existing, backed-up experiment directory. For local work, create
`runs/` at the repository root; that entire directory is ignored by Git.
From the checkout:

```bash
python software/scripts/new_run.py hardware/operations_template \
  --base /data/warm_tdm --name sq1-bringup \
  --purpose "Tune the B33 setup and record the initial noise capture"
```

The command prints the copied notebook path. It needs only standard Python;
it does not import Rogue, open a client, change hardware, or launch Jupyter.
Paths use UTC dates/times plus a unique suffix, so repeat invocations never reuse
an existing measurement directory. The base must already exist: unavailable
storage is an error, not a reason to save elsewhere.

```text
/data/warm_tdm/2026-09-23/143205_sq1-bringup_ab12cd34/
├── operations_template.ipynb  # editable measurement copy, retain outputs
├── run.json                  # purpose, operator, template origin and environment
├── README.md                 # observations/outcome, or write these in the notebook
├── config/                   # configuration snapshots and fixture profiles
├── data/                     # captures and check results
├── figures/                  # exported plots
└── provenance/               # original template, source patches, connection records
```

The original template copy and SHA-256 identify the starting notebook even if
its source checkout was dirty. Creation and connection records identify the
client revision, tracked patch (excluding notebooks), untracked Python/JSON/YAML
sources, submodule status and available environment versions. These are
provenance aids, not a complete reproducible system image. Preserve relevant
firmware builds/model patches and external environment records separately.

## Open and connect

Use a Rogue-enabled Jupyter kernel. When running from a checkout, export its
absolute path before launching Jupyter from the run directory:

```bash
export WARM_TDM_PATH=/absolute/path/to/warm-tdm
cd /data/warm_tdm/2026-09-23/143205_sq1-bringup_ab12cd34
jupyter lab
```

The notebook registers the checkout's software, firmware and SURF Python paths.
It does not depend on `../scripts` or its original location. Installed environments
may provide these modules directly instead. `runs.find_run()` searches the kernel
working directory and parents for `run.json`; use `runs.validate_run("/path/to/run")`
explicitly if the kernel starts elsewhere.

Hardware notebooks connect with:

```python
sess = ops.connect(host="localhost", port=9099, run_dir=RUN_DIR)
```

`run_dir` must name a directory created by `new_run.py`. Its existing `data/`
and `config/` are reused without timestamp nesting or fallback. `path=` remains
the legacy base-directory API for older callers; do not combine a custom `path`
with `run_dir`. Configuration snapshots use unique time-based names under
`config/`; captures use `data/`. Stream captures have distinct names on each call,
and individual raw captures get separate subdirectories so a repeated capture
does not reuse a previous file. `sess.new_session()` explicitly selects a different
legacy output directory and should not be used while working in a run copy.

**Server and client must see the run at the same absolute path.** DataWriter,
waveform captures and configuration commands write on the server; local path
validation cannot prove the server mount exists. Use a shared filesystem or run
Jupyter on the server host. Do not point a remote server at a laptop-only path.
Notebook connection cells record readable board identities and identity-read
errors, and accept an optional operator-declared server revision. Unknown server
software remains unknown; the client checkout does not establish it.

Review fixture-specific row map, enabled columns, FAS lines, currents and gains
before setup. The operations template uses the earlier notebook's 8×10 example
consistently in both formats; it is not a universal hardware preset. Bring-up
remains interactive. A failed setup cell may leave its prior writes applied;
use the explicit stop/zero operation as appropriate before restarting setup.
Capture and sweep cells own timing cleanup around their acquisitions. Stop/zero
zeros column outputs and does not promise row-output zeroing.

## Resume and retain the result

Save the notebook with its outputs. On a kernel restart, rerun the storage and
connection cells, then choose which operations to repeat; reconnecting does not
retune, replay earlier cells, or create a new run. Rerunning setup/tuning cells
still changes hardware. Record unsuccessful and interrupted attempts alongside
successful results. Retain original captures; put later analysis in another
notebook within the same run and use relative paths for portable references.
Embedded device configs and historical server paths may still contain absolute
paths; a moved record supports offline analysis, not automatic hardware restore.

Before closing, save the notebook and settings and write a brief outcome with
data filenames. Keep runs on backed-up experiment storage. Issues/lab logs link
to the run location and relevant evidence instead of committing acquisitions.
Notebook edits that improve reusable behavior are deliberately ported back to
the template or operations package. Copies never synchronize back automatically.

## Gain exploration and cosim

The gain-sweep notebook uses an existing tune and timing configuration. It
measures `AccumError` and flux changes on the actual logical rows from
`RowReadoutOrder`, sweeps only the selected column, and restores its original P
gain on failure or completion. I/D remain unchanged. Opposing flux changes
across rows cannot cancel, but excursions between polls can be missed. The
notebook retains completed candidates on interruption, ends timing, and applies
an eligible chosen gain only to the measured column when explicitly selected.
A low polled residual does not establish physical lock or disturbance rejection.

Cosim notebooks call the maintained batch scripts in-process, preserving their
cleanup and pass/fail rules. Every invocation has its own directory and console
log. Create `config/simulation.json` using the manifest instructions in the
[cosim guide](../software/cosim/README_cosim.md), describing the actual running
simulator/server. Example tuning/PID profiles copied into `config/` are starting
points to edit, not verified operating points. `cosim/pid_lock` is an exploration
recipe; its trajectory and console are diagnostic evidence, not an acceptance
pass. Inspect completed reports/captures and add plots to the working notebook.

## Template development and migration

Edit the `.ipynb` templates directly under `software/notebooks/`. There are no
paired `.py` sources or synchronization step. Keep reusable logic in the
operations package or batch verification scripts that the notebooks call.
Before committing a template, clear all outputs and execution counts in Jupyter,
save it, and run:

```bash
python software/scripts/check_notebooks.py
```

The read-only check validates basic notebook/cell structure and requires cleared
outputs and execution counts. It does not execute cells, and allows notebook
magics. It runs in CI and the software regression suite. Jupyter checkpoints,
measurement copies and historical notebooks are excluded. The template picker
also excludes checkpoints.

Template `.ipynb` files are tracked under the template directory; root `runs/`
and measurement copies elsewhere in the checkout remain ignored. Retain outputs
in measurement copies; clearing outputs is a template maintenance step only.

The [software entry-point index](../software/README.md) maps retired/moved paths
to replacements. Existing historical notebook bytes and outputs are preserved in
[measurement references](reference/measurements/README.md). The old `LatencyDebug`
record is not promoted to a generic acquisition procedure: its replacement
measures client register-read latency only.
