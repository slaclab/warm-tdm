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
    colCount = len(group.ColumnMap.get())    

    # Setup PID controller
    pid = [PID(kp, ki, kd) for _ in range(len(group.ColumnMap.value()))]

    for p in pid:
        p.setpoint = 0  # want to zero out SaOut
        p.output_limits = (-0.5, 0.5)
        p.sample_time = None

    # Final output should be near SaBias, so start near there
    # Start at half the current bias
    control =  group.SaBiasVoltage.get()/2.0  #np.zeros(len(group.ColumnMap.value()))

    group.SaOffset.set(value=control)


    current = group.SaOutAdc.get()
    masked = current
#    print('Initial Values')
#    for i in range(len(control)):
        #print(f'i= {i}, saOut={masked[i]}, saOffset={control[i]}')
    #print()

    mult = np.array([1 if en else 0 for en in group.ColTuneEnable.value()],np.float64)
    count = 0

    while count < maxLoops:
        count += 1

        current = group.SaOutAdc.get()
        masked = current * mult

        # All channels have converged
        if (max(masked) < precision) and (min(masked) > (-1.0*precision)):
            break

        for i, p in enumerate(pid):
            change = p(masked[i])
            control[i] = np.clip(control[i] + change, 0.0, 2.499)
            #print(f'i= {i}, saOut={masked[i]}, saOffset={control[i]}, change={change}')

        group.SaOffset.set(control)

        if process is not None and process._runEn is False:
            return control

    if count == maxLoops:
        raise Exception(f"saOffset PID loop failed to converge after {maxLoops} loops")
    else:
        print(f'saOffset PID loop Converged after {count} loops')

    return control




#SA TUNING
def saFbSweep(*, group, bias, saFbRange, process):
    """Returns a list of Curves objects.
    Iterate over a range of SaFb values for each column at a single SaBias point.
    Capture SaOut value at each step
    Return list of Curve objects containing curves for each column
    """
    row = 0
    colCount = len(group.ColumnMap.get())
    curves = [warm_tdm_api.Curve(bias[i]) for i in range(colCount)]

    saFbArray = np.zeros(colCount, np.float64)

    numSteps = len(saFbRange[0])

    sleep = group.SaTuneProcess.SaFbSampleDelay.get()

    # Iterate through the steps
    for idx in range(numSteps):

        # Setup data
        #print(f'Writing SaFbForce values = {saFbRange[:, idx]}')
        group.SaFbForceCurrent.set(saFbRange[:, idx])

        time.sleep(sleep)
        points = group.SaOut.get() #group.HardwareGroup.ColumnBoard[0].DataPath.WaveformCapture.AdcAverage.get() #group.SaOut.get()
        
        #print(f'saFb step {idx} - {points}')

        for col in range(colCount):
            curves[col].addPoint(points[col])

        if process is not None:
            process.Advance()
            #Progress.set(pctLow + pctRange*((idx+1)/numSteps))
            


    # Reset FB to zero after sweep
    group.SaFbForceCurrent.set(value=np.zeros(colCount, np.float64))

    return curves

def saBiasSweep(*, group, process):
    """Returns a list of CurveData objects.
    Creates a list of CurveData objects, corresponding to each column.
    Iterates through SaBias values determined by Rogue variables.
    Calls saFbSweep to generate curves, adding them
    to their corresponding data objects
    """

    # Extract iteration steps from Rogue variables
    # Create CurveData obects for storing output data
    colCount = len(group.ColumnMap.get())
    colTuneEnable = group.ColTuneEnable.value()    
    numBiasSteps = group.SaTuneProcess.SaBiasNumSteps.get()
    numFbSteps = group.SaTuneProcess.SaFbNumSteps.get()
    saBiasRange = np.zeros((colCount, numBiasSteps), np.float64)
    saFbRange = np.zeros((colCount, numFbSteps), np.float64)

    datalist = []    
    for col in range(colCount):
        low = group.SaTuneProcess.SaBiasLowOffset.get()
        high = group.SaTuneProcess.SaBiasHighOffset.get()
        saBiasRange[col] = np.linspace(low,high,numBiasSteps,endpoint=True)

        low = group.SaTuneProcess.SaFbLowOffset.get()
        high = group.SaTuneProcess.SaFbHighOffset.get()
        saFbRange[col] = np.linspace(low,high,numFbSteps,endpoint=True)

        datalist.append(warm_tdm_api.CurveData(xValues=saFbRange[col]))
    
            
    process.TotalSteps.set(numBiasSteps * numFbSteps)

    #print(f'Bias sweep - {saBiasRange}')
    #print(f'Fb sweep = {saFbRange}')

    # Iterate over each SA Bias point
    # Set the SaBias, set the proper Offset
    # Sweep the SaFb range with saFbSweep()
    for idx in range(numBiasSteps):
        group.SaFbForceCurrent.set(np.zeros(colCount, np.float64))
        # Update process message 
        if process is not None:
            process.Message.set(f'SaBias step {idx+1} out of {numBiasSteps}')
        

        # Only set bias for enabled columns
        #print(f'Setting SaBias values = {saBiasRange[:, idx]}')
        group.SaBiasCurrent.set(saBiasRange[:, idx])
        #print('Starting saOffset()')
        saOffset(group=group)
        #print('Done saOffset()')        

        curves = saFbSweep(group=group,bias=saBiasRange[:, idx], saFbRange=saFbRange, process=process)

        for col in range(colCount):
            # Only add the curve if column is enabled for tuning
            if colTuneEnable[col]:
                datalist[col].addCurve(curves[col])

        # check for stopped process
        if process is not None and process._runEn == False:
            print('Process stopped, exiting saBiasSweep')
            break

    for d in datalist:
        d.update()

    # Return SaBias back to initial values
    #group.SaBias.set(start)
    #saOffset(group)


    return datalist

