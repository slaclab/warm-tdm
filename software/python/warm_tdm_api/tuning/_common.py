"""Shared tuning primitives used across the SA, FAS, and SQ1 procedures.

These helpers are the cross-cutting pieces of the tuning package:

- :func:`_pause_point` — cooperative Stop/Pause handling for every sweep loop.
- :func:`saOffset` — null the SA-output ADCs by servoing the SA-offset DACs.
- :func:`saFbServo` — null the SA output by servoing SA feedback; used after
  each FAS or SQ1 stimulus change.

The public functions operate on the Group-level PyRogue array variables, which
apply ``ColTuneEnable`` and batch board accesses, so callers pass complete
column vectors rather than walking individual board/channel nodes.
"""

import numpy as np

from simple_pid import PID


def _pause_point(process, publish=None):
    """Handle a Stop/Pause request at a safe boundary in a tuning loop.

    Parameters
    ----------
    process : PausableProcess or None
        Calling process. Tuning process classes derive from
        :class:`warm_tdm_api.PausableProcess`.
    publish : callable, optional
        Callback used to publish the currently collected data before waiting
        in a paused state.

    Returns
    -------
    bool
        ``True`` while work should continue, or ``False`` after Stop.
    """
    if process is None:
        return True
    return process.pausePoint(publish)


def saOffset(*, group, process=None, publish=None):
    """Servo each enabled SA offset DAC until the measured ADC is nulled.

    The initial offset estimate is derived from the current SA-bias voltage.
    Each loop reads all enabled ADC channels once, updates only channels still
    outside ``SaOffsetProcess.Precision``, and writes the resulting offset
    vector as one Group-level transaction.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing the SA bias/offset controls and ADC measurements.
    process : pyrogue.Process, optional
        Parent tuning process used for Stop/Pause handling. ``None`` runs the
        servo synchronously without cooperative process controls.
    publish : callable, optional
        Publishes partial parent-sweep results before a pause.

    Returns
    -------
    numpy.ndarray
        Final SA-offset control voltage for every logical column. Disabled
        columns retain the value in the Group shadow and are not written.

    Raises
    ------
    Exception
        If the enabled channels do not converge within ``MaxLoops``.
    """

    # Snapshot the servo configuration once; these local parameters are held
    # constant for the entire convergence attempt.
    kp = group.SaOffsetProcess.Kp.get()
    ki = group.SaOffsetProcess.Ki.get()
    kd = group.SaOffsetProcess.Kd.get()
    precision = group.SaOffsetProcess.Precision.get()
    maxLoops = group.SaOffsetProcess.MaxLoops.get()
    colCount = group.NumColumns.get()
    enabled_mask = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    enabled_columns = np.flatnonzero(enabled_mask)

    # Keep one controller per logical column so each enabled channel has
    # independent PID state. Disabled controllers are never evaluated.
    pid = [PID(kp, ki, kd) for _ in range(colCount)]

    for p in pid:
        p.setpoint = 0  # want to zero out SaOut
        p.output_limits = (-0.5, 0.5)
        p.sample_time = None

    # The required offset normally tracks the SA-bias voltage. Starting nearby
    # avoids a long traversal from zero on both hardware and simulation models.
    control = group.SaBiasVoltage.get() * 0.9

    group.SaOffset.set(value=control)

    masked = np.zeros(colCount, dtype=np.float64)
    count = 0

    while count < maxLoops:
        if not _pause_point(process, publish):
            return control

        count += 1

        # One Group-array read refreshes the enabled ADC channels in parallel.
        current = group.SaOutAdc.get()
        masked.fill(0.0)
        masked[enabled_columns] = current[enabled_columns]

        # Stop only when every enabled channel is inside the requested band.
        done = np.abs(masked[enabled_columns]) < precision
        if np.all(done):
            break
        # Update the shared control vector in memory, then issue one grouped
        # write rather than one transaction for every unconverged column.
        changed = False
        for i, is_done in zip(enabled_columns, done):
            if not is_done:
                change = pid[i](masked[i])
                control[i] = np.clip(control[i] + change, 0, 4.999)
                changed = True

        if changed:
            group.SaOffset.set(control)

        if not _pause_point(process, publish):
            return control

    if count == maxLoops:
        group._log.warning(f'saOffset failed to converge: ADC={masked}, control={control}')
        raise Exception(f"saOffset PID loop failed to converge after {maxLoops} loops")
    else:
        group._log.info(f'saOffset PID loop converged after {count} loops')

    return control


