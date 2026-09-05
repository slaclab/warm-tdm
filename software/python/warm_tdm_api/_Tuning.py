"""Hardware-facing SA, FAS, SQ1, and diagnostic tuning routines.

The public functions in this module operate on the Group-level PyRogue array
variables. Those variables apply ``ColTuneEnable`` and batch accesses to the
underlying boards, so tuning code should pass complete column vectors rather
than walking individual board/channel nodes. Long-running sweeps cooperate with
Process Stop/Pause requests and may publish partial curve data at safe points.
"""

import numpy as np
import time

from simple_pid import PID
import warm_tdm_api


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


def _fas_minimum_center(x_values, points, tolerance):
    """Find the center of a sampled FAS-response minimum.

    Start at the global minimum and expand in both directions while adjacent
    samples remain within ``tolerance`` of it. This avoids the low-current bias
    of ``argmin()`` when the servo response has a flat, quantized bottom.

    Parameters
    ----------
    x_values : array-like
        FAS-current samples in acquisition order.
    points : array-like
        SA-feedback response samples corresponding to ``x_values``.
    tolerance : float
        Maximum response above the global minimum that remains part of the
        selected contiguous region.

    Returns
    -------
    tuple
        ``(center, low_index, high_index, minimum_value)``. ``center`` is the
        midpoint between the first and last FAS-current samples in the region.

    Raises
    ------
    ValueError
        If no finite response samples are available.
    """
    x_values = np.asarray(x_values, dtype=np.float64)
    points = np.asarray(points, dtype=np.float64)
    count = min(x_values.size, points.size)
    if count == 0:
        raise ValueError('Cannot select a FAS minimum from an empty curve')

    x_values = x_values[:count]
    points = points[:count]
    finite = np.isfinite(points)
    if not np.any(finite):
        raise ValueError('Cannot select a FAS minimum from non-finite samples')

    finite_indices = np.flatnonzero(finite)
    minimum_index = int(
        finite_indices[np.argmin(points[finite_indices])])
    minimum_value = points[minimum_index]
    threshold = minimum_value + max(0.0, float(tolerance))

    low = minimum_index
    while low > 0 and finite[low - 1] and points[low - 1] <= threshold:
        low -= 1
    high = minimum_index
    while (high + 1 < count and finite[high + 1]
           and points[high + 1] <= threshold):
        high += 1

    center = 0.5 * (x_values[low] + x_values[high])
    return float(center), low, high, float(minimum_value)


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




# SA tuning
def saFbSweep(*, group, bias, saFbRange, process, curves=None,
              publish=None):
    """Measure SA output versus SA feedback at one SA-bias point.

    At each feedback step, the complete column vector is written through the
    force-current path, the configured wall-clock settling delay is observed,
    and one Group-array SA-output sample is appended to each curve. If any
    enabled ADC channel approaches a rail, :func:`saOffset` recenters it before
    the sweep continues.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being tuned.
    bias : array-like
        SA-bias current associated with each column's curve.
    saFbRange : numpy.ndarray
        Feedback currents shaped ``(num_columns, num_steps)``.
    process : pyrogue.Process or None
        Parent SA-tune process for progress and Stop/Pause handling.
    curves : list[Curve], optional
        Existing per-column curves to extend. Supplying them permits partial
        results to be published while the sweep is running.
    publish : callable, optional
        Partial-result callback passed to pause points and offset recovery.

    Returns
    -------
    list[Curve]
        One response curve per logical column. On Stop, each curve contains
        only the completed samples.

    Notes
    -----
    After a normal or user-stopped sweep, enabled SA-feedback force values are
    reset to zero. Disabled columns are preserved by the Group-level tune mask.
    """
    colCount = group.NumColumns.get()
    enabled_mask = np.asarray(group.ColTuneEnable.value(), dtype=bool)

    # Callers that support live plotting create and attach the curves before
    # entering the sweep; standalone callers can let this function create them.
    if curves is None:
        curves = [warm_tdm_api.Curve(bias[i]) for i in range(colCount)]

    numSteps = len(saFbRange[0])

    sleep = group.SaTuneProcess.SaFbSampleDelay.get()

    # Each column may eventually use a different range, so select one full
    # column vector at every step even when the configured ranges are equal.
    for idx in range(numSteps):

        if not _pause_point(process, publish):
            break

        # Drive only the enabled columns through the force-current override.
        group.SaFbForceCurrent.set(saFbRange[:, idx])

        # This is a wall-clock delay for real hardware. It does not advance
        # simulated time in a VCS co-simulation.
        time.sleep(sleep)
        points = group.SaOut.get()

        for col in range(colCount):
            curves[col].addPoint(points[col])

        if process is not None:
            process._incrementSteps(1)

        # SaOut just refreshed the ADC block; reuse that shadow instead of
        # issuing a second hardware read solely for the rail check.
        adcs = group.SaOutAdc.get(read=False)
        if np.any(np.abs(adcs[enabled_mask]) > 0.8):
            group._log.warning(f'High ADC value seen: SaBias={bias}, SaFb={saFbRange[:, idx]}, ADCs={adcs}')
            offset = saOffset(
                group=group, process=process, publish=publish)
            # saOffset exits on a freshly sampled ADC value.
            adc_after = group.SaOutAdc.get(read=False)
            # SaOut derives from the ADC and offset blocks just refreshed
            # above; use those cached values rather than reading them again.
            group._log.debug(
                'After re-offset: SaOffset=%s, ADC=%s, SaOut=%s',
                offset, adc_after, group.SaOut.get(read=False))

        if not _pause_point(process, publish):
            break

    # Leave the force path in a deterministic neutral state between bias curves.
    group.SaFbForceCurrent.set(value=np.zeros(colCount, np.float64))

    return curves

