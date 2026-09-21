# SQ1 feedback scale: recovered hardware notebook evidence

## Question and result (2026-09-17)

The user expects approximately 3–4 SQ1 flux quanta across the feedback DAC.
The standard software amplifier model instead gives about 304 uA peak-to-peak.
The 10 uA simulation period would therefore occupy only 539 DAC codes.

A historical notebook contains real hardware outputs absent from its current
version. The saved SQ1 curves repeat approximately every **21.7 uA**, and its
readout plot records a conversion of **18571.0 pA/code**. Taken together, these
imply approximately **1170 DAC codes per quantum** and **14 quanta across the
DAC**, still substantially more than the requested 3–4. These are evidence for
one saved run, not a wafer-independent specification or an independent physical
current calibration.

The user subsequently supplied another agent's findings from notebooks on a
different machine: they configure SQ1 `FluxQuantum` from a **90 pH feedback
mutual inductance**, giving **22.976 uA**. With the standard amplifier model,
that is **1238 codes per quantum** and **13.24 quanta across the DAC**. This
agrees with the overall range concern while remaining about 5.6% above the
period estimated from the recovered September plots. Keep design input and
observed spacing distinct until the raw curves and wafer identity are known.

The investigation initially changed only these notes. The user subsequently
requested the nominal wafer SQ1 period be set to **23 uA**; the implementation
and validation are recorded below. The earlier SA-model alignment request
remains canceled.

## Nominal 23 uA model update

- Shared `SQ1_SQUID_SYNTHETIC_C.currentPerPhi0Amp` is 23e-6 A; the `WaferSim`
  compatibility generic defaults to that shared value.
- PID cosimulation defaults and example JSON program a 23 uA quantum and
  scale the near-mid-slope seed from 7 to 16.1 uA (same 0.7-period position).
  The older Group tune seed scales from 7.37 to 16.951 uA. No new measured
  lock point is claimed.
- Default SQ1 tuning span scales from +/-15 to +/-34.5 uA, retaining three
  periods and 31 samples. SSA/FAS settings and amplifier defaults are unchanged.
- Existing PID gains and thresholds remain starting values; changing the
  period changes plant slope, so closed-loop acceptance requires a rebuilt
  GroupTb run. The historical 10 uA measurements remain labeled as such.
- Validation: `make test` in `firmware/simulations/WaferModelTb` passed all six
  GHDL testbenches (device equations, compatibility wrapper, detector scale,
  profiles, group harness, and variation). Focused software checks passed:
  `test_cosim_checks.py` and `test_supporting_helpers.py`, 17 tests and 29
  subtests. Changed Python files parse; both JSON profiles match the built-in
  defaults; the 0.7-period and 0.737-period seeds retain their old phases.
  The new 23 uA period rounds to integer Q=1239 at the default amplifier scale.
- Full vendor-IP GroupTb cosimulation was not rerun. Rebuild the simulation
  and restart the software server before evaluating lock/settling at 23 uA.

## Reproducible source

Notebook at commit `d70ee913ed8100e79fae669ff673096e2d83ce3f` (2026-09-11):

