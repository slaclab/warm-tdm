# PID cosim verification — Progress

## 2026-09-16 — integer flux-jump audit and corrections

The [flux-jump review](FLUX_JUMP_REVIEW.md) verified that the full-precision
wrap direction preserves `F + J*Q`, then reproduced and fixed four RTL/transport
faults: masked visits writing the count without a DAC wrap, Q=0 consuming count
range, debug/software losing the ninth count bit, and the 24-bit internal FIFO
losing sign extension before BiquadFilter's Int32 converter. The negative
readout counterexample was −21862 becoming +16755354. The internal integer
stream now carries all 32 bits; the external readout layout is unchanged.

The software quantum conversion now treats a flux period as a current
difference using `abs(currentPerLsb())`. Previously an inverted-amplifier
zero-current setting could encode signed −1 instead of disabling wraps.
Negative, sub-resolution and overrange period requests are rejected.

**User decision: keep the signed nine-bit net count (−256..255).** Beyond its
endpoints the actuator can still wrap while the count saturates; the resulting
loss of a quantum from readout history is explicitly documented and tested as
an operating limit. Single-wrap slew/clipping and pre-wrap I anti-windup also
remain unchanged. No new FSM cycles were added.

Integer PID-debug is now **v3**, still 96 bytes: body word 7 preserves all nine
count bits in a signed int32. V1/v2 files retain their original decoding, with
their original eight-bit count limitation. FP/readout/waveform versions are
unchanged. The full-feedback word remains at frame byte 64.

Final GHDL 6.0.0/cocotb 2.0.1 run passed **all 40 RTL cases**, with no skips:
eight new flux cases and nine retained-feedback cases in each of the 8-row/
inverted and 256-row/normal configurations, five existing properties, and the
11-write historical-stimulus comparison. All six pytest configurations passed.
The **37 targeted Python tests** passed (29 format/receiver, six cosim checks,
two quantum-conversion tests; 25 subtests). A broader helper-suite run hit one
unrelated stale `ColumnModule` subtest referencing the removed
`_ColumnModule.py`; it is recorded in the review rather than marked passed.

Vivado 2024.1 synthesis/timing, full PyRogue tree construction, and physical
closed-loop/flux-wrap performance remain unverified locally. The review gives
the reproducible commands, failure evidence, operating constraints and follow-up
checks. No frozen golden/reference RTL was changed.

## 2026-09-16 — retained integer fractional feedback

The `43a5bee` working tree now implements the
[fractional-feedback design](INTEGER_FRACTIONAL_FEEDBACK.md): full-precision
feedback per row, initialized from the captured DAC after a clear and retained
for subsequent updates. The DAC output alone is quantized. A validity bit
participates in the existing clear sweep; masked rows hold their state.
The candidate paths need one saved-feedback-plus-correction addition.
There are no additional FSM states or changes to the diagnostic PidResults
meaning. Existing register addresses are preserved. `sq1FbFull` now holds the
retained full-precision value, replacing its unused integer-only accumulation.
AdcDspFp is unchanged. The simplified feedback path updates `sq1FbFull`, applies
one flux shift, clamps it, and converts once to the integer `sq1Fb`. The
`sq1FbCommand` and `sq1FbWrapped` temporaries and parallel integer wrap were
removed. Flux thresholds now inspect the full-precision value; wrapping precedes
DAC clipping and rounding, including half-code ties. The 38-bit payload's guard
bit permits a one-quantum recovery of overrange corrections before the clamp.

The dedicated GHDL bench feeds actual DAC writes back into later row visits;
its sequences and exact rational expectations cover retained fractions,
rounding, independent rows, initialization/reseeding, lifecycle, wrapping,
clipping and anti-windup. The frozen pre-split golden remains unchanged; the
historical stimulus comparison has explicit new expectations for visits that
now use saved feedback instead of reloading externally changed DAC values.
The current regression includes nine feedback cases in each of two row-count/
DAC-encoding configurations, five existing properties, and the 11-write
historical-stimulus comparison. All 24 cases pass under GHDL 6.0.0 / cocotb
2.0.1, including the AXI RAM/debug addition. The quarter-code case failed on the baseline;
the retained-feedback expectation is two codes over eight visits, and 1/64-code
corrections first move on visit 33. Width coverage includes one-wrap recovery
of +/-8500.25 to +/-6500.25 and the fractional-bit-23 test.
PidResults is retained for debugging, with possible later deletion/reuse
recorded in the design note and beside its RAM instance.
`sq1FbFull` now uses `surf.AxiDualPortRam` at `0x7000 + 8*row`, with a
38-bit signed Q15.23 value and bit-38 validity. The Python driver exposes both
fields and per-row status links. The fixed PID-debug v2 frame adds the
post-wrap/clamp, pre-rounding `sq1FbFull` word (96 bytes total). Existing FSM
cycles carry it; the live and file decoders retain compatibility with 88-byte
v1 frames. Other stream formats remain v1. Host writes and both halves of AXI
readback, validity/clear/mask behavior, and real debug FIFO output were checked
at both row-count extremes. All 16 format/receiver tests and six existing
cosim-check tests pass; full PyRogue tree construction and hardware were not
available locally. See the design note for the reproducible commands and
validation details.
Vivado 2024.1 synthesis/timing and system performance are not established by
these unit checks. In particular, the historical cosim lock/deadband results
below predate fractional carry and must not be treated as its validation.

> This effort has grown well beyond the original layered-verification plan. It
> now spans (1) a real RTL bug fix in integer `AdcDsp`, (2) a model-free
> bit-exact cocotb bench that caught it, (3) **two** operations-software
> regression fixes carried on the `ops-fixes` branch, and (4) a SQUID wafer-model
> refinement to make the closed-loop cosim lockable. Read the "Current state"
> block first; the dated sections below are newest-first history.

## Current state at a glance (2026-09-16)

**DONE**
- **Layer 1 integer re-qual — re-opened by review, then two MORE regressions
  fixed.** The whole-path bit-exact bench caught the first bug (`eb14424`, stale
  per-row PID state), but a code review (`REVIEW.md`) showed the 9-write golden
  *under-constrained* the compare (constant feedback DAC + small errors only) and
  produced two GHDL counterexamples. Both independently re-verified against the
  frozen pre-split reference and now **fixed + covered** (see 2026-09-16 section):
  1. **Feedback captured one row too early** — `AdcAccumulator` latched `sq1FbDac`
     at `rowStrobe` (before the FastDacDriver drives the new row), coupling each
     row's writeback to its predecessor. Fixed: capture moved to `firstSample`.
  2. **18-bit overflow wrapped instead of saturating** — `AdcDsp:617` sliced the
     low 18 bits of the 32-bit accumError (a +249000 sum → −13144, sign reversed).
     Fixed: saturating `resize` (clamp ±131071); the shared accumulator keeps the
     full 32-bit sum because the FP DSP needs it.
  Bench extended (per-visit DAC + overflow vectors); demonstrated fail on unfixed
  RTL → pass after fix. Compare passes 11/11, property bench green.
  **These two were the leading explanation for the non-independent-row lock
  failures** — feedback coupling directly produces correlated per-row error and
  initial-condition sensitivity — and cosim confirmed it (below).
