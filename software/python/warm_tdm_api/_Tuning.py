import numpy as np
import time

from simple_pid import PID
import warm_tdm_api


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

    saBiasResults = saBiasSweep(group=group, process=process, doBiasRamp=doBiasRamp)

    stopped = process is not None and process._runEn is False
    if doSet and not stopped:
        # SA tune is per-column: saBiasSweep returns one tuned SaFb (xOut) per
        # column. The same value is written to every row slot, so this does not
        # depend on the row map — broadcast across the full maxRows address space
        # rather than the readout list (which may not be set yet when saTune runs).
        for col in range(group.NumColumns.get()):
            # xOut represents the tuned saFB. Set it for every row.
            for row in range(group.MaxRows.get()):
                group.SaFbCurrent.set(index=(col,row), value=saBiasResults[col].xOut)
            # biasOut represents the tuned SA Bias point
            group.SaBiasCurrent.set(index=col, value=saBiasResults[col].biasOut)

        # Run saOffset to zero out the ADC value at the tuned SaBias,SaFb point
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
    
    pid = [PID(kp, ki, kd) for _ in range(group.NumColumns.get())]

    for p in pid:
        p.setpoint = 0 # want to zero out SaOut
        p.output_limits = (-0.5, 0.5)
        p.sample_time   = None

    control = group.SaFbForceCurrent.get()

    current = group.SaOutAdc.get()
    masked = current
    mult = np.array([1 if en else 0 for en in group.ColTuneEnable.value()], np.float64)    
    count = 0

    for count in range(maxLoops):
        if process._runEn is False:
            group._log.info('Process stopped, exiting saFbServo')
            return control

        current = group.SaOutAdc.get()
        masked = current * mult

        # All channels have converged
        if (max(masked) < precision) and (min(masked) > (-1.0*precision)):
            group._log.debug('saFbServo converged after %s loops', count+1)
            break

        for i, p in enumerate(pid):
            change = p(masked[i])
            control[i] = control[i] + change

        group.SaFbForceCurrent.set(control)

    else:
        group._log.warning(f'saFb PID loop failed to converge after {maxLoops} loops')
        return control

    return control

def fasSweep(*, group, row, process):
    """Sweep the physical one-level FAS line mapped from ``row``."""
    row_map = group.RowMap.get()
    mapping = row_map[row]
    if 'csAddr' in mapping or 'csBoard' in mapping:
        raise RuntimeError(
            'The simple FAS tune supports one-level RowMap entries only')

    board = int(mapping['rsBoard'])
    address = int(mapping['rsAddr'])
    driver = group.HardwareGroup.RowBoard[board].RowDacDriver
    if not callable(getattr(driver, 'manual_set', None)):
        raise RuntimeError(
            f'RowBoard[{board}] firmware/software does not provide ManualSet')

    low = process.FasFluxLowOffset.get()
    high = process.FasFluxHighOffset.get()
    steps = process.FasFluxNumSteps.get()
    delay = process.FasFluxSampleDelay.get()
    currents = np.linspace(low, high, steps, endpoint=True)
    data = warm_tdm_api.CurveData(xValues=currents)
    for column in range(group.NumColumns.get()):
        data.addCurve(warm_tdm_api.Curve(column))

    off_current = driver.FasOff.Current.get(index=address, read=True)
    try:
        for current in currents:
            if not process._runEn:
                break
            driver.manual_set(address=address, current=current)

            # Stop() waits for the worker thread, so keep a user-configured
            # settling delay interruptible rather than sleeping in one block.
            deadline = time.monotonic() + max(0.0, delay)
            while process._runEn and time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    break
                time.sleep(min(0.05, remaining))
            if not process._runEn:
                break

            points = saFbServo(group=group, process=process)
            if not process._runEn:
                break
            for column, point in enumerate(points):
                data.curveList[column].addPoint(point)
            process._incrementSteps(1)
    finally:
        driver.manual_set(address=address, current=off_current)

    data.logicalRow = row
    data.board = board
    data.address = address
    data.fasOn = None
    return data

