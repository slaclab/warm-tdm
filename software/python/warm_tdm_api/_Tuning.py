import numpy as np
import time

from simple_pid import PID
import warm_tdm_api


def saOffset(*, group):
    """Returns float.
    Run PID loops to determine saOffset that properly offsets saBias
    """

    # Get parameters from the Process
    process = group.SaOffsetProcess
    kp = process.Kp.get()
    ki = process.Ki.get()
    kd = process.Kd.get()
    precision = process.Precision.get()
    timeout = process.Timeout.get()

    # Setup PID controller
    pid = [PID(kp, ki, kd) for _ in range(len(group.ColumnMap.value()))]

    for p in pid:
        p.setpoint = 0  # want to zero out SaOut
        p.output_limits = (-0.5, 0.5)
        p.sample_time = None

    stime = time.time()

    # Final output should be near SaBias, so start there.
    control = group.SaBias.get()

    group.SaOffset.set(control)
    current = group.SaOut.get()
    masked = current
#    print('Initial Values')
#    for i in range(len(control)):
        #print(f'i= {i}, saOut={masked[i]}, saOffset={control[i]}')
    #print()

    mult = np.array([1 if en else 0 for en in group.ColTuneEnable.value()],np.float32)
    count = 0

    while True:
        count += 1

        # Limit convergance to 1 minute
        if (time.time() - stime) > timeout:
            raise Exception(f"saOffset PID loop failed to converge after {timeout} seconds")

        current = group.SaOut.get()
        masked = current * mult

        # All channels have converged
        if (max(masked) < precision) and (min(masked) > (-1.0*precision)):
            break

        for i, p in enumerate(pid):
            change = p(masked[i])
            control[i] = np.clip(control[i] + change, 0.0, 2.499)
            #print(f'i= {i}, saOut={masked[i]}, saOffset={control[i]}, change={change}')

        group.SaOffset.set(control)

    print(f'saOffset PID loop Converged after {count} loops')

    return control




#SA TUNING
def saFbSweep(*, group, bias, saFbRange, pctLow, pctRange, process):
    """Returns a list of Curves objects.
    Iterates through SaFb values determined by lowoffset,highoffset,steps and
    calls SaOffset to generate points
    """
    row = 0
    colCount = len(group.ColumnMap.get())
    curves = [warm_tdm_api.Curve(bias[i]) for i in range(colCount)]

    saFbArray = np.zeros(colCount, np.float)

    numSteps = len(saFbRange[0])

    sleep = group.SaTuneProcess.SaFbSampleDelay.get()

    # Iterate through the steps
    for idx in range(numSteps):

        # Setup data
        for col in range(colCount):
            if group.ColTuneEnable.value()[col] is True:
                saFbArray[col] = saFbRange[col][idx]

        # large burst transaction of write data
        group.SaFbForce.set(value=saFbArray)

        if process is not None:
            process.Progress.set(pctLow + pctRange*(idx/numSteps))

        time.sleep(sleep)
        points = group.HardwareGroup.ColumnBoard[0].DataPath.WaveformCapture.AdcAverage.get() #group.SaOut.get()

#        print(f'saFb step {idx} - {saFbArray[5]} - {points[5]}')

        for col in range(colCount):
            curves[col].addPoint(points[col])

    # Reset FB to zero after sweep
    group.SaFbForce.set(value=np.zeros(colCount, np.float))

    return curves

