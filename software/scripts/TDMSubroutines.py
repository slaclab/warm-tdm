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


#test instantiation of curve and data objects

####
def gencurve(l):
	ret = []
	offset = random.uniform(-1,1)
	for i in range(l):
		ret.append(math.sin(i/2) + random.uniform(-.2 + offset,.2 + offset))
	return ret
curvelist = []
for i in range(3):
	curvelist.append(Curve(i + 30,gencurve(20)))

d = CurveData(range(20),curvelist)
# d.plot()
####



def saOffset(group, row):
# 	Adjusts the SA_OFFSET value to zero out the SA_OUT value read by the ADC
# Resulting SA_OFFSET is made available for readback	
	pid = PID(1, .1, .05)
	pid.setpoint = 0 #want to zero the saOut value
	while True: #not sure of the properties of this loop
		out = group.SaOut.get(index=row) #get current saout
		control = pid(out) #get control value to set offset to
		group.SaOffset.set(index=row,value=control) #set offset
		if abs(control) < 1: #What will be the condition to exit this loop?
			break
	print ("took measurement")
	return control


#SA TUNING
def saFlux(group,bias,column,row=0): #Get the data class working with this
	low = group.SaFbLowOffset.get()
	high = group.SaFbHighOffset.get()
	step = group.SaFbStepSize.get()

	curve = Curve(bias)

	for saFb in np.arange(low,high,step):
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

	return data

def saTune(group,column,row=0):
	# group.Init()
	# print("initialized")
	saFluxBiasResults = saFluxBias(group,column,row)
	print("got saFluxBias results")

	peak = saFluxBiasResults.maxPeak()
	print("found maxpeak")
	
	mid = saFluxBiasResults.midpoint()
	print("found midpoint")
	

	return saFluxBiasResults

	
#set row to index 0


#FAS TUNING
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
		off, on = min(results), max(results) #assuming results is a list


#turn on rowtunenable
#SQ1 TUNING
#output vs sq1 feedback for various values of sq1 bias for every row for every column 
def sq1Flux(group,row):
	data = []
	fb = group.Sq1FbLowOffset.get()
	while fb <= group.Sq1FbHighOffset.get(): #some set of fb
		data.append(SaOffset(group,fb,row))
		fb += group.Sq1FbStepSize.get()
	return data

def sq1FluxRow(group):
	for row in range(group.NumRows.get()):
		#on value is not a boolean, change this
		group.fasBias[row].set(True)  #will on be a boolean?
		group.SaFb[row].set() #does this come from a config file
	results = sq1Flux(group)

def sq1FluxRowBias(group):
	data = {'xvalues' : [], #Need to know these
			'curves' : {}}
	#with offset as a function of s sq1FB, with each curve being a different Sq1Bias
	sq1Bias = group.Sq1BiasLowOffset.get()
	while SaFb <= group.Sq1BiasHighOffset.get():
		data['curves'][sq1Bias] = sq1FluxRow(group)
		sq1Bias += group.Sq1BiasStepSize.get()
	return data

def sq1Tune(group):
	data = []
	for row in range(group.NumRows.get()):
		curves = sq1FluxRowBias()
		mid = midpoint(curves)
		data.append((curves,mid))
		#What to do with these results?


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
		group.fasBias[row].set(True)
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


