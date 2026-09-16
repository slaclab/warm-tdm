"""SQ1 (first-stage SQUID) tuning.

For each active logical row, sweep SQ1 feedback across a family of SQ1-bias
points, using the shared :func:`saFbServo` to null the SA output at each point,
and fit each column's operating point. Row SA-feedback setpoints come from the
prior SA tune via the shared :func:`saOffset` startup step.
"""

import numpy as np

import warm_tdm_api

from ._common import _pause_point, saOffset, saFbServo


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


def sq1BiasSweep(*, group, process, rowIndex, doBiasRamp=True,
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

    colTuneEnable = group.colEnableBools
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


def sq1Tune(group, process, doSet=True, doBiasRamp=True):
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
    doSet : bool, default=True
        Program the fitted per-(column, row) lock point into the readout tables
        (``Sq1FbCurrent``/``Sq1BiasCurrent``/``SaFbCurrent``) after a complete
        sweep. Mirrors :func:`saTune`'s apply; a stopped run leaves the tables
        unchanged.
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
        If no active rows or no tuning columns are enabled, or (when ``doSet``)
        an enabled column/row produced no fitted operating point.
    """
    # Resolve active rows and columns once so the topology cannot change during
    # a long-running tune.
    outputs = []
    rowTuneList = [
        int(row) for row in group.RowReadoutOrder.get(read=True)]
    colTuneEnable = group.colEnableBools
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

    # Cache the force-current baseline and SA row tables for subsequent rows.
    sa_fb_force_base = group.SaFbForceCurrent.get()
    sa_fb_table = group.SaFbCurrent.get()

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

    completed = True
    for rowNumber, rowIndex in enumerate(rowTuneList):
        if not _pause_point(
                process, lambda: process._publishResults(outputs)):
            log.info('SQ1 tune stopped before row %s', rowIndex)
            completed = False
            break

        # Each row can occupy a different SA branch. Row zero is already loaded
        # above; load subsequent rows immediately before activation.
        if rowNumber != 0:
            loadSaFbSetpoints(rowIndex)

        # Row activation/deactivation spans only this row's bias/feedback sweep.
        log.debug(
            'SQ1 tune activating row %s (%d/%d)',
            rowIndex, rowNumber + 1, numEnabledRows)
        group.ManualRowOn(rowIndex)
        try:
            # Collect one CurveData family per logical column for this row.
            log.info(
                'SQ1 tune starting bias sweep for row %s (%d/%d)',
                rowIndex, rowNumber + 1, numEnabledRows)
            results = sq1BiasSweep(
                group=group, process=process, rowIndex=rowIndex,
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
            group.ManualRowOff(rowIndex)

        # A Stop inside the final row's sweep never reaches another loop-entry
        # check. Keep even fitted partial results from being applied in that case.
        if not _pause_point(process, lambda: process._publishResults(outputs)):
            completed = False
            break

    log.info(
        'SQ1 tune complete: collected %d/%d row result(s)',
        len(outputs), numEnabledRows)

    if doSet and completed and outputs:
        # Program the fitted per-(column, row) lock point into the readout
        # tables, mirroring saTune's apply. Read the whole tables so untuned
        # rows/columns are preserved; the Group setters mask disabled columns.
        sq1FbTable = group.Sq1FbCurrent.get(read=False)
        sq1BiasTable = group.Sq1BiasCurrent.get(read=False)
        saFbTable = group.SaFbCurrent.get(read=False)
        for rowNumber, results in enumerate(outputs):
            rowIndex = rowTuneList[rowNumber]
            for col in enabledColumns:
                result = results[col]
                if any(value is None or not np.isfinite(value)
                       for value in (result.xOut, result.biasOut, result.yOut)):
                    raise RuntimeError(
                        f'SQ1 tune produced no fitted operating point for '
                        f'enabled column {col}, row {rowIndex}')
                sq1FbTable[col, rowIndex] = result.xOut
                sq1BiasTable[col, rowIndex] = result.biasOut
                saFbTable[col, rowIndex] = result.yOut
        log.debug('SQ1 tune applying fitted lock point to '
                  'Sq1Fb/Sq1Bias/SaFb readout tables')
        group.Sq1FbCurrent.set(sq1FbTable)
        group.Sq1BiasCurrent.set(sq1BiasTable)
        group.SaFbCurrent.set(saFbTable)
    elif doSet and not completed:
        log.info('SQ1 tune stopped; leaving partial results unapplied')

    return outputs
