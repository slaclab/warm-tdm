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

with warm_tdm_api.GroupRoot() as root:
	pyrogue.pydm.runPyDM(root=root,title='Subroutines',sizeX=1000,sizeY=500) #Probably wrong

#taken from ucsc project
outFile = "summary.pdf"
pdf = matplotlib.backends.backend_pdf.PdfPages(outFile)
figs = plt.figure()


#### not sure where something like this will fit in

with pyrogue.interfaces.VirtualClient(host,port) as client:
    root = client.root
    group = root.group[0]

    tunevalues = saTune()
    group.SaBias.set(tunevalues[0])
    group.SaOffset.set(tunevalues[1])
    group.saFb.set(tunevalues[2])
####



def maxPeak(data): #Where data is a dict for one graph
	maxcurve = None #list of this form: [amplitude,minpoint,maxpoint]
	xval = 0
	for curve in data['curves']:
		min_offset_point, max_offset_point = [0,data[curve][0]],[0,data[curve][0]] #store the points of max and min offset
		for point in data[curve]: #didn't use min/max because wanted to know the index
			if point > max_offset_point:
				max_offset_point = [xval,point]
			if point < min_offset_point:
				min_offset_point = [xval,point]
		
		curve_amplitude = max_offset_point[1] - min_offset_point[1]

		if not maxcurve or curve_amplitude > maxcurve:
			maxcurve = [curve_amplitude, min_offset_point, max_offset_point]

		xval += 1
	return maxcurve


	#given the curve dictionary structure, find SA_BIAS value with max peak to peak
def midpoint(data):
	#given the SA_FLUX curve, find the midpoint
	curve = maxpeak(data)
	return (curve[2][0] - curve[1][0])/2 #returns midpoint x value




#INITIALIZATION AND OFFSET ADJUSTMENT
def initialize(group):
	#Open and read config file (maybe)
	inFile = sys.argv[1]
	for column in (group.NumRows.get()):
		SaBias[column].set() #still don't know what we are setting these to
		saFb[column].set()

def SaOffsetPid(group, fb, row):
# 	Adjusts the SA_OFFSET value to zero out the SA_OUT value read by the ADC
# Resulting SA_OFFSET is made available for readback	
	pid = PID(1, .1, .05)
	pid.setpoint(0) #want to zero the saOut value
	while True: #not sure of the properties of this loop
		out = group.SaOut.get() #get current saout
		control = pid(out) #get control value to set offset to
		group.saOffset.set(control) #set offset
		if : #What will be the condition to exit this loop?
			break
	return control

def SaOffsetSweep(group, fb, row): #optional
	offset = group.SaLowOffset.get()
	while offset < group.SaHighOffset.get():
		SaOffset.set(offset)
		out = SaOut.get()
		if out <= 0:
			break
		offset += group.SaOffsetStepsize.get():
	return offset



#SA TUNING
def saFlux(group,bias):
	curve = []
	saFb = group.SaFbLowOffset.get()
	while saFb <= group.SaFbHighOffset.get(): #some set of SA_FB values
		group.saFb[row?].set(fb)
		curve.append(group.SaOffset.get())
		saFb += group.SaFbStepSize.get()
	return curve

def saFluxBias(group):
	data = {'xvalues' : [],
			'curves' : {}}

	bias = group.SaBiasLowOffset.get()
	while bias <= group.SaBiasHighOffset.get(): #some set of SA BIAS values
		data['curves'][bias] = saFlux(bias) #assuming this will return a list
		bias += group.SaBiasStepSize.get()
	return data

def saTune(group):
	#row agnostic?
	initialize()
	saFluxBiasResults = saFluxBias()
	peak = maxPeak(saFluxBiasResults)
	midpoint = midpoint(saFluxBiasResults) 
	#record sa offset
	#There will be a function to summarize the data in a plot
	return #SA_BIAS, SA_OFFSET & SA_FB



#FAS TUNING
def fasFlux(group,row):
	data = []
	offset = group.FaxFluxLowOffset.get()
	while offset <= group.FasFluxHighOffset.get():
		group.saFb[row].set(offset)
		offset += group.FasFluxStepSize.get()
		#is SaOut a variable we can access? how will we determine when it is 0

def fasTune(group):
	for row in range(64):
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
		group.saFb[row].set(?) #does this come from a config file
	results = sq1Flux(group)

def sq1FluxRowBias(group):
	data = {'xvalues' : [], #Need to know these
			'curves' : {}}
	#with offset as a function of s sq1FB, with each curve being a different Sq1Bias
	sq1Bias = group.Sq1BiasLowOffset.get()
	while saFb <= group.Sq1BiasHighOffset.get():
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
	while saFb <= group.Sq1FbHighOffset.get():
		data.append(SaOffset(group,saFb,row))
		saFb += group.Sq1FbStepSize.get()
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
	while bias <= group.TesBiasHighOffset.get()
		group.TesBias[row].set(bias)
		offset = SaOffset(row)
		offsets.append(offset)
		bias += group.TesBiasStepSize.get()
	return offsets

def tesRampRow(group):
	data = []
	for row in range(group.NumRows.get()):
		group.fasBias[row].set(True)
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

