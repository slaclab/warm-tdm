import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
import time
from mpl_toolkits.mplot3d import Axes3D #not sure if necessary


#taken from ucsc project
outFile = "summary.pdf"
pdf = matplotlib.backends.backend_pdf.PdfPages(outFile)
figs = plt.figure()



#### not sure where something like this will fit in

with pyrogue.interfaces.VirtualClient(host,port) as client:
    root = client.root
    group = root.group[0]

    tunevalues = saTune()
    group.saBias.set(tunevalues[0])
    group.saOffset.set(tunevalues[1])
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

	for column in (group.numRows.get()):
		saBias[column].set() #still don't know what we are setting these to
		saFb[column].set()


def saOffset(group, fb, row):
	pass
	#is this necessary, or will it be at a lower level?

#SA TUNING
def saFlux(group):
	curve = []
	for fb in : #some set of SA_FB values
		group.saFb.set(fb)
		curve.append(group.saOffset.get())
	return curve
	###
	

def saFluxBias(group):
	data = {'xvalues' : [] #Need to know these
			'curves' : {}}
	for bias in : #some set of SA BIAS values
		data['curves'][bias] = saFlux() #assuming this will return a list

		


def saTune(group):
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
	for bias in fasbiasvalues:
		group.saFb[row].set(bias)
		#is saOut a variable we can access? how will we determine when it is 0


def fasTune(group):
	for row in range(64):
		results = fasFlux(group,row)
		off, on = min(results), max(results) #assuming results is a list




#SQ1 TUNING
def sq1Flux(group,row):
	data = []
	for fb in : #some set of fb
		data.append(saOffset(group,fb,row))

	return data

def sq1FluxRow(group):
	for row in range(group.numRows.get()):
		group.fasBias[row].set(True)  #will on be a boolean?
		group.saFb[row].set(?) #does this come from a config file
	results = sq1Flux(group)

def sq1FluxRowBias(group):
	data = {'xvalues' : [] #Need to know these
			'curves' : {}}
			#with offset as a function of s sq1FB, with each curve being a different sq1Bias
	for bias in sq1biasvalues: #What are these values?
		data['curves'][bias] = sq1FluxRow(group)
		#Do something with sq1FluxRow()
		#maybe data['curves'][bias] = sq1FluxRow()?
		#assuming sq1fluxrow returns a list
	return data

def sq1Tune(group):
	data = []
	for row in range(group.numRows.get()):
		curves = sq1FluxRowBias()
		mid = midpoint(curves)
		data.append((curves,mid))
		#What to do with these results?

#SQ1 DIAGNOSTIC

def sq1Ramp(group,row):
	data = []
	for fb in : #some set of sq1fb values
		data.append(saOffset(group,fb,row))
	return data

def sq1RampRow(group):
	rowsdata = []
	for row in range(group.numRows.get()):
		group.fasBias[row].set(True)
		rowsdata.append(sq1Ramp(group,row))


#TES BIAS DIAGNOSTIC

def tesRamp(group,row):
	offsets = [] #is tesRamp meant to return a list like this?
	for bias in : #some set of tesBias values
		group.tesBias[row].set(bias)
		offset = saOffset(row)
		offsets.append(offset)

def tesRampRow(group):
	data = []
	for row in range(group.numRows.get()):
		group.fasBias[row].set(True)
		data.append(tesRamp(row))
	return data



# accessible variables:
# root.group[n].numCols
# root.group[n].numRows
# root.group[n].tesBias[32]
# root.group[n].saBias[32]
# root.group[n].saOffset[32]
# root.group[n].sq1Bias[32][64]
# root.group[n].sq1Fb[32][64]
# root.group[n].fllEnable
# root.group[n].fasFlux[32][64][2]


#General form: root.group[0].saOffset