def fasTune(*,group,process=None):
    """Run the original one-level FAS-minimum algorithm on working hardware paths.

    Active logical rows come from ``RowIndexOrderList`` and are resolved through
    ``RowMap``. Sweep points use ``RowDacDriver2.manual_set()``; persistent
    ``FasOn`` entries are written only after every row sweep completes.
    ``FasOff`` is never modified.
    """
    if process is None:
        raise ValueError('fasTune requires its FasTuneProcess')

    tx = group.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
    if tx.Running.get(read=True):
        raise RuntimeError('FAS tuning requires timing to be stopped')

    row_map = group.RowMap.get()
    active_rows = [int(row) for row in group.RowIndexOrderList.get(read=True)]
    enabled_columns = [
        column for column, enabled in enumerate(group.ColTuneEnable.get())
        if enabled
    ]
    if not active_rows:
        raise RuntimeError('FAS tuning requires at least one active row')
    if not enabled_columns:
        raise RuntimeError('FAS tuning requires at least one enabled column')

    targets = []
    drivers = {}
    for row in active_rows:
        if row < 0 or row >= len(row_map):
            raise RuntimeError(
                f'Active logical row {row} is outside RowMap length '
                f'{len(row_map)}')
        mapping = row_map[row]
        if 'csAddr' in mapping or 'csBoard' in mapping:
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

    unique_targets = {}
    for _, board, address, driver in targets:
        unique_targets[(board, address)] = driver

    mode_snapshot = {
        board: driver.Mode.get(read=True)
        for board, driver in drivers.items()
    }
    sa_fb_snapshot = np.array(
        group.SaFbForceCurrent.get(read=True), copy=True)
    fas_on_snapshot = {
        key: driver.FasOn.Current.get(index=key[1], read=True)
        for key, driver in unique_targets.items()
    }

    curves = []
    candidates = {}
    programming_started = False
    process.TotalSteps.set(
        len(active_rows) * process.FasFluxNumSteps.get())

    try:
        for driver in drivers.values():
            driver.Mode.set(1, write=True)

        for index, (row, board, address, _) in enumerate(targets):
            process.Message.set(
                f'FAS row {row} ({index + 1}/{len(targets)})')
            curve = fasSweep(group=group, row=row, process=process)
            curves.append(curve)
            if not process._runEn:
                process.Message.set('Stopped by user; FasOn unchanged')
                return curves

            minima = []
            for column in enabled_columns:
                points = curve.curveList[column].points
                if points:
                    minima.append(curve.xValues[int(np.argmin(points))])
            if not minima:
                raise RuntimeError(
                    f'No FAS samples were collected for logical row {row}')
            candidates.setdefault((board, address), []).append(
                float(np.median(minima)))

        selected = {
            key: float(np.median(values))
            for key, values in candidates.items()
        }

        if not process._runEn:
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        programming_started = True
        for key, current in selected.items():
            if not process._runEn:
                break
            unique_targets[key].FasOn.Current.set(
                index=key[1], value=current, write=True)

        # Also catches Stop arriving during the last register write.
        if not process._runEn:
            for key, original in fas_on_snapshot.items():
                unique_targets[key].FasOn.Current.set(
                    index=key[1], value=original, write=True)
            programming_started = False
            process.Message.set('Stopped by user; FasOn unchanged')
            return curves

        for curve in curves:
            curve.fasOn = selected[(curve.board, curve.address)]
        process.Message.set('FAS tune complete')
        return curves

    except Exception:
        if programming_started:
            for key, current in fas_on_snapshot.items():
                unique_targets[key].FasOn.Current.set(
                    index=key[1], value=current, write=True)
        raise
    finally:
        for key, driver in unique_targets.items():
            try:
                off_current = driver.FasOff.Current.get(
                    index=key[1], read=True)
                driver.manual_set(address=key[1], current=off_current)
            except Exception as exc:
                group._log.error(
                    'Failed to return row board %s address %s to FasOff: %s',
                    key[0], key[1], exc)
        try:
            group.SaFbForceCurrent.set(sa_fb_snapshot)
        finally:
            for board, mode in mode_snapshot.items():
                drivers[board].Mode.set(mode, write=True)