- **Closed-loop lock CONFIRMED in cosim (rebuilt with the fixed RTL).** Row
  symmetry restored (all 8 rows identical at P=0), and with the correct-sign
  hardware coefficient (raw P=−0.0006) all 8 rows converge-and-hold (`FluxJumps=0`)
  — the first clean lock. The prior "flat / diverging" gains were a wrong-sign
  artifact (positive *normalized* P → wrong raw sign). See the 2026-09-16 section.
- **Layer 2 step-response (centerpiece) DONE (integer path).** Per-visit PID-debug
  capture shows a +60 µA `TesBias` step → `accumError` −18620 → one-visit recovery
  to the deadband, `FluxJumps=0`. En route, fixed a **third bug** (`50f96cb`): the
  PID-debug frame decoders still assumed the pre-split 80-byte body, so every
  integer PID-debug frame failed to decode (broke the documented cosim PID capture).
  Float-path step-response still owed.
- **Cosim infra (Layer 2) — UP.** Integer-path `GroupTb` + `warmTdmServer --sim`
  + VirtualClient/`ops.Session` client connect and drive registers end-to-end
  (Vivado 2025.1 + VCS X-2025.06). Both PID datapaths elaborate via
  `USE_FLOAT_PID_G` (commit `b75e586`).
- **Two operations-software regressions — FIXED + merged.** The `263296e`
  mask-based enabled-set refactor had broken the operations `Session` over
  VirtualClient (and thus the documented cosim verify scripts). Both fixed on the
  `ops-fixes` branch (worktree `warm-tdm-cleanup`), pushed to origin, merged into
  `channelization` (`164d246`→merge `d79792a`; `5549d4c`→merge `bae0aa2`). See
  the evening section for details.
- **PID-lock root cause (model) — FOUND + FIXED (uncommitted).** The ideal RSJ
  V–Φ model is steepest at its minima, so the (real-hardware-fit) tune point sat
  on an ungovernable near-vertical slope. Fixed with the `SQUID_SINUSOID_BLEND_C`
  sinusoid blend; the no-variation integer sim is **built with the blend and
  tuned** (SaBias 55 / SaFb 9.03, Sq1Bias 50 / Sq1Fb 8.48, FAS on 150 µA / Ic
  100 µA). A live V–Φ sweep confirms 8.48 µA sits on a **steep monotonic slope**
  (≈ −0.044 V/µA between 7 and 9 µA) — a lock is physically possible.
- **"Constant −93000 accumError" mystery — ROOT-CAUSED (operator error, not RTL).**
  With PID off the muxed `accumError` read a constant −93000/row; suspicion fell
  on the new `AdcAccumulator`/`AdcBaselines`. Trace cleared it: `AdcBaselines` RAM
  reads all-zero, the accumulator is a clean `Σ signed(adcData(15:2))`, and
  `WaveformCapture` (which feeds `SaOutAdc`) and `AdcAccumulator` tap the **same**
  `selectedAdcStreams` (`DataPath.vhd:519`/`:541`). The real cause: the SA was
  never nulled — the null call was `saOffset()` (a no-op) instead of the Session's
  `sa_offset()`. `SaOutAdc` sat at −0.0454 V (= −372/sample × 250 = −93000). After
  a real `sess.sa_offset()`: `SaOutAdc → +0.001 V`, `accumError −93000 → +3500`
  (just the null residual). **AdcBaselines is innocent.**

