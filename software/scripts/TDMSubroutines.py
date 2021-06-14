import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
from mpl_toolkits.mplot3d import Axes3D #not sure if necessary




#General form: root.group[0].saOffset


def maxPeak(group,data): #Where data is a dict for one graph
	maxcurve = None #[amplitude,minpoint,maxpoint]
	xval = 0
	for curve in data['curves']:
		min_offset_point, max_offset_point = [0,data[curve][0]],[0,data[curve][0]] #store the points of max and min offset
		
		for point in data[curve]:
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
def midpoint(group,curve):
	#given the SA_FLUX curve, find the midpoint
	return curve[2][0] - curve[1][0]/2 #returns midpoint x value



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
def saFluxBias():
	for bias in : #some set of SA BIAS values
		saFlux()

def saFlux():

	### will use something like this (in a loop?)
	root.group[?].SA_OFFSET.get()
	###
	return SA_OFFSET result

def saTune():
	saFluxBiasResults = saFluxBias()
	peak = maxPeak()
	midpoint = midpoint() #very rough idea of what's going on

	#There will be a function to summarize the data in a plot

	return #SA_BIAS, SA_OFFSET & SA_FB

#FAS tuning

with pyrogue.interfaces.VirtualClient(host,port) as client:
    root = client.root
    group = root.group[0]

    tunevalues = saTune()
    group.SA_BIAS.set(tunevalues[0])
    group.SA_OFFSET.set(tunevalues[1])
    group.SA_FB.set(tunevalues[2])

def fasFlux():
	
	
def fasTune():
	for row in range(64):