def saBiasSweep(*, group, process, doBiasRamp=True):
    """Acquire a family of SA-feedback curves over SA-bias current.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being tuned.
    process : SaTuneProcess or None
        Supplies sweep settings, progress state, and Stop/Pause handling.
    doBiasRamp : bool, default=True
        Sweep the configured SA-bias range when true. When false, acquire one
        curve at each column's currently loaded SA-bias value.

    Returns
    -------
    list[CurveData]
        One fitted curve family per logical column. Disabled columns retain an
        empty result and are not written.

    Notes
    -----
    SQ1 bias and feedback force paths are cleared once before acquisition so
    they cannot influence the SA response. The final SA-bias sweep value remains
    applied; :func:`saTune` optionally replaces it with the fitted value.
    """

    # Resolve all sweep settings once so GUI edits cannot reshape a run midway.
    colCount = group.NumColumns.get()
    colTuneEnable = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    numBiasSteps = group.SaTuneProcess.SaBiasNumSteps.get() if doBiasRamp else 1
    numFbSteps = group.SaTuneProcess.SaFbNumSteps.get()
    if doBiasRamp:
        # A common configured range is broadcast into column-major form for the
        # vector Group setters and per-column CurveData containers.
        bias_values = np.linspace(
            group.SaTuneProcess.SaBiasLowOffset.get(),
            group.SaTuneProcess.SaBiasHighOffset.get(),
            numBiasSteps,
            endpoint=True)
        saBiasRange = np.broadcast_to(
            bias_values, (colCount, numBiasSteps)).copy()
    else:
        # One array read obtains every currently loaded bias instead of issuing
        # one hardware access per column.
        saBiasRange = group.SaBiasCurrent.get().reshape(colCount, 1)

    fb_values = np.linspace(
        group.SaTuneProcess.SaFbLowOffset.get(),
        group.SaTuneProcess.SaFbHighOffset.get(),
        numFbSteps,
        endpoint=True)
    saFbRange = np.broadcast_to(
        fb_values, (colCount, numFbSteps)).copy()
    datalist = [
        warm_tdm_api.CurveData(xValues=saFbRange[col])
        for col in range(colCount)]
    
            
    if process is not None:
        process.TotalSteps.set(numBiasSteps * numFbSteps)


    # These paths are not swept during SA tune. Clear them once, staging all
    # three force-current arrays before one grouped hardware commit.
    zero_columns = np.zeros(colCount, np.float64)
    warm_tdm_api.stageAndCommit(
        (group.SaFbForceCurrent, zero_columns),
        (group.Sq1BiasForceCurrent, zero_columns),
        (group.Sq1FbForceCurrent, zero_columns))

    # Each outer-loop point establishes SA bias and recenters the offset before
    # acquiring its complete SA-feedback response curve.
    for idx in range(numBiasSteps):
        publish = (
            None if process is None
            else lambda: process._publishResults(datalist))
        if not _pause_point(process, publish):
            group._log.info('Process stopped, exiting saBiasSweep')
            break

        if process is not None:
            process.Message.set(f'SaBias step {idx+1} out of {numBiasSteps}')
        

        curves = [
            warm_tdm_api.Curve(saBiasRange[col, idx])
            for col in range(colCount)]
        # Attach the curve before acquisition so Pause can publish samples from
        # an incomplete curve. Untuned columns are deliberately omitted.
        for col in range(colCount):
            # Only add the curve if column is enabled for tuning
            if colTuneEnable[col]:
                datalist[col].addCurve(curves[col])

        group.SaBiasCurrent.set(saBiasRange[:, idx])
        saOffset(group=group, process=process, publish=publish)

        saFbSweep(
            group=group,
            bias=saBiasRange[:, idx],
            saFbRange=saFbRange,
            process=process,
            curves=curves,
            publish=publish)

        # Do not begin another bias point after an interrupted inner sweep.
        if not _pause_point(process, publish):
            group._log.info('Process stopped, exiting saBiasSweep')
            break

    # Fit every completed curve family and populate biasOut/xOut/yOut.
    for d in datalist:
        d.update()

    return datalist

def saTune(*, group, process=None, doSet=True, doBiasRamp=True):
    """Run the complete SA bias/feedback tune for all enabled columns.

    The acquisition phase calls :func:`saBiasSweep`, whose ``CurveData`` fit
    selects the bias curve with the largest usable response and an operating
    feedback point on that curve. When requested, fitted values are staged into
    the per-row SA-feedback RAM, SA-bias DACs, and feedback force path in one
    grouped commit, followed by a final offset servo.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being tuned.
    process : SaTuneProcess, optional
        Parent process for progress, partial publication, and Stop/Pause.
    doSet : bool, default=True
        Apply fitted SA bias and feedback values after a successful sweep.
    doBiasRamp : bool, default=True
        Sweep SA bias when true; otherwise fit one curve at the loaded bias.

    Returns
    -------
    list[CurveData]
        One fitted SA-tune result per logical column.

    Raises
    ------
    RuntimeError
        If an enabled column does not produce a fitted bias/feedback point when
        ``doSet`` is enabled.

    Notes
    -----
    Stopping before the apply phase leaves the partially collected results
    available but does not program them into the readout tables.
    """
    group._log.info(f'saTune starting: doBiasRamp={doBiasRamp}, doSet={doSet}')

    colTuneEnable = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    saBiasResults = saBiasSweep(group=group, process=process, doBiasRamp=doBiasRamp)

    publish = (
        None if process is None
        else lambda: process._publishResults(saBiasResults))
    stopped = not _pause_point(process, publish)
    if doSet and not stopped:
        # Build complete arrays in memory first. Group-level setters mask
        # disabled columns, so their cached placeholder values are never sent.
        col_count = group.NumColumns.get()
        max_rows = group.MaxRows.get()
        tunedSaFb = group.SaFbForceCurrent.get(read=False)
        tunedSaBias = group.SaBiasCurrent.get(read=False)
        saFbTable = np.zeros((col_count, max_rows), dtype=np.float64)

        # SA tune produces one feedback value per column. Replicate it through
        # the full hardware row RAM; this remains valid before RowMap is loaded.
        for col in range(col_count):
            if not colTuneEnable[col]:
                group._log.debug(
                    'SA tune leaving disabled column %d unchanged', col)
                continue

            result = saBiasResults[col]
            if result.xOut is None or result.biasOut is None:
                raise RuntimeError(
                    f'SA tune produced no fitted result for enabled column {col}')

            # Fill the complete column shadow table now; the grouped commit
            # writes one array block instead of one transaction per row.
            saFbTable[col, :] = result.xOut
            tunedSaFb[col] = result.xOut
            tunedSaBias[col] = result.biasOut

        group._log.debug(
            'SA tune staging fitted SaFb table, SA bias, and force-current '
            'operating point: SaFb=%s SaBias=%s',
            tunedSaFb.tolist(), tunedSaBias.tolist())
        warm_tdm_api.stageAndCommit(
            (group.SaFbCurrent, saFbTable),
            (group.SaBiasCurrent, tunedSaBias),
            (group.SaFbForceCurrent, tunedSaFb))

        # Recenter the output at the operating point that readout will use.
        saOffset(group=group, process=process, publish=publish)
    elif doSet:
        group._log.info('Process stopped; leaving partial SA tune results unapplied')

    group._log.info('saTune complete')
    return saBiasResults


