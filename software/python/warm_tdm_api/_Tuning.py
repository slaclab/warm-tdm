import numpy as np
import time

from simple_pid import PID
import warm_tdm_api


def _fas_minimum_center(x_values, points, tolerance):
    """Return the center of the contiguous near-minimum region.

    Start at the global minimum and expand in both directions while adjacent
    samples remain within ``tolerance`` of it. This avoids the low-current bias
    of ``argmin()`` when the servo response has a flat, quantized bottom.
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


def saOffset(*, group, process=None):
    """Returns float.
    Run PID loops to determine saOffset that properly offsets saBias
    """

    # Get parameters from the Process
    kp = group.SaOffsetProcess.Kp.get()
    ki = group.SaOffsetProcess.Ki.get()
    kd = group.SaOffsetProcess.Kd.get()
    precision = group.SaOffsetProcess.Precision.get()
    maxLoops = group.SaOffsetProcess.MaxLoops.get()
    colCount = group.NumColumns.get()    

    # Setup PID controller
    pid = [PID(kp, ki, kd) for _ in range(group.NumColumns.get())]

    for p in pid:
        p.setpoint = 0  # want to zero out SaOut
        p.output_limits = (-0.5, 0.5)
        p.sample_time = None

    # Final output should be near SaBias, so start near there
    # Start at half the current bias
    # control = np.zeros(group.NumColumns.get())
    control = group.SaBiasVoltage.get() * 0.9

    group.SaOffset.set(value=control)


    current = group.SaOutAdc.get()
    masked = current

    mult = np.array([1 if en else 0 for en in group.ColTuneEnable.value()],np.float64)
    count = 0

    while count < maxLoops:
        count += 1

        current = group.SaOutAdc.get()
        masked = current * mult

        # All channels have converged
        done = [precision > masked[i] > (-1.0)*precision for i in range(len(masked))]
        if all(done):
            break
#         if (max(masked) < precision) and (min(masked) > (-1.0*precision)):
#             break

        for i, p in enumerate(pid):
            if done[i] == False:
                change = p(masked[i])
                control[i] = np.clip(control[i] + change, 0, 4.999)
                group.SaOffset.set(control[i], index=i)

#         group.SaOffset.set(control)

        if process is not None and process._runEn is False:
            return control

    if count == maxLoops:
        group._log.warning(f'saOffset failed to converge: ADC={masked}, control={control}')
        raise Exception(f"saOffset PID loop failed to converge after {maxLoops} loops")
    else:
        group._log.info(f'saOffset PID loop converged after {count} loops')

    return control




#SA TUNING
def saFbSweep(*, group, bias, saFbRange, process):
    """Returns a list of Curves objects.
    Iterate over a range of SaFb values for each column at a single SaBias point.
    Capture SaOut value at each step
    Return list of Curve objects containing curves for each column
    """
    row = 0
    colCount = group.NumColumns.get()
    curves = [warm_tdm_api.Curve(bias[i]) for i in range(colCount)]

    saFbArray = np.zeros(colCount, np.float64)

    numSteps = len(saFbRange[0])

    sleep = group.SaTuneProcess.SaFbSampleDelay.get()

    # Iterate through the steps
    for idx in range(numSteps):

        # Bail promptly on Stop(): this inner sweep is long in cosim, so without
        # a per-step check a Stop() would wait for the whole sweep to finish.
        if process is not None and process._runEn is False:
            group._log.info('Process stopped, exiting saFbSweep')
            break

        # Setup data
        group.SaFbForceCurrent.set(saFbRange[:, idx])

        time.sleep(sleep)
        points = group.SaOut.get()

        for col in range(colCount):
            curves[col].addPoint(points[col])

        if process is not None:
            process._incrementSteps(1)
            #Progress.set(pctLow + pctRange*((idx+1)/numSteps))

        adcs = group.SaOutAdc.get()
        if np.any(np.abs(adcs) > 0.8):
            group._log.warning(f'High ADC value seen: SaBias={bias}, SaFb={saFbRange[:, idx]}, ADCs={adcs}')
            saOffset(group=group, process=process)
            group._log.debug('After re-offset: SaOffset=%s, ADC=%s, SaOut=%s', group.SaOffset.get(), group.SaOutAdc.get(), group.SaOut.get())

    # Reset FB to zero after sweep
    group.SaFbForceCurrent.set(value=np.zeros(colCount, np.float64))

    return curves

def saBiasSweep(*, group, process, doBiasRamp=True):
    """Returns a list of CurveData objects.
    Creates a list of CurveData objects, corresponding to each column.
    Iterates through SaBias values determined by Rogue variables.
    Calls saFbSweep to generate curves, adding them
    to their corresponding data objects
    """

    # Extract iteration steps from Rogue variables
    # Create CurveData obects for storing output data
    colCount = group.NumColumns.get()
    colTuneEnable = group.ColTuneEnable.value()    
    numBiasSteps = group.SaTuneProcess.SaBiasNumSteps.get() if doBiasRamp else 1
    numFbSteps = group.SaTuneProcess.SaFbNumSteps.get()
    saBiasRange = np.zeros((colCount, numBiasSteps), np.float64)
    saFbRange = np.zeros((colCount, numFbSteps), np.float64)
    loadedBiases = None if doBiasRamp else np.asarray(group.SaBiasCurrent.get(), dtype=np.float64)

    datalist = []    
    for col in range(colCount):
        if doBiasRamp:
            low = group.SaTuneProcess.SaBiasLowOffset.get()
            high = group.SaTuneProcess.SaBiasHighOffset.get()
            saBiasRange[col] = np.linspace(low,high,numBiasSteps,endpoint=True)
        else:
            # Retune at the bias values already loaded into the readout configuration.
            saBiasRange[col, 0] = loadedBiases[col]

        low = group.SaTuneProcess.SaFbLowOffset.get()
        high = group.SaTuneProcess.SaFbHighOffset.get()
        saFbRange[col] = np.linspace(low,high,numFbSteps,endpoint=True)

        datalist.append(warm_tdm_api.CurveData(xValues=saFbRange[col]))
    
            
    if process is not None:
        process.TotalSteps.set(numBiasSteps * numFbSteps)


    # Iterate over each SA Bias point
    # Set the SaBias, set the proper Offset
    # Sweep the SaFb range with saFbSweep()
    for idx in range(numBiasSteps):
        group.SaFbForceCurrent.set(np.zeros(colCount, np.float64))
        group.Sq1BiasForceCurrent.set(np.zeros(colCount, np.float64))
        group.Sq1FbForceCurrent.set(np.zeros(colCount, np.float64))        
        # Update process message 
        if process is not None:
            process.Message.set(f'SaBias step {idx+1} out of {numBiasSteps}')
        

        group.SaBiasCurrent.set(saBiasRange[:, idx])
        group.SaOffset.set(value=np.zeros(colCount, np.float64))
        adcs = group.SaOutAdc.get()
        group._log.info(f'SA Bias step {idx+1}/{numBiasSteps} - ADC before offset = {adcs}')
        saOffset(group=group, process=process)

        curves = saFbSweep(group=group,bias=saBiasRange[:, idx], saFbRange=saFbRange, process=process)

        for col in range(colCount):
            # Only add the curve if column is enabled for tuning
            if colTuneEnable[col]:
                datalist[col].addCurve(curves[col])

        # check for stopped process
        if process is not None and process._runEn == False:
            group._log.info('Process stopped, exiting saBiasSweep')
            break

    for d in datalist:
        d.update()

    # Return SaBias back to initial values
    #group.SaBias.set(start)
    #saOffset(group)


    return datalist

def saTune(*, group, process=None, doSet=True, doBiasRamp=True):
    """
    Initializes group, runs saFluxBias and collects and sets SaFb, SaOffset, and SaBias
    Returns a list of CurveData objects
    Args
    ----
    group  : group
    pctVar : pr.Variable
        Variable to set current percentage complete

    Returns
    ----
    CurveData object where result of saOffset subroutine
     is plotted against SaFb values, which each curve
     representing a different bias.
    """
    group._log.info(f'saTune starting: doBiasRamp={doBiasRamp}, doSet={doSet}')

    colTuneEnable = np.asarray(group.ColTuneEnable.value(), dtype=bool)
    saBiasResults = saBiasSweep(group=group, process=process, doBiasRamp=doBiasRamp)

    stopped = process is not None and process._runEn is False
    if doSet and not stopped:
        # Tuning sweeps use the force-current path while timing is stopped.
        # Preserve disabled columns and replace enabled columns with the fitted
        # operating point so the final offset tune observes the same SA
        # feedback that is stored in the per-row readout table below.
        tunedSaFb = np.array(
            group.SaFbForceCurrent.get(read=True), copy=True)

        # SA tune is per-column: saBiasSweep returns one tuned SaFb (xOut) per
        # column. The same value is written to every row slot, so this does not
        # depend on the row map — broadcast across the full maxRows address space
        # rather than the readout list (which may not be set yet when saTune runs).
        for col in range(group.NumColumns.get()):
            if not colTuneEnable[col]:
                group._log.debug(
                    'SA tune leaving disabled column %d unchanged', col)
                continue

            result = saBiasResults[col]
            if result.xOut is None or result.biasOut is None:
                raise RuntimeError(
                    f'SA tune produced no fitted result for enabled column {col}')

            # xOut represents the tuned saFB. Set it for every row.
            for row in range(group.MaxRows.get()):
                group.SaFbCurrent.set(
                    index=(col, row), value=result.xOut)
            tunedSaFb[col] = result.xOut
            # biasOut represents the tuned SA Bias point
            group.SaBiasCurrent.set(index=col, value=result.biasOut)

        group._log.debug(
            'SA tune applying fitted SaFb to force-current path before '
            'offset tune: %s', tunedSaFb.tolist())
        group.SaFbForceCurrent.set(tunedSaFb)

        # Run saOffset to zero out the ADC value at the tuned SaBias,SaFb point.
        saOffset(group=group, process=process)
    elif doSet:
        group._log.info('Process stopped; leaving partial SA tune results unapplied')

    group._log.info('saTune complete')
    return saBiasResults


#FAS TUNING
def saFbServo(*, group, process):
    """Returns list of SaFb values which zero out SaOut.
    Each element corresponds with a column
    """

    # Setup PID controller
    kp = process.ServoKp.get()
    ki = process.ServoKi.get()
    kd = process.ServoKd.get()
    precision = process.ServoPrecision.get()
    maxLoops = process.ServoMaxLoops.get()
    log = process._log
    log.debug(
        'SA FB servo start: kp=%s ki=%s kd=%s precision=%s maxLoops=%s',
        kp, ki, kd, precision, maxLoops)
    
    pid = [PID(kp, ki, kd) for _ in range(group.NumColumns.get())]

    for p in pid:
        p.setpoint = 0 # want to zero out SaOut
        p.output_limits = (-0.5, 0.5)
        p.sample_time   = None

    control = group.SaFbForceCurrent.get()

    current = group.SaOutAdc.get()
    masked = current
    mult = np.array([1 if en else 0 for en in group.ColTuneEnable.value()], np.float64)    
    log.debug(
        'SA FB servo initial state: enabledMask=%s control=%s adc=%s',
        mult.tolist(), np.asarray(control).tolist(), np.asarray(current).tolist())
    count = 0

    for count in range(maxLoops):
        if process._runEn is False:
            log.debug(
                'SA FB servo stopped before loop %d; returning control=%s',
                count + 1, np.asarray(control).tolist())
            return control

        current = group.SaOutAdc.get()
        masked = current * mult
        log.debug(
            'SA FB servo loop %d/%d: adc=%s masked=%s control=%s',
            count + 1, maxLoops, np.asarray(current).tolist(),
            np.asarray(masked).tolist(), np.asarray(control).tolist())

        # All channels have converged
        if (max(masked) < precision) and (min(masked) > (-1.0*precision)):
            log.debug(
                'SA FB servo converged after %d loop(s): control=%s',
                count + 1, np.asarray(control).tolist())
            break

        for i, p in enumerate(pid):
            change = p(masked[i])
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

def fasSweep(*, group, row, process):
    """Sweep the physical one-level FAS line mapped from ``row``."""
    log = process._log
    row_map = group.RowMap.get()
    mapping = row_map[row]
    log.debug('FAS sweep row %s mapping: %s', row, mapping)
    if 'csAddr' in mapping or 'csBoard' in mapping:
        log.error('FAS sweep row %s has unsupported two-level mapping: %s',
                  row, mapping)
        raise RuntimeError(
            'The simple FAS tune supports one-level RowMap entries only')

    board = int(mapping['rsBoard'])
    address = int(mapping['rsAddr'])
    driver = group.HardwareGroup.RowBoard[board].RowDacDriver
    if not callable(getattr(driver, 'manual_set', None)):
        log.error(
            'FAS sweep row %s cannot find manual_set on RowBoard[%s]',
            row, board)
        raise RuntimeError(
            f'RowBoard[{board}] firmware/software does not provide ManualSet')

    low = process.FasFluxLowOffset.get()
    high = process.FasFluxHighOffset.get()
    steps = process.FasFluxNumSteps.get()
    delay = process.FasFluxSampleDelay.get()
    enabled_columns = np.asarray(group.ColTuneEnable.get(), dtype=bool)
    currents = np.linspace(low, high, steps, endpoint=True)
    log.debug(
        'FAS sweep row %s start: board=%d address=%d low=%s high=%s '
        'steps=%d delay=%s currents=%s',
        row, board, address, low, high, steps, delay, currents.tolist())
    data = warm_tdm_api.CurveData(xValues=currents)
    for column in range(group.NumColumns.get()):
        data.addCurve(warm_tdm_api.Curve(column))

    off_current = driver.FasOff.Current.get(index=address, read=True)
    log.debug(
        'FAS sweep row %s captured FasOff[%d]=%s uA',
        row, address, off_current)
    try:
        for step, current in enumerate(currents):
            if not process._runEn:
                log.debug(
                    'FAS sweep row %s stopped before step %d/%d',
                    row, step + 1, len(currents))
                break
            request = driver.manual_set(address=address, current=current)
            log.debug(
                'FAS sweep row %s step %d/%d ManualSet: requested=%s uA '
                'result=%s',
                row, step + 1, len(currents), current, request)

            # Stop() waits for the worker thread, so keep a user-configured
            # settling delay interruptible rather than sleeping in one block.
            deadline = time.monotonic() + max(0.0, delay)
            while process._runEn and time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    break
                time.sleep(min(0.05, remaining))
            if not process._runEn:
                log.debug(
                    'FAS sweep row %s stopped while settling step %d/%d',
                    row, step + 1, len(currents))
                break

            log.debug(
                'FAS sweep row %s step %d/%d starting SA FB servo',
                row, step + 1, len(currents))
            points = saFbServo(group=group, process=process)
            if not process._runEn:
                log.debug(
                    'FAS sweep row %s stopped during SA FB servo at '
                    'step %d/%d', row, step + 1, len(currents))
                break
            log.debug(
                'FAS sweep row %s step %d/%d response=%s',
                row, step + 1, len(currents), np.asarray(points).tolist())
            for column, point in enumerate(points):
                if enabled_columns[column]:
                    data.curveList[column].addPoint(point)
            process._incrementSteps(1)
            log.debug(
                'FAS sweep row %s step %d/%d recorded',
                row, step + 1, len(currents))
    finally:
        log.debug(
            'FAS sweep row %s restoring board=%d address=%d to FasOff=%s uA',
            row, board, address, off_current)
        request = driver.manual_set(address=address, current=off_current)
        log.debug('FAS sweep row %s FasOff restore result=%s', row, request)

    data.logicalRow = row
    data.board = board
    data.address = address
    data.fasOn = None
    log.debug(
        'FAS sweep row %s complete: collectedPoints=%s',
        row, [len(curve.points) for curve in data.curveList])
    return data

def fasTune(*, group, process=None, doSet=True):
    """Run the original one-level FAS-minimum algorithm on working hardware paths.

    Active logical rows come from ``RowIndexOrderList`` and are resolved through
    ``RowMap``. Sweep points use ``RowDacDriver2.manual_set()``; persistent
    ``FasOn`` entries are optionally written only after every row sweep
    completes. A provisional SQ1 bias makes the FAS state observable before SQ1
    tuning; the original SQ1 force-current values are restored on exit.
    ``FasOff`` is never modified.
    """
    if process is None:
        raise ValueError('fasTune requires its FasTuneProcess')

    log = process._log
    log.debug('FAS tune entry: doSet=%s', doSet)
    tx = group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
    timing_running = tx.Running.get(read=True)
    log.debug('FAS tune timing Running=%s', timing_running)
    if timing_running:
        log.error('FAS tune rejected because timing is running')
        raise RuntimeError('FAS tuning requires timing to be stopped')

    row_map = group.RowMap.get()
    active_rows = [int(row) for row in group.RowIndexOrderList.get(read=True)]
    enabled_columns = [
        column for column, enabled in enumerate(group.ColTuneEnable.get())
        if enabled
    ]
    log.debug(
        'FAS tune configuration: activeRows=%s enabledColumns=%s '
        'rowMapLength=%d', active_rows, enabled_columns, len(row_map))
    if not active_rows:
        log.error('FAS tune rejected because the active row list is empty')
        raise RuntimeError('FAS tuning requires at least one active row')
    if not enabled_columns:
        log.error('FAS tune rejected because no columns are enabled')
        raise RuntimeError('FAS tuning requires at least one enabled column')

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
        drivers[board] = driver
        targets.append((row, board, address, driver))
        log.debug(
            'FAS tune logical row %d resolved to board=%d address=%d',
            row, board, address)

    unique_targets = {}
    for _, board, address, driver in targets:
        unique_targets[(board, address)] = driver

    mode_snapshot = {
        board: driver.Mode.get(read=True)
        for board, driver in drivers.items()
    }
    sa_fb_snapshot = np.array(
        group.SaFbForceCurrent.get(read=True), copy=True)
    sq1_bias_snapshot = np.array(
        group.Sq1BiasForceCurrent.get(read=True), copy=True)
    sq1_fb_snapshot = np.array(
        group.Sq1FbForceCurrent.get(read=True), copy=True)
    fas_on_snapshot = {
        key: driver.FasOn.Current.get(index=key[1], read=True)
        for key, driver in unique_targets.items()
    }
    log.debug(
        'FAS tune snapshots: modes=%s SaFbForceCurrent=%s '
        'Sq1BiasForceCurrent=%s Sq1FbForceCurrent=%s FasOn=%s',
        mode_snapshot, sa_fb_snapshot.tolist(), sq1_bias_snapshot.tolist(),
        sq1_fb_snapshot.tolist(), fas_on_snapshot)

    curves = []
    candidates = {}
    programming_started = False
    process.TotalSteps.set(
        len(active_rows) * process.FasFluxNumSteps.get())
    log.debug('FAS tune TotalSteps=%s', process.TotalSteps.value())

    try:
        bootstrap_bias = np.array(sq1_bias_snapshot, copy=True)
        bootstrap_fb = np.array(sq1_fb_snapshot, copy=True)
        bootstrap_bias[enabled_columns] = process.Sq1BiasCurrent.get()
        bootstrap_fb[enabled_columns] = 0.0
        log.debug(
            'FAS tune applying bootstrap SQ1 state to enabled columns: '
            'bias=%s feedback=%s',
            bootstrap_bias.tolist(), bootstrap_fb.tolist())
        group.Sq1FbForceCurrent.set(bootstrap_fb)
        group.Sq1BiasForceCurrent.set(bootstrap_bias)

        for board, driver in drivers.items():
            log.debug('FAS tune setting RowBoard[%d] Mode=MANUAL', board)
            driver.Mode.set(1, write=True)

        for index, (row, board, address, _) in enumerate(targets):
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
            row_sa_fb = np.array(
                group.SaFbForceCurrent.get(read=True), copy=True)
            for column in enabled_columns:
                row_sa_fb[column] = group.SaFbCurrent.get(
                    index=(column, row), read=True)
            log.debug(
                'FAS tune logical row %d applying SA-tuned feedback to '
                'force-current path: %s', row, row_sa_fb.tolist())
            group.SaFbForceCurrent.set(row_sa_fb)

            curve = fasSweep(group=group, row=row, process=process)
            curves.append(curve)
            if not process._runEn:
                log.debug(
                    'FAS tune stopped after logical row %d; '
                    'leaving FasOn unchanged', row)
                process.Message.set('Stopped by user; FasOn unchanged')
                return curves

            minima = []
            minimum_tolerance = process.FasMinimumTolerance.get()
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

        selected = {
            key: float(np.median(values))
            for key, values in candidates.items()
        }
        log.debug(
            'FAS tune physical-line candidates=%s selected=%s',
            candidates, selected)

        if not process._runEn:
            log.debug('FAS tune stopped before FasOn programming')
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        for curve in curves:
            curve.fasOn = selected[(curve.board, curve.address)]

        if not doSet:
            log.debug(
                'FAS tune SetAfterFinish is disabled; leaving FasOn unchanged '
                'and publishing candidates=%s', selected)
            return curves

        programming_started = True
        for key, current in selected.items():
            if not process._runEn:
                log.debug(
                    'FAS tune stopped between FasOn writes; rollback required')
                break
            log.debug(
                'FAS tune programming RowBoard[%d] FasOn[%d]=%s uA',
                key[0], key[1], current)
            unique_targets[key].FasOn.Current.set(
                index=key[1], value=current, write=True)

        # Also catches Stop arriving during the last register write.
        if not process._runEn:
            log.debug(
                'FAS tune rolling back FasOn after Stop: snapshot=%s',
                fas_on_snapshot)
            for key, original in fas_on_snapshot.items():
                log.debug(
                    'FAS tune rollback RowBoard[%d] FasOn[%d]=%s uA',
                    key[0], key[1], original)
                unique_targets[key].FasOn.Current.set(
                    index=key[1], value=original, write=True)
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
                    'FAS tune rollback RowBoard[%d] FasOn[%d]=%s uA',
                    key[0], key[1], current)
                unique_targets[key].FasOn.Current.set(
                    index=key[1], value=current, write=True)
        raise
    finally:
        log.debug('FAS tune cleanup starting')
        for key, driver in unique_targets.items():
            try:
                off_current = driver.FasOff.Current.get(
                    index=key[1], read=True)
                log.debug(
                    'FAS tune cleanup RowBoard[%d] address=%d '
                    'ManualSet FasOff=%s uA',
                    key[0], key[1], off_current)
                request = driver.manual_set(
                    address=key[1], current=off_current)
                log.debug(
                    'FAS tune cleanup RowBoard[%d] address=%d result=%s',
                    key[0], key[1], request)
            except Exception as exc:
                log.error(
                    'Failed to return row board %s address %s to FasOff: %s',
                    key[0], key[1], exc)
        try:
            log.debug(
                'FAS tune restoring SaFbForceCurrent=%s',
                sa_fb_snapshot.tolist())
            group.SaFbForceCurrent.set(sa_fb_snapshot)
        finally:
            try:
                log.debug(
                    'FAS tune restoring Sq1BiasForceCurrent=%s',
                    sq1_bias_snapshot.tolist())
                group.Sq1BiasForceCurrent.set(sq1_bias_snapshot)
            finally:
                try:
                    log.debug(
                        'FAS tune restoring Sq1FbForceCurrent=%s',
                        sq1_fb_snapshot.tolist())
                    group.Sq1FbForceCurrent.set(sq1_fb_snapshot)
                finally:
                    for board, mode in mode_snapshot.items():
                        log.debug(
                            'FAS tune restoring RowBoard[%d] Mode=%s',
                            board, mode)
                        drivers[board].Mode.set(mode, write=True)
        log.debug('FAS tune cleanup complete')

#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column
def sq1FbSweep(*, group, bias, fbRange, process):
    """Returns list of curve objects.
    Iterates through Sq1Fb values determined by lowoffset,
    highoffset,step. Generates curve points with saOffset()
    """
    colCount = group.NumColumns.get()
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
        if process._runEn is False:
            log.debug(
                'SQ1 FB sweep stopped before step %d/%d',
                fbStep + 1, numSteps)
            break

        # Set SQ1 FB
        feedback = fbRange[:, fbStep]
        log.debug(
            'SQ1 FB sweep step %d/%d writing feedback=%s',
            fbStep + 1, numSteps, np.asarray(feedback).tolist())
        group.Sq1FbForceCurrent.set(feedback)


        if servoDisable is False:
            # Servo saFB
            log.debug(
                'SQ1 FB sweep step %d/%d starting SA FB servo',
                fbStep + 1, numSteps)
            points = saFbServo(group=group, process=process)
        else:
            # Open Loop mode - temporary for testing
            points = group.SaOut.get()

        if process._runEn is False:
            log.debug(
                'SQ1 FB sweep stopped during step %d/%d; '
                'discarding incomplete point',
                fbStep + 1, numSteps)
            break

        log.debug(
            'SQ1 FB sweep step %d/%d response=%s',
            fbStep + 1, numSteps, np.asarray(points).tolist())

        # Add points to curves
        for col in range(colCount):
            curves[col].addPoint(points[col])

        process._incrementSteps(1)
        log.debug(
            'SQ1 FB sweep step %d/%d recorded', fbStep + 1, numSteps)

        # check for stopped process
        if process is not None and process._runEn == False:
            log.debug('SQ1 FB sweep stopped after step %d/%d',
                      fbStep + 1, numSteps)
            break

    log.debug(
        'SQ1 FB sweep complete: collectedPoints=%s',
        [len(curve.points) for curve in curves])
    return curves


def sq1BiasSweep(group, process, rowIndex, doBiasRamp=True):
    """Returns list of CurveData objects, corresponding to each column.
    Iterates through Sq1Bias values determined by
    lowoffset,highoffset,step,and gets curves by calling sq1FbSweep
    """

    # Extract iteration steps from Rogue variables
    # Create CurveData obects for storing output data
    colCount = group.NumColumns.get()
    log = process._log
    numBiasSteps = process.Sq1BiasNumSteps.get() if doBiasRamp else 1
    numFbSteps = process.Sq1FbNumSteps.get()
    biasRange = np.zeros((colCount, numBiasSteps), np.float64)
    fbRange = np.zeros((colCount, numFbSteps), np.float64)
    loadedBiases = None if doBiasRamp else np.asarray(group.Sq1BiasCurrent.get(), dtype=np.float64)[:, rowIndex]

    colTuneEnable = np.asarray(group.ColTuneEnable.get(), dtype=bool)
    datalist = []
    for col in range(colCount):
        if doBiasRamp:
            low = process.Sq1BiasLowOffset.get()
            high = process.Sq1BiasHighOffset.get()
            biasRange[col] = np.linspace(low, high, numBiasSteps, endpoint=True)
        else:
            # Retune at the SQ1 bias already loaded for this row.
            biasRange[col, 0] = loadedBiases[col]

        low = process.Sq1FbLowOffset.get()
        high = process.Sq1FbHighOffset.get()
        fbRange[col] = np.linspace(low, high, numFbSteps, endpoint=True)

        datalist.append(warm_tdm_api.CurveData(xValues=fbRange[col]))

    log.debug(
        'SQ1 bias sweep row=%s start: doBiasRamp=%s enabledMask=%s '
        'biasSteps=%d feedbackSteps=%d biasLow=%s biasHigh=%s '
        'feedbackLow=%s feedbackHigh=%s',
        rowIndex, doBiasRamp, colTuneEnable.tolist(), numBiasSteps, numFbSteps,
        np.asarray(biasRange[:, 0]).tolist(),
        np.asarray(biasRange[:, -1]).tolist(),
        np.asarray(fbRange[:, 0]).tolist(),
        np.asarray(fbRange[:, -1]).tolist())

    # Iterate over each bias point
    for biasStep in range(numBiasSteps):
        if process._runEn is False:
            log.debug(
                'SQ1 bias sweep row=%s stopped before bias step %d/%d',
                rowIndex, biasStep + 1, numBiasSteps)
            break

        # Reset FB to zero
        # This is probably unnecessary
        log.debug(
            'SQ1 bias sweep row=%s step %d/%d resetting feedback to zero',
            rowIndex, biasStep + 1, numBiasSteps)
        group.Sq1FbForceCurrent.set(np.zeros(colCount, np.float64))

        # Set SQ1 Bias
        bias = biasRange[:, biasStep]
        log.debug(
            'SQ1 bias sweep row=%s step %d/%d writing bias=%s',
            rowIndex, biasStep + 1, numBiasSteps,
            np.asarray(bias).tolist())
        group.Sq1BiasForceCurrent.set(bias)

        # Sweep SQ1 FB at the bias
        curves = sq1FbSweep(
            group=group, bias=bias, fbRange=fbRange, process=process)

        # Assign curves by column (if enabled for tuning)
        for col in range(colCount):
            if colTuneEnable[col]:
                datalist[col].addCurve(curves[col])

        log.debug(
            'SQ1 bias sweep row=%s step %d/%d complete: '
            'collectedPoints=%s',
            rowIndex, biasStep + 1, numBiasSteps,
            [len(curve.points) for curve in curves])

        # check for stopped process
        if process is not None and process._runEn == False:
            log.debug(
                'SQ1 bias sweep row=%s stopped after bias step %d/%d',
                rowIndex, biasStep + 1, numBiasSteps)
            break


    # Compute best bias point for each column
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
    """
    Runs Sq1BiasSweep for each row, collecting CurveData objects.
    During this loop, sets the resulting Sq1Bias and Sq1Fb values

    Args
    ----
    group : group
    Returns
    ----
    list
        list of list of CurveData objects 
    """
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

    def loadSaFbSetpoints(rowIndex):
        # Timing is stopped during SQ1 tuning, so the per-row SaFb RAM does
        # not drive the DAC. Copy the SA-tuned values for this row into the
        # force-current path before the software servo starts. Preserve the
        # force values of columns that are not enabled for tuning.
        rowSaFb = np.array(
            group.SaFbForceCurrent.get(read=True), copy=True)
        for column in enabledColumns:
            rowSaFb[column] = group.SaFbCurrent.get(
                index=(column, rowIndex), read=True)
        log.debug(
            'SQ1 tune row=%s applying per-row SA feedback setpoints to '
            'force-current path: %s', rowIndex, rowSaFb.tolist())
        group.SaFbForceCurrent.set(rowSaFb)

    # Establish the SA offset from a valid SA-tuned feedback point instead of
    # a stale force-current value left by an earlier operation.
    loadSaFbSetpoints(rowTuneList[0])
    log.debug('SQ1 tune starting initial SA offset adjustment')
    saOffset(group=group, process=process)
    log.debug('SQ1 tune initial SA offset adjustment complete')
    
    for rowNumber, rowIndex in enumerate(rowTuneList):
        if process._runEn is False:
            log.info('SQ1 tune stopped before row %s', rowIndex)
            break

        # Each row can have a different SA feedback operating point. Reset the
        # force-current path before activating and sweeping this row so the
        # servo starts on the intended SA branch.
        loadSaFbSetpoints(rowIndex)

        #Activate the row
        log.debug(
            'SQ1 tune activating row %s (%d/%d)',
            rowIndex, rowNumber + 1, numEnabledRows)
        group.ActivateRowIndex(rowIndex)
        try:
            # Run the sq1 bias sweep
            log.info(
                'SQ1 tune starting bias sweep for row %s (%d/%d)',
                rowIndex, rowNumber + 1, numEnabledRows)
            results = sq1BiasSweep(
                group, process, rowIndex=rowIndex,
                doBiasRamp=doBiasRamp)
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
    """Sweep Sq1Fb around its current value and record saOffset at each point."""
    center = group.Sq1FbCurrent.get(index=(column, row))
    low = center + low_offset
    high = center + high_offset
    numSteps = int((high - low) / step) + 1
    group._log.info(f'sq1Ramp row={row}, col={column}: center={center:.2f}, {numSteps} steps')

    outputs = []
    for fb in np.arange(low, high + step, step):
        group.Sq1FbForceCurrent.set(value=fb, index=column)
        offset = saOffset(group=group)
        outputs.append(offset)
    return outputs

def sq1RampRow(group, column, **kwargs):
    """Iterate through all rows, activating each, and call sq1Ramp."""
    numRows = group.MaxRows.get()
    group._log.info(f'sq1RampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(sq1Ramp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results


def tesRamp(group, row, column, low_offset=0.0, high_offset=100.0, step=1.0):
    """Sweep TesBias around its current value and record saOffset at each point."""
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
    """Iterate through all rows, activating each, and call tesRamp."""
    numRows = group.MaxRows.get()
    group._log.info(f'tesRampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(tesRamp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results
