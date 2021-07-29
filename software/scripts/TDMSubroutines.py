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
# outFile = "summary.pdf"
# pdf = matplotlib.backends.backend_pdf.PdfPages(outFile)

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

def pidLoop(group, row, column, inputvar, precision = 1):
	pid = PID(1, .1, .05) #These constants need to be tuned
	pid.setpoint = 0 #want to zero out SaOut
	while True:
		out = group.SaOut.get(index=row) #get current SaOut
		control = pid(out) #get control value to set offset to
		if column:
			inputvar.set(index = (row,column), value = control)
		else:
			inputvar.set(index=row,value=control)
		if abs(control) < precision: #Exit the loop when within precision range
			break
	return control


# def saOffset(group, row):
# # 	Adjusts the SA_OFFSET value to zero out the SA_OUT value read by the ADC
# # Resulting SA_OFFSET is made available for readback	
# 	pid = PID(1, .1, .05) #These constants need to be tuned
# 	pid.setpoint = 0 #want to zero the saOut value
# 	while True: 
# 		out = group.SaOut.get(index=row) #get current saout
# 		control = pid(out) #get control value to set offset to
# 		group.SaOffset.set(index=row,value=control) #set offset
# 		if abs(control) < 1: 
# 			break
# 	return control

def saOffset(group,row,column, precision = 1):
	return pidLoop(group, row, column, group.SaOffset, precision)

#SA TUNING
def saFlux(group,bias,column,row=0):
	low = group.SaFbLowOffset.get()
	high = group.SaFbHighOffset.get()
	step = group.SaFbStepSize.get()

	curve = Curve(bias)

	for saFb in np.arange(low,high + step,step):
		group.SaFb.set(index = (row,column), value = saFb)
		curve.addPoint(saOffset(group,row,None)) #column is not a component
	
	return curve

def saFluxBias(group,column,row=0):
	low = group.SaBiasLowOffset.get()
	high = group.SaBiasHighOffset.get()
	step = group.SaBiasStepSize.get()

	data = CurveData()

	data.populateXValues(low,high + step,step)

	for bias in np.arange(low, high + step, step): #may be better to use while loop
		data.addCurve(saFlux(group,bias,column,row))
	
	data.update()
	return data

def saTune(group,column,row=0):
	group.Init()
	# print("initialized")
	saFluxBiasResults = saFluxBias(group,column,row)

	group.SaFb.set(index = (row,column), value = saFluxBiasResults.fbOut)
	group.SaOffset.set(index = column, value = saFluxBiasResults.offsetOut)
	group.SaBias.set(index = column, value = saFluxBiasResults.biasOut)

	return saFluxBiasResults

	#set row to index 0


#FAS TUNING

#fasflux is/will be an accessible variable, just need it to be added
def saFb(group,row,column,precision = 1):
	return pidLoop(group,row,column,group.SaFb,precision)

def fasFlux(group,row,column):
	low = group.FasFluxLowOffset.get()
	high = group.FasFluxHighOffset.get()
	step = group.FasFluxStepSize.get()

	data = CurveData()
	data.populateXValues(low,high + step,step)
	curve = Curve(row)

	for flux in np.arange(low,high + step,step):
		group.FasFluxOn.set(index = row, value = flux)
		curve.addPoint(saFb(group,row,column,precision = 1))

	data.addCurve(curve)
	data.update()
	return data

def fasTune(group,column):
	for row in range(group.NumRows.get()):
		results = fasFlux(group,row,column)
		group.FasFluxOn.set(index = row, value = results.bestCurve.points_[results.bestCurve.highindex_]) #Set fas flux on and off values
		group.FasFluxOff.set(index = row, value = results.bestCurve.points_[results.bestCurve.lowindex_])



#turn on rowtunenable
#SQ1 TUNING - output vs sq1 feedback for various values of sq1 bias for every row for every column 
# def sq1Flux():

# def sq1FluxRow():
# def sq1FluxRowBias():
# def sq1Tune():
# 	sq1FluxRowBiasResults = sq1FluxRowBias(col)


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