[software/jupyter/operations_template.ipynb](https://github.com/slaclab/warm-tdm/blob/d70ee913ed8100e79fae669ff673096e2d83ce3f/software/jupyter/operations_template.ipynb)

The September 14 cleanup (`3b29a70`) removed the executed outputs. The current
notebook and paired `.py` therefore do not reveal the full evidence. Recover
without changing the working notebook using:

```bash
git show d70ee91:software/jupyter/operations_template.ipynb > /tmp/operations_template-d70ee91.ipynb
```

This investigation recovered the notebook and its original PNG outputs under
`/private/tmp/warm-tdm-notebook-evidence/`. Git is the durable source; large
notebook/image artifacts are not duplicated in this task directory.

Cell numbers below are zero-based JSON cell indices:

| Cell | Saved evidence |
|---|---|
| 2 | Hardware report: ColumnFpgaBoard325Coord10G, built September 11 with Vivado 2024.1; RowFpgaBoard built March 26; device DNA and firmware hashes |
| 4 | Executed cable-resistance setup, 116 ohms roundtrip |
| 6 | Columns 0–3 enabled; logical row order `[10,11,12,13]` |
| 13 | FAS calculation refers to NIST mux21_s4, two-level, Mfas=6.3 pH; this is a FAS parameter, not SQ1 feedback coupling |
| 16 | SQ1 sweep settings: -30 to +30 uA, 120 points, SQ1 bias 50 uA; this source cell has no execution count |
| 17 | Executed plotting cell, 16 stored SQ1 curves for four columns and four row positions |
| 21 | Executed output of fitted lock points: SQ1 bias 50 uA, SQ1 FB about 10.34–11.85 uA; these feedback values are operating points, not flux periods |
| 23 | Acquisition reports a hardware data-file path |
| 25 | Saved readout plot explicitly labels SQ1FB-to-pA factor 18571.0 |

The figures label rows by position in the tune result. Position 0 corresponds
to logical row 10 for the displayed row order. Notebook cells were executed
out of order: the cell 23 output names `data_20260911_150347.dat`, while the
cell 25 figure title names `data_20260911_145858.dat`. Do not treat every output
as one uninterrupted acquisition or assume all runtime configuration is saved.

The recorded acquisition directory is:

```text
/sdf/group/faders/users/bareese/projects/warm-tdm-cleanup/software/data/20260911/1789156819/
```

It is not available in this local workspace. The data file's embedded config,
if available, is the next source for the actual per-channel amplifier model
settings used during acquisition.

## Period estimate and FFT limitation

The four row-position-0 plots show successive peak spacings around 21.7 uA.
For example, column 0 peaks are approximately -28.8, -7.0, and +14.6 uA;
column 1 peaks are approximately -27.9, -6.2, and +15.5 uA. Reading the blue
trace pixels in the original PNGs gave spacings approximately 21.5–21.8 uA
across these four plots. This is a raster estimate, not a fit to raw samples.

Their legends instead display `phi0: 20.17`. `_CurveClass.Curve.updatePeak`
selects the largest non-DC FFT bin with no interpolation. With 120 points
over an inclusive 60 uA sweep, bin k=3 gives:

```text
period = N * dx / k = 120 * (60/119) / 3 = 20.168067... uA
```

Consequently the legend's two decimal places do not establish that precision
for the physical period. Use approximately 21–22 uA for this investigation;
precise flux-jump calibration needs the raw sweep or a better period fit.

## Amplifier scale and range implications

Standard `FpgaBoardColumnFebChannel.SQ1FbAmp` uses InputR=100 ohms,
FbR=402 ohms and ShuntR=7680 ohms per side. The base fast-DAC model supplies
FSADJ=2000 ohms, LoadR=24.9 ohms, and FilterR=149.7 ohms per side.
`FastDacAmplifierDiff` gives gain 5.02 and includes both series shunts/filters.

At the saved 116-ohm cable setting:

```text
IOUTFS = (1.2 / 2000) * 32 = 0.0192 A
Rout = 2*149.7 + 2*7680 + 116 = 15775.4 ohms
uA/code = 2*IOUTFS*24.9*5.02 / (16384*Rout) * 1e6
        = 0.018570943526
endpoint span = 16383 * uA/code = 304.247768 uA
Q at 21.7 uA = approximately 1168.5 codes
quanta across endpoint span = approximately 14.02
```

The saved plot's 18571.0 pA/code agrees with this calculation. Default cable
resistance 120 ohms instead gives 304.170642 uA; the cable difference cannot
explain the range mismatch. The 7.68-kohm shunt was an intentional change from
1 kohm in commit `4e0ee5a` (2025-05-20), but source history does not prove the
populated resistor value on the board used in this run.

For a physical quantum of approximately 21.7 uA, 3–4 quanta require a full
span approximately **65–87 uA**, or **3.5–4.7 times less current per DAC code**
than this model. The absolute uA values depend on the amplifier model matching
hardware. If a common current-scale error affects both plotted sweep current
and computed full span, correcting that label alone does not change the
inferred number of DAC codes per quantum.

The simulation's 10 uA value exists in `WaferSim.SQ1_PHINOT_G` from the January
28 simulation commit (`1e0ba92`); no measurement provenance was found for it.
It should not be described as the hardware value established by this notebook.

## User-supplied evidence from notebooks on another machine

The user reports another agent inspected January 13/22, March 12, and April
10/20 notebooks under `/u1/warm-tdm/warm-tdm/software/scripts/`. These files
were not independently accessed in this workspace. According to that report:

- SQ1 `FluxQuantum` is programmed per column using `Phi0 / Mfb`, with Mfb
  approximately 90 pH and a comment identifying single-level NIST mux15b.
- The nominal result is 22.976 uA; FAS uses its separate 6.3 pH coupling and
  approximately 328 uA period. The FAS value is not the SQ1 PID quantum.
- The notebooks do not override SQ1FB gain/shunts/FSADJ; only TES amplifier
  settings and, in one notebook, cable resistance are explicitly changed.
- The reported SQ1 defaults match this checkout exactly. The resulting
  120-ohm-cable calculations are 18.566 nA/code and 304.171 uA span.

The inductance calculation was independently recomputed locally:

```text
Phi0 = 6.62607015e-34 / (2 * 1.602176634e-19)
Q = Phi0 / (90e-12) * 1e6 = 22.97593165 uA
Q_DAC = 22.97593165 / 0.0185662358835 = 1237.5116 codes
full_span / Q = 13.2387
3–4 quanta = 68.9278–91.9037 uA total span
required current-per-code reduction = 3.31–4.41 times
```

Thus 10 uA is too small as a representative quantum for these hardware
notebooks, but replacing it with 23 uA does not produce the intended 3–4
quanta over the existing amplifier range. This does not by itself establish
an erroneous software conversion or prove the populated hardware values.
The September notebook's FAS comment names mux21_s4/two-level, so matching
wafer identity across these runs is also unproven.

The -30..+30 uA tune sweep is only a characterization interval. It does not
limit the integer PID's feedback range; its +/-7862-code threshold remains
near the physical DAC rails (approximately +/-146 uA at this scale).

## Other findings and next steps

- The 2022 DMM and March notebooks contain SA measurements, grounding/noise
  tests and load-board tests. They do not establish a current SQ1 period.
- Historical analysis constant `1224.23093499038` pA/code was introduced in
  `b09f75e` (2026-03-31) on plots labeled **TES Current Eq.** Its derivation is
  absent. It cannot establish a lower SQ1 feedback-amplifier gain. The current
  analysis code still labels TES-equivalent current while deriving only the
  SQ1 feedback output-current slope: distinguish these units in any follow-up
  calibration review; no coupling ratio is established here.
- Inspect the saved hardware capture configuration and populated amplifier
  values before deciding whether the software model or physical range needs
  changing. Fit the raw SQ1 sweep for an accurate quantum. Do not program the
  raster estimate or coarse FFT-bin period as a calibrated flux jump.
- Multi-wrap arithmetic remains specified over the full supported Q range;
  its correctness does not depend on the 10 uA simulation fixture.
