import numpy as np
import sys
import math
import time
import random #for testing purposes

import pyrogue
import pyrogue.pydm
import rogue

from simple_pid import PID #for saOffset

import CurveClass as cc

import warm_tdm_api

#pid loop 

def pidLoop(group,row,column,inputvar,lowerbound,upperbound,precision=1):
    """Returns value that gets SaOut within a defined precision range.
    """
    pid = PID(1,.1,.05) #These constants need to be tuned
    pid.setpoint = 0 #want to zero out SaOut
    while True:
        out = group.SaOut.get(index=row) #get current SaOut
        assert(out < upperbound)
        assert(out > lowerbound)
        control = pid(out) #get control value to set offset to

        #time.sleep(0.1) #settling time

        if column is not None:
            inputvar.set(index=(column,row),value=control)
        else:
            inputvar.set(index=row,value=control)
        if abs(control) < precision: #Exit the loop when within precision range
            return control

def saOffset(group,row,column,precision=1): #put the column loop in here 
    """Returns float.
    Calls pidLoop using saOffset as the input variable.
    """
    lower = -100 
    upper = 100
    percolumnresult = []
    for col in range(len(group.ColMap.get())):
        percolumnresult.append(pidLoop(group=group,
                   row=row,
                   column=None,
                   inputvar=group.SaOffset,
                   lowerbound=lower,
                   upperbound=upper,
                   precision=precision)



#SA TUNING
def saFlux(group,bias,row = 0):
    """Returns a list of Curves objects.
    Iterates through SaFb values determined by lowoffset,highoffset,step and 
    calls SaOffset to generate points
    """
    curves = []
    saFbOffsetRange = []

    for col in range(len(group.ColMap.get())):
        low = group.SaFbLowOffset.get(index=(col,row)) + group.SaFbLowOffset.get()
        high = group.SaBiasHighOffset.get(index=(col,row)) + group.SaFbHighOffset.get()
        numsteps = group.SaFbNumSteps.get(index=col)
        saFbOffsetRange.append(np.linspace(low,high,numsteps,endpoint=True))

    for col in range(len(group.ColMap.get())):

        # low[col] = group.SaFb.get(index=(col,row)) + group.SaFbLowOffset.get()
        # high[col] = group.SaFb.get(index=(col,row)) + group.SaFbHighOffset.get()
        # step[col] = group.SaFbStepSize.get() #Doesn't need to be inside of loop, including for simplicity
        # saFbOffsetRange[col] = [low[col], ... high[col]]
        # curves[col] = cc.Curve(bias)

        curves.append(cc.Curve(bias))

    for idx in range(len(saFbOffsetRange[0])):

        for col in range(len(group.ColMap.get())):
            group.SaFb.set(index=(row,col),value=saFbOffsetRange[col][idx])

        points = saOffset(group,row)

        for col in range(len(group.ColMap.get())):
            curves[col].addPoint(points[col])

    return curves

def saFluxBias(group,row = 0):
    """Returns a list of CurveData objects.
    Creates a list of CurveData objects, corresponding to each
    column
    Iterates through SaBias values determined by low,high,
    step and calls saFlux to generate curves, adding them 
    to their corresponding data objects
    """
    step = group.SaBiasStepSize.get()

    datalist = []
    for col in range(len(group.ColMap.get())):
        low = group.SaBias.get(index=col) + group.SaBiasLowOffset.get()
        high = group.SaBias.get(index=col) + group.SaBiasHighOffset.get()

        data = cc.CurveData()
        data.populateXValues(low,high+step,step)
        datalist.append(data)

    for bias in np.arange(low,high+step,step):
        curves = saFlux(group,bias,row)
        for dataindex in range(len(datalist)):
            datalist[dataindex].addCurve(curves[dataindex])
    for dataobject in datalist:
        dataobject.update()

    return datalist

def saTune(group,row = 0):
    """
    Initializes group, runs saFluxBias and collects and sets SaFb, SaOffset, and SaBias
    Returns a list of CurveData objects
    Args
    ----
    group : group
    row : int
        row to operate on, default to zero

    Returns
    ----
    CurveData object where result of saOffset subroutine
     is plotted against SaFb values, which each curve 
     representing a different bias.
    """
    group.Init()
    saFluxBiasResults = saFluxBias(group,row)
    for col in range(len(group.ColMap.get())):
        group.SaFb.set(index=(row,col),value=saFluxBiasResults[col].fbOut)
        group.SaOffset.set(index=col,value=saFluxBiasResults[col].offsetOut)
        group.SaBias.set(index=col,value=saFluxBiasResults[col].biasOut)
    return saFluxBiasResults



#FAS TUNING
def saFb(group,row,precision=1):
    """Returns list of SaFb values which zero out SaOut. 
    Each element corresponds with a column 
    """
    lowerbound = -100
    upperbound = 100
    colresults = []
    for col in range(len(group.ColMap.get())):
        pidresult = pidLoop(group=group,
                            row=row,
                            column=col,
                            inputvar=group.SaFb,
                            lowerbound=lowerbound,
                            upperbound=upperbound,
                            precision=precision)
        colresults.append(pidresult)
    return colresults 

def fasFlux(group,row):
    """Returns a list of CurveData objects, each element corresponding to a column.
    Iterates through FasFluxOn values determined by 
    lowoffset,highoffset,step,calling saFb to generate
     points. Adds this curve to a CurveData object.
    """
    low = group.FasFluxOn.get(index=row) + group.FasFluxLowOffset.get()
    high = group.FasFluxOn.get(index=row) + group.FasFluxHighOffset.get()
    step = group.FasFluxStepSize.get()

    datalist = []
    saFbResults = saFb(group,row,precision=1)


    group.FasFluxOn.set(index=row,value=flux)
    for col in range(len(group.ColMap.get())):

       
        data = cc.CurveData()
        data.populateXValues(low,high+step,step)
        coldata = [data]*len(group.ColMap.get())
        curve = cc.Curve(row)

        for flux in np.arange(low,high+step,step):
            
            curve.addPoint(saFbResults[col]) #Confused about this
        
        data.addCurve(curve)
        data.update()
        datalist.append(data)
    return datalist

def fasTune(group):
    """
    Iterate through all rows, measuring results from
    fasFlux subroutine, and setting FasFluxOn and FasFluxOff
    accordingly. 

    Args
    ----
    group : group
    column : int
        column to operate on
    Returns
    ----
    list
        list of CurveData objects where result of saFb
        subroutine is plotted against fasFlux
    """
    curves = []
    for row in range(group.NumRows.get()):
        results = fasFlux(group,row)
        group.FasFluxOn.set(index=row,value=results.bestCurve.points_[results.bestCurve.highindex_][0]) #Set fas flux on and off values
        group.FasFluxOff.set(index=row,value=results.bestCurve.points_[results.bestCurve.lowindex_][0])
        curves.append(results)
    return curves



#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column 
def sq1Flux(group,bias,row):
    """Returns list of curve objects.
    Iterates through Sq1Fb values determined by lowoffset,
    highoffset,step. Generates curve points with saOffset()
    """
    curves = []
    for col in range(len(group.ColMap.get())):
        low = group.Sq1Fb.get(index=(col,row)) + group.Sq1FbLowOffset.get()
        high = group.Sq1Fb.get(index=(col,row)) + group.Sq1FbHighOffset.get()
        step = group.Sq1FbStepSize.get()

        curve = cc.Curve(bias)
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
        #set the corresponding saFb value for the row (wouldn't they already have been set?) 
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

        data = cc.CurveData()
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


