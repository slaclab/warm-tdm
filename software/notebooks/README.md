# Maintained notebook templates

Copy a template with [new_run.py](../scripts/new_run.py) before executing it.
See [Notebook measurement runs](../../docs/notebook-runs.md) for creation,
connection, resuming, provenance, storage and template maintenance.

| Template name | Purpose |
|---|---|
| `hardware/operations_template` | Fixture-specific bring-up, tuning, capture and analysis |
| `hardware/operations_gain_sweep` | Explore P gains on an already-tuned instrument |
| `cosim/checks` | Batch-equivalent controls, readout and stop/zero checks |
| `cosim/pid` | PID behavior verification with recorded data for analysis |
| `cosim/tuning` | Reduced sensor-model tuning and curve inspection |
| `cosim/pid_lock` | Lock trajectory exploration using the batch recipe |
| `diagnostics/register_latency` | Read-only timing-register round-trip measurements |

The `.ipynb` files are the maintained templates. Edit them directly in Jupyter;
there are no paired Python sources or generation step. Reusable operations and
verification logic belong in the operations package or `software/cosim/` scripts.

Before committing a template, clear all cell outputs and execution counts and
save the notebook. Validate its basic structure and cleared outputs with:

```bash
python software/scripts/check_notebooks.py
```

The check never executes or rewrites notebooks. It supports notebook magics and
ignores Jupyter checkpoints. Measurement copies and historical records are outside
its scope: retain their outputs as evidence.
