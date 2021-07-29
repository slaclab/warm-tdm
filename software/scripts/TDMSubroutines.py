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
outFile = "summary.pdf"
pdf = matplotlib.backends.backend_pdf.PdfPages(outFile)

#### for testing
def gencurve(l):
	ret = []
	offset = random.uniform(-1,1)
	for i in range(l):
		ret.append(math.sin(i/2) + random.uniform(-.2 + offset,.2 + offset))
	return ret
curvelist = []
for i in range(3):
	curvelist.append(Curve(i + 30,gencurve(20)))

c = CurveData(list(range(20)),curvelist)
c.update()
# d.plot()
####


def saOffset(group, row):
# 	Adjusts the SA_OFFSET value to zero out the SA_OUT value read by the ADC
# Resulting SA_OFFSET is made available for readback	
	pid = PID(1, .1, .05) #These constants need to be tuned
	pid.setpoint = 0 #want to zero the saOut value
	while True: 
		out = group.SaOut.get(index=row) #get current saout
		control = pid(out) #get control value to set offset to
		group.SaOffset.set(index=row,value=control) #set offset
		if abs(control) < 1: 
			break
	return control


#SA TUNING
def saFlux(group,bias,column,row=0):
	low = group.SaFbLowOffset.get()
	high = group.SaFbHighOffset.get()
	step = group.SaFbStepSize.get()

	curve = Curve(bias)

	for saFb in np.arange(low,high + step,step):
		group.SaFb.set(index = (row,column), value = saFb)
		curve.addPoint(saOffset(group,row))
	
	return curve

def saFluxBias(group,column,row=0):
	low = group.SaBiasLowOffset.get()
	high = group.SaBiasHighOffset.get()
	step = group.SaBiasStepSize.get()

	data = CurveData()

	data.populateXValues(low,high,step)

	for bias in np.arange(low, high + step, step): #may be better to use while loop
		data.addCurve(saFlux(group,bias,column,row))
	
	data.update()
	return data

def saTune(group,column,row=0):
	group.Init()
	# print("initialized")
	saFluxBiasResults = saFluxBias(group,column,row)

	peak = saFluxBiasResults.maxPeak()
	
	mid = saFluxBiasResults.midPoint()
	

	return saFluxBiasResults

	#set row to index 0


#FAS TUNING

#fasflux is/will be an accessible variable, just need it to be added
def fasFlux(group,row):
	data = []
	offset = group.FasFluxLowOffset.get()
	while offset <= group.FasFluxHighOffset.get():
		group.SaFb[row].set(offset)
		offset += group.FasFluxStepSize.get()
		#is SaOut a variable we can access? how will we determine when it is 0

def fasTune(group):
	for row in range(group.NumRows.get()):
		results = fasFlux(group,row)
		off, on = min(results), max(results) #wrong, need to change


#turn on rowtunenable
#SQ1 TUNING
#output vs sq1 feedback for various values of sq1 bias for every row for every column 
def sq1Flux(group,row,bias):
	low = group.Sq1FbLowOffset.get()
	high = group.Sq1FbHighOffset.get()
	step = group.Sq1FbStepSize.get()
	
	curve = Curve(bias)
	for fb in np.arange(low,high,step):
		return
	while fb <= group.Sq1FbHighOffset.get(): #some set of fb
		data.append(SaOffset(group,fb,row))
		fb += group.Sq1FbStepSize.get()
	return data

def sq1FluxRow(group,sq1Bias):
	for row in range(group.NumRows.get()):
		group.fasBias[row].set(on)  #At what level will this be stored
		group.SaFb[row].set() #does this come from a config file
	results = sq1Flux(group)

def sq1FluxRowBias(group):
	pass
	

def sq1Tune(group):
	sq1FluxRowBiasResults = sq1FluxRowBias(group)
	for row in range(group.NumRows.get()): 
		#Record sq1 bias value which results in the max peak to peak in the sq1 flux curve
		data = sq1FluxRowBias()
		#record sq1 fb value at the midpoint between high and low point in the sq1flux curve
		#This is done within the class
	
	return #?

def sq1Flux(group):
	pass
def sq1FluxRow(group,sq1Bias):
	something = Curve(sq1Bias)

	for row in range(group.NumRows.get()):
		group.FasFlux.set(group.FasFluxOn)

def sq1FluxRowBias(group):
	low = group.Sq1BiasLowOffset.get()
	high = group.Sq1BiasHighOffset.get()
	step = group.Sq1BiasStepSize.get()
	
	data.populateXValues(low,high,step)

	data = CurveData()

	for sq1Bias in np.arange(low,high,step):
		data.addCurve(sq1FluxRow(group,sq1Bias)) #with offset as a function of sq1FB, with each curve being a different Sq1Bias
	
	data.update()

	return data


def sq1Tune(group):
	data = sq1FluxRowBias()

	for row in range(group.NumRows.get()): #or maybe for row in a list of curvedata objects
		pass
		#record sq1Bias value which results in the largest peak to peak value in the sq1Flux curve
		#record sq1Fb value at the midpoint between a high and low point in the chosen sq1flux curve
		#these are both done by the class


#SQ1 DIAGNOSTIC
#output vs sq1 feedback for every row  for every column
def sq1Ramp(group,row):
	data = []
	sq1Fb = group.Sq1FbLowOffset.get()
	while SaFb <= group.Sq1FbHighOffset.get():
		data.append(SaOffset(group,SaFb,row))
		SaFb += group.Sq1FbStepSize.get()
	return data

def sq1RampRow(group):
	rowsdata = []
	for row in range(group.NumRows.get()):
		group.fasBias[row].set(on)
		rowsdata.append(sq1Ramp(group,row))


#TES BIAS DIAGNOSTIC
def tesRamp(group,row): #out vs tes for row for column 
	offsets = [] #is tesRamp meant to return a list like this?
	bias = group.TesBiasLowOffset.get()
	while bias <= group.TesBiasHighOffset.get():
		group.TesBias[row].set(bias)
		offset = SaOffset(row)
		offsets.append(offset)
		bias += group.TesBiasStepSize.get()
	return offsets

def tesRampRow(group):
	data = []
	for row in range(group.NumRows.get()):
		group.FasBias[row].set(True)
		data.append(tesRamp(row))
	return data



# accessible variables:
# root.group[n].NumColumns
# root.group[n].NumRows
# root.group[n].TesBias[32]
# root.group[n].SaBias[32]
# root.group[n].SaOffset[32]
# root.group[n].Sq1Bias[32][64]
# root.group[n].Sq1Fb[32][64]
# root.group[n].FllEnable
# root.group[n].fasFlux[32][64][2]


#General form: root.group[0].SaOffset

