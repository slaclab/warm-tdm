## Fast-DAC force-current drivers and the stop_and_zero safe-baseline routine.
##
## The densest, most self-contained Session cluster: the FastDacDriver override
## one-shot (Issue #86) and its software write-and-verify coordination (Issue
## #32). Relies on TopologyCore state (self.cbs, self.group, self.chans_per_board,
## self.coordinator_cb). Mounted on Session.

import time
import logging

import numpy as np

log = logging.getLogger(__name__)


class ForceDacMixin:
    """Fast-DAC force-current writes (verified) + the stop_and_zero baseline."""

    # Fast-DAC force-current drivers that ride the FastDacDriver override
    # one-shot (Issue #86): Group setter variable -> per-column-board driver
    # device (whose DacCurrentNow reads back the actual driven output).
    _FAST_DAC_FORCE = {
        'Sq1Fb':   ('Sq1FbForceCurrent',   'SQ1Fb'),
        'SaFb':    ('SaFbForceCurrent',    'SAFb'),
        'Sq1Bias': ('Sq1BiasForceCurrent', 'SQ1Bias'),
    }

    def _read_dac_now(self, dev_name):
        """{(board_idx, chan): DacCurrentNow (uA)} for one fast-DAC driver.

        ``DacCurrentNow`` is a LinkVariable computed from the *cached* DacRawNow
        (its ``linkedGet`` reads ``DacRawNow.value()``, not ``.get()``). With
        polling off (e.g. simulation, where the Root sets ``pollEn=False``) or
        between poll ticks that cache is stale, so a naive read reports an old
        value -- which silently defeats the verify loop. Force a fresh read of
        ``DacRawNow`` first so the returned current reflects the live DAC output.
        """
        out = {}
        for idx, cb in sorted(self.cbs.items()):
            dev = getattr(cb, dev_name, None)
            if dev is None or not hasattr(dev, 'DacCurrentNow'):
                continue
            for ch in range(self.chans_per_board):
                try:
                    if hasattr(dev, 'DacRawNow'):
                        dev.DacRawNow[ch].get()   # refresh dependency (live read)
                    out[(idx, ch)] = float(dev.DacCurrentNow[ch].get())
                except Exception:
                    break
        return out

    def _apply_force_verified(self, kind, target_uA, tol_uA=0.5, tries=5,
                              settle_sec=0.1):
        """Write a fast-DAC force current and confirm it reached the DAC output,
        re-issuing on a mismatch (bounded).

        Software coordination for the FastDacDriver override one-shot race
        (Issue #86): the override register is only serviced while the driver FSM
        is in IDLE, so a write issued during the post-EndRun drain can be
        dropped. Once the run is stopped the FSM parks in IDLE (``stageNextRow``
        is gated by ``running`` in the RTL), so a re-issued write is always
        serviced -- this converges, typically in one retry. Reading DacCurrentNow
        back also gives real confirmation the output moved (what Issue #32
        wanted), instead of a blind write.

        ``target_uA`` is a scalar (broadcast to every column) or a per-global-
        column sequence. Returns ``(converged, residual)`` where residual is
        ``{(board, chan): current}`` for channels still off target.
        """
        setter_name, dev_name = self._FAST_DAC_FORCE[kind]
        setter = getattr(self.group, setter_name)
        ncol = len(setter.get())
        target = (np.full(ncol, float(target_uA)) if np.isscalar(target_uA)
                  else np.asarray(target_uA, dtype=float))

        residual = {}
        for _ in range(max(1, tries)):
            setter.set(target.tolist())
            time.sleep(settle_sec)
            residual = {}
            for (idx, ch), val in self._read_dac_now(dev_name).items():
                col = idx * self.chans_per_board + ch
                tgt = target[col] if col < len(target) else 0.0
                if abs(val - tgt) > tol_uA:
                    residual[(idx, ch)] = val
            if not residual:
                return True, {}
        return False, residual

    def set_force(self, kind, current_uA, tol_uA=0.5, tries=5, settle_sec=0.1):
        """Set a fast-DAC force current and verify it reached the DAC, retrying.

        ``kind`` is one of ``Sq1Fb`` / ``SaFb`` / ``Sq1Bias``. Stop the run first
        -- the override is a stopped-state operation; during a MUX run the per-row
        RAM overwrites the DAC output every row. Retries close the override
        one-shot race (Issue #86). Returns ``(converged, residual)``.
        """
        if kind not in self._FAST_DAC_FORCE:
            raise ValueError(f"set_force kind must be one of "
                             f"{list(self._FAST_DAC_FORCE)}, got {kind!r}")
        ok, residual = self._apply_force_verified(
            kind, current_uA, tol_uA=tol_uA, tries=tries, settle_sec=settle_sec)
        if not ok:
            log.warning("set_force(%s, %s): %d channel(s) did not reach target "
                        "within %.2f uA after %d tries: %s", kind, current_uA,
                        len(residual), tol_uA, tries, residual)
        return ok, residual

    def stop_and_zero(self, settle_sec=2.0, poll_sec=0.05):
        """Return to a safe baseline: stop MUX, then zero the column outputs.

        Order matters. The force/override DAC path (Sq1FbForceCurrent etc. ->
        FastDacDriver override RAM) is only serviced while the driver FSM sits in
        its IDLE state, i.e. when the run has stopped -- and the override write is
        a single-cycle event. So this method:
          1. ends any active run and switches the coordinator to manual timing;
          2. waits for TimingTx.Running to drop (bounded by ``settle_sec``) so the
             DAC FSM is guaranteed idle;
          3. THEN zeros the fast-DAC force outputs with **read-back verification
             and bounded retry** (``_apply_force_verified``), so a write dropped
             at the stop boundary is re-issued until DacCurrentNow confirms ~0;
             the slow bias/offset outputs are zeroed with a single write.

        The verify-and-retry closes the override one-shot race (Issue #86) in
        software -- no RTL change -- and gives real confirmation the biases
        zeroed, which is what the "biases don't zero after MUX" report (Issue #32)
        actually needed. See G2 in docs/plans/wtj-refactor/PLAN.md.

        Not yet a hardware interlock:
          - Verification covers the fast DACs (SQ1Fb/SAFb/SQ1Bias) via their
            DacCurrentNow read-back; a warning is logged if any channel cannot be
            driven to ~0 within the retry budget.
          - Row DAC zeroing is still left commented (row-select / FAS DAC outputs
            untouched) pending a bench check.

        Args:
            settle_sec (float): max time to wait for Running to drop after EndRun
                (EndRun completes on the next row-boundary, so this is not
                instantaneous).
            poll_sec (float): poll interval while waiting for Running to drop.
        """
        cb0 = self.coordinator_cb
        tx = cb0.WarmTdmCore.Timing.TimingTx

        # 1. Stop the run and leave MUX mode. EndRun completes on the next
        #    row-boundary timeslot, so Running does not drop instantly.
        if tx.Running.get():
            tx.EndRun()
        tx.Mode.set(0)

        # 2. Wait for the run to actually stop, so the FastDacDriver FSM is idle
        #    and will service the override writes below.
        deadline = time.time() + settle_sec
        while tx.Running.get():
            if time.time() > deadline:
                log.warning("stop_and_zero: TimingTx.Running did not drop within "
                            "%.1f s; zeroing anyway (writes may not land).", settle_sec)
                break
            time.sleep(poll_sec)

        # 3a. Zero the fast-DAC force outputs WITH read-back verification + retry.
        #     These ride the FastDacDriver override one-shot (Issue #86): a single
        #     blind write issued at the stop boundary can be dropped. Re-issuing
        #     until DacCurrentNow confirms ~0 closes that race in software and
        #     confirms the biases actually zeroed.
        all_ok = True
        for kind in self._FAST_DAC_FORCE:
            ok, residual = self._apply_force_verified(kind, 0.0)
            if not ok:
                all_ok = False
                log.warning("stop_and_zero: %s did not verify to ~0 after retries; "
                            "residual (board,chan)->uA: %s", kind, residual)

        # 3b. Zero the remaining (slow) bias/offset outputs. These do not go
        #     through the override FSM, so a single write is sufficient.
        r = None
        try:
            for r in ['SaBiasCurrent', 'SaOffset', 'TesBias']:
                var = getattr(self.group, r)
                var.set(np.zeros_like(var.get()))
        except (AttributeError, TypeError) as e:
            log.error("Error zeroing %s: %s", r, e)

        # TODO: zero row DACs once the reorder is confirmed on the bench
        # for i, rdd in self.rdds.items():
        #     rdd.FasOn.Current.set(np.zeros_like(rdd.FasOn.Current.get()))
        #     rdd.FasOff.Current.set(np.zeros_like(rdd.FasOn.Current.get()))

        log.info("stop_and_zero: run stopped, manual timing; fast-DAC force "
                 "outputs zeroed and verified via DacCurrentNow (%s); slow "
                 "bias/offset outputs zeroed. Row DACs left untouched.",
                 "all channels ~0" if all_ok else "WITH RESIDUALS -- see warnings")
