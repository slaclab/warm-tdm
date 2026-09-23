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

Each `.py` is the canonical percent-cell source; its `.ipynb` is generated,
output-free, and committed for convenient copying. Use only `# %%` and
`# %% [markdown]` cell markers; write notebook magics as `# %...` in code cells.
The small repository converter supports this format without a Jupytext dependency.

```bash
python software/scripts/sync_notebooks.py
python software/scripts/sync_notebooks.py --check
```

Synchronization only touches this directory. Measurement copies are standalone
notebooks: retain their outputs and never regenerate them from these sources.
