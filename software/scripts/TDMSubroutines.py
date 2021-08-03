import numpy as np
import sys
import math
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
import time
import random #for testing purposes

import pyrogue
import pyrogue.pydm
import rogue

from mpl_toolkits.mplot3d import Axes3D #not sure if necessary

from simple_pid import PID #for saOffset

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')

import warm_tdm_api

from CurveClass import *

def pidLoop(group,row,column,inputvar,precision=1):
	pid = PID(1,.1,.05) #These constants need to be tuned
	pid.setpoint = 0 #want to zero out SaOut
	while True:
		out = group.SaOut.get(index=row) #get current SaOut
		control = pid(out) #get control value to set offset to
		if column is not None:
			inputvar.set(index=(column,row),value=control)
		else:
			inputvar.set(index=row,value=control)
		if abs(control) < precision: #Exit the loop when within precision range
			return control

def saOffset(group,row,column,precision=1):
	return pidLoop(group,row,None,group.SaOffset,precision)



#SA TUNING
def saFlux(group,bias,column,row = 0):
	low = group.SaFbLowOffset.get()
	high = group.SaFbHighOffset.get()
	step = group.SaFbStepSize.get()

	curve = Curve(bias)

	for saFb in np.arange(low,high+step,step):
		group.SaFb.set(index=(row,column),value=saFb)
		curve.addPoint(saOffset(group,row,None)) #column is not a component
	
	return curve

def saFluxBias(group,column,row = 0):
	low = group.SaBiasLowOffset.get()
	high = group.SaBiasHighOffset.get()
	step = group.SaBiasStepSize.get()

	data = CurveData()

	data.populateXValues(low,high+step,step)

	for bias in np.arange(low,high+step,step): #may be better to use while loop
		data.addCurve(saFlux(group,bias,column,row))
	
	data.update()
	return data

def saTune(group,column,row = 0):
	group.Init()

	saFluxBiasResults = saFluxBias(group,column,row)

	group.SaFb.set(index=(row,column),value=saFluxBiasResults.fbOut)
	group.SaOffset.set(index=column,value=saFluxBiasResults.offsetOut)
	group.SaBias.set(index=column,value=saFluxBiasResults.biasOut)

	return saFluxBiasResults



#FAS TUNING
def saFb(group,row,column,precision=1):
	return pidLoop(group,row,column,group.SaFb,precision)

def fasFlux(group,row,column):
	low = group.FasFluxLowOffset.get()
	high = group.FasFluxHighOffset.get()
	step = group.FasFluxStepSize.get()

	data = CurveData()
	data.populateXValues(low,high+step,step)
	curve = Curve(row)

	for flux in np.arange(low,high+step,step):
		group.FasFluxOn.set(index=row,value=flux)
		curve.addPoint(saFb(group,row,column,precision=1))

	data.addCurve(curve)
	data.update()
	return data

def fasTune(group,column):
	curves = []
	for row in range(group.NumRows.get()):
		results = fasFlux(group,row,column)
		group.FasFluxOn.set(index=row,value=results.bestCurve.points_[results.bestCurve.highindex_]) #Set fas flux on and off values
		group.FasFluxOff.set(index=row,value=results.bestCurve.points_[results.bestCurve.lowindex_])
		curves.append(results)
	return curves	



#SQ1 TUNING - output vs sq1fb for various values of sq1 bias for every row for every column 
def sq1Flux(group,bias,column,row):
	low = group.Sq1FbLowOffset.get()
	high = group.Sq1FbHighOffset.get()
	step = group.Sq1FbStepSize.get()
	curve = Curve(bias)
	for fb in np.arange(low,high+step,step):
		group.Sq1Fb.set(index=(column,row),value=fb)
		offset = saOffset(group,row,None)
		curve.addPoint(offset)
	return curve

def sq1FluxRow(group,column,row,bias):
	for row in range(group.NumRows.get()):
		group.RowTuneIndex.set(row)
		group.RowTuneEn.set(True)
		#set the corresponding saFb value for the row (?)
	curve = sq1Flux(group,bias,column,row)
	return curve
	
def sq1FluxRowBias(group,column,row):
	low = group.Sq1BiasLowOffset.get()
	high = group.Sq1BiasHighOffset.get()
	step = group.Sq1BiasStepSize.get()

	lowFb = group.Sq1FbLowOffset.get()
	highFb = group.Sq1FbHighOffset.get()
	stepFb= group. Sq1FbStepSize.get() 

	data = CurveData()
	data.populateXValues(lowFb,highFb+stepFb,stepFb) #data object is set up

	for bias in np.arange(low,high+step,step):
		data.addCurve(sq1FluxRow(group,column,row,bias))
	return data

def sq1Tune(group,column):
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
	low = group.Sq1FbLowOffset.get()
	high = group.Sq1FbHighOffset.get()
	step = group.Sq1FbStepSize.get()

	outputs = []
	for fb in np.arange(low,high+step,step):
		group.Sq1Fb.set(index=(column,row),value=fb)
		offset = saOffset(group,row,column)
		outputs.append(offset)
	return outputs

def sq1RampRow(group,column):
	for row in range(group.NumRows.get()):
		group.RowTuneIndex.set(row)
		group.RowTuneEn.set(True)
		sq1RampResults = sq1Ramp(group,row,column)
	group.RowTuneEn.set(False)



#TES BIAS DIAGNOSTIC - what to do with this data?
def tesRamp(group,row, column):
	low = group.TesBiasLowOffset.get()
	high = group.TesBiasHighOffset.get()
	step = group.TesBiasStepSize.get()

	outputs = []
	for bias in np.arange(low,high,step):
		group.TesBias.set(index=row,value=bias)
		offset = saOffset(group,row,column=0)
		outputs.append(offset)
	return outputs

def tesRampRow(group,column):
	for row in range(group.NumRows.get()):
		#group.fasBias.set(index=row, value=group.fasFluxOn.get()) #Not this 
		group.RowTuneIndex.set(row)
		group.RowTuneEn.set(True)
		tesRampResults = tesRamp(group,row,column)
	group.RowTuneEn.set(False)


