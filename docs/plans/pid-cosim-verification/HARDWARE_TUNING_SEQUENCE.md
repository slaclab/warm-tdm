# Hardware notebook tuning sequence

Investigation dated September 18, 2026. This follows the
[23 uA retune investigation](SQ1_RETUNE.md) and records historical evidence
for SA feedback, SQ1 bias/feedback, and SA-offset ordering. No control code was
changed for this investigation. Full cosim lock remains unresolved on #70.

## Sources and limits

The strongest local evidence is the executed
[September 11 operations notebook at d70ee91](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/jupyter/operations_template.ipynb).
Its connection output identifies real ColumnFpgaBoard325Coord10G and
RowFpgaBoard firmware, device DNA, and hardware acquisition files. September
14 cleanup removed the saved outputs from the current notebook.

Cell numbers below are zero-based JSON indices. Recover the source with:

```bash
git show d70ee91:software/jupyter/operations_template.ipynb
```

The matching revision's helper implementations explain calls inside the
tuning processes. The notebook does not record a Python-package revision for
the running server, so this is source correlation, not proof of every runtime
line. Cells were executed and edited out of order: the SQ1 tune cell has no
execution count despite later saved curves/results, and the displayed SA
plot's 40–50 uA multi-bias sweep differs from the saved single-bias call.
The acquisition and plotted-file timestamps also differ. Treat this as a
hardware workflow with saved results, not a complete chronological run log or
proof that every fitted channel locked.

All tracked and ignored notebooks under local `software/` were checked, plus
historical notebook versions in Git. The specific January/April notebooks
previously reported under `/u1/warm-tdm/warm-tdm/software/scripts/` on another
machine are not present here. The local January/February notebook revisions
contain plotting/latency examples; the March 2022 notebooks mostly contain SA
and load-board work. January 22 and April 22, 2026 **helper code** provides
older corroboration of the offset ordering, but is not a substitute for those
missing executed notebooks.

## Reconstructed sequence

| Stage | Notebook / matching helper behavior | SA offset |
|---|---|---|
| Initial state | Cell 2 reports timing stopped/manual. Cell 6 selects columns 0–3 and logical rows `[10,11,12,13]`. Cell 8 zeros SQ1 feedback, SQ1 bias, and SA feedback force currents. | No explicit offset call here. |
| SA sweep | Cell 10 calls `ops.sa_tune(SetAfterFinish=True)`. `saBiasSweep` zeros the SQ1 force paths, sets each SA bias, and calls `saOffset` before the feedback sweep. `saFbSweep` can also recenter when an ADC approaches its rail. | Adjusted during SA characterization. The separate notebook `ops.sa_offset()` line is commented out. |
| Apply SA result | `saTune` copies SA `xOut` into each column's row RAMs **and** `SaFbForceCurrent`, applies SA `biasOut`, then calls `saOffset`. | Null established at the fitted SA operating point with SQ1 bias zero. |
| Set FAS | Cell 13 sets ON to half the computed 328.2 uA FAS quantum, approximately 164.1 uA, and OFF to zero. The scripted FAS-tune cell 14 has no execution count. | No offset call in the executed FAS setup cell. |
| Start SQ1 tune | Cell 16 requests a -30..+30 uA feedback sweep with SQ1 bias 50 uA. `sq1Tune` loads the first row's SA-tuned feedback into `SaFbForceCurrent`, calls `saOffset` once, then activates rows for their sweeps. Subsequent rows reload their SA feedback starting point. | Reference established before applying the SQ1 sweep stimulus; not rerun per row or per SQ1 feedback point. |
| Measure SQ1 curves | `sq1BiasSweep` writes `Sq1BiasForceCurrent`; `sq1FbSweep` writes `Sq1FbForceCurrent` and runs `saFbServo`, which varies `SaFbForceCurrent` to null `SaOutAdc`. | Held fixed. **SA feedback** is the servo actuator and the measured ordinate of the SQ1 curve. |
| Apply SQ1 result | Executed cell 21 writes SQ1 `biasOut`, `xOut`, and **`yOut`** into the SQ1-bias, SQ1-feedback, and SA-feedback RAMs for each actual logical row. | No new offset run. |
| Acquire | Cell 23 calls `setup_mux(...)` and `take_data(...)`. Their matching implementations configure/start readout without calling `saOffset` or changing the fitted DAC tables. | The tuning reference is retained into readout. |

At the start of SQ1 tuning, the function itself does not zero stale SQ1 bias
left by a previous SQ1 sweep. The clean notebook sequence obtains zero SQ1
bias from the preceding SA tune. Repeating only SQ1 tune without reestablishing
that starting state should not be assumed equivalent.

Relevant helper sources at the notebook revision:

- [SA tuning and final apply](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/python/warm_tdm_api/tuning/_sa.py)
- [SQ1 acquisition and initial offset](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/python/warm_tdm_api/tuning/_sq1.py)
- [Separate offset and SA-feedback servos](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/python/warm_tdm_api/tuning/_common.py)
- [MUX setup](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/python/warm_tdm_api/operations/session/_setup.py)
- [Acquisition](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/python/warm_tdm_api/operations/session/_acquisition.py)

## Exact saved SQ1 apply results

Executed cell 21, execution count 24, uses this mapping:

```python
logical_row = group.RowIndexOrderList.get()[row_position]
result = sq1TuneOutput[row_position][column]
cb.SQ1Bias.Column[column].Current_[logical_row].set(result['biasOut'])
cb.SQ1Fb.Column[column].Current_[logical_row].set(result['xOut'])
cb.SAFb.Column[column].Current_[logical_row].set(result['yOut'])
```

The table rounds the saved values; all currents are software-reported uA.

| Column | Logical row | SQ1 bias | SQ1 feedback | SA feedback |
|---:|---:|---:|---:|---:|
| 0 | 10 | 50.0 | 11.34454 | 15.50700 |
| 0 | 11 | 50.0 | 11.84874 | 15.77829 |
| 0 | 12 | 50.0 | 11.84874 | 15.84719 |
| 0 | 13 | 50.0 | 11.84874 | 15.85469 |
| 1 | 10 | 50.0 | 11.84874 | 12.43593 |
| 1 | 11 | 50.0 | 11.84874 | 13.07591 |
| 1 | 12 | 50.0 | 11.84874 | 12.37332 |
| 1 | 13 | 50.0 | 11.84874 | 13.27303 |
| 2 | 10 | 50.0 | 10.84034 | 13.14262 |
| 2 | 11 | 50.0 | 11.34454 | 12.59512 |
| 2 | 12 | 50.0 | 11.84874 | 13.10125 |
| 2 | 13 | 50.0 | 11.34454 | 12.97817 |
| 3 | 10 | 50.0 | 10.33613 | 13.47665 |
| 3 | 11 | 50.0 | 11.34454 | 0.84421 |
| 3 | 12 | 50.0 | 11.84874 | 13.75720 |
| 3 | 13 | 50.0 | 11.34454 | 13.96859 |

The column-3 / row-11 SA-feedback result is an outlier and is retained here;
the notebook does not establish that it is a good operating point. The saved
results nevertheless establish that the applied SA feedback came from each
**SQ1** fit. They also show real-hardware SQ1 characterization at 50 uA bias;
100 uA should not be treated as a general hardware requirement.

## Older code and later automation

- [March 21, 2023 change a26a682](https://github.com/slaclab/warm-tdm/commit/a26a6827b45fed233ac109469acaca04e4a18679)
  explicitly added `saOffset` before the SQ1 row loop.
- [January 22, 2026 helper](https://github.com/slaclab/warm-tdm/blob/950521c3b9d7d501347ef33c481617ff5f115b8a/software/python/warm_tdm_api/_Tuning.py)
  and [April 22 helper](https://github.com/slaclab/warm-tdm/blob/68652720cfe8e094df9465e5f4b2cdf5af22cd3d/software/python/warm_tdm_api/_Tuning.py)
  retain the pre-SQ1 offset call and use `saFbServo` at SQ1 sweep points. Their
  in-function application of the three SQ1 results is commented out. Unlike
  the September helper, these versions do not explicitly force the fitted
  SA feedback before the final SA offset call; do not copy that omission into
  the current stopped-timing workflow.
- September 14 commit `ec3039b` added SQ1 `SetAfterFinish` to automate the
  notebook's manual three-value apply. It defaults to **False** in the current
  process. The maintained notebook explicitly requests `SetAfterFinish=True`.

## Implication for the cosim investigation

Follow the hardware workflow's distinction between the two servos: establish
the common SA-offset reference before SQ1 characterization, then retain it
while finding and applying all three per-row SQ1 results. The SQ1 fit's
`yOut` is what makes each row compatible with that common reference.

The current `cosim_pid_lock.py` and `verify_cosim_pid.apply_lock` call
`sa_offset()` immediately before muxed readout after changing row tables.
The recovered hardware notebook has no corresponding call. If the force
DACs or selected-row state differ from the fitted state, that extra offset
run changes the ADC target against which the SQ1 fits were obtained. This is
a concrete integration difference to test, not yet proof of the reported
constant-error failure.

Do not repair the recipe by restoring every row's SA-only feedback, and do
not discard the fitted `SaFb=yOut`. For a completed tune, preserve its offset
into readout. A seed-only shortcut must deliberately reproduce an equivalent
SA reference and complete row operating point; changing row-table numbers
and nulling an unrelated force state does not do so.

Validation for this investigation was read-only notebook JSON extraction,
saved-output inspection, and source tracing at pinned Git revisions. No
notebook, hardware session, or cosim was executed, and no production code was
changed.