# Shared software servo used by FAS and SQ1 tuning
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

def fasSweep(*, group, row, board, address, driver, enabled_mask,
             off_current, currents, delay, process, publish=None):
    """Measure the nulled SA-feedback response to one physical FAS line.

    The caller has already resolved the logical-row mapping, placed the row
    board in MANUAL mode, and cached its FAS-off current. Each FAS-current point
    is driven with ``manual_set()``, then :func:`saFbServo` determines the SA
    feedback required to null the enabled columns.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being measured.
    row : int
        Logical row associated with the physical FAS line.
    board : int
        Row-board index containing the line.
    address : int
        Board-local FAS address in the range 0..31.
    driver : warm_tdm.RowDacDriver2
        Row-DAC driver, already configured for MANUAL operation.
    enabled_mask : array-like of bool
        Logical columns whose servo responses should be recorded.
    off_current : float
        Cached current used to return this line to its inactive state.
    currents : array-like
        Ordered FAS-current sweep values.
    delay : float
        Interruptible wall-clock delay after each manual write, in seconds.
    process : FasTuneProcess
        Parent process providing servo parameters, progress, and control state.
    publish : callable, optional
        Receives the in-progress ``CurveData`` at pause points.

    Returns
    -------
    CurveData
        Per-column SA-feedback responses plus ``logicalRow``, ``board``,
        ``address``, and an initially unset ``fasOn`` result.

    Notes
    -----
    The physical line is returned to ``off_current`` in a ``finally`` block,
    including after Stop or an acquisition exception.
    """
    log = process._log
    log.debug(
        'FAS sweep row %s start: board=%d address=%d low=%s high=%s '
        'steps=%d delay=%s currents=%s',
        row, board, address, currents[0], currents[-1], len(currents), delay,
        currents.tolist())
    # Attach physical/logical metadata before acquisition so an incomplete
    # curve can be serialized while paused or stopped.
    data = warm_tdm_api.CurveData(xValues=currents)
    for column in range(group.NumColumns.get()):
        data.addCurve(warm_tdm_api.Curve(column))
    data.logicalRow = row
    data.board = board
    data.address = address
    data.fasOn = None

    publish_data = None if publish is None else lambda: publish(data)

    log.debug(
        'FAS sweep row %s using captured FasOff[%d]=%s uA',
        row, address, off_current)
    try:
        for step, current in enumerate(currents):
            if not _pause_point(process, publish_data):
                log.debug(
                    'FAS sweep row %s stopped before step %d/%d',
                    row, step + 1, len(currents))
                break

            # MANUAL mode was set and verified once by fasTune; rechecking it
            # here would add a register read to every co-simulation point.
            request = driver.manual_set(
                address=address, current=current, check_mode=False)
            # Record a point only after the inner servo completes; partial
            # servo iterations are not valid FAS response samples.
            log.debug(
                'FAS sweep row %s step %d/%d ManualSet: requested=%s uA '
                'result=%s',
                row, step + 1, len(currents), current, request)

            # Stop() waits for the worker thread, so keep a user-configured
            # settling delay interruptible rather than sleeping in one block.
            deadline = time.monotonic() + max(0.0, delay)
            while time.monotonic() < deadline:
                if not _pause_point(process, publish_data):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    break
                time.sleep(min(0.05, remaining))
            if not _pause_point(process, publish_data):
                log.debug(
                    'FAS sweep row %s stopped while settling step %d/%d',
                    row, step + 1, len(currents))
                break

            log.debug(
                'FAS sweep row %s step %d/%d starting SA FB servo',
                row, step + 1, len(currents))
            points = saFbServo(
                group=group, process=process, publish=publish_data)
            if not _pause_point(process, publish_data):
                log.debug(
                    'FAS sweep row %s stopped during SA FB servo at '
                    'step %d/%d', row, step + 1, len(currents))
                break
            log.debug(
                'FAS sweep row %s step %d/%d response=%s',
                row, step + 1, len(currents), np.asarray(points).tolist())
            for column, point in enumerate(points):
                if enabled_mask[column]:
                    data.curveList[column].addPoint(point)
            process._incrementSteps(1)
            log.debug(
                'FAS sweep row %s step %d/%d recorded',
                row, step + 1, len(currents))
            if not _pause_point(process, publish_data):
                break
    finally:
        log.debug(
            'FAS sweep row %s restoring board=%d address=%d to FasOff=%s uA',
            row, board, address, off_current)
        request = driver.manual_set(
            address=address, current=off_current, check_mode=False)
        log.debug('FAS sweep row %s FasOff restore result=%s', row, request)

    log.debug(
        'FAS sweep row %s complete: collectedPoints=%s',
        row, [len(curve.points) for curve in data.curveList])
    return data