def saTune(*, group, process=None, doSet=True):
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
#    group.Init()

    #group.RowTuneIndex.set(0)
    #group.RowTuneMode.set(True)
    saBiasResults = saBiasSweep(group=group,process=process)

    if doSet:
        for col in range(len(group.ColumnMap.get())):
            # xOut represents the tuned saFB. Set it for every row.
            for row in range(len(group.RowMap.get())):
                group.SaFbCurrent.set(index=(col,row), value=saBiasResults[col].xOut)
            # biasOut represents the tuned SA Bias point
            group.SaBias.set(index=col, value=saBiasResults[col].biasOut)

        # Run saOffset to zero out the ADC value at the tuned SaBias,SaFb point
        saOffset(group=group)
            
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
    
    pid = [PID(kp, ki, kd) for _ in range(len(group.ColumnMap.value()))]

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
            break

        for i, p in enumerate(pid):
            change = p(masked[i])
            control[i] = np.clip(control[i] + change, -100. ,100.0 ) # Check this clip range

        group.SaFbForceCurrent.set(control)

    else:
        raise Exception(f"saFb PID loop failed to converge after {maxLoops} loops")

    print(f'saFb PID loop Converged after {count} loops')

    return control

def fasSweep(*, group, row, process):
    """Returns a 2D numpy array with indecies [col, fasFluxPoint]
    Iterates through FasFluxOn values determined by
    lowoffset,highoffset,step,calling saFb to generate points. 
    Adds this curve to the numpy array
    """

    colCount = len(group.ColumnMap.get())
    numSteps = group.FasTuneProcess.FasFluxNumSteps.get()
    low =  group.FasTuneProcess.FasFluxLowOffset.get()
    high = group.FasTuneProcess.FasFluxHighOffset.get()
    fasFluxRange = np.linspace(low, high, numSteps, endpoint=True)

    # Create the CurveData structure
    data = warm_tdm_api.CurveData(xvalues=fasFluxRange)
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
            process.Advance()
            if process._runEn == False:
                print('Process stopped, exiting fasSweep()')
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

    process.TotalSteps.set(numRows * process.FasFluxNumSteps.get())

    #group.RowForceEn.set(True)

    # Generate FAS Flux curves for each row
    for row in range(numRows):
        #group.RowForceIndex.set(row)
        if process is not None:
            process.Message.set(f'Row {row} out of {numRows}')
            #process.Process.set(row/numRows)

        # Generate and save the curves
        curve = fasSweep(group=group, process=process)
        curves.append(curve)

        # Minumum index of the curve is FasFluxOn
        # Use median across all columns as FasFlowOn for that row
        group.FasFluxOn.set(index=row, value=np.median(curve.argmin(1)))

        # check for stopped process
        if process is not None and process._runEn == False:
            print('Process stopped, fasTune()')
            break
        
        
    #group.RowForceEn.set(False)
    return curves

#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column
def sq1FbSweep(*, group, bias, fbRange, row, process):
    """Returns list of curve objects.
    Iterates through Sq1Fb values determined by lowoffset,
    highoffset,step. Generates curve points with saOffset()
    """
    print(f'sq1FbSweep({bias=}, {fbRange=}, {row=})')
    colCount = len(group.ColumnMap.get())
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

        process.Advance()

        # check for stopped process
        if process is not None and process._runEn == False:
            print('Process stopped, sq1FbSweep()')
            break

    return curves