**IN FLIGHT**
- **Closed-loop integer PID lock — PARTIAL (most rows lock, a few don't).** Three
  findings turned this around; details in the night section:
  1. **P is the stabilizing knob, not I.** The RTL adds pidResult to sq1Fb every
     visit (`sq1Fb += P·error`, `AdcDsp.vhd:761`) → "P" is a single integrator
     that nulls the error. **I-only is a double integrator** (`sumAccum += error`
     *and* `sq1Fb += I·sumAccum`) and oscillates at any gain/sign — every I-only
     sweep was structurally doomed. On the descending slope the stable P sign is
     **positive**. (The one-visit mux delay is by-design, not the problem — it
     just bounds the max stable gain.)
  2. **Operating point must be mid-slope** (user-confirmed). The steep, linear SQ1
     zero-crossing is ~7 µA (≈ Φ0/4 of the 10 µA period); the fitted **8.48 µA**
     (≈0.85 Φ0) drifting toward the extremum would not lock at any gain. Seeding
     ~7 µA is what let P lock.
  3. **`FluxQuantum` must be set to Φ0 by the setup scripts** (user-confirmed) —
     it defaults to **0 µA** (flux-jump wrap disabled). Now set to 10 µA.
  With mid-slope + FluxQuantum=Φ0 + sample_num=20 + **P=+0.05**, rows 0–4 lock to
  ≈±1000 counts (≈±0.006 V, ADC quant floor), but **high rows (5–7) still swing**
  and sometimes pin at a uniform value (e.g. all = 4420/8800) — a sign they aren't
  converging independently (row 6 is an outlier even with PID off). Run-to-run
  variance is high; the lock is not yet robust. Process captured in
  `software/scripts/hwtest/cosim_pid_lock.py`.
  Next: chase the high-row non-convergence (row visitation / RowReadoutOrder for
  rows 5–7; the row-6 offset), reduce run-to-run variance, tune P finer.
- **Code TODOs surfaced (not yet done):** `setup_mux` (or the tune-point setup)
  must set `FluxQuantum = Φ0`; `SetSimSq1TunePoint` should seed the SQ1 operating
  point at mid-slope (default 7.37 µA is fine; the 8.48 µA fit was off-slope).

**OWED (not started / blocked)**
- Layer 2 closed-loop **step-response** (the centerpiece), integer then float —
  gated on the lock converging first.
- Layer 1 **FP `AdcDspFp` unit bench** under VCS — blocked by `cocotb_test` 2.0.1
  (no VHDL/VCS-MX backend). FP validated via cosim instead until harness reworked.
- Layer 3 **synthesis** (Vivado 2024.1) of the fixed RTL: timing + utilization;
  confirm FP IP synthesizes under 2024.1.

**Uncommitted on `channelization` right now** (the two-regression fix + coverage)
- `firmware/common/warm_tdm/rtl/AdcAccumulator.vhd` — feedback capture moved
  `rowStrobe` → `firstSample` (finding 1).
- `firmware/common/warm_tdm/rtl/AdcDsp.vhd` — saturating `resize` of accumError at
  the 32→18-bit load (finding 2).
- `tests/warm_tdm/adc_dsp/_pid_bitexact.py` — per-visit `sq1fb_dac` + overflow
  visits in the shared stimulus.
- `tests/warm_tdm/adc_dsp/golden_refs/presplit_dac_writes.json` — regenerated
  golden (11 writes) from the pre-split RTL under the extended stimulus.
- `docs/plans/pid-cosim-verification/PROGRESS.md` — this update.
- (NOTE: the WaferSimPkg sinusoid blend, `_Group.py` SaFb seed, squid-vphi-shaping
  README, and cosim-tuning-settings.md that a prior revision listed here as
  "uncommitted" were committed in `94215d6`; that note was stale.)

## 2026-09-16 — review found two more integer-path regressions; both fixed + covered

A code review (`docs/plans/pid-cosim-verification/REVIEW.md`, against HEAD
`94215d6`) produced two GHDL counterexamples proving the 9-write bit-exact golden
did **not** establish general equivalence to the pre-split DSP. Both were
independently re-verified here against the current RTL and the frozen pre-split
reference, then fixed, with regression coverage that fails on the unfixed RTL and
passes after the fix.

### Finding 1 — feedback captured one row too early (FIXED)
`AdcAccumulator.vhd` latched `sq1FbDac` in `IDLE_S` at `rowStrobe` — the edge that
re-points the row select, before `FastDacDriver` drives the new row's DAC value.
The pre-split DSP read feedback in `PREP_PID_S`, after accumulation
(`presplit_rtl/AdcDsp.vhd:692`), when the DAC has settled. Net: each row's
writeback used the **previous** row's feedback → rows coupled by visit order. This
is the leading explanation for correlated per-row error and initial-condition
sensitivity in the lock work.
Fix: move the `sq1FbDac` capture to the `firstSample` transition (leaving the
`seqStart`/`daqReadoutStart`/reset at `rowStrobe`). The feedback enters `AdcDsp`
solely via `accumIn.sq1FbDac`, so the accumulator-side move fully addresses it.

### Finding 2 — 18-bit overflow wrapped instead of saturating (FIXED)
`AdcDsp.vhd:617` sliced the low 18 bits of the 32-bit `accumIn.accumError` and
reinterpreted them as signed — a modulo wrap (+249000 → −13144, sign reversed).
The pre-split path accumulated into `sfixed(17:0)` whose `resize` saturates.
Fix: `v.accumError := resize(to_sfixed(accumIn.accumError, 31, 0), v.accumError)`
(saturates to ±131071). **Contract = final-sum saturation**, applied in the
integer `AdcDsp` consumer — NOT in the shared `AdcAccumulator`, which must keep the
full 32-bit sum for the FP DSP (`AdcDspFp.vhd:654` feeds it losslessly to Int2Fp).
Final vs pre-split's per-sample saturation is bit-exact for all physically
realizable inputs: within one row window `(adc−baseline)` holds a constant sign so
the running sum is monotonic and cannot rail-then-reverse. Only adversarial
mid-window sign flips (which a settled row never produces) would differ.

### Coverage — the bench now bites (fail → pass demonstrated)
The shared stimulus (`_pid_bitexact.py`) held `sq1fb_dac=0x2000` constant and drove
only small errors, so it saw neither bug. Extended:
- per-visit `sq1fb_dac` on `RowVisit`, driven one clock **after** `rowStrobe`
  (modelling `FastDacDriver`) with distinct values per visit → exposes finding 1;
- two overflow visits (`adc_code=±1000 × num_samples=250` → ±249000, straddling the
  ±131071 rails) → exposes finding 2.
Regenerated the golden from the pre-split RTL (11 writes). On the **unfixed**
current RTL the compare FAILED on all 11 (Group A base-DAC lag; Group B landed
mid-range `(0,12658)`/`(1,4962)` instead of the saturated rails `(0,0)`/`(1,16383)`).
After both fixes: compare **passes 11/11**, property bench green (GHDL 1.0.0).

### Cosim (system level) — row symmetry RESTORED, clean lock achieved, PI gains tuned
Rebuilt the integer no-variation cosim with the fixed RTL
(`USE_FLOAT_PID=0 VARIATION_SEED=0 make vcs`, Vivado 2025.1 + VCS X-2025.06),
re-ran `SetCosimTunePoints` + a PID-enabled run, polling per-row `AccumError`
**live** (stopped-state reads are stale — REVIEW.md).
- **The coupling fix works end-to-end.** With the DSP enabled at **P=0**
  (telemetry, no writeback) and Sq1Fb held, **all 8 rows read an identical settled
  error (8820)**. With `VARIATION_SEED=0` (identical plants) that is exactly
  correct. The pre-fix asymmetry (`[2780,4280,3020,1200,2900,2900,2900,2900]` —
  rows 0–3 distinct, 4–7 sharing a stale value) is **gone**: it was the
  feedback-capture coupling, now fixed. This is the system-level confirmation of
  finding 1.
- **CLEAN CLOSED-LOOP LOCK ACHIEVED (P-only, correct sign).** The blocker was the
  gain SIGN, not the plant. `set_pid` writes *normalized* gains (raw = norm/N); the
  earlier sweeps used *positive* normalized P, i.e. the wrong raw sign (hence
  +0.05 diverging = positive feedback, and small values crawling so slowly they
  read "flat"). The hardware coefficient is **raw P = −0.0006** (norm −0.012 at
  N=20; confirmed `P_CoefRaw = −0.0006`). With it, a single row's trajectory
  converges and holds: `AccumError 1720→800`, `Sq1Fb 7.00→6.73 µA` (feedback
  moves — not stationary), then steady. **All 8 rows lock** (AccumError ~840–1560,
  distinct feedbacks, `FluxJumps=0`) — no shared-stale-value pathology. This is the
  first clean converge-and-hold; prior sessions were defeated by the coupling bug +
  wrong sign + contaminated sequential (no re-null) runs.
- **Residual ~800–1500 counts is a P-only actuator deadband** (the reviewer's
  prediction): correction ≈ 0.5/|P_raw| counts rounds below one DAC code near null.
- **PI GAINS TUNED — the I term works (first time).** With a clean per-point
  protocol (clear PID state + re-seed Sq1Fb=7 + null-once; **raw** coefficients),
  swept P then I. P-only: residual ≈ 0.5/|P_raw|, all P stable (no oscillation up to
  raw −0.0024). Adding a small I closes the deadband: at raw P=−0.0006,
  **I=−2e-5 (raw)** converges cleanly and monotonically to ~120 counts (~0.7 mV),
  no limit cycle, SumAccum bounded, FluxJumps=0; I=−3e-5 begins a quantization
  limit-cycle. **Recommended raw P=−0.0006, I=−2e-5, D=0.** The prior "I never
  works" was windup from un-cleared state + wrong sign — the earlier quick-I test
  that "drifted" reused carried-over integrator state between phases. Full table in
  `cosim-tuning-settings.md`.
- **Measurement gotchas found (for a reproducible harness — experiment #3):**
  writing the per-row `Sq1FbCurrent` RAM *while running* races the sequencer and
  fails verify ("override is a stopped-state operation"); set it STOPPED, then run.
  And a fresh `StartRun` + short (~2 s) settle does NOT refresh all 8 rows'
  `AccumError` (many read 0 or half-settled) — a trustworthy error-vs-Sq1Fb curve
  needs a fixed-visit-count capture with adequate settle, not wall-clock snapshots.

### Live cosim state (left running for continued lock work)
Integer no-variation build (fixed RTL) is up: `./simv` (bridges 10000/11000/20000/
21000) + `warmTdmServer --sim --columnBoards 1 --rowBoards 1 --rowAddrBits 5
--maxRows 32` (Rogue 9099). Fixture seeded via `SetCosimTunePoints`. Tear down with
the usual kill (server → simv) if not continuing.

### Layer 2 step-response (centerpiece) — DONE for the integer path
Captured a `TesBias` step-response at **per-visit resolution** via the PID-debug
stream (`take_data` → `StreamData.pid[col][row]`), the PLAN's intended method.
With the tuned gains (raw P=−0.0006, I=−2e-5) locked, a +60 µA `TesBias` step on
col 0:
- `accumError` jumps to **−18620** on the first captured row-0 visit, then recovers
  to **+60** (the deadband) on the **next** visit — near-deadbeat — as `sq1FbStart`
  moves 8569→8580 (+11 codes); holds there. `numFluxJumps=0` (no relock). The step
  is also bidirectionally stable (register-poll step-up + step-back stayed locked).
- Register-polling can only confirm "stays locked" (the servo recovers within one
  ~1 s poll); the per-visit debug stream is what resolves the excursion/recovery.

**Third bug found + fixed en route (SW): PID-debug frame decode was broken on
`channelization`.** The accumulator split removed the AdcDsp body "word 1"
baseline word (baseline moved to AdcAccumulator), making the integer PID-debug
body 72 B / 9 words, but the Python decoders still assumed 80 B / 10 words — so
every 88-byte frame failed (`StreamData.pid` empty/raising; `PidDebugger` rejecting
all frames on a 96-vs-88 size check). Fixed in `50f96cb`: `PID_DEBUG_TYPE` and
`PID_DEBUG_FIELDS` (`_DataFormats.py`), the live `_PidDebugger.py` register-map
offsets (shift accumError+ down one word), and a `streamreader.py` guard that skips
boundary-fragment frames instead of aborting the file. Validated: decoded streams
now show monotonic `readoutCount` and correct `numSamples`. This had broken the
documented cosim PID capture (verify_cosim_readout PID checks) — undetected since
the cosim scripts weren't re-run after the split/frame-header refactors.
- Capture caveat: the per-visit debug stream is FIFO-throttled at the fast row
  rate, so a `take_data` window yields a short contiguous burst (~9 sequences) — a
  snapshot spanning the step, not every visit. Enough to see excursion→recovery.

### Flux-jump exercise (integer path)
- **RTL flux-jump logic QUALIFIED model-free (`888762f`).** Added three AdcDsp
  cocotb property tests that seed the feedback at the ±7862 rail and push it over:
  positive rail wraps down one `FluxQuantum` and `numFluxJumps=+1`; negative rail
  wraps up and `-1`; repeated crossings accumulate the per-row count. Exact wrapped
  `sq1Fb` readback asserted. Fills the gap left by the bit-exact/property benches
  (which never reached the rail). TESTS=8 PASS=8 under GHDL.
- **Cosim TES-ramp flux-jump demo — BLOCKED by the synthetic model (characterized).**
  A TES-bias ramp runs and the servo tracks/stays locked (`FluxJumps=0`), but can't
  reach the rail: the ±7862 threshold is ~138 µA of SQ1 feedback from the 7 µA
  operating point, and the TES→SQ1 coupling is tiny (~0.024 µA_fb/µA_TES even at
  `TES_CURRENT_SCALE=1000`). Pushing coupling to ~1:1 (`TES_CURRENT_SCALE≈40000`,
  the new GroupTb env generic `18c797b`) reaches the rail regime but amplifies a
  small TES-bias baseline offset enough to break the base lock at TesBias=0;
  seeding the operating point near the rail doesn't lock cleanly (model not cleanly
  periodic that far up). A clean cosim demo needs model surgery (zero the TES-bias
  baseline offset; and/or make the model periodic near the rail). Deferred — the
  RTL flux-jump path is already qualified by the unit bench above.

### Float path (AdcDspFp) — couldn't lock; root-caused + FIXED (`f6f1e55`)
Switched the cosim to the FP build (`USE_FLOAT_PID=1` rebuild + `warmTdmServer
--floatPid`; `VirtualAdcDspFp` confirmed). Findings:
- **FP PID-debug decoder is correct** (5 body words = 40 bytes, matches the RTL —
  no skew like the integer path had). FP captures decode.
- **`set_pid` is broken for FP** (requires `PidD_Gain`, which the PI-only FP group
  lacks → early return). Worked around by setting `AdcDspFp.P_Coef`/`I_Coef`
  (float) directly. (Real bug; REVIEW follow-on — fix set_pid to only require the
  gains present.)
- **FP couldn't lock — root cause (RTL): `AdcDspFp` cleared `sq1FbFull` to 0 at
  StartRun and never used `accumIn.sq1FbDac`,** so the servo started from feedback
  0 = SQ1 V–Φ extremum (ungovernable), not the tuned 7 µA. Confirmed: FP feedback
  slid 7→0→−4.7 µA and diverged. (Exactly the REVIEW-flagged concern.)
- **Fixed (`f6f1e55`):** on each row's first post-clear visit, seed `sq1FbFull`
  from `convOffsetBin(accumIn.sq1FbDac)` via Int2Fp (new `SEED_CONVERT_S` state),
  using a NaN sentinel in the SQ1FB_FULL RAM to mark "unseeded". Rebuilt + verified
  in cosim: `Sq1FbFull` seeds to 377 codes (=7 µA) and **the FP servo locks**
  (mean|error| ~60–700, stable across a P sweep) where it diverged before.
- FP tuning notes: stable P sign is **positive** (raw `P_Coef≈+1e-4`; opposite the
  integer path — float datapath sign differs); residual is lowest near P=0 because
  the seed already lands on the null. A benign `FluxJumps=1/row` appears at the
  7 µA seed — the FP wrap centers the DAC near zero (DAC reads 7−Φ0≈−3 µA while the
  internal full-feedback is correctly 7 µA, an equivalent flux point).

### Owed next
- **FP step-response** (now unblocked): capture a `TesBias` step recovery on the
  FP path via the (verified) FP PID-debug stream.
- **Fix `set_pid` for FP** (only require/write the gains that exist) — REVIEW
  follow-on, enables the documented FP tuning interface.
- **(Optional) tidy the FP seed wrap:** seed `sq1FbFull` already wrapped to
  ±Φ0/2 so the 7 µA seed doesn't register a startup flux jump (cosmetic).
- **(Optional) cosim flux-jump demo:** requires zeroing the model's TES-bias
  baseline offset so a high `TES_CURRENT_SCALE` is usable, then a fine TES ramp
  from the operating point through the rail.
- NOTE: the cosim sim is currently stopped; resuming needs a `make vcs` rebuild
  (use default `TES_CURRENT_SCALE`=1 for normal work).
- **(Optional) shrink the P-only residual deadband** — reviewer experiment #5
  (measure per-row plant slope g, pick P from `z≈1+gP`), rather than a bolt-on I
  (which drifted in the quick test). Not blocking the step-response.
- **Layer 3 synthesis** (Vivado 2024.1) of the fixed RTL; confirm FP IP synthesizes.
- Software follow-ons from REVIEW.md (unchanged list above).
- Software follow-ons from REVIEW.md still owed (see PLAN out-of-scope list):
  `Session.set_pid` PidD_Gain requirement for FP; FP `Sq1FbFull` not seeded from
  `accumIn.sq1FbDac`; `SetCosimTunePoints` stale fixture (FAS 163 µA on a 300 µA
  period); `cosim_pid_lock.py` fixture/visit-count robustness.

## 2026-09-15 (night, latest) — sinusoid sim tuned; −93000 mystery root-caused; lock partial

The sinusoid-blend integer sim is built (VARIATION_SEED=0, USE_FLOAT_PID=0, FAS
Ic=100 µA) and running with `warmTdmServer --sim` (1 col + 1 row board, 32 rows,
Rogue on 9099). Chasing the first closed-loop lock.

### DONE — the "constant −93000 accumError" was an un-nulled SA, not `AdcBaselines`
With PID off, the muxed per-row `accumError` read a constant −93000. The new
`AdcAccumulator`/`AdcBaselines` module was suspected. **Traced and cleared:**
- `AdcBaselines` RAM reads **all zero** (live read of `DataPath.AdcAccumulator[0].
  AdcBaselines`); the accumulator is a clean `Σ (signed(adcData(15:2)) −
  signed(baseline(15:2)))` (`AdcAccumulator.vhd:136-141`) — exactly the
  bit-exact-verified math.
- `WaveformCapture` (source of `Group.SaOutAdc` via `AdcAverage`) and every
  `AdcAccumulator` tap the **same** `selectedAdcStreams` (`DataPath.vhd:519` and
  `:541`). So nulling `SaOutAdc` *does* zero the accumulated stream.
- Actual cause: the SA was **never nulled**. The null was called as `saOffset()`
  (nonexistent on Session → silent no-op) instead of `sess.sa_offset()`.
  `SaOutAdc` sat at −0.0454 V; −0.0454 V ↔ −372/sample, × SampleCount 250 =
  −93000. After a real `sess.sa_offset()`: `SaOutAdc → +0.001 V` and per-row
  `accumError → +3500` (the residual the null leaves), row 6 an outlier at −16750
  (worth a look but not the −93000 issue).

Lesson: `sess.sa_offset()` (Session method) — not `saOffset` — must be run just
before `run_mux()` to zero the muxed baseline; there is no per-row baseline
written (`AdcBaselines` stays 0 by design).

### DONE — mux params + why 20 samples/row helps
`setup_mux(num_pts=400)` → RowPeriodCycles 400 (3.2 µs @ 125 MHz), window cycles
50→300, **SampleCount 250**. Dropping to `sample_num=20` shrinks the per-visit
error ~12×, which stopped the integrator from railing (`SumAccum` went from pinned
at ±131071 to bounded). Recommend `sample_num ≈ 20–32` near the row end.

### DONE — V–Φ slope at the operating point (lock is possible)
Stopped-state sweep of forced `Sq1Fb` vs `SaOutAdc` (col 0):

```
Sq1Fb µA:  2      3      4      5      6      7      8      9     10     11     12     13     14
SaOutAdc: -.051  -.007  +.017  +.025  +.020  +.000  -.039  -.087  -.075  -.092  -.064  -.016  +.013
```

The tune point 8.48 µA is on a steep, monotonic descending slope (7→9 µA,
≈ −0.044 V/µA) — not an extremum. So a lock is physically realizable; the failure
to lock is a control-loop issue, not the operating point.

### DONE — the PID structure: P is the stable knob, I-only is a double integrator
Reading the RTL PID pipeline (`AdcDsp.vhd`) explained why no I-only gain ever
locked:
- Every visit: `sq1Fb := sq1Fb + pidResult` (`:761`) and, with I≠0,
  `sumAccum := sumAccum + accumError` (`:743`), `pidResult += I·sumAccum`.
- So **P** contributes `sq1Fb += P·error` — the *output* integrates the error →
  P alone is a stable single integrator that nulls steady-state error (and with
  I=0 the RTL forces `sumAccum=0`). **I** contributes `sq1Fb += I·ΣΣerror` — a
  **double integrator** (180° phase lag), oscillatory at any gain or sign.
- On the descending V–Φ slope the stable P sign is **positive** (an earlier
  P=−0.1 diverged = positive feedback / wrong sign).

The one-visit mux feedback delay (sq1Fb computed for a row is applied at that
row's next visit) is **by design** — it only bounds the max stable loop gain, it
is not the failure. (Earlier "feedback delay is the problem" framing was wrong.)

### DONE — two setup gaps confirmed with the user
- **Operating point must be MID-SLOPE.** V–Φ sweep: SQ1 period 10 µA, peak ~5 µA,
  min ~10 µA, steep descending zero-crossing ~7.5 µA. The fitted **8.48 µA**
  (≈0.85 Φ0) sits past mid-slope toward the extremum — user expects mid-slope.
  `SetSimSq1TunePoint`'s default seed (7.37 µA) is essentially mid-slope; the
  8.48 µA came from a fit and is off. Seeding ~7 µA is what let P lock.
- **`FluxQuantum` defaults to 0 µA** (flux-jump wrap disabled; `FluxJumps`=0 so
  not the current oscillation, but a latent gap). User: it should be set to Φ0
  **by the setup scripts**. Set to 10 µA for these runs.

### IN FLIGHT — partial lock; high rows don't converge
With SA nulled, mid-slope (~7 µA), `FluxQuantum`=10 µA, `sample_num=20`, P-only:
- **P=+0.02:** mae ~9–13k (too low to hold).
- **P=+0.05 (best):** mae ~2.5k; rows 0–4 lock to ≈±1000 counts (≈±0.006 V, the
  ADC quant floor). **Rows 5–7 keep swinging** and sometimes pin at a uniform
  value (all = 4420, or 8800) — they are not converging independently (row 6 was
  an outlier at −16750 even with PID off).
- **P=+0.10:** mae ~5–6k (worse — past the stability edge).
Run-to-run variance is high (same P=0.05 gave mae 22→2.5k one run, 2k→16k the
next), so the lock is real but not robust.

Repeatable process saved as `software/scripts/hwtest/cosim_pid_lock.py`
(seed mid-slope → set FluxQuantum=Φ0 → `sa_offset` → `setup_mux` → `set_pid` →
`run_mux` → poll per-row `AccumError`; CLI args for gains / operating point).

**Next diagnostics:** (a) why do rows 5–7 share an identical `AccumError` and not
servo — check `RowReadoutOrder` / row visitation / per-row FAS gating for the high
rows; (b) chase the row-6 offset; (c) reduce run-to-run variance (settle time,
window placement); (d) once robust, fold FluxQuantum=Φ0 into `setup_mux` and land
the SQ1 tune seed at mid-slope in `SetSimSq1TunePoint`.

## 2026-09-15 (evening) — ops-fixes regressions resolved; PID-lock root cause + SQUID model fix

### DONE — two operations-software regressions fixed on `ops-fixes`, merged
Bringing up the integer cosim exposed two regressions from the `263296e`
mask-based enabled-set refactor that broke the operations `Session` over
VirtualClient — and therefore the documented cosim verify scripts
(`verify_cosim_readout.py`, `verify_cosim_tuning.py`, …) that build the Session
that way. Both fixed on the `ops-fixes` branch (worktree `warm-tdm-cleanup`,
`branch ops-fixes`, up to date with `origin/ops-fixes`), then merged into
`channelization`:

1. **VirtualClient-safe topology reads** — commit `164d246` ("sw: make
   operations Session column-enable/topology reads VirtualClient-safe"). `setup_mux`
   was raising `AttributeError` on `colEnableBools`; now reads column-enable /
   `NumColumns` topology through VirtualClient-safe accessors
   (`col_enable_bools` / `NumColumns`). Touches `software/python/warm_tdm_api/
   _Group.py`, `operations/session/_core.py`, `operations/session/_setup.py`,
   `tuning/_ramp.py`. Merged via `d79792a`.
2. **FastDacVariable per-column gating** — commit `5549d4c` ("sw: fix
   FastDacVariable per-column gating to decode the ColEnableMask bitmask"). The
   gating indexed the scalar `ColEnableMask` bitmask instead of decoding it,
   raising `TypeError: 'int' object is not subscriptable` in
   `SetCosimTunePoints` / `SetSimSaTunePoint`; now decodes via `_colEnabled`.
   Touches `software/python/warm_tdm_api/_GroupVariables.py`. Merged via `bae0aa2`.

Net: the "operations `Session` broken over VirtualClient" BLOCKER from the
afternoon section is closed. `Group.SetCosimTunePoints()` (server-side command
that seeds a tune point and runs saOffset — "converged after 5 loops") now runs.

### DONE — PID-lock root cause (ideal V–Φ steepest at its minima)
With the ideal SQUID model the servo would **not** lock — it railed / oscillated
/ wound up regardless of gain magnitude or sign. Root cause (confirmed with the
model owner): the ideal RSJ V–Φ in `WaferSimPkg.idealSquidVoltage`
(`ic = criticalCurrentAmp·|cos(π·phase)|`, `vOut = Rn·√(iBias²−ic²)`) is steepest
at its **minima** (near-vertical tangent, flat rounded maxima). The tune point is
fit against real, sinusoidal hardware curves, so it lands the *model* on that
ungovernable steep region — enormous, strongly nonlinear local loop gain
(`SumAccum` saturating, error swinging full-scale, `sq1Fb` railing). Re-tuning
doesn't help; it just re-finds the same steep-near-minimum spot.

Two related findings confirmed:
- Use **normalized** PID gains: `sess.set_pid()` (`PidP/I/D_Gain`), which are
  sample-count-normalized — **not** the raw `P_Coef`. The raw-vs-normalized
  distinction matters for reproducing hardware behavior.
- The correct **raw P sign is negative** (≈ `−0.0006` on hardware).

### IN FLIGHT — SQUID V–Φ model fix (UNCOMMITTED)
Implemented a fundamental-harmonic "sinusoid blend" in `idealSquidVoltage`, gated
by a single package constant `SQUID_SINUSOID_BLEND_C` (in `WaferSimPkg.vhd`,
default `1.0` = pure sinusoid with the same min/max envelope; `0.0` = old ideal,
bit-identical). It rounds the ideal cusp and moves the steep region to mid-slope,
so the real-hardware tune point + gain (incl. the `≈ −0.0006` raw P sign) should
transfer and the loop can lock. Rationale, the single-constant-vs-record-field
choice, and alternatives (option 2 Gaussian flux-smear `σΦ`; option 3 cusp-round
softened radical `δ`; option 4 physical `βL`/thermal) are written up in
`docs/design/squid-vphi-shaping/README.md` (new, uncommitted).

### DONE — VARIATION_SEED env→generic wiring (committed `580165b`)
Wired a `VARIATION_SEED` env var → `GroupTb` generic through
`firmware/simulations/GroupTb/ruckus.tcl`, so `VARIATION_SEED=0` builds an
all-channels-identical sim (removes per-device operating-point spread while
chasing the first lock). Committed as `580165b` ("Set variation seed to zero for
pid testing").

### NEXT (in flight, this session)
1. Rebuild the no-variation integer sim with `SQUID_SINUSOID_BLEND_C=1.0`
   (`VARIATION_SEED=0 USE_FLOAT_PID=0 make vcs` in `firmware/simulations/GroupTb`).
2. Re-run tuning starting with SA tune (`sess.sa_tune` with a modest sweep-point
   count — the sim is slow), aiming for a real closed-loop integer-path PID lock
   (error → ~0).
3. Repeat for the float path (`USE_FLOAT_PID=1`).
4. Closed-loop **step-response** (Layer 2 centerpiece): `TesBias` step, observe
   `sq1Fb` recover the error; capture + analyze via the tagged-header reader.
5. Layer 3 synthesis (Vivado 2024.1) of the fixed RTL.

### How to resume the cosim (exact recipe)
Toolchain / env:
- **SIM** = Vivado **2025.1** + VCS **X-2025.06**. Source both directly (do NOT
  pipe): `source /sdf/group/faders/tools/xilinx/2025.1/Vivado/2025.1/settings64.sh`
  and `source /sdf/group/faders/tools/synopsys/vcs/X-2025.06/settings.sh`.
- **Synthesis** = Vivado **2024.1** (2025.1 has the hold-time bug).
- conda env **`warm-tdm-r615`** for the software / client side.

Bring-up sequence (integer no-variation build):
1. In `firmware/simulations/GroupTb`: `VARIATION_SEED=0 USE_FLOAT_PID=0 make vcs`
   (float path = `USE_FLOAT_PID=1`).
2. `behav/sim_vcs_mx.sh` to build `simv`, then run `./simv` (free-running; TCP
   bridges on 10000/11000/20000/21000).
3. `warmTdmServer.py --sim --columnBoards 1 --rowBoards 1 --rowAddrBits 5
   --maxRows 32` (Rogue on 9099).
4. Connect a `VirtualClient` + `ops.Session(client.root.Group)` client.
5. `Group.SetCosimTunePoints()` (server-side: seeds a tune point + runs saOffset,
   "converged after 5 loops"), then `sess.set_pid(...)` (normalized gains) and
   `sess.sa_tune(...)`.


> **NOTE (superseded blocker):** the "operations `Session` broken over
> VirtualClient" BLOCKER described in this section is **RESOLVED** — see the
> evening section above (two fixes on `ops-fixes`, merged into `channelization`).
> The cosim infra + integer/float elaboration status here still stands.


### Done — whole-path bit-exact re-qualification (integer path)
Built the two-bench model-free re-qualification and it did its job — proved the
accumulation move bit-exact AND caught a real per-row PID-state bug.
- **Capture bench** (`test_AdcDsp_bitexact_capture.py`, commit `d45303f`): drives
  the pre-split `AdcDsp` snapshot (`golden_refs/presplit_rtl/`, commit `5645f7e`)
  with a scripted raw-ADC + timing stimulus; records its mAxil SQ1-FB-DAC writes
  as the golden (`presplit_dac_writes.json`, 9 writes / 3 rows × 3 visits).
- **Compare bench** (`test_AdcDsp_bitexact_compare.py`, commit `bf4d5d9`): replays
  the identical stimulus into the current `AdcAccumulator`+`AdcDsp`
  (`AdcDspAccumCompareWrapper`) and asserts the mAxil writes match bit-for-bit.
- Shared driver `_pid_bitexact.py`: one deterministic stimulus (single source of
  truth) + mAxil write monitor + dormant `read_state()`/`collect_diag` diagnostic
  hook (per-visit PID-state register dump) for future divergence localization.
- Sim enablers: `AdcAccumulator` gained `SIMULATION_G` (commit `9788c6f`, default
  false) to infer its baseline RAM under GHDL, mirroring `AdcDsp`.

### Bug found + fixed (commit `eb14424`)
`accumError` matched every visit (accumulation move IS bit-exact), but the
current integer `AdcDsp` read STALE per-row state: `lastAccumError`/`sumAccum`
came from the previous *visit* (any row), not the current row — cross-
contaminating the I-term integrator and D-term. Root cause: post-split, `AdcDsp`
learns the row only at `accumValid` (`accumIn.logicalRow`), then reads its
`READ_LATENCY_G=3` per-row state RAMs at `PREP_PID_S` only ~2 cycles later —
insufficient setup. Fix: drive `pidStateRamAddr` from `accumIn.logicalRow` at
`accumValid` + add a `PREP_WAIT_S` hold state (mirrors how `AdcDspFp` already
gates its RAM read on `WAIT_INT2FP_S waitCount=3`). Compare now passes 9/9;
property bench still green. Latent because the cosim defaulted to the float path.

### Integer fix validated through full-system elaboration
`USE_FLOAT_PID=0 make vcs` + `sim_vcs_mx.sh` on `GroupTb` WITH the `eb14424` fix
builds/elaborates clean under VCS + Vivado 2025.1 ("Ready to simulate", exit 0).
So the fix is sound at unit-bit-exact AND full-system-elaboration levels.

### BLOCKER: FP `AdcDspFp` cocotb bench under VCS is not runnable as documented
`test_AdcDspFp.py` (`WARM_TDM_SIM=vcs`) cannot run with the installed
`cocotb_test` 2.0.1: its `Vcs` backend compiles only `verilog_sources` (no
`vhdlan`/VHDL step) and additionally builds a command list containing a
`PosixPath` (`cocotb_config.lib_name_path`) that `" ".join(cmd)` rejects
(simulator.py:295). There is no `vcs_mx`/`xsim` backend. So the handoff doc's
"AdcDspFp under VCS via WARM_TDM_SIM=vcs" recipe is not achievable without harness
work (switch to `cocotb_tools.runner`, or add a VCS-MX backend). The FP path is
still validatable under VCS via the GroupTb cosim (Vivado export -> VCS-MX, which
handles VHDL and already elaborates the float path).

### Layer 2 cosim: infra UP, integer fix validated through connectivity
Brought up the full integer-path cosim (Vivado 2025.1 + VCS): `./simv` free-runs
with TCP bridges on 10000/11000/20000/21000; `warmTdmServer --sim
--columnBoards 1 --rowBoards 1 --rowAddrBits 5 --maxRows 32` serves Rogue on 9099;
a `VirtualClient` + `ops.Session` client connected, saw 1 column + 1 row board,
and read live registers over the sim link — i.e. the integer RTL WITH the
`eb14424` fix is driveable end-to-end in cosim.

### BLOCKER: operations `Session` (setup_mux/tuning/acquisition) broken over VirtualClient
`sess.setup_mux(...)` raises `AttributeError: GroupRoot.Group has no attribute
colEnableBools`. Root cause: the operations refactor (commit `263296e`, "mask-
based enabled-set interface") made `setup_mux` (and the tuning/acquisition paths)
depend on real `Group`-DEVICE Python members — the `colEnableBools` `@property`,
`self.config` (a plain attr set at device construction, incl. `numColumns`),
`_numCols`, `PidX_Gain` — none of which `VirtualClient`'s `VirtualGroup` mirrors
(it only exposes the Rogue node tree). So `ops.Session(client.root.Group)` cannot
run setup_mux/tuning over VirtualClient, which also breaks the documented cosim
verify scripts (`verify_cosim_readout.py`, `verify_cosim_tuning.py`, …) that
construct the Session exactly that way. Likely undetected because cosim wasn't
re-run against these scripts since `263296e`.

Options to unblock the PID lock smoke: (a) make the operations Session work over
VirtualClient (client-side adapter supplying config/colEnableBools/_numCols from
the Rogue nodes, or refactor setup_mux to use only Rogue nodes) — the right fix,
benefits all cosim scripts; (b) hand-roll the muxed-PID config via raw registers
(large, must also establish a lockable operating point); (c) defer.

### Still owed
- Layer 2: closed-loop cosim step-response, integer + float (blocked above).
- Layer 1 FP unit bench: needs harness rework to run under VCS-MX (or run under
  Questa/Xcelium if ever available), or fold FP coverage into the cosim.
- Layer 3: Vivado 2024.1 synth of the fixed RTL (timing/util; FP IP under 2024.1).

## 2026-09-15 (later) — GroupTb PID-path parameterized; both paths elaborate (Layer 2 gate)

### Done
- **`GroupTb` parameterized for both PID datapaths.** Promoted the hardcoded
  `USE_FLOAT_PID_C := true` to a `USE_FLOAT_PID_G` generic on the `GroupTb`
  entity (default `true`, preserving prior behavior); `ruckus.tcl` sets it on the
  `sim_1` fileset from the `USE_FLOAT_PID` env var, so `make vcs` builds the float
  path and `USE_FLOAT_PID=0 make vcs` builds the integer path — no VHDL edit
  between runs. Mirrors the target `ruckus.tcl` `set_property generic` convention.
  Files: `firmware/simulations/GroupTb/tb/GroupTb.vhd`,
  `firmware/simulations/GroupTb/ruckus.tcl` (uncommitted, pending review).
- **Elaboration gate: PASS (both paths), Vivado 2025.1 + VCS X-2025.06.**
  - Float: `make vcs` export OK; VCS elab command carries
    `-gv USE_FLOAT_PID_G="true"`. Identical to the prior hardcoded default (already
    known-good in cosim), so covered by equivalence.
  - Integer: `USE_FLOAT_PID=0 make vcs` export OK (`-gv USE_FLOAT_PID_G="false"`);
    full `sim_vcs_mx.sh` compile/elaborate/link of `GroupTb` succeeded ("All of 30
    modules done", "Verdi KDB elaboration done", "Ready to simulate", exit 0).
    This exercises the `GEN_FIXED_PID` `DataPath` branch through the full `GroupTb`
    for the first time — the parent-crossbar/port check the plan wanted. The
    `FLT_FMA` static-elaboration assertion *warnings* are benign (FP IP compiled in
    but unused on the integer datapath).

### Also done — Layer 1 integer bench restored to green (commit 6728d92)
Running the integer `AdcDsp` GHDL bench surfaced three surf-update/rename drifts
that had rotted the Issue #90 framework; all fixed:
- `tests/common/regression_utils.py` (warm-tdm shim) lacked `sample_after_tpd`,
  which updated surf `tests/axi/utils.py` now imports via `tests.common.
  regression_utils` — added the timing-sampling trio mirroring surf.
- Both DSP cocotb wrappers still assigned `accumIn.rowIndex`; the logical-row
  rename made it `logicalRow`. Fixed (external `ACCUM_ROW_INDEX` port unchanged).
- surf RAM refactor: `TrueDualPortRam`/`DualPortRam`/`SimpleDualPortRam` now
  pull in `TrueDualPortRamInferred`/`SimpleDualPortRamInferred`; added both to
  the benches' surf allowlists. `make rtl_import` re-run also clears stale
  `base/ram/inferred -> base/ram/rtl` symlink moves in `build/SRC_VHDL`.
Result: `pytest tests/warm_tdm/adc_dsp/test_AdcDsp.py` → 1 passed (5 PID
property checks under GHDL). FP bench collects cleanly (run gated to VCS).

### Next (unchanged priority)
- Layer 1 **bit-exact golden diff** (still owed): drive identical scripted
  stimulus and compare against a captured pre-split (ops-fixes-era) reference.
  Design fork to settle first (see below).
- Layer 2: wire and run the closed-loop cosim step-response, now runnable for
  both PID paths via the new generic (`warmTdmServer --sim`, TesBias step).

### Decision + feasibility (2026-09-15) — whole-path captured golden
Chosen approach (user): **whole-path, captured golden** — resurrect the
pre-split `AdcDsp` once, drive scripted raw-ADC stimulus, capture output vectors
to a checked-in golden; CI drives the new `AdcAccumulator`+`AdcDsp` on identical
stimulus and asserts bit-exact vs golden. Truly model-free (plan's intent).

**Feasibility PROVEN.** Reference commit `5645f7e` ("Clean up delayed timing
paths…", the immediate pre-split, post-PID-clear-fixes state). Its `AdcDsp` +
contemporaneous `TimingPkg`/`WarmTdmPkg`/`FixedPkg` (no `FrameHeaderPkg` yet)
elaborate clean under GHDL 1.0 + *current* surf via `ghdl -i`/`-m`. Only
snapshot-local change needed: add `use ieee.std_logic_unsigned.all;` (old file
left `numeric_std` commented; the original build resolved the `slv`
`pidStateRamAddr + 1` counter increment via the synopsys package — unsigned
semantics, faithful). Spike lived in gitignored `build/presplit_spike/`.

**Design for the two benches (to build):**
- Snapshot the 4 old files into a committed dir (e.g.
  `tests/warm_tdm/adc_dsp/golden_refs/presplit_rtl/`), compiled into a `warm_tdm`
  GHDL lib (so old `AdcDsp`'s `library warm_tdm` refs resolve) — separate pytest
  run / sim_build from the current-RTL bench, so no lib clash.
- Shared deterministic stimulus (raw ADC AXI stream + `LocalTimingType` +
  `sq1FbDac` + AXI-Lite coef/baseline config). Both old `AdcDsp` and new
  `AdcAccumulator` take the SAME raw-ADC+timing interface, so the driver is shared.
- Observable = the `mAxil` SQ1-FB-DAC RAM write master transactions (addr,data) —
  the true PID output, present identically on both old and new `AdcDsp`. Capture
  bench writes golden JSON; compare bench diffs bit-exact.
- Intricate part = replicating the old sample/row-strobe accumulation protocol
  exactly; study old `AdcDsp` adcAxisMaster+timing consumption before writing the
  driver.

### (superseded) Open design question — bit-exact reference capture
The property bench proves PID *behavior*; the plan's Tier-1 claim is *bit-exact*
equivalence of the accumulation-numerics move (old `sfixed` accum inside AdcDsp
-> new `signed(31:0)` accum in AdcAccumulator + PID in AdcDsp). Interfaces differ
across the split (old AdcDsp consumed the raw ADC stream; new AdcDsp consumes
`accumIn : AdcAccumResultType`), so the comparison strategy is not yet fixed:
whole-path (old AdcDsp vs new AdcAccumulator+AdcDsp on identical raw-ADC
stimulus) vs decomposed (AdcAccumulator accum vs old accum; PID stage golden).
Also undecided: which pre-split commit is the reference, and whether the golden
is captured to data files or the old RTL runs live in the bench.

## 2026-09-15 — plan established; Layer 0 largely done

### Done
- **Register cross-check (Layer 0): PASS.** VHDL crossbar/local-register offsets
  vs PyRogue `RemoteVariable` offsets verified by hand for `AdcDsp` (7-master
  crossbar: local 0x00–0x60 + RAMs 0x1000/0x2000/0x3000/0x6000), `AdcDspFp`
  (5-master: PI-only coefs + RAMs 0x1000/0x2000/0x3000/0x4000), and
  `AdcAccumulator` (baseline RAM at 0x000). The accumulator-split offset shifts
  are consistent on both sides, and the baseline RAM is confirmed moved out of
  `AdcDsp` into `AdcAccumulator`. The `sfs-check-registers` parser could not do
  this (blind to the crossbar + `AxiDualPortRam` + local-endpoint pattern; it
  reported 0 VHDL registers and false "python-only" findings).
- **Import smoke (Layer 0): PASS.** `warm_tdm`, `warm_tdm_api`, `.operations`,
  `.tuning`, `.session` import in `warm-tdm-r615`; `AdcDsp`/`AdcDspFp`/
  `AdcAccumulator` device classes load (surf Python on `PYTHONPATH`).
- **Synthesis fix (unblocks Layer 3 elaboration):** added the missing
  `use warm_tdm.WarmTdmPkg.all` to `WarmTdmCommon2.vhd` (commit `f46837a`). Its
  `config : out WarmTdmConfigType` port referenced a `WarmTdmPkg` type with only
  `library warm_tdm;` in scope, failing `ColumnFpgaBoard` synthesis at
  `WarmTdmCommon2.vhd:75`. Pre-existing on `channelization` (present at `bc0ebdb`),
  surfaced on the first `ColumnFpgaBoard` synthesis. Audited: all other
  `WarmTdmConfigType` users already had the use clause.

### Confirmed for the plan
- The sim closes the servo loop physically with a wafer load (SaOut couples to
  TesBias and sq1Fb through the SQUID transfer functions), so the closed-loop
  step-response test (Layer 2) is realizable.
- The 40-vs-80-byte PID-debug frame mismatch that blocked the pre-convergence
  `fp-pid` is resolved on `channelization` by the Issue #82 tagged-header reader
  dispatch.

### Not yet done
- Layer 0: `software/tests/` pytest (pytest missing from `warm-tdm-r615`).
- Layer 1: integer `AdcDsp` GHDL bit-exact regression vs a captured pre-split
  reference; `AdcDspFp` bench under VCS.
- Layer 2: wire and run the closed-loop cosim step-response (integer + float).
- Layer 3: Vivado 2024.1 synthesis of `ColumnFpgaBoard325Coord10G` (timing +
  utilization); confirm the FP IP synthesizes under 2024.1.

### Next
Elaborate `GroupTb` with `USE_FLOAT_PID_G` both true and false (Vivado 2025.1) —
the next gate. Re-run `ColumnFpgaBoard` synthesis to confirm `f46837a` clears the
reported error and to surface any next first-synthesis issue.