def fasTune(*, group, process=None, doSet=True):
    """Tune the one-level FAS-on current for every active logical row.

    Active logical rows come from ``RowIndexOrderList`` and are resolved through
    ``RowMap``. Sweep points use ``RowDacDriver2.manual_set()``; persistent
    ``FasOn`` entries are optionally written only after every row sweep
    completes. A provisional SQ1 bias makes the FAS state observable before SQ1
    tuning; the original SQ1 force-current values are restored on exit.
    ``FasOff`` is never modified.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing the row mapping, row-DAC drivers, and SA readout.
    process : FasTuneProcess
        Required process supplying sweep/servo settings and partial-result
        publication.
    doSet : bool, default=True
        Program selected currents into persistent ``FasOn`` RAM after every row
        completes. When false, return and publish candidates without programming.

    Returns
    -------
    list[CurveData]
        One FAS sweep result per completed active row, in active-row order.
        Each successful result includes its selected physical ``fasOn`` value.

    Raises
    ------
    ValueError
        If no ``process`` is supplied.
    RuntimeError
        If timing is running, no rows or columns are enabled, a row mapping is
        invalid/two-level, ManualSet is unavailable, or a row produces no data.

    Notes
    -----
    All force-current overrides and row-board modes are snapshotted and restored
    on exit. Persistent ``FasOn`` programming is deferred until all sweeps
    succeed and is rolled back if Stop or an exception interrupts programming.
    """
    if process is None:
        raise ValueError('fasTune requires its FasTuneProcess')

    log = process._log
    log.debug('FAS tune entry: doSet=%s', doSet)
    # Manual row actuation is only deterministic while sequenced timing is off.
    tx = group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
    timing_running = tx.Running.get(read=True)
    log.debug('FAS tune timing Running=%s', timing_running)
    if timing_running:
        log.error('FAS tune rejected because timing is running')
        raise RuntimeError('FAS tuning requires timing to be stopped')

    row_map = group.RowMap.get()
    active_rows = [int(row) for row in group.RowIndexOrderList.get(read=True)]
    enabled_mask = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    enabled_columns = np.flatnonzero(enabled_mask).tolist()
    log.debug(
        'FAS tune configuration: activeRows=%s enabledColumns=%s '
        'rowMapLength=%d', active_rows, enabled_columns, len(row_map))
    if not active_rows:
        log.error('FAS tune rejected because the active row list is empty')
        raise RuntimeError('FAS tuning requires at least one active row')
    if not enabled_columns:
        log.error('FAS tune rejected because no columns are enabled')
        raise RuntimeError('FAS tuning requires at least one enabled column')

    # Resolve logical rows once. The simple tuner intentionally rejects the
    # two-level chip-select mapping because it can drive only one physical line.
    targets = []
    drivers = {}
    for row in active_rows:
        if row < 0 or row >= len(row_map):
            raise RuntimeError(
                f'Active logical row {row} is outside RowMap length '
                f'{len(row_map)}')
        mapping = row_map[row]
        log.debug('FAS tune resolving logical row %d: %s', row, mapping)
        if 'csAddr' in mapping or 'csBoard' in mapping:
            log.error(
                'FAS tune rejected logical row %d two-level mapping: %s',
                row, mapping)
            raise RuntimeError(
                'The simple FAS tune supports one-level RowMap entries only')
        board = int(mapping['rsBoard'])
        address = int(mapping['rsAddr'])
        if address < 0 or address >= 32:
            raise RuntimeError(
                f'RowMap[{row}] rsAddr={address} is outside 0..31')
        try:
            driver = group.HardwareGroup.RowBoard[board].RowDacDriver
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            raise RuntimeError(
                f'RowMap[{row}] references unavailable row board {board}') from exc
        if not callable(getattr(driver, 'manual_set', None)):
            raise RuntimeError(
                f'RowBoard[{board}] firmware/software does not provide '
                'ManualSet')
        drivers[board] = driver
        targets.append((row, board, address, driver))
        log.debug(
            'FAS tune logical row %d resolved to board=%d address=%d',
            row, board, address)

    # Several logical rows may alias one physical line; preserve one snapshot
    # and later combine their candidates for each unique board/address pair.
    unique_targets = {}
    for _, board, address, driver in targets:
        unique_targets[(board, address)] = driver

    # Freeze settings for the run so a GUI edit cannot change the sweep midway.
    sweep_currents = np.linspace(
        process.FasFluxLowOffset.get(),
        process.FasFluxHighOffset.get(),
        process.FasFluxNumSteps.get(),
        endpoint=True)
    sweep_delay = process.FasFluxSampleDelay.get()
    minimum_tolerance = process.FasMinimumTolerance.get()

    # Launch all initial hardware reads together, then reconstruct the converted
    # currents from the refreshed shadows. These snapshots also drive cleanup.
    driver_items = list(drivers.items())
    board_count = len(driver_items)
    snapshots = warm_tdm_api.readAndCheck(
        group.SaFbForceCurrent,
        group.Sq1BiasForceCurrent,
        group.Sq1FbForceCurrent,
        group.SaFbCurrent,
        *(driver.Mode for _, driver in driver_items),
        *(driver.FasOn.Current for _, driver in driver_items),
        *(driver.FasOff.Current for _, driver in driver_items))
    (sa_fb_snapshot,
     sq1_bias_snapshot,
     sq1_fb_snapshot,
     sa_fb_table) = snapshots[:4]
    # Split the grouped result back into per-board lookup tables. Complete FAS
    # arrays replace repeated per-address reads inside the row loop.
    row_snapshots = snapshots[4:]
    mode_snapshot = dict(zip(
        drivers, row_snapshots[:board_count]))
    fas_on_tables = dict(zip(
        drivers, row_snapshots[board_count:2 * board_count]))
    fas_off_tables = dict(zip(
        drivers, row_snapshots[2 * board_count:]))
    fas_on_snapshot = {
        key: fas_on_tables[key[0]][key[1]]
        for key in unique_targets
    }
    log.debug(
        'FAS tune snapshots: modes=%s SaFbForceCurrent=%s '
        'Sq1BiasForceCurrent=%s Sq1FbForceCurrent=%s FasOn=%s',
        mode_snapshot, sa_fb_snapshot.tolist(), sq1_bias_snapshot.tolist(),
        sq1_fb_snapshot.tolist(), fas_on_snapshot)

    curves = []
    candidates = {}
    programming_started = False
    process.TotalSteps.set(len(active_rows) * len(sweep_currents))
    log.debug('FAS tune TotalSteps=%s', process.TotalSteps.value())

    try:
        # SQ1 must be biased for the simulated FAS response to be observable.
        # Preserve disabled columns while applying the bootstrap only to the
        # enabled force paths.
        bootstrap_bias = sq1_bias_snapshot.copy()
        bootstrap_fb = sq1_fb_snapshot.copy()
        bootstrap_bias[enabled_columns] = process.Sq1BiasCurrent.get()
        bootstrap_fb[enabled_columns] = 0.0
        log.debug(
            'FAS tune applying bootstrap SQ1 state to enabled columns: '
            'bias=%s feedback=%s',
            bootstrap_bias.tolist(), bootstrap_fb.tolist())
        warm_tdm_api.stageAndCommit(
            (group.Sq1FbForceCurrent, bootstrap_fb),
            (group.Sq1BiasForceCurrent, bootstrap_bias))

        # Every subsequent ManualSet assumes MANUAL mode. Stage all row-board
        # mode changes first and verify them in one grouped commit.
        for board, driver in drivers.items():
            log.debug('FAS tune setting RowBoard[%d] Mode=MANUAL', board)
        warm_tdm_api.stageAndCommit(*[
            (driver.Mode, 1) for driver in drivers.values()])

        for index, (row, board, address, _) in enumerate(targets):
            if not _pause_point(
                    process, lambda: process._publishResults(curves)):
                process.Message.set('Stopped by user; FasOn unchanged')
                return curves

            log.debug(
                'FAS tune starting logical row %d (%d/%d), board=%d '
                'address=%d',
                row, index + 1, len(targets), board, address)
            process.Message.set(
                f'FAS row {row} ({index + 1}/{len(targets)})')

            # Timing is stopped during FAS tuning, so the per-row SAFb RAM is
            # not driving the DAC. Explicitly copy this row's SA-tuned values
            # into the force-current path before starting the software servo.
            # Starting on the fitted SA branch avoids inheriting a stale or
            # railed override value from an earlier operation.
            row_sa_fb = sa_fb_snapshot.copy()
            for column in enabled_columns:
                row_sa_fb[column] = sa_fb_table[column, row]
            log.debug(
                'FAS tune logical row %d applying SA-tuned feedback to '
                'force-current path: %s', row, row_sa_fb.tolist())
            group.SaFbForceCurrent.set(row_sa_fb)

            curve = fasSweep(
                group=group,
                row=row,
                board=board,
                address=address,
                driver=drivers[board],
                enabled_mask=enabled_mask,
                off_current=fas_off_tables[board][address],
                currents=sweep_currents,
                delay=sweep_delay,
                process=process,
                publish=lambda data: process._publishResults(
                    curves + [data]))
            curves.append(curve)
            if not _pause_point(
                    process, lambda: process._publishResults(curves)):
                log.debug(
                    'FAS tune stopped after logical row %d; '
                    'leaving FasOn unchanged', row)
                process.Message.set('Stopped by user; FasOn unchanged')
                return curves

            # Select a minimum for each enabled column, then use the median so
            # one noisy or marginal column cannot dominate the physical line.
            minima = []
            for column in enabled_columns:
                points = curve.curveList[column].points
                if points:
                    minimum, low, high, minimum_value = _fas_minimum_center(
                        curve.xValues, points, minimum_tolerance)
                    minima.append(minimum)
                    log.debug(
                        'FAS tune row %d column %d minimum-region center=%s '
                        'uA indices=%d..%d x=%s..%s uA minimum=%s uA '
                        'tolerance=%s uA from %d point(s)',
                        row, column, minimum, low, high,
                        curve.xValues[low], curve.xValues[high],
                        minimum_value, minimum_tolerance, len(points))
            if not minima:
                log.error(
                    'FAS tune logical row %d produced no enabled-column '
                    'samples', row)
                raise RuntimeError(
                    f'No FAS samples were collected for logical row {row}')
            row_candidate = float(np.median(minima))
            candidates.setdefault((board, address), []).append(row_candidate)
            log.debug(
                'FAS tune row %d candidate=%s uA from minima=%s',
                row, row_candidate, np.asarray(minima).tolist())

        # Collapse aliased logical-row candidates to one programmed current per
        # physical board/address pair.
        selected = {
            key: float(np.median(values))
            for key, values in candidates.items()
        }
        log.debug(
            'FAS tune physical-line candidates=%s selected=%s',
            candidates, selected)

        for curve in curves:
            curve.fasOn = selected[(curve.board, curve.address)]

        if not _pause_point(
                process, lambda: process._publishResults(curves)):
            log.debug('FAS tune stopped before FasOn programming')
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        if not doSet:
            log.debug(
                'FAS tune SetAfterFinish is disabled; leaving FasOn unchanged '
                'and publishing candidates=%s', selected)
            return curves

        # Defer all persistent writes until acquisition and fitting succeed,
        # then stage every selected FasOn entry before one grouped commit.
        programming_started = True
        for key, current in selected.items():
            log.debug(
                'FAS tune staging RowBoard[%d] FasOn[%d]=%s uA',
                key[0], key[1], current)
        warm_tdm_api.stageAndCommit(*[
            (unique_targets[key].FasOn.Current, current, key[1])
            for key, current in selected.items()
        ])

        # Catch Stop arriving during the grouped register transaction. A Pause
        # waits here and resumes without rolling back the completed write.
        if not _pause_point(
                process, lambda: process._publishResults(curves)):
            log.debug(
                'FAS tune rolling back FasOn after Stop: snapshot=%s',
                fas_on_snapshot)
            for key, original in fas_on_snapshot.items():
                log.debug(
                    'FAS tune staging rollback RowBoard[%d] FasOn[%d]=%s uA',
                    key[0], key[1], original)
            warm_tdm_api.stageAndCommit(*[
                (unique_targets[key].FasOn.Current, original, key[1])
                for key, original in fas_on_snapshot.items()
            ])
            programming_started = False
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        log.debug('FAS tune programming complete: selected=%s', selected)
        process.Message.set('FAS tune complete')
        return curves

    except Exception:
        log.exception('FAS tune failed')
        if programming_started:
            log.debug(
                'FAS tune rolling back FasOn after failure: snapshot=%s',
                fas_on_snapshot)
            for key, current in fas_on_snapshot.items():
                log.debug(
                    'FAS tune staging rollback RowBoard[%d] FasOn[%d]=%s uA',
                    key[0], key[1], current)
            warm_tdm_api.stageAndCommit(*[
                (unique_targets[key].FasOn.Current, current, key[1])
                for key, current in fas_on_snapshot.items()
            ])
        raise
    finally:
        # Manual outputs and force-current overrides are temporary measurement
        # state. Restore them even when fitting or persistent programming fails.
        log.debug('FAS tune cleanup starting')
        for key, driver in unique_targets.items():
            try:
                off_current = fas_off_tables[key[0]][key[1]]
                log.debug(
                    'FAS tune cleanup RowBoard[%d] address=%d '
                    'ManualSet FasOff=%s uA',
                    key[0], key[1], off_current)
                request = driver.manual_set(
                    address=key[1], current=off_current, check_mode=False)
                log.debug(
                    'FAS tune cleanup RowBoard[%d] address=%d result=%s',
                    key[0], key[1], request)
            except Exception as exc:
                log.error(
                    'Failed to return row board %s address %s to FasOff: %s',
                    key[0], key[1], exc)
        log.debug(
            'FAS tune restoring force currents as one transaction group: '
            'SaFb=%s Sq1Bias=%s Sq1Fb=%s',
            sa_fb_snapshot.tolist(), sq1_bias_snapshot.tolist(),
            sq1_fb_snapshot.tolist())
        for board, mode in mode_snapshot.items():
            log.debug(
                'FAS tune staging RowBoard[%d] Mode=%s', board, mode)
        warm_tdm_api.stageAndCommit(
            (group.SaFbForceCurrent, sa_fb_snapshot),
            (group.Sq1BiasForceCurrent, sq1_bias_snapshot),
            (group.Sq1FbForceCurrent, sq1_fb_snapshot),
            *[(drivers[board].Mode, mode)
              for board, mode in mode_snapshot.items()])
        log.debug('FAS tune cleanup complete')

