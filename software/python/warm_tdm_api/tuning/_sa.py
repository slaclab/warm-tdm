"""SA (Series Array) amplifier tuning.

Sweep SA output versus SA feedback across a family of SA-bias points, fit each
column's response, and optionally program the fitted bias/feedback operating
point. Builds on the shared :func:`saOffset` primitive.
"""

import numpy as np
import time

import warm_tdm_api

from ._common import _pause_point, saOffset


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
