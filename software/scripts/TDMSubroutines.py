import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
import time

import pyrogue
import pyrogue.pydm
import rogue

from mpl_toolkits.mplot3d import Axes3D #not sure if necessary
from simple_pid import PID #might be used for saOffset

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')

import warm_tdm_api

#taken from ucsc project
outFile = "summary.pdf"
pdf = matplotlib.backends.backend_pdf.PdfPages(outFile)
figs = plt.figure()


# Data = {‘xvalues’ : [1,2,2,3],
#         ‘curves’ : {34 : [35,23,15,25],
#                     35 : [34,34,34,34,], }
def peak(curvelist):
    low, high = 0 
    for i in range(len(curvelist)):
        if curvelist[i] < curvelist[low]:
            low = i
        elif curvelist[i] > curvelist[high]:
            high = i
    return (low,high,curvelist[high] - curvelist[low])

        
def maxPeak(data):
    highestpeak = 0
    for curve in range(len(data['curves'])):
        height = peak(data['curves'][curve])[2]
        if height > highestpeak:
            highestpeak = height
            #probably need to use .items()?

        
        

# def maxPeak(data): #Where data is a dict for one graph
# 	maxcurve = None #list of this form: [amplitude,minpoint,maxpoint]
# 	xval = 0
# 	for curve in range(len(data['curves'])):
# 		min_offset_point, max_offset_point = [0, data['curves'][curve][0]],[0, data['curves'][curve][0]] #store the points of max and min offset
# 		for point in data['curves'][curve]: #didn't use min/max because wanted to know the index
# 			if point > max_offset_point:
# 				max_offset_point = [xval,point]
# 			if point < min_offset_point:
# 				min_offset_point = [xval,point]
		
# 		curve_amplitude = max_offset_point[1] - min_offset_point[1]

# 		if not maxcurve or curve_amplitude > maxcurve:
# 			maxcurve = [curve_amplitude, min_offset_point, max_offset_point]

# 		xval += 1
# 	return maxcurve


	#given the curve dict structure, find SA_BIAS value with max peak to peak
def midpoint(data): #given the SA_FLUX curve, find the midpoint
	curve = maxpeak(data)
	return (curve[2][0] - curve[1][0])/2 #returns midpoint x value

def saOffset(group, fb, row):
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
	return control

def saOffsetSweep(group, fb, row): #optional
	offset = group.SaLowOffset.get()
	while offset < group.SaHighOffset.get():
		SaOffset.set(value=offset)
		out = SaOut.get()
		if out <= 0:
			break
		offset += group.SaOffsetStepsize.get()
	return offset



#SA TUNING
def saFlux(group,bias,column,row=0):
	curve = []
	SaFb = group.SaFbLowOffset.get()
	while SaFb <= group.SaFbHighOffset.get():
		group.SaFb.set(index=(row,column),value=SaFb) 
		curve.append(saOffset(group,SaFb,row))
		SaFb += group.SaFbStepSize.get()
	return curve

def saFluxBias(group,column,row=0):
	data = {'xvalues' : [],
			'curves' : {}}

	bias = group.SaBiasLowOffset.get()
	while bias <= group.SaBiasHighOffset.get():
		data['curves'][bias] = saFlux(group,bias,row,column) 
		bias += group.SaBiasStepSize.get()
	return data


def saTune(group,column,row=0):
	# group.Init()
	# print("initialized")
	saFluxBiasResults = saFluxBias(group,row,column)
	print("got saFluxBias results")

	peak = maxPeak(saFluxBiasResults)
	print("found maxpeak")
	
	midpoint = midpoint(saFluxBiasResults)
	print("found midpoint")
	#record sa offset
	#There will be a function to summarize the data in a plot
	return #SA_BIAS, SA_OFFSET & SA_FB

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