# SQ1 tuning
def sq1FbSweep(*, group, bias, fbRange, process, curves=None,
               publish=None):
    """Measure SA response versus SQ1 feedback at one SQ1-bias point.

    Each feedback vector is applied through the SQ1 force-current path. In the
    normal closed-loop mode, :func:`saFbServo` records the SA feedback required
    to null the output; ``ServoDisable`` instead records open-loop ``SaOut`` for
    diagnostics.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being tuned.
    bias : array-like
        SQ1-bias current associated with each column's curve.
    fbRange : numpy.ndarray
        SQ1-feedback currents shaped ``(num_columns, num_steps)``.
    process : Sq1TuneProcess
        Supplies servo configuration, progress, and Stop/Pause handling.
    curves : list[Curve], optional
        Existing per-column curves to extend for partial-result publication.
    publish : callable, optional
        Publishes the enclosing row result before a pause.

    Returns
    -------
    list[Curve]
        One response curve per logical column, possibly partial after Stop.

    Notes
    -----
    The SQ1-feedback force path remains at the last attempted sweep value. The
    caller establishes the next value or restores operating state.
    """
    colCount = group.NumColumns.get()
    if curves is None:
        curves = [warm_tdm_api.Curve(bias[i]) for i in range(colCount)]
    numSteps = len(fbRange[0])
    log = process._log
    servoDisable = process.ServoDisable.get()
    log.debug(
        'SQ1 FB sweep start: bias=%s steps=%d servoDisable=%s '
        'feedbackLow=%s feedbackHigh=%s',
        np.asarray(bias).tolist(), numSteps, servoDisable,
        np.asarray(fbRange[:, 0]).tolist(),
        np.asarray(fbRange[:, -1]).tolist())

    for fbStep in range(numSteps):
        if not _pause_point(process, publish):
            log.debug(
                'SQ1 FB sweep stopped before step %d/%d',
                fbStep + 1, numSteps)
            break

        # Apply one complete feedback vector; the Group tune mask prevents
        # writes to disabled columns.
        feedback = fbRange[:, fbStep]
        log.debug(
            'SQ1 FB sweep step %d/%d writing feedback=%s',
            fbStep + 1, numSteps, np.asarray(feedback).tolist())
        group.Sq1FbForceCurrent.set(feedback)


        if servoDisable is False:
            # Closed loop: measure the SA-feedback correction needed for null.
            log.debug(
                'SQ1 FB sweep step %d/%d starting SA FB servo',
                fbStep + 1, numSteps)
            points = saFbServo(
                group=group, process=process, publish=publish)
        else:
            # Open loop is retained as a diagnostic view of raw SA response.
            points = group.SaOut.get()

        if not _pause_point(process, publish):
            log.debug(
                'SQ1 FB sweep stopped during step %d/%d; '
                'discarding incomplete point',
                fbStep + 1, numSteps)
            break

        log.debug(
            'SQ1 FB sweep step %d/%d response=%s',
            fbStep + 1, numSteps, np.asarray(points).tolist())

        # A point is valid only after the servo completes without Stop.
        for col in range(colCount):
            curves[col].addPoint(points[col])

        process._incrementSteps(1)
        log.debug(
            'SQ1 FB sweep step %d/%d recorded', fbStep + 1, numSteps)

        if not _pause_point(process, publish):
            break

    log.debug(
        'SQ1 FB sweep complete: collectedPoints=%s',
        [len(curve.points) for curve in curves])
    return curves


