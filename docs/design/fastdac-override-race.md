# FastDacDriver force/override write: the one-shot race

Why writing a force/override DAC value (`Sq1FbForceCurrent`, `SaFbForceCurrent`,
`Sq1BiasForceCurrent`) can silently fail to reach the DAC, why it showed up as
"biases don't zero after MUX" (Issue #32), and what to do about it. Written while
graduating `operations.stop_and_zero` (Issue #83, G2); reconstructed from
`firmware/common/warm_tdm/rtl/FastDacDriver.vhd` and the surf
`AxiDualPortRam`/`SynchronizerFifo` it uses.

> Status (2026-08-14): **analysis + agreed interim fix.** The software reorder
> (below) is committed and is expected to resolve the practical case; it needs
> bench confirmation. The firmware hardening is proposed, not yet implemented.

## The two DAC-value paths

`FastDacDriver` drives 8 fast DACs from a single state machine (`timingRxClk125`
domain). One output register `r.dacOut` has two sources:

1. **MUX path** — per-row values live in a per-channel dual-port RAM
   (`GEN_AXIL_RAM`, addressed by `r.rowIndex`). On each row the FSM walks
   `IDLE_S -> DATA_S -> WRITE_S -> ...`, loading `ramDout` and clocking the DACs
   on the row strobe. This is what runs during a muxed run.

2. **Force/override path** — a separate 8-entry override RAM
   (`U_AxiDualPortRam_OVERRIDE`, `OVERRIDE_AXIL_C`). An AXI write to it drives the
   DAC *without* waiting for a row strobe: `IDLE_S` sees `overrideWrValid`, jumps
   to `OVER_SEL_S -> OVER_WRITE_S -> OVER_WRITE_FALL_S -> OVER_CLK_0_RISE_S`,
   which latches `r.dacOut` and pulses the DAC clock. This is the "manually set
   the DAC" mechanism, and it is reachable whether or not a run is active.

Rogue mapping: `ColumnBoard[*].{SAFb,SQ1Fb,SQ1Bias}.OverrideCurrent` ->
override RAM; the Group `*ForceCurrent` link variables fan out over those.

## The race

`overrideWrValid` is the `valid` output of the override RAM's clock-crossing
`SynchronizerFifo`, instantiated with `rd_en => '1'` (surf
`AxiDualPortRam.vhd`). With read-enable tied high, `valid` asserts for **exactly
one `timingRxClk125` cycle** per queued AXI write.

`FastDacDriver` only *looks* at `overrideWrValid` in `IDLE_S`
(`FastDacDriver.vhd`, `when IDLE_S => ... if (overrideWrValid = '1')`). There is
no latch: if the one-cycle `valid` pulse lands while the FSM is anywhere else in
its sequence, the pulse is gone. The override RAM still holds the new value, but
**nothing re-reads it** — the DAC keeps its previous output.

During a muxed run the FSM is almost never idle (it cycles through
`DATA_S/WRITE_S/CLK_*` every row), so a force write issued while running — or in
the window right after `EndRun` while the last row drains — is likely to be
dropped. That is exactly Issue #32: after `EndRun()`, a `Sq1FbForceCurrent := 0`
appeared not to move the DAC, because the write raced the still-running FSM.

Note `running=0` handling (`CLK_0_RISE_S`) returns the FSM to `IDLE_S` but does
**not** re-latch or re-apply the override value, so leaving MUX does not by
itself repair a dropped force write.

## Interim fix (software, committed)

`operations.stop_and_zero` was reordered: end the run and switch to manual timing
**first**, poll `TimingTx.Running` until it drops (bounded), and only **then**
write the force/bias zeros. Once `Running=0` the FSM parks in `IDLE_S` between
override writes, so each write finds the FSM idle and is serviced. This removes
the practical failure without a firmware rebuild.

Residual risk: it relies on the FSM being idle "long enough" between/after
writes. In practice, once stopped, `IDLE_S` is the resting state and each AXI
write is a separate FIFO entry seen on its own idle cycle, so back-to-back writes
are fine. Still, this is timing-by-construction, not timing-by-guarantee — hence
the firmware hardening below. **Needs bench confirmation** (emulate does not
clock the DAC FSM against live timing).

## Proposed firmware hardening (not yet implemented)

Make an override write robust regardless of FSM state. Options, cheapest first:

1. **Latch a pending-override request.** Add `v.overridePending := '1'` (plus
   captured `dacDb`/`dacNum`) whenever `overrideWrValid` is seen in *any* state,
   and service it from `IDLE_S`. One bit + a small hold register; the FSM already
   funnels through `IDLE_S` between rows, so the request is honored on the next
   idle tick instead of being dropped. Lowest risk.
   - Edge case: coalesce multiple writes to the same channel (last-value-wins)
     and handle writes to different channels (queue depth 8 = one per DAC, or
     accept last-wins per idle visit).

2. **Give the override FIFO real back-pressure.** Drive the RAM's `rd_en` from
   the FSM (read only when about to service) instead of `'1'`, so `valid`
   holds until consumed. Cleaner data-flow but touches the surf instantiation
   contract (rd_en semantics) and the CDC — more invasive.

3. **Re-apply override on running -> idle.** On the `running` falling edge,
   re-drive `r.dacOut` from the last override values. Only fixes the
   leaving-MUX case, not force writes issued mid-run; weakest.

Recommendation: **option 1** (pending-request latch) if/when this is done in
firmware — it directly closes the race with minimal surface area. The same
pattern applies to `RowDacDriver2`'s manual row activate/deactivate override
(`MANUAL_RS_*`), which has the analogous "serviced only from a specific state"
shape and is why row-DAC zeroing in `stop_and_zero` stays commented for now.

## Status / next steps

- [x] Software reorder in `stop_and_zero` (committed, Issue #83 G2).
- [ ] Bench: confirm the reorder reliably zeros column force/bias DACs after a
      real muxed run (swh76's Issue #32 repro is the test).
- [ ] Decide whether to also do the firmware pending-latch (option 1). If yes,
      open a firmware issue and extend the same fix to `RowDacDriver2`, then
      un-comment the row-DAC zeroing in `stop_and_zero`.
