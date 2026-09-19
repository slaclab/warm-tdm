##
## PID servo metrics from a captured PID-debug stream (data model #3).
##
## The PID-debug stream is a per-(col,row) timeseries over readout visits (see
## streamreader.py / warm_tdm._DataFormats). This module turns that timeseries
## into scalar servo metrics -- steady-state residual, settling, overshoot,
## flux-jump and drop rates -- used both by the closed-loop cosim harness
## (software/scripts/hwtest/verify_cosim_pid.py) and, eventually, by the offline
## analyzer/diagnosis layer planned in docs/plans/channelization/PID_ANALYZER_PLAN.md.
##
## The integer (AdcDsp) and float (AdcDspFp) controllers log different field
## NAMES for the same physical quantities, so everything here is format-agnostic:
## a semantic name ('error', 'feedback', ...) resolves to whichever concrete
## field is present in the record. The kept fields (see PID_DEBUG_FIELDS /
## PID_DEBUG_FP_FIELDS) do NOT include the frame runTime, so visits are taken in
## natural append order -- which is the order the reader decoded them, i.e. visit
## order.
##
## Everything guards short/empty series and returns None rather than raising, so
## a harness can record a metric table even for a loop that never locked.

import numpy as np

# Semantic quantity -> ordered concrete field aliases (first present & nonempty
# wins). Integer names first, then float. See warm_tdm._DataFormats
# PID_DEBUG_FIELDS (integer) and PID_DEBUG_FP_FIELDS (float).
_FIELD_ALIASES = {
    'error':      ('accumError', 'accumErrorFp'),
    'feedback':   ('sq1FbEnd', 'sq1FbInt', 'sq1FbNewFp', 'sq1FbFull', 'sq1FbFullFp'),
    'integrator': ('sumAccumError', 'newSumAccum', 'sumAccumFp'),
    'flux_jumps': ('numFluxJumps',),
    'drops':      ('dropCount',),
}


def _slot(pid_data, col, row):
    """Resolve pid_data + (col,row) to the field->list dict for that channel.

    Accepts a StreamData/PidDebugData (uses its ``.pid``), a raw ``pid`` dict
    (``pid[col][row]``), or a single channel's ``{field: list}`` dict directly.
    Returns {} when the channel is absent.
    """
    pid = getattr(pid_data, 'pid', pid_data)
    if not isinstance(pid, dict):
        return {}
    # Already a single channel's {field: list}?
    if any(k in pid for k in ('accumError', 'accumErrorFp')):
        return pid
    rows = pid.get(col)
    if not isinstance(rows, dict):
        return {}
    slot = rows.get(row)
    return slot if isinstance(slot, dict) else {}


def _series(slot, semantic):
    """First present & nonempty alias for a semantic name, as a float array; else None."""
    for name in _FIELD_ALIASES[semantic]:
        values = slot.get(name)
        if values is not None and len(values):
            return np.asarray(values, dtype=float)
    return None


def pid_metrics(pid_data, col, row, *, settle_frac=0.5, deadband=None):
    """Servo metrics for one (col,row) PID-debug timeseries. Format-agnostic.

    Args:
        pid_data: StreamData, PidDebugData, a ``pid[col][row]`` dict, or a single
            channel's ``{field: list}`` dict.
        col, row: channel selectors (ignored when a single-channel dict is passed).
        settle_frac: fraction of the series treated as the settled tail for
            steady-state residual/RMS (default 0.5 = second half).
        deadband: settle tolerance for ``settling_visits`` (in the error's own
            units). Defaults to ``max(2*steady_rms, tiny)`` when None.

    Returns:
        dict of metrics; any metric that cannot be computed from the available
        data is None. Never raises on short/empty/missing series.
    """
    slot = _slot(pid_data, col, row)
    error = _series(slot, 'error')
    fmt = ('integer' if 'accumError' in slot else
           'float' if 'accumErrorFp' in slot else None)

    metrics = dict(format=fmt, n_visits=0, steady_residual=None, steady_rms=None,
                   peak_abs_error=None, overshoot=None, settling_visits=None,
                   feedback_mean=None, flux_jump_delta=None, flux_jump_events=None,
                   drop_rate=None, integrator_windup=None)

    fb = _series(slot, 'feedback')
    if fb is not None and len(fb):
        # Mean actuator over the settled tail -- used to see the servo move the
        # feedback to reject a TesBias step (robust where the transient peak is
        # too sparse to catch reliably).
        metrics['feedback_mean'] = float(np.mean(fb[int(len(fb) * settle_frac):]))

    fj = _series(slot, 'flux_jumps')
    if fj is not None and len(fj):
        metrics['flux_jump_delta'] = float(fj[-1] - fj[0])
        metrics['flux_jump_events'] = int(np.count_nonzero(np.diff(fj)))

    drops = _series(slot, 'drops')
    if drops is not None and len(drops) > 1:
        metrics['drop_rate'] = float((drops[-1] - drops[0]) / len(drops))

    if error is None or len(error) == 0:
        return metrics

    n = len(error)
    metrics['n_visits'] = n
    tail = error[int(n * settle_frac):]
    if len(tail):
        metrics['steady_residual'] = float(np.mean(np.abs(tail)))
        metrics['steady_rms'] = float(np.sqrt(np.mean(tail ** 2)))

    metrics['peak_abs_error'] = float(np.max(np.abs(error)))

    integ = _series(slot, 'integrator')
    if integ is not None and len(integ):
        metrics['integrator_windup'] = float(np.max(np.abs(integ)))

    # Settling + overshoot are only meaningful once there is a clear excursion
    # (a step or a startup transient) followed by a tail to settle into.
    if n >= 4 and metrics['steady_residual'] is not None:
        settled_mean = float(np.mean(tail))
        peak_idx = int(np.argmax(np.abs(error)))
        tol = deadband if deadband is not None else max(2.0 * (metrics['steady_rms'] or 0.0), 1e-9)

        # settling_visits: visits from the peak excursion until |error| stays
        # within tol of the settled mean for the remainder of the capture.
        settled = np.abs(error - settled_mean) <= tol
        settle_at = None
        for i in range(peak_idx, n):
            if settled[i] and bool(np.all(settled[i:])):
                settle_at = i
                break
        if settle_at is not None:
            metrics['settling_visits'] = int(settle_at - peak_idx)

        # overshoot: after the peak, the largest excursion PAST the settled mean
        # on the opposite side of the peak, as a fraction of the initial step.
        step = error[peak_idx] - settled_mean
        if abs(step) > tol and peak_idx + 1 < n:
            after = error[peak_idx + 1:] - settled_mean
            opposite = -after if step > 0 else after
            over = float(np.max(opposite)) if len(opposite) else 0.0
            metrics['overshoot'] = float(max(0.0, over / abs(step)))

    return metrics


def pid_metrics_all(pid_data, cols, rows, **kwargs):
    """{(col,row): pid_metrics(...)} over the given cols and rows."""
    return {(c, r): pid_metrics(pid_data, c, r, **kwargs)
            for c in cols for r in rows}
