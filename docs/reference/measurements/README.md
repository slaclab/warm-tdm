# Historical measurement notebooks

These notebooks were moved byte-for-byte from `software/jupyter/` and
`software/scripts/` during the software workflow reorganization. Their saved
outputs and observations are evidence from the original setup, not maintained
instructions or acceptance of current firmware. Filenames do not establish a
year; do not infer one from the month/day suffixes.

| Notebook | Record |
|---|---|
| [DMM measurements](DMM_Measurements_2-17.ipynb) | Warm electronics / MCE bias and feedback measurements |
| [Bench testing](Testing_3-25.ipynb) | Reworked board with load board |
| [B33 cryogenic testing](Testing_B33_Cryo_3-25.ipynb) | Grounding, noise and tuning observations |
| [B33 load board](Testing_B33_Load-board_3-25.ipynb) | Load-board comparison near the cryostat |
| [Old notebook template](jupyter_template.ipynb) | Retained outputs from the retired JupyterPlotter example |
| [Latency investigation](LatencyDebug.ipynb) | Original setup/register exploration and outputs |

New measurement records belong in external run directories; see
[Notebook measurement runs](../../notebook-runs.md). The old template and latency
notebook were retained here so retirement did not discard their saved outputs.