def sq1BiasSweep(group, process, rowIndex, doBiasRamp=True,
                 completedOutputs=None):
    """Acquire SQ1-feedback curve families for one active logical row.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group being tuned.
    process : Sq1TuneProcess
        Supplies SQ1 sweep settings, servo controls, and result publication.
    rowIndex : int
        Logical row currently selected on the row boards.
    doBiasRamp : bool, default=True
        Sweep the configured SQ1-bias range when true. When false, acquire one
        feedback curve at the loaded per-row SQ1-bias value for each column.
    completedOutputs : list, optional
        Results from earlier rows, included when publishing this partial row.

    Returns
    -------
    list[CurveData]
        One fitted SQ1 curve family per logical column for ``rowIndex``.
        Disabled columns remain empty and are not written.

    Notes
    -----
    Bias and feedback are driven through force-current overrides because timing
    is stopped during tuning. Their last sweep values remain applied until the
    caller changes or restores them.
    """

    # Freeze sweep dimensions and ranges before any hardware changes.
    colCount = group.NumColumns.get()
    log = process._log
    numBiasSteps = process.Sq1BiasNumSteps.get() if doBiasRamp else 1
    numFbSteps = process.Sq1FbNumSteps.get()
    if doBiasRamp:
        # Every column uses the configured range, represented in column-major
        # form for vector writes and per-column curve fitting.
        bias_values = np.linspace(
            process.Sq1BiasLowOffset.get(),
            process.Sq1BiasHighOffset.get(),
            numBiasSteps,
            endpoint=True)
        biasRange = np.broadcast_to(
            bias_values, (colCount, numBiasSteps)).copy()
    else:
        # Read all enabled per-row bias RAMs together, then select this row from
        # the cached two-dimensional table.
        loaded_biases = group.Sq1BiasCurrent.get()
        biasRange = loaded_biases[:, rowIndex].reshape(colCount, 1)

    fb_values = np.linspace(
        process.Sq1FbLowOffset.get(),
        process.Sq1FbHighOffset.get(),
        numFbSteps,
        endpoint=True)
    fbRange = np.broadcast_to(
        fb_values, (colCount, numFbSteps)).copy()

    colTuneEnable = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    datalist = [
        warm_tdm_api.CurveData(xValues=fbRange[col])
        for col in range(colCount)]
    if completedOutputs is None:
        completedOutputs = []
    # Include the in-progress row after all fully completed earlier rows.
    publish = lambda: process._publishResults(
        completedOutputs + [datalist])

    log.debug(
        'SQ1 bias sweep row=%s start: doBiasRamp=%s enabledMask=%s '
        'biasSteps=%d feedbackSteps=%d biasLow=%s biasHigh=%s '
        'feedbackLow=%s feedbackHigh=%s',
        rowIndex, doBiasRamp, colTuneEnable.tolist(), numBiasSteps, numFbSteps,
        np.asarray(biasRange[:, 0]).tolist(),
        np.asarray(biasRange[:, -1]).tolist(),
        np.asarray(fbRange[:, 0]).tolist(),
        np.asarray(fbRange[:, -1]).tolist())

    # Attach each bias curve before acquisition so Pause can display an
    # incomplete feedback sweep without fabricating missing samples.
    for biasStep in range(numBiasSteps):
        if not _pause_point(process, publish):
            log.debug(
                'SQ1 bias sweep row=%s stopped before bias step %d/%d',
                rowIndex, biasStep + 1, numBiasSteps)
            break

        curves = [
            warm_tdm_api.Curve(biasRange[col, biasStep])
            for col in range(colCount)]
        for col in range(colCount):
            if colTuneEnable[col]:
                datalist[col].addCurve(curves[col])

        # Apply the current bias point to all enabled columns in one Group write.
        bias = biasRange[:, biasStep]
        log.debug(
            'SQ1 bias sweep row=%s step %d/%d writing bias=%s',
            rowIndex, biasStep + 1, numBiasSteps,
            np.asarray(bias).tolist())
        group.Sq1BiasForceCurrent.set(bias)

        # Sweep feedback and servo SA output back to zero at every point.
        curves = sq1FbSweep(
            group=group,
            bias=bias,
            fbRange=fbRange,
            process=process,
            curves=curves,
            publish=publish)

        log.debug(
            'SQ1 bias sweep row=%s step %d/%d complete: '
            'collectedPoints=%s',
            rowIndex, biasStep + 1, numBiasSteps,
            [len(curve.points) for curve in curves])

        # Do not begin another bias curve after an interrupted inner sweep.
        if not _pause_point(process, publish):
            log.debug(
                'SQ1 bias sweep row=%s stopped after bias step %d/%d',
                rowIndex, biasStep + 1, numBiasSteps)
            break


    # Fit each curve family to choose SQ1 bias, SQ1 feedback, and corresponding
    # SA-feedback operating point.
    for d in datalist:
        d.update()

    log.debug(
        'SQ1 bias sweep row=%s complete: results=%s',
        rowIndex,
        [
            {
                'column': col,
                'enabled': bool(colTuneEnable[col]),
                'biasOut': data.biasOut,
                'xOut': data.xOut,
                'yOut': data.yOut,
            }
            for col, data in enumerate(datalist)
        ])
    return datalist

