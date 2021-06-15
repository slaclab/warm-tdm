import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
from mpl_toolkits.mplot3d import Axes3D #not sure if necessary


#taken from ucsc project
outFile = "summary.pdf"
pdf = matplotlib.backends.backend_pdf.PdfPages(outFile)
figs = plt.figure()

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



#Enable mask
#TES bias value for 8 channels

#Set SA_FB and SA_BIAS to initial values
def initialize(): #INIT? didn't want to use "init"
	#Open and read config file
	inFile = sys.argv[1]

	#check for num of sys arguments

	tesBiases = [] #Maybe these will be stored as a list?
	with open(inFile) as f:
		pass
		#How many lines will there be to read in?


	#Will we be iterating through each group, or just working on one group per instance?

	for column in range(32):
		#Drive high current on TES_BIAS

		root.group[?].tesBias[column].high_current()
		root.group[?].tesBias[column].set(tesBiases[column])

	for row in range(64):
		root.group[?].superconducting.set(False) # or "Off"?

	#Turn on FLL logic




with pyrogue.interfaces.VirtualClient(host,port) as client:
    root = client.root
    group = root.group[0]

    tunevalues = saTune()
    group.saBias.set(tunevalues[0])
    group.saOffset.set(tunevalues[1])
    group.saFb.set(tunevalues[2])

#SA TUNING
def saFlux(group):
	curve = []
	for feedback in : #some set of SA_FB values
		group.saFb.set(feedback)
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
def fasFlux(group):
	for bias in fasbiasvalues:

def fasTune(group):
	for row in range(64):
		results = fasFlux()
		off, on = min(results), max(results) #assuming results is a list



#SQ1 TUNING
def sq1Flux(group):
	pass
	#is this needed, or does it happen at a lower level?

def sq1Flux(group):
	pass

def sq1FluxRow(group):
	#confused
	results = sq1Flux()

def sq1FluxRowBias(group):
	data = {'xvalues' : [] #Need to know these
			'curves' : {}}
			#with offset as a function of s sq1FB, with each 
			#curve being a different sq1Bias


	for bias in sq1biasvalues: #What are these values?
		data['curves'][bias] = []
		#Do something with sq1FluxRow()
		sq1FluxRow()
		#maybe data['curves'][bias] = sq1FluxRow()?
		#not sure what data type is returned by sq1Fluxrow


def sq1Tune(group):
	for row in range(group.numRows.get()):
		data = sq1FluxRowBias()
		mid = midpoint(data)
		#What to do with these results?