#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column
def sq1FbSweep(*, group, bias, fbRange, process):
    """Returns list of curve objects.
    Iterates through Sq1Fb values determined by lowoffset,
    highoffset,step. Generates curve points with saOffset()
    """
    colCount = group.NumColumns.get()
    curves = [warm_tdm_api.Curve(bias[i]) for i in range(colCount)]
    numSteps = len(fbRange[0])

    servoDisable = process.ServoDisable.get()

    for fbStep in range(numSteps):
        # Set SQ1 FB
        group.Sq1FbForceCurrent.set(fbRange[:, fbStep])


        if servoDisable is False:
            # Servo saFB            
            points = saFbServo(group=group, process=process)
        else:
            # Open Loop mode - temporary for testing
            points = group.SaOut.get()

        # Add points to curves
        for col in range(colCount):
            curves[col].addPoint(points[col])

        process._incrementSteps(1)

        # check for stopped process
        if process is not None and process._runEn == False:
            group._log.info('Process stopped, exiting sq1FbSweep')
            break

    return curves


def sq1BiasSweep(group, process, rowIndex, doBiasRamp=True):
    """Returns list of CurveData objects, corresponding to each column.
    Iterates through Sq1Bias values determined by
    lowoffset,highoffset,step,and gets curves by calling sq1FbSweep
    """

    # Extract iteration steps from Rogue variables
    # Create CurveData obects for storing output data
    colCount = group.NumColumns.get()
    numBiasSteps = process.Sq1BiasNumSteps.get() if doBiasRamp else 1
    numFbSteps = process.Sq1FbNumSteps.get()
    biasRange = np.zeros((colCount, numBiasSteps), np.float64)
    fbRange = np.zeros((colCount, numFbSteps), np.float64)
    loadedBiases = None if doBiasRamp else np.asarray(group.Sq1BiasCurrent.get(), dtype=np.float64)[:, rowIndex]

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


    # Iterate over each bias point
    for biasStep in range(numBiasSteps):
        # Reset FB to zero
        # This is probably unnecessary
        group.Sq1FbForceCurrent.set(np.zeros(colCount, np.float64))

        # Set SQ1 Bias
        group.Sq1BiasForceCurrent.set(biasRange[:, biasStep])

        # Sweep SQ1 FB at the bias
        curves = sq1FbSweep(group=group, bias=biasRange[:, biasStep], fbRange=fbRange, process=process)

        # Assign curves by column (if enabled for tuning)
        for col in range(colCount):
            if group.ColTuneEnable.get()[col]:
                datalist[col].addCurve(curves[col])

        # check for stopped process
        if process is not None and process._runEn == False:
            group._log.info('Process stopped, exiting sq1BiasSweep')
            break


    # Compute best bias point for each column
    for d in datalist:
        d.update()

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
    numRows = group.MaxRows.get()
    rowTuneList = group.RowIndexOrderList.value()
    colTuneEnable = group.ColTuneEnable.value()
    numEnabledRows = len(rowTuneList)
    numColumns = group.NumColumns.get()

    numBiasSteps = process.Sq1BiasNumSteps.get() if doBiasRamp else 1
    totalSteps = numEnabledRows * numBiasSteps * process.Sq1FbNumSteps.get()
    process.TotalSteps.set(totalSteps)
    group._log.info(f'sq1Tune starting: {numEnabledRows} rows, {totalSteps} total steps')

    #group.RowForceEn.set(True)
    saOffset(group=group, process=process)
    
    for rowIndex in rowTuneList:
        if process._runEn is False:
            group._log.info('Process stopped, exiting sq1Tune')
            break

        #Activate the row
        group.ActivateRowIndex(rowIndex)

        # Run the sq1 bias sweep
        group._log.info(f'sq1BiasSweep row={rowIndex}')
        results = sq1BiasSweep(group, process, rowIndex=rowIndex, doBiasRamp=doBiasRamp)
        for i, r in enumerate(results):
            group._log.debug('Results col %s: bias=%s, xOut=%s, yOut=%s', i, r.biasOut, r.xOut, r.yOut)
            
        outputs.append(results)

        group.DeactivateRowIndex(rowIndex)

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
