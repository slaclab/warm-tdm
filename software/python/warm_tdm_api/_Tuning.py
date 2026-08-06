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
            saOffset(group=group)
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
        saOffset(group=group)        

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

    if doSet:
        for col in range(group.NumColumns.get()):
            # xOut represents the tuned saFB. Set it for every row.
            for row in range(group.NumRows.get()):
                group.SaFbCurrent.set(index=(col,row), value=saBiasResults[col].xOut)
            # biasOut represents the tuned SA Bias point
            group.SaBiasCurrent.set(index=col, value=saBiasResults[col].biasOut)

        # Run saOffset to zero out the ADC value at the tuned SaBias,SaFb point
        saOffset(group=group)

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
    """Returns a 2D numpy array with indecies [col, fasFluxPoint]
    Iterates through FasFluxOn values determined by
    lowoffset,highoffset,step,calling saFb to generate points. 
    Adds this curve to the numpy array
    """

    colCount = group.NumColumns.get()
    numSteps = group.FasTuneProcess.FasFluxNumSteps.get()
    low =  group.FasTuneProcess.FasFluxLowOffset.get()
    high = group.FasTuneProcess.FasFluxHighOffset.get()
    fasFluxRange = np.linspace(low, high, numSteps, endpoint=True)

    # Create the CurveData structure
    data = warm_tdm_api.CurveData(xValues=fasFluxRange)
    #data = np.zeros((colCount, fasFluxRange.size, 2), dtype=float)

    # Add a Curve for each column
    for col in range(colCount):
        data.addCurve(warm_tdm_api.Curve(col))

    # Sweep the flux range
    for step in range(numSteps):
        # Set a the fasFlux value for the row 
        # Below is wrong. Need to drive FAS Flux value       
        group.FasFluxOn.set(index=row, value=fasFluxRange[step])

        # Servo the saFb
        points = saFbServo(group=group)

        for col in range(colCount):
            data.curveList[col].addPoint(points[col])

        # check for stopped process
        if process is not None:
            process._incrementSteps(1)
            if process._runEn == False:
                group._log.info('Process stopped, exiting fasSweep')
                break

    return data

def fasTune(*,group,process=None):
    """
    Iterate through all rows, measuring results from
    fasSweep subroutine, and setting FasFluxOn and FasFluxOff
    accordingly.

    Args
    ----
    group : group

    pctVar : pr.Variable
        Variable to set current percentage complete

    Returns
    ----
    list
        list of CurveData objects where result of saFb
        subroutine is plotted against fasSweep
    """
    curves = []
    numRows = group.NumRows.get()

    group._log.info(f'fasTune starting: {numRows} rows')
    process.TotalSteps.set(numRows * process.FasFluxNumSteps.get())

    #group.RowForceEn.set(True)

    # Generate FAS Flux curves for each row
    for row in range(numRows):
        #group.RowForceIndex.set(row)
        if process is not None:
            process.Message.set(f'Row {row} out of {numRows}')
            #process.Process.set(row/numRows)

        # Generate and save the curves
        curve = fasSweep(group=group, row=row, process=process)
        curves.append(curve)

        # Minumum index of the curve is FasFluxOn
        # Use median across all columns as FasFlowOn for that row
        group.FasFluxOn.set(index=row, value=np.median(curve.argmin(1)))

        # check for stopped process
        if process is not None and process._runEn == False:
            group._log.info('Process stopped, exiting fasTune')
            break
        
        
    #group.RowForceEn.set(False)
    return curves

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
    numRows = group.NumRows.get()
    rowTuneList = group.RowIndexOrderList.value()
    colTuneEnable = group.ColTuneEnable.value()
    numEnabledRows = len(rowTuneList)
    numColumns = group.NumColumns.get()

    numBiasSteps = process.Sq1BiasNumSteps.get() if doBiasRamp else 1
    totalSteps = numEnabledRows * numBiasSteps * process.Sq1FbNumSteps.get()
    process.TotalSteps.set(totalSteps)
    group._log.info(f'sq1Tune starting: {numEnabledRows} rows, {totalSteps} total steps')

    #group.RowForceEn.set(True)
    saOffset(group=group)
    
    for rowIndex in rowTuneList:
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
    numRows = group.NumRows.get()
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
    numRows = group.NumRows.get()
    group._log.info(f'tesRampRow col={column}: {numRows} rows')
    results = []
    for row in range(numRows):
        group.ActivateRowIndex(row)
        results.append(tesRamp(group, row, column, **kwargs))
        group.DeactivateRowIndex(row)
    return results
