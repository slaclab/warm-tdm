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

def saOffset(group,row,column,precision=1):
    """Returns float.
    Calls pidLoop using saOffset as the input variable
    """
    lowerbound = -100 
    upperbound = 100
    return pidLoop(group,row,None,group.SaOffset,lowerbound,upperbound,precision)



#SA TUNING
def saFlux(group,bias,column,row = 0):
    """Returns a Curve object.
    Iterates through SaFb values determined by lowoffset,highoffset,step and 
    calls SaOffset to generate points
    """
    low = group.SaFb.get(index=(column,row)) + group.SaFbLowOffset.get()
    high = group.SaFb.get(index=(column,row)) + group.SaFbHighOffset.get()
    step = group.SaFbStepSize.get()

    curve = cc.Curve(bias)

    for saFb in np.arange(low,high+step,step):
        group.SaFb.set(index=(row,column),value=saFb)
        curve.addPoint(saOffset(group,row,None)) #column is not a component
    
    return curve

def saFluxBias(group,column,row = 0):
    """Returns a CurveData object.
    Iterates through SaBias values determined by low,high,step and calls 
    saFlux to generate curves.
    """
    low = group.SaBias.get(index=column) + group.SaBiasLowOffset.get()
    high = group.SaBias.get(index=column) + group.SaBiasHighOffset.get()
    step = group.SaBiasStepSize.get()

    data = cc.CurveData()

    data.populateXValues(low,high+step,step)

    for bias in np.arange(low,high+step,step):
        data.addCurve(saFlux(group,bias,column,row))
    
    data.update()
    return data
    
def saTune(group,column,row = 0):
    """Returns a CurveData object.
    Initializes group
    Runs saFluxBias and collects and sets SaFb, SaOffset, and SaBias
    """
    group.Init()
    saFluxBiasResults = saFluxBias(group,column,row)
    group.SaFb.set(index=(row,column),value=saFluxBiasResults.fbOut)
    group.SaOffset.set(index=column,value=saFluxBiasResults.offsetOut)
    group.SaBias.set(index=column,value=saFluxBiasResults.biasOut)

    return saFluxBiasResults



#FAS TUNING
def saFb(group,row,column,precision=1):
    #Returns (float) SaFb value which zeros out SaOut
    lowerbound = -100
    upperbound = 100
    return pidLoop(group,row,column,group.SaFb,lowerbound,upperbound,precision)

def fasFlux(group,row,column):
    """Returns a CurveData object.
    Iterates through FasFluxOn values determined by 
    lowoffset,highoffset,step,calling saFb to generate points. Adds
    this curve to a CurveData object.
    """
    low = group.FasFluxOn.get(index=row) + group.FasFluxLowOffset.get()
    high = group.FasFluxOn.get(index=row) + group.FasFluxHighOffset.get()
    step = group.FasFluxStepSize.get()

    data = cc.CurveData()
    data.populateXValues(low,high+step,step)
    curve = cc.Curve(row)

    for flux in np.arange(low,high+step,step):
        group.FasFluxOn.set(index=row,value=flux)
        curve.addPoint(saFb(group,row,column,precision=1))

    data.addCurve(curve)
    data.update()
    return data

def fasTune(group,column):
    """Returns a list of CurveData objects.
    Iterate through all rows, measuring results from
    fasFlux subroutine, and setting FasFluxOn and FasFluxOff
    accordingly. 
    """
    curves = []
    for row in range(group.NumRows.get()):
        results = fasFlux(group,row,column)
        group.FasFluxOn.set(index=row,value=results.bestCurve.points_[results.bestCurve.highindex_]) #Set fas flux on and off values
        group.FasFluxOff.set(index=row,value=results.bestCurve.points_[results.bestCurve.lowindex_])
        curves.append(results)
    return curves   



#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column 
def sq1Flux(group,bias,column,row):
    """Returns Curve object.
    Iterates through Sq1Fb values determined by lowoffset,highoffset,step
    Generates curve points with saOffset()
    """
    low = group.Sq1Fb.get(index=(column,row)) + group.Sq1FbLowOffset.get()
    high = group.Sq1Fb.get(index=(column,row)) + group.Sq1FbHighOffset.get()
    step = group.Sq1FbStepSize.get()
    curve = cc.Curve(bias)
    for fb in np.arange(low,high+step,step):
        group.Sq1Fb.set(index=(column,row),value=fb)
        offset = saOffset(group,row,None)
        curve.addPoint(offset)
    return curve

def sq1FluxRow(group,column,row,bias):
    """Returns Curve object. 
    Iterates through rows, enabling tuning for each row.
    Calls sq1Flux on row passed as argument
    """
    for row in range(group.NumRows.get()):
        group.RowTuneIndex.set(row)
        group.RowTuneEn.set(True)
        #set the corresponding saFb value for the row (wouldn't they already have been set?) 
    curve = sq1Flux(group,bias,column,row)
    return curve

def sq1FluxRowBias(group,column,row):
    """Returns CurveData object.
    Iterates through Sq1Bias values determined by lowoffset,highoffset,step,
    and gets curves by calling sq1FluxRow

    """
    low = group.Sq1Bias.get(index=(column,row)) + group.Sq1BiasLowOffset.get()
    high = group.Sq1Bias.get(index=(column,row)) + group.Sq1BiasHighOffset.get()
    step = group.Sq1BiasStepSize.get()

    lowFb = group.Sq1Fb.get(index=(column,row)) + group.Sq1FbLowOffset.get()
    highFb = group.Sq1Fb.get(index=(column,row)) + group.Sq1FbHighOffset.get()
    stepFb= group.Sq1FbStepSize.get() 

    data = cc.CurveData()
    data.populateXValues(lowFb,highFb+stepFb,stepFb) 

    for bias in np.arange(low,high+step,step):
        data.addCurve(sq1FluxRow(group,column,row,bias))
    return data

def sq1Tune(group,column):
    """Returns list of CurveData Objects
    Runs Sq1FluxRowBias for each row, collecting CurveData objects.
    During this loop, sets the resulting Sq1Bias and Sq1Fb values
    """
    outputs = []
    group.RowTuneEn.set(True)
    for row in range(group.NumRows.get()):
        results = sq1FluxRowBias(group,column,row)
        results.update()

        group.Sq1Bias.set(index=(row,column),value=results.biasOut)
        group.Sq1Fb.set(index=(row,column),value=results.fbOut)
        outputs.append(results)
    return outputs



#SQ1 DIAGNOSTIC -output vs sq1 feedback for every row  for every column
def sq1Ramp(group,row, column):
    """Returns list of offsets that zero out SaOut depending on the bias
    Iterates through Sq1Fb values determined by lowoffset,highoffset,step
    and records output of saOffset().
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
        group.RowTuneIndex.set(row)
        group.RowTuneEn.set(True)
        sq1RampResults = sq1Ramp(group,row,column)
    group.RowTuneEn.set(False)



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
        #group.fasBias.set(index=row, value=group.fasFluxOn.get()) #Not this 
        group.RowTuneIndex.set(row)
        group.RowTuneEn.set(True)
        tesRampResults = tesRamp(group,row,column)
    group.RowTuneEn.set(False)