def sq1BiasSweep(group, row, process):
    """Returns list of CurveData objects, corresponding to each column.
    Iterates through Sq1Bias values determined by
    lowoffset,highoffset,step,and gets curves by calling sq1FluxRow
    """

    # Extract iteration steps from Rogue variables
    # Create CurveData obects for storing output data
    print(f'saBiasSweep({row=})')
    
    colCount = len(group.ColumnMap.get())
    numBiasSteps = process.Sq1BiasNumSteps.get()
    numFbSteps = process.Sq1FbNumSteps.get()
    biasRange = np.zeros((colCount, numBiasSteps), np.float64)
    fbRange = np.zeros((colCount, numFbSteps), np.float64)

    datalist = []    
    for col in range(colCount):
        low = process.Sq1BiasLowOffset.get()
        high = process.Sq1BiasHighOffset.get()
        biasRange[col] = np.linspace(low, high, numBiasSteps, endpoint=True)

        low = process.Sq1FbLowOffset.get()
        high = process.Sq1FbHighOffset.get()
        fbRange[col] = np.linspace(low, high, numFbSteps, endpoint=True)

        datalist.append(warm_tdm_api.CurveData(xValues=fbRange[col]))

    # Only run FB sweeps if tuning is enabled on this row.
    # Otherwise return CurveData with no curves
    if group.RowTuneEnable.get()[row]:
        # Iterate over each bias point
        for biasStep in range(numBiasSteps):
            # Reset FB to zero
            # This is probably unnecessary
            group.Sq1FbForceCurrent.set(np.zeros(colCount, np.float64))

            # Set SQ1 Bias
            group.Sq1BiasForceCurrent.set(biasRange[:, biasStep])

            # Sweep SQ1 FB at the bias
            curves = sq1FbSweep(group=group, bias=biasRange[:, biasStep], fbRange=fbRange, row=row, process=process)
        
            # Assign curves by column (if enabled for tuning)
            for col in range(colCount):
                if group.ColTuneEnable.get()[col]:
                    datalist[col].addCurve(curves[col])
            
    # Compute best bias point for each column
    for d in datalist:
        d.update()

    return datalist

def sq1Tune(group, process):
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
    rowTuneEnable = group.RowTuneEnable.value()
    colTuneEnable = group.ColTuneEnable.value()    
    numEnabledRows = len([x for x in rowTuneEnable if x == True]) # This will count number of True in array
    numColumns = group.NumColumns.get()

    totalSteps = numEnabledRows * process.Sq1BiasNumSteps.get() * process.Sq1FbNumSteps.get()
    process.TotalSteps.set(totalSteps)

    #group.RowForceEn.set(True)
    saOffset(group=group)
    
    for row in range(group.NumRows.get()):
        results = sq1BiasSweep(group, row, process)
        outputs.append(results)
        
        if rowTuneEnable[row]:
            for col in range(numColumns):
                if colTuneEnable[col]:
                    group.Sq1BiasCurrent.set(index=(col, row), value=results[col].biasOut)
                    group.Sq1FbCurrent.set(index=(col, row), value=results[col].xOut)
                    group.SaFbCurrent.set(index=(col, row), value=results[col].yOut)

    return outputs



#SQ1 DIAGNOSTIC -output vs sq1 feedback for every row  for every column
def sq1Ramp(group, row, column):
    """Returns list of offsets that zero out SaOut depending
    on the biasIterates through Sq1Fb values determined by
    lowoffset,highoffset,step and records output of saOffset().
    """
    low = group.Sq1Fb.get() + group.Sq1FbLowOffset.get()
    high = group.Sq1Fb.get() + group.Sq1FbHighOffset.get()
    step = group.Sq1FbStepSize.get()

    outputs = []
    for fb in np.arange(low,high+step,step):
        group.Sq1Fb.set(index=(column,row),value=fb)
        offset = saOffset(group,row,column)
        outputs.append(offset)
    return outputs

def sq1RampRow(group,column):
    """Iterates through all rows, enabling tuning, and then calls sq1Ramp
    """
    for row in range(group.NumRows.get()):
        group.RowForceIndex.set(row)
        group.RowForceEn.set(True)
        sq1RampResults = sq1Ramp(group,row,column)
    group.RowForceEn.set(False)



#TES BIAS DIAGNOSTIC - what to do with this data?
def tesRamp(group,row, column):
    """Returns list of offsets that zero out SaOut depending on the bias
    Iterates through TesBias values determined by lowoffset,highoffset,step
    and records output of saOffset().
    """
    low = group.TesBias.get() + group.TesBiasLowOffset.get()
    high = group.TesBias.get() + group.TesBiasHighOffset.get()
    step = group.TesBiasStepSize.get()

    outputs = []
    for bias in np.arange(low,high,step):
        group.TesBias.set(index=row,value=bias)
        offset = saOffset(group,row,column=0)
        outputs.append(offset)
    return outputs

def tesRampRow(group,column):
    """Iterates through all rows, enabling tuning, and then calls tesRamp
    """
    for row in range(group.NumRows.get()):
        group.RowForceEn.set(True)
        tesRampResults = tesRamp(group,row,column)
    group.RowForceEn.set(False)