def sq1Tune(group, process, doBiasRamp=True):
    """Run SQ1 bias/feedback acquisition for every active logical row.

    Before tuning, this routine reads the complete SA-feedback row table once.
    For each logical row it copies that row's SA-tuned feedback into the force
    path, activates the row, acquires its SQ1 curve families, and guarantees row
    deactivation afterward.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing active-row order, SA operating points, and SQ1 controls.
    process : Sq1TuneProcess
        Supplies sweep/servo settings, progress, and partial-result publication.
    doBiasRamp : bool, default=True
        Sweep SQ1 bias for every row when true; otherwise acquire one curve at
        each row's loaded SQ1-bias values.

    Returns
    -------
    list[list[CurveData]]
        Results indexed by completed active-row position and then logical column.
        A stopped run may contain fewer rows and a partial final row is published
        by the process rather than appended to this return value.

    Raises
    ------
    RuntimeError
        If no active rows or no tuning columns are enabled.

    Notes
    -----
    This function measures and fits SQ1 operating points; it does not program
    the fitted values into the per-row SQ1 bias/feedback readout RAMs.
    """
    # Resolve active rows and columns once so the topology cannot change during
    # a long-running tune.
    outputs = []
    rowTuneList = [
        int(row) for row in group.RowIndexOrderList.get(read=True)]
    colTuneEnable = np.asarray(group.ColTuneEnable.get(), dtype=bool)
    enabledColumns = [
        col for col, enabled in enumerate(colTuneEnable) if enabled]
    numEnabledRows = len(rowTuneList)

    numBiasSteps = process.Sq1BiasNumSteps.get() if doBiasRamp else 1
    totalSteps = numEnabledRows * numBiasSteps * process.Sq1FbNumSteps.get()
    process.TotalSteps.set(totalSteps)
    log = process._log
    log.info(
        'SQ1 tune starting: rows=%s enabledColumns=%s doBiasRamp=%s '
        'totalSteps=%d',
        list(rowTuneList),
        enabledColumns,
        doBiasRamp, totalSteps)
    log.debug(
        'SQ1 tune servo configuration: kp=%s ki=%s kd=%s precision=%s '
        'maxLoops=%s disable=%s',
        process.ServoKp.get(), process.ServoKi.get(), process.ServoKd.get(),
        process.ServoPrecision.get(), process.ServoMaxLoops.get(),
        process.ServoDisable.get())

    if not rowTuneList:
        log.error('SQ1 tune rejected because the active row list is empty')
        raise RuntimeError('SQ1 tuning requires at least one active row')
    if not enabledColumns:
        log.error('SQ1 tune rejected because no columns are enabled')
        raise RuntimeError('SQ1 tuning requires at least one enabled column')

    # Fetch the force-current baseline and every enabled column's SA row table
    # together. Subsequent row changes use only these cached arrays.
    sa_fb_force_base, sa_fb_table = warm_tdm_api.readAndCheck(
        group.SaFbForceCurrent, group.SaFbCurrent)

    def loadSaFbSetpoints(rowIndex):
        """Apply one row's SA-tuned feedback through the force-current path."""
        # Timing is stopped, so the readout RAM does not drive the DAC. Begin
        # from the saved baseline to preserve every disabled column.
        rowSaFb = sa_fb_force_base.copy()
        for column in enabledColumns:
            rowSaFb[column] = sa_fb_table[column, rowIndex]
        log.debug(
            'SQ1 tune row=%s applying per-row SA feedback setpoints to '
            'force-current path: %s', rowIndex, rowSaFb.tolist())
        group.SaFbForceCurrent.set(rowSaFb)

    # Establish offset from the first row's known SA operating branch before
    # any SQ1 stimulus is applied.
    loadSaFbSetpoints(rowTuneList[0])
    log.debug('SQ1 tune starting initial SA offset adjustment')
    saOffset(
        group=group,
        process=process,
        publish=lambda: process._publishResults(outputs))
    log.debug('SQ1 tune initial SA offset adjustment complete')
    
    for rowNumber, rowIndex in enumerate(rowTuneList):
        if not _pause_point(
                process, lambda: process._publishResults(outputs)):
            log.info('SQ1 tune stopped before row %s', rowIndex)
            break

        # Each row can occupy a different SA branch. Row zero is already loaded
        # above; load subsequent rows immediately before activation.
        if rowNumber != 0:
            loadSaFbSetpoints(rowIndex)

        # Row activation/deactivation spans only this row's bias/feedback sweep.
        log.debug(
            'SQ1 tune activating row %s (%d/%d)',
            rowIndex, rowNumber + 1, numEnabledRows)
        group.ActivateRowIndex(rowIndex)
        try:
            # Collect one CurveData family per logical column for this row.
            log.info(
                'SQ1 tune starting bias sweep for row %s (%d/%d)',
                rowIndex, rowNumber + 1, numEnabledRows)
            results = sq1BiasSweep(
                group, process, rowIndex=rowIndex,
                doBiasRamp=doBiasRamp,
                completedOutputs=outputs)
            for i, result in enumerate(results):
                log.debug(
                    'SQ1 tune row=%s column=%s result: '
                    'bias=%s xOut=%s yOut=%s',
                    rowIndex, i, result.biasOut,
                    result.xOut, result.yOut)

            outputs.append(results)
        finally:
            log.debug('SQ1 tune deactivating row %s', rowIndex)
            group.DeactivateRowIndex(rowIndex)

    log.info(
        'SQ1 tune complete: collected %d/%d row result(s)',
        len(outputs), numEnabledRows)
    return outputs