def saBiasSweep(*, group, process):
    """Returns a list of CurveData objects.
    Creates a list of CurveData objects, corresponding to each
    column
    Iterates through SaBias values determined by low,high,
    steps and calls saFbSweep to generate curves, adding them
    to their corresponding data objects
    """

    datalist = []
    saBiasRange = []
    saFbRange = []
    colCount = len(group.ColumnMap.get())
    numBiasSteps = group.SaTuneProcess.SaBiasNumSteps.get()
    numFbSteps = group.SaTuneProcess.SaFbNumSteps.get()
    pctRange = 1.0/numBiasSteps

    # Get current sabias values
    bias = group.SaBias.get()

    for col in range(colCount):
        low = group.SaTuneProcess.SaBiasLowOffset.get()
        high = group.SaTuneProcess.SaBiasHighOffset.get()
        saBiasRange.append(np.linspace(low,high,numBiasSteps,endpoint=True))

        low = group.SaTuneProcess.SaFbLowOffset.get()
        high = group.SaTuneProcess.SaFbHighOffset.get()
        saFbRange.append(np.linspace(low,high,numFbSteps,endpoint=True))

        datalist.append(warm_tdm_api.CurveData(xvalues=saFbRange[col]))

    for idx in range(numBiasSteps):
        for col in range(colCount):
            if group.ColTuneEnable.value()[col] is True:
                bias[col] = saBiasRange[col][idx]

        group.SaBias.set(bias)
        saOffset(group=group)

        #print(f'saBias step {idx} - {bias}')

        if process is not None:
            process.Message.set(f'SaBias step {idx} out of {numBiasSteps}')

        curves = saFbSweep(group=group,bias=bias,saFbRange=saFbRange, pctLow=idx/numBiasSteps,pctRange=pctRange,process=process)

        for col in range(colCount):
            datalist[col].addCurve(curves[col])

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
    group.Init()
    group.RowTuneIndex.set(0)
    group.RowTuneEn.set(True)
    saBiasResults = saBiasSweep(group=group,process=process)

    if doSet:
        for col in range(len(group.ColumnMap.get())):
            for row in range(len(group.RowMap.get())):
                group.SaFb.set(index=(col,row),value=saBiasResults[col].fbOut)
            group.SaOffset.set(index=col,value=saBiasResults[col].offsetOut)
            group.SaBias.set(index=col,value=saBiasResults[col].biasOut)
        group.RowForceEn.set(False)
    return saBiasResults


#FAS TUNING
def saFb(*,group,row,precision=1.0):
    """Returns list of SaFb values which zero out SaOut.
    Each element corresponds with a column
    """

    # Setup PID controller
    pid = [PID(1,.1,.05)] * len(group.ColumnMap.get())

    for p in pid:
        p.setpoint = 0 # want to zero out SaOut
        p.output_limits = (0.0, 1.0)
        p.sample_time   = 0.1

    stime = time.time()

    control = group.SaFb.get()

    while True:

        # Limit convergance to 1 minute
        if (time.time() - stime) > 60:
            raise Exception("saFb PID loop failed to converge after 60 seconds")

        current = group.SaOut.get()

        # All channels have converged
        if (max(current) < precision) and (min(current) > (-1.0*precision)):
            break

        for i, p in enumerate(pid):
            control[i][row] = p(current[i])

        group.SaFb.set(control)

    return control

def fasFlux(*,group,row,pctLow,pctRange,process):
    """Returns a list of CurveData objects, each element corresponding to a column.
    Iterates through FasFluxOn values determined by
    lowoffset,highoffset,step,calling saFb to generate
     points. Adds this curve to a CurveData object.
    """

    colCount = len(group.ColumnMap.get())
    numSteps = group.FasTuneProcess.FasFluxNumSteps.get()

    low = group.FasFluxOn.get(index=row) + group.FasTuneProcess.FasFluxLowOffset.get()
    high = group.FasFluxOn.get(index=row) + group.FasTuneProcess.FasFluxHighOffset.get()

    fasFluxRange = np.linspace(low,high,numSteps,endpoint=True)

    curves = [warm_tdm_api.Curve(0) for i in range(colCount)]

    for idx in range(numSteps):
        group.FasFluxOn.set(index=row,value=fasFluxRange[idx])

        if process is not None:
            process.Progress.set(pctLow + pctRange*(idx/numSteps))

        points = saFb(group=group,row=row)

        for col in range(colCount):
            curves[col].addPoint(points[col])

    datalist = [warm_tdm_api.CurveData(xvalues=fasFluxRange)] * colCount

    for col in range(colCount):
        datalist[col].addCurve(curves[col])
        #datalist[col].update()

    return datalist

def fasTune(*,group,process=None):
    """
    Iterate through all rows, measuring results from
    fasFlux subroutine, and setting FasFluxOn and FasFluxOff
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
        subroutine is plotted against fasFlux
    """
    curves = []
    numRows = group.NumRows.get()
    pctRange = 1.0/numRows

    group.RowForceEn.set(True)

    for row in range(numRows):
        group.RowForceIndex.set(row)
        if process is not None:
            process.Message.set(f'Row {row} out of {numRows}')
        curves.append(fasFlux(group=group,row=row,pctLow=row/numRows,pctRange=pctRange,process=process))

    group.RowForceEn.set(False)
    return curves