def saFbServo(*, group, process, publish=None):
    """Servo SA feedback until every enabled SA-output ADC is nulled.

    This servo is used after each FAS or SQ1 stimulus change. Its PID gains and
    convergence limits come from the calling process. The current feedback
    override shadow is used as the initial condition, avoiding a redundant
    hardware read at every sweep point.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing the SA-feedback overrides and output ADCs.
    process : FasTuneProcess or Sq1TuneProcess
        Supplies ``ServoKp``, ``ServoKi``, ``ServoKd``, precision, loop limit,
        logging, and Stop/Pause state.
    publish : callable, optional
        Publishes partial parent-sweep results before a pause.

    Returns
    -------
    numpy.ndarray
        Last SA-feedback force-current vector. On convergence this is the
        nulled solution; on Stop or timeout it is the last attempted value.

    Notes
    -----
    A timeout is logged but does not raise, allowing the caller to retain the
    sampled diagnostic curve. Disabled columns are neither updated nor written.
    """

    # Hold the selected gains constant for this convergence attempt.
    kp = process.ServoKp.get()
    ki = process.ServoKi.get()
    kd = process.ServoKd.get()
    precision = process.ServoPrecision.get()
    maxLoops = process.ServoMaxLoops.get()
    log = process._log
    col_count = group.NumColumns.get()
    enabled_mask = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    enabled_columns = np.flatnonzero(enabled_mask)
    log.debug(
        'SA FB servo start: kp=%s ki=%s kd=%s precision=%s maxLoops=%s',
        kp, ki, kd, precision, maxLoops)

    # One controller per column preserves independent history; only enabled
    # controllers are evaluated below.
    pid = [PID(kp, ki, kd) for _ in range(col_count)]
    for p in pid:
        p.setpoint = 0
        p.output_limits = (-0.5, 0.5)
        p.sample_time = None

    # The caller establishes this force-current state before every sweep and
    # every servo update below writes through the same variable, so its shadow
    # is authoritative for the starting point.
    control = group.SaFbForceCurrent.get(read=False)

    masked = np.zeros(col_count, dtype=np.float64)
    log.debug(
        'SA FB servo initial state: enabledMask=%s control=%s',
        enabled_mask.astype(np.float64).tolist(), np.asarray(control).tolist())

    for count in range(maxLoops):
        if not _pause_point(process, publish):
            log.debug(
                'SA FB servo stopped before loop %d; returning control=%s',
                count + 1, np.asarray(control).tolist())
            return control

        # Read all enabled ADC channels together, but evaluate convergence only
        # over the tune mask so an untuned channel cannot hold the loop open.
        current = group.SaOutAdc.get()
        masked.fill(0.0)
        masked[enabled_columns] = current[enabled_columns]
        log.debug(
            'SA FB servo loop %d/%d: adc=%s masked=%s control=%s',
            count + 1, maxLoops, np.asarray(current).tolist(),
            np.asarray(masked).tolist(), np.asarray(control).tolist())

        if np.all(np.abs(masked[enabled_columns]) < precision):
            log.debug(
                'SA FB servo converged after %d loop(s): control=%s',
                count + 1, np.asarray(control).tolist())
            break

        # Update the complete shadow vector, then let the Group variable commit
        # only the enabled column blocks as one operation.
        for i in enabled_columns:
            change = pid[i](masked[i])
            control[i] = control[i] + change

        group.SaFbForceCurrent.set(control)
        log.debug(
            'SA FB servo loop %d wrote control=%s',
            count + 1, np.asarray(control).tolist())

    else:
        log.warning(
            'SA FB servo failed to converge after %d loop(s): '
            'masked=%s control=%s',
            maxLoops, np.asarray(masked).tolist(),
            np.asarray(control).tolist())
        return control

    log.debug('SA FB servo return: control=%s', np.asarray(control).tolist())
    return control