def sq1Ramp(group, row, column, low_offset=-77.0, high_offset=77.0, step=1.0):
    """Run a diagnostic SQ1-feedback ramp for one row/column operating point.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing the SQ1-feedback RAM and force-current controls.
    row : int
        Logical row used to read the ramp center. The caller must activate the
        desired row when required; this function does not change row selection.
    column : int
        Logical column whose SQ1 feedback is swept.
    low_offset, high_offset : float
        Inclusive feedback offsets relative to the loaded ``(column, row)``
        operating point, in microamps.
    step : float
        Feedback-current increment in microamps.

    Returns
    -------
    list[numpy.ndarray]
        SA-offset servo result for every requested feedback point.

    Notes
    -----
    Only ``column`` is written through the SQ1-feedback force path. The final
    feedback and SA-offset controls remain applied after the ramp.
    """
    # Center the diagnostic span on the configured per-row readout value rather
    # than on whatever temporary force-current value happens to be active.
    center = group.Sq1FbCurrent.get(index=(column, row))
    low = center + low_offset
    high = center + high_offset
    numSteps = int((high - low) / step) + 1
    group._log.info(f'sq1Ramp row={row}, col={column}: center={center:.2f}, {numSteps} steps')

    # Each stimulus point requires a fresh SA-offset convergence measurement.
    outputs = []
    for fb in np.arange(low, high + step, step):
        group.Sq1FbForceCurrent.set(value=fb, index=column)
        offset = saOffset(group=group)
        outputs.append(offset)
    return outputs

def sq1RampRow(group, column, **kwargs):
    """Run :func:`sq1Ramp` for every hardware row on one column.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group whose rows are activated in turn.
    column : int
        Logical column to ramp.
    **kwargs
        Forwarded to :func:`sq1Ramp`.

    Returns
    -------
    list[list[numpy.ndarray]]
        Ramp results indexed by hardware row and then feedback point.

    Notes
    -----
    This diagnostic iterates ``MaxRows``, not ``RowIndexOrderList``.
    """
    numRows = group.MaxRows.get()
    group._log.info(f'sq1RampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(sq1Ramp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results


def tesRamp(group, row, column, low_offset=0.0, high_offset=100.0, step=1.0):
    """Run a diagnostic TES-bias ramp while measuring required SA offset.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group containing TES-bias and SA-offset controls.
    row : int
        Logical row associated with the diagnostic. The caller is responsible
        for row activation; TES bias itself is column-wide.
    column : int
        Logical TES-bias column to sweep.
    low_offset, high_offset : float
        Half-open bias span relative to the current TES-bias value, in microamps.
    step : float
        TES-bias increment in microamps.

    Returns
    -------
    list[numpy.ndarray]
        SA-offset servo result for every requested TES-bias point.

    Notes
    -----
    The final TES-bias and SA-offset controls remain applied after the ramp.
    """
    # Use the currently loaded bias as the origin for the requested relative span.
    center = group.TesBias.get(index=column)
    low = center + low_offset
    high = center + high_offset
    numSteps = int((high - low) / step)
    group._log.info(f'tesRamp row={row}, col={column}: center={center:.2f}, {numSteps} steps')

    outputs = []
    for bias in np.arange(low, high, step):
        group.TesBias.set(index=column, value=bias)
        offset = saOffset(group=group)
        outputs.append(offset)
    return outputs

def tesRampRow(group, column, **kwargs):
    """Run :func:`tesRamp` for every hardware row on one column.

    Parameters
    ----------
    group : warm_tdm_api.Group
        Group whose rows are activated in turn.
    column : int
        Logical TES-bias column to ramp.
    **kwargs
        Forwarded to :func:`tesRamp`.

    Returns
    -------
    list[list[numpy.ndarray]]
        Ramp results indexed by hardware row and then TES-bias point.

    Notes
    -----
    This diagnostic iterates ``MaxRows``, not ``RowIndexOrderList``.
    """
    numRows = group.MaxRows.get()
    group._log.info(f'tesRampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(tesRamp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results