#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column
def sq1Flux(group,bias,row):
    """Returns list of curve objects.
    Iterates through Sq1Fb values determined by lowoffset,
    highoffset,step. Generates curve points with saOffset()
    """
    curves = []
    Sq1FbOffsetRange = []

    for col in range(len(group.ColMap.get())):
        low = group.Sq1Fb.get(index=(col,row)) + group.Sq1FbLowOffset.get()
        high = group.Sq1Fb.get(index=(col,row)) + group.Sq1FbHighOffset.get()
        numsteps = group.Sq1FbNumSteps.get()
        Sq1FbOffsetRange.append(np.linspace(low,high,numsteps,endpoint=True))

    for col in range(len(group.ColMap.get())):
        curves.append(warm_tdm_api.Curve(bias))

    for idx in range(len(Sq1FbOffsetRange[0])):
        for col in range(len(group.ColMap.get)):
            group.Sq1Fb.set(index=(col,row),value=Sq1FbOffsetRange[col][idx])
        points = saOffset(group,row)

        for col in range(len(group.ColMap.get())):
            curves[col].addPoint(points[col])

    ###OLD CODE BELOW
    for col in range(len(group.ColMap.get())):
        curve = warm_tdm_api.Curve(bias)
        for fb in np.arange(low,high+step,step):
            group.Sq1Fb.set(index=(col,row),value=fb)
            offset = saOffset(group,row,None)
            curve.addPoint(offset)
        curves.append(curve)
    return curves

def sq1FluxRow(group,row,bias):
    """Returns Curve object.
    Iterates through rows, enabling tuning for each row.
    Calls sq1Flux on row passed as argument
    """

    for row in range(group.NumRows.get()):
        group.RowForceIndex.set(row)
        group.RowForceEn.set(True)
        #set the corresponding saFb value for the row
    curves = sq1Flux(group,bias,row)
    return curves

def sq1FluxRowBias(group,row):
    """Returns list of CurveData objects, corresponding to each column.
    Iterates through Sq1Bias values determined by
    lowoffset,highoffset,step,and gets curves by calling sq1FluxRow
    """

    datalist = []

    for col in range(len(group.ColMap.get())):
        low = group.Sq1Bias.get(index=(col,row)) + group.Sq1BiasLowOffset.get()
        high = group.Sq1Bias.get(index=(col,row)) + group.Sq1BiasHighOffset.get()
        step = group.Sq1BiasStepSize.get()

        lowFb = group.Sq1Fb.get(index=(col,row)) + group.Sq1FbLowOffset.get()
        highFb = group.Sq1Fb.get(index=(col,row)) + group.Sq1FbHighOffset.get()
        stepFb= group.Sq1FbStepSize.get()

        data = warm_tdp_api.CurveData()
        data.populateXValues(lowFb,highFb+stepFb,stepFb)

        for bias in np.arange(low,high+step,step):
            data.addCurve(sq1FluxRow(group,row,bias))
        datalist.append(data)
    return datalist

def sq1Tune(group,column):
    """
    Runs Sq1FluxRowBias for each row, collecting CurveData objects.
    During this loop, sets the resulting Sq1Bias and Sq1Fb values

    Args
    ----
    group : group
    column : int
        column to operate on
    Returns
    ----
    list
        list of CurveData objects where saOffset subroutine result
        is plotted against sq1Fb. Each curve represents a different
        sq1Bias, and each CurveData object in the list corresponds
        with a different row
    """
    outputs = []
    group.RowForceEn.set(True)
    for row in range(group.NumRows.get()):
        results = sq1FluxRowBias(group,row)
        for data in results:
            data.update()

        group.Sq1Bias.set(index=(row,column),value=results.biasOut)
        group.Sq1Fb.set(index=(row,column),value=results.fbOut)
        outputs.append(results)
    return outputs



#SQ1 DIAGNOSTIC -output vs sq1 feedback for every row  for every column
def sq1Ramp(group,row, column):
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
