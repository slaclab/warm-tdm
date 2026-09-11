# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

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

        DacCurrentNow handles its own dependency read. Failed reads are retained
        as NaN so they cannot be mistaken for successfully verified channels.
        """
        out = {}
        for idx, cb in sorted(self.cbs.items()):
            for ch in range(self.chans_per_board):
                key = (idx, ch)
                try:
                    dev = getattr(cb, dev_name)
                    value = float(dev.DacCurrentNow[ch].get())
                    if not np.isfinite(value):
                        raise ValueError(f"non-finite current: {value}")
                    out[key] = value
                except Exception as exc:
                    out[key] = float('nan')
                    log.warning("Cannot verify %s board %s channel %s: %s",
                                dev_name, idx, ch, exc)
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
        ``{(board, chan): current}`` for channels still off target; NaN marks
        missing, failed or non-finite readback. Invalid targets/topology raise
        before any write. All expected channels must verify.
        """
        setter_name, dev_name = self._FAST_DAC_FORCE[kind]
        setter = getattr(self.group, setter_name)
        ncol = len(setter.get())
        target = (np.full(ncol, float(target_uA)) if np.isscalar(target_uA)
                  else np.asarray(target_uA, dtype=float))

        expected = {(idx, ch): idx * self.chans_per_board + ch
                    for idx in self.cbs for ch in range(self.chans_per_board)}
        if not expected or set(expected.values()) != set(range(ncol)):
            raise ValueError("Force vector must cover every expected board/channel")
        if target.shape != (ncol,) or not np.all(np.isfinite(target)):
            raise ValueError(f"Force target must contain {ncol} finite values")
        if not np.isfinite(tol_uA) or tol_uA < 0:
            raise ValueError("tol_uA must be finite and nonnegative")
        if not isinstance(tries, (int, np.integer)) or tries < 1:
            raise ValueError("tries must be a positive integer")
        if not np.isfinite(settle_sec) or settle_sec < 0:
            raise ValueError("settle_sec must be finite and nonnegative")

        residual = {}
        for _ in range(tries):
            setter.set(target.tolist())
            time.sleep(settle_sec)
            readings = self._read_dac_now(dev_name)
            residual = {}
            for key, col in expected.items():
                val = readings.get(key, float('nan'))
                if not np.isfinite(val) or abs(val - target[col]) > tol_uA:
                    residual[key] = val
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
          1. ends any active run (EndRun);
          2. waits for TimingTx.Running to drop (bounded by ``settle_sec``), still
             in the current free-running mode so EndRun's row-boundary can occur,
             then switches the coordinator to manual timing (Mode 0). Switching to
             manual before the run stops would halt the row boundaries EndRun is
             waiting for and strand it with Running asserted;
          3. THEN zeros the fast-DAC force outputs with **read-back verification
             and bounded retry** (``_apply_force_verified``), so a write dropped
             at the stop boundary is re-issued until DacCurrentNow confirms ~0;
             slow bias/offset writes are attempted separately.

        The verify-and-retry closes the override one-shot race (Issue #86) in
        software -- no RTL change -- and checks fresh finite DAC readbacks,
        addressing the "biases don't zero after MUX" report (Issue #32). See docs/design/fastdac-override-race.md.

        Not yet a hardware interlock:
          - Verification covers the fast DACs (SQ1Fb/SAFb/SQ1Bias) via their
            DacCurrentNow read-back; a warning is logged if any channel cannot be
            driven to ~0 within the retry budget.
          - Row DAC zeroing is still left commented (row-select / FAS DAC outputs
            untouched) pending a bench check.

        Returns True only if timing stopped, all expected fast-DAC readbacks
        verified and slow-output writes completed; otherwise logs and returns
        False after attempting the remaining outputs. This does not independently
        measure physical outputs.

        Args:
            settle_sec (float): max time to wait for Running to drop after EndRun
                (EndRun completes on the next row-boundary, so this is not
                instantaneous).
            poll_sec (float): poll interval while waiting for Running to drop.
        """
        if not np.isfinite(settle_sec) or settle_sec < 0:
            raise ValueError("settle_sec must be finite and nonnegative")
        if not np.isfinite(poll_sec) or poll_sec <= 0:
            raise ValueError("poll_sec must be finite and positive")
        cb0 = self.coordinator_cb
        tx = cb0.WarmTdmCore.Timing.TimingTx

        # 1. End any active run. EndRun completes on the next row-boundary
        #    timeslot, so Running does not drop instantly. Do NOT switch to
        #    manual timing (Mode 0) yet: Mode 0 halts row-boundary generation, so
        #    switching before EndRun completes strands the pending end-of-run and
        #    leaves Running asserted (the row boundary EndRun waits for never
        #    arrives). Switch to manual mode only after the run has stopped.
        all_ok = True
        try:
            if tx.Running.get():
                tx.EndRun()
        except Exception:
            all_ok = False
            log.exception("stop_and_zero: could not end run")

        # 2. Wait for the run to actually stop -- still in the current
        #    (free-running) mode so EndRun's row-boundary can occur -- so the
        #    FastDacDriver FSM is idle and will service the override writes below.
        deadline = time.monotonic() + settle_sec
        try:
            while tx.Running.get():
                if time.monotonic() >= deadline:
                    all_ok = False
                    log.warning("stop_and_zero: timing still running; attempting "
                                "zeroing without claiming a verified stop")
                    break
                time.sleep(min(poll_sec, max(0, deadline - time.monotonic())))
        except Exception:
            all_ok = False
            log.exception("stop_and_zero: could not verify timing stopped")

        # 3. Now that the run has stopped, switch the coordinator to manual
        #    timing so no further MUX row-boundaries are generated before zeroing.
        try:
            tx.Mode.set(0)
        except Exception:
            all_ok = False
            log.exception("stop_and_zero: could not set manual timing mode")

        # 3a. Zero the fast-DAC force outputs WITH read-back verification + retry.
        #     These ride the FastDacDriver override one-shot (Issue #86): a single
        #     blind write issued at the stop boundary can be dropped. Re-issuing
        #     until DacCurrentNow confirms ~0 closes that race in software and
        #     checks the complete finite readback vector.
        for kind in self._FAST_DAC_FORCE:
            try:
                ok, residual = self._apply_force_verified(kind, 0.0)
            except Exception:
                all_ok = False
                log.exception("stop_and_zero: %s zeroing failed", kind)
                continue
            if not ok:
                all_ok = False
                log.warning("stop_and_zero: %s did not verify to ~0 after retries; "
                            "residual (board,chan)->uA: %s", kind, residual)

        # 3b. Zero the remaining (slow) bias/offset outputs. These do not go
        #     through the override FSM, so a single write is sufficient.
        for name in ['SaBiasCurrent', 'SaOffset', 'TesBias']:
            try:
                var = getattr(self.group, name)
                var.set(np.zeros_like(var.get()))
            except Exception:
                all_ok = False
                log.exception("stop_and_zero: error zeroing %s", name)

        # TODO: zero row DACs once the reorder is confirmed on the bench
        # for i, rdd in self.rdds.items():
        #     rdd.FasOn.Current.set(np.zeros_like(rdd.FasOn.Current.get()))
        #     rdd.FasOff.Current.set(np.zeros_like(rdd.FasOn.Current.get()))

        if all_ok:
            log.info("stop_and_zero: timing stopped, fast-DAC readbacks verified "
                     "zero, slow-output writes completed. Row DACs untouched.")
        else:
            log.error("stop_and_zero: incomplete cleanup/verification; see errors above")
        return all_ok
