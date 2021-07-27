import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf


class CurveData():
	
	def __init__(self,xvalues = [],curves = []):
		self.xValues_ = xvalues
		self.curveList_ = curves
		self.maxPeakCurve = None
	
	def maxPeak(self):
		self.updateCurves()
		for curve in self.curveList_:
			if not self.maxPeakCurve or curve.peakheight_ > self.maxPeakCurve.peakheight_:
				self.maxPeakCurve = curve
	
	def updateCurves(self):
		for curve in self.curveList_:
			curve.updatePeak()

	def populateXValues(self,low,high,step):
		print("populating")
		i = low
		while i <= high:
			self.addFb(i)
			i += step
	
	def plot(self):
		self.maxPeak() #might not want to call this here
		fig = plt.figure()
		ax = fig.add_subplot(111)
		for curveindex in range(len(self.curveList_)):
			ax.plot(self.xValues_,self.curveList_[curveindex].points_) #plot the curves
		ax.plot(self.xValues_[self.maxPeakCurve.highindex_],self.maxPeakCurve.points_[self.maxPeakCurve.highindex_],"^") #plot the max point
		ax.plot(self.xValues_[self.maxPeakCurve.lowindex_],self.maxPeakCurve.points_[self.maxPeakCurve.lowindex_],"v")#plot the min point
		plt.show()
	
	def midpoint(self):
		return (self.maxPeakCurve.points_[self.maxPeakCurve.highindex_] + self.maxPeakCurve.points_[self.maxPeakCurve.lowindex_]) / 2
	
	def asDict(self):
		curvedict = {}
		for curve in self.curveList_:
			curvedict[curve.bias_] = curve.points_[:]
		return {'xValues':self.xValues_, 'curves':curvedict}

	def __repr__(self):
		return str(self.asDict())

	def addCurve(self,curve):
		self.curveList_.append(curve)

	def addFb(self,fb):
		self.xValues_.append(fb)


class Curve():
#plotting offset as a function of sq1FB, with each curve being a different sq1Bias
	def __init__(self,bias,points = []):
		self.bias_ = bias
		self.points_ = points
		self.lowindex_ = 0
		self.highindex_ = 0
		self.peakheight_ = 0
		self.midpoint_ = 0

	def updatePeak(self):
		for i in range(len(self.points_)):
			if self.points_[i] < self.points_[self.lowindex_]:
				self.lowindex_ = i
			elif self.points_[i] > self.points_[self.highindex_]:
				self.highindex_ = i
		self.peakheight_ = self.points_[self.highindex_] - self.points_[self.lowindex_]

	def addPoint(self,point):
		self.points_.append(point)