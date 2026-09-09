# Plan: PID-debug stream analyzer (fixed + floating point)

## Context

The warm-TDM FP-PID firmware (Issue #70) needs a tool to inspect, **diagnose**, and
**compare** the per-(col,row) PID-servo telemetry from both the fixed-point (`AdcDsp`)
and floating-point (`AdcDspFp`) paths — the core evidence for whether FP PID resolves
the SQ1 oscillation (Issue #42), plus a way to spot common servo faults and get tuning
guidance.

The PID debug stream is a per-(col,row) time series over readout visits carrying the
control signals: error (`accumError`), integrator (`sumAccum`), controller output
(`pidResult`), actuator (`sq1Fb`), `numFluxJumps`, `dropCount`, and a 48-bit `runTime`.
The loop is a PI(+D on fixed) flux-locked servo nulling `accumError` via `sq1Fb`. Gains
are register-based and captured in the file config — FP `pCoef`/`iCoef` (float32,
`AdcDspFp.vhd` X"04"/X"08"); fixed `accumShift` (X"00") + P/I shift/mult regs — so offline
recommendations are feasible.

**Fixed vs float format differences** (drives Phase 1b): fixed is PI+D / fixed-point and
logs `pidResult`(i64) + before/after actuator (`sq1FbStart`/`sq1FbEnd`); float is PI-only
/ float32 and logs the **unclamped vs applied** feedback (`sq1FbFullFp` vs `sq1FbInt`) and
**before/after integrator** (`sumAccumFp`/`newSumAccum`). Asymmetries worth addressing:
float computes `saturatedHigh/Low` but doesn't emit them, and neither path logs a
numeric-overflow flag (the `6aec8a2` width bug shows fixed-point overflow is a real hazard).
Deliberately NOT changing: fixed `numFluxJumps` i8 is adequate per-visit; `baseline`/setpoint
is ~always 0 in practice (why it was dropped — not re-adding); float `readoutCount` is
redundant with `runTime`.

Today's tooling is fragmented/partly broken: float exists only as a standalone script; the
fixed decoder `_DataFormats.PID_DEBUG_TYPE` is **stale** (expects a 10-word/80-byte body
with `baseline`; RTL emits 9 beats / no baseline → off-by-one, size gate rejects frames);
no analysis/diagnosis/comparison.

The **channelization** branch (Issue #82) is the foundation: self-describing 16-byte header
(`FrameHeaderPkg.vhd`), `FormatType` enum (`PID_FIXED`/`PID_FLOAT`), both decoder
dataclasses, and a `StreamReader` dispatching on `formatType`.

Decisions with the user: **reconcile channelization onto current cleanup first**; **no
capture files yet** (derive formats from RTL + self-check tests); **add the cheap telemetry
now** (pack new flags into spare frame bits, bump `formatVersion`); tuning recs delivered
**staged** (directional hints v1, quantitative auto-tune later); v1 emphasis is **broad
issue coverage**.

Worktree/branch: `/sdf/group/faders/users/bareese/projects/warm-tdm-channelization`, branch `channelization`.

---

## Phase 0 (prerequisite): Reconcile channelization with current cleanup

Merge current `cleanup` into `channelization` (merge, not rebase). `merge-base` `f0af673`;
cleanup +42, channelization +19. Only **7 files** conflict: `AGENTS.md`,
`firmware/python/warm_tdm/_HardwareGroup.py`, RTL `ColumnFpgaBoard.vhd`,
`ColumnFpgaBoardAwaXe.vhd`, `AdcDsp.vhd`, `DataPath.vhd`, `WarmTdmCore2.vhd`. Format infra
(`_DataFormats.py`, `streamreader.py`, `AdcDspFp.vhd`) is not in the conflict set.

1. Backup branch `channelization-backup-presync-<date>`.
2. `git merge cleanup`; reuse earlier resolutions: ColumnFpgaBoard generics = cleanup's
   superset; **AdcDsp.vhd must keep both** channelization's header emission
   (`emitFrameHeaderWord0/1`, `FRAME_FORMAT_PID_FIXED_C`) **and** cleanup's `6aec8a2` fix;
   DataPath/WarmTdmCore2/AwaXe = union. Reconcile submodule pointers to newer.
3. Verify: no markers; `surf.*` entities resolve; crossbar indices in range;
   `python -c "import warm_tdm, warm_tdm_api"` OK.

## Phase 1: Fix the stale fixed-point format (`firmware/python/warm_tdm/_DataFormats.py`)

Re-derive `PID_DEBUG_TYPE` from post-reconcile `AdcDsp.vhd` (2-word header + body beats;
**no baseline**). Confirm word count/offsets via `grep pidDebugMaster.tData AdcDsp.vhd`.
Update `PID_DEBUG_TYPE`, `PID_DEBUG_BODY_BYTES`/`PID_DEBUG_FRAME_BYTES`,
`PID_DEBUG_FIELDS`; drop `baseline`. Add a **fixed→real scaling** table from the RTL
`ufixed`/`sfixed` formats (accumError, sumAccum, pidResult, sq1Fb) — needed by metrics +
comparison. Float (`PID_DEBUG_FP_TYPE`/`PidDebugFp`) already matches RTL.

## Phase 1b: Cheap firmware telemetry additions (RTL + decoders + formatVersion)

Pack into **existing spare frame bits** (no frame-size growth); bump
`FRAME_FORMAT_VERSION_C` in `FrameHeaderPkg.vhd` ("extend, never renumber").
- **`AdcDspFp.vhd` word 4**: emit the already-computed `saturatedHigh`/`saturatedLow` into
  bits (15:14) (currently hardcoded "00"), and a small **status/flags** nibble into (31:24)
  (currently 0) — e.g. locked, flux-jump-applied, overflow.
- **`AdcDsp.vhd`**: add a **status/overflow flags** byte in spare bits — a numeric-overflow
  sticky bit plus a saturation flag (derive from `pidResult` vs the clamped `sq1FbEnd`).
  Leave `numFluxJumps` i8 (adequate per-visit — not widened).
- **Not doing**: `readoutCount` on float (redundant with `runTime`), re-adding `baseline`
  (~always 0). The analyzer derives the visit index from `runTime`(+`dropCount`).
- Update the **Python decoders** in `_DataFormats.py` (`PidDebug`, `PidDebugFp`) to expose
  the new flag fields; add them to `PID_DEBUG_FIELDS`/the FP field set.
- Requires a **bitfile rebuild** (Vivado 2024.1) to exercise on hardware; the SW decoders
  and analyzer can be developed/tested against synthetic frames meanwhile.

## Phase 2: Analyzer core — `software/python/warm_tdm_api/operations/pid_analysis.py`

Consumes `PidDebugData` (reuse `data.py` + `_resolve_pid_data`). Three layers:

**(a) Metrics** `pid_metrics(pid_data, col=None, row=None) -> dict` per (col,row):
steady-state error (residual `accumError` after settling) + RMS/noise; **oscillation**
(FFT + autocorrelation of `accumError`/`sq1Fb` → dominant freq, amplitude, growth flag);
settling time / overshoot; actuator **saturation** (now from the emitted flags, else
`sq1FbFull` vs `sq1FbInt` / `pidResult` vs `sq1FbEnd`); **windup** (integrator drift while
railed); flux-jump & drop rates. numpy/scipy.

**(b) Diagnosis** `diagnose_pid(metrics) -> list[Finding]` — broad rule-based catalog:
limit-cycle oscillation, diverging/not-locked, steady-state offset, sluggish/underdamped,
overshoot/ringing, integrator windup, actuator saturation, flux-jump thrash, high drops,
**numeric overflow** (fixed, from the new flag). Findings: {col,row,kind,severity,evidence}.

**(c) Recommendations** `recommend_gains(findings, current_gains, method='directional')`:
- **v1 directional**: fault → gain direction + rough factor, using gains read from config
  (FP `pCoef`/`iCoef`; fixed `accumShift`+regs). oscillation→lower Kp/Ki; offset→raise Ki;
  sluggish→raise Kp; windup→lower Ki/clamp.
- **v2 (deferred, `method=` hook)**: quantitative auto-tune (limit-cycle ultimate gain/
  period → Ziegler–Nichols, or step-response fit) → numeric Kp/Ki.

`report_pid(pid_data)` runs metrics→diagnosis→recs → per-(col,row) summary.

## Phase 3: Fixed-vs-float comparison (`analysis.py` + `pid_analysis.py`)

- `compare_pid(crstring, quantity='accumError', pid_data_a, pid_data_b, mode='overlay',
  ax=None)` in `analysis.py`: reuse `_resolve_pid_data`×2, `get_row_col`, the `shaped`/
  `expand_channels` adaptation, `make_color_cycle`/`add_channel_legend`. A **semantic field
  map** resolves `quantity` per format w/ fixed→real scaling (accumError↔accumErrorFp,
  integrator sumAccum↔sumAccumFp, sq1fb sq1FbEnd↔sq1FbInt, fluxJumps/dropCount common);
  align x by `runTime`/`readoutCount` or truncate for `mode='diff'`.
- `compare_pid_report(fixed, float)` in `pid_analysis.py`: run metrics+diagnosis on both,
  tabulate deltas (e.g. limit-cycle amplitude fixed vs float at matched gains) — the #70 headline.

## Phase 4: Register exports (`operations/__init__.py`)

Add `compare_pid`, `pid_metrics`, `diagnose_pid`, `recommend_gains`, `report_pid`,
`compare_pid_report` to import blocks + `__all__`. `data.py` unchanged.

## Phase 5: Collapse standalone scripts to thin CLIs

`scripts/PidDebugFileReader.py` + `PidDebugFileReaderFp.py` → argparse wrappers over the ops
module that can emit `report_pid`/`compare_pid_report`. Preserve `col&0b111`/`row&0xFF`
masks, the offline (no device-tree) parse path, and the FP reader's data return. Drop the
fixed reader cruft (`FastDacAmplifierSE`, broken `PidDebugMessage`, duplicated dtypes).

## Phase 6: Tests (no capture files yet)

Pytest with **synthetic frames incl. injected faults**:
- round-trip decode fixed/float (incl. the new flag fields) → assert values + sizes; an
  `itemsize == header + N*8` guard against drift.
- diagnosis: synthesized oscillating error → *oscillation* (freq/amp); railed `sq1Fb` +
  saturation flag → *saturation*; constant offset → *offset*; monotonic error →
  *diverging*; overflow flag set → *numeric overflow*. One case per fault kind.
- recommendations: directional hints match injected faults + gains.
- `compare_pid`/`compare_pid_report`: two synthetic `PidDebugData` (via `_pid=` wrap) →
  overlay/diff shapes + metric deltas.

---

## Verification (end-to-end)

- `conda activate warm-tdm-r615`; `python -c "import warm_tdm, warm_tdm_api"`.
- `pytest` new tests green (decode + synthetic-fault diagnosis + comparison).
- REPL: load fixed & float `PidDebugData`; `plot_pid_debug` both; `report_pid` prints
  diagnosis+hints; `compare_pid('c0r5', quantity=...)` overlays; `compare_pid_report`
  tabulates limit-cycle deltas.
- **Firmware**: rebuild the FP bitfile (Vivado 2024.1) to emit the new flags; bench-validate
  byte-exact decode + physical metrics against a real capture (fixed + float). Until then,
  correctness rests on RTL-derived dtypes + synthetic tests; re-run the itemsize guard on
  any `AdcDsp.vhd`/`AdcDspFp.vhd` change.

## Risks / open items

- **Fixed-format re-derivation is RTL-only** (no capture) — highest residual risk; itemsize
  guard + RTL cross-check mitigate.
- **Reconcile merge**: `AdcDsp.vhd` must keep both channelization's header emission and
  cleanup's `6aec8a2` fix.
- **Phase 1b changes bit meanings** → `formatVersion` bump; old captures decode under the
  old version. Decoders should branch on `FrameHeader.formatVersion`. Coordinate with the
  channelization "extend, never renumber" rule; needs a bitfile rebuild to test on HW.
- **Fixed→real scaling** trust depends on reading `ufixed`/`sfixed` formats correctly —
  document assumed formats by the scaling table.
- **Diagnosis thresholds** are heuristic — expose as tunable params; validate on first real
  captures before trusting hints. v2 auto-tune out of v1 scope (hook only).
