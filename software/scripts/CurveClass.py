import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf


class CurveData():
	
	def __init__(self,xvalues = [],curves = []):
		self.xValues_ = xvalues[:]
		self.curveList_ = curves[:]
		self.maxPeakCurve = None
		self.biasOut = None
		self.offsetOut = None
		self.fbOut = None

	def update(self):
		self.maxPeak()
		self.midPoint()
	
	def maxPeak(self):
		self.updateCurves()
		for curve in self.curveList_:
			if self.maxPeakCurve is None or curve.peakheight_ > self.maxPeakCurve.peakheight_:
				self.maxPeakCurve = curve
		self.biasOut = self.maxPeakCurve.bias_
	
	def updateCurves(self):
		for curve in self.curveList_:
			curve.updatePeak()

	def populateXValues(self,low,high,step):
		for xvalue in np.arange(low,high + step,step):
			self.addFb(xvalue)

	
	def plot(self):
		self.update() #might not want to call this here
		fig = plt.figure()
		ax = fig.add_subplot(111)
		for curveindex in range(len(self.curveList_)):
			ax.plot(self.xValues_,self.curveList_[curveindex].points_) #plot the curves
		ax.plot(self.xValues_[self.maxPeakCurve.highindex_],self.maxPeakCurve.points_[self.maxPeakCurve.highindex_],"^") #plot the max point
		ax.plot(self.xValues_[self.maxPeakCurve.lowindex_],self.maxPeakCurve.points_[self.maxPeakCurve.lowindex_],"v")#plot the min point
		ax.plot(self.fbOut,self.offsetOut,"s")
		plt.show()
	
	def midPoint(self):
		curve = self.maxPeakCurve
		midY = (curve.points_[curve.highindex_] + curve.points_[curve.lowindex_]) / 2
		self.offsetOut = midY
		midX = (curve.highindex_ + curve.lowindex_)/2
		self.fbOut = midX

	def addCurve(self,curve):
		self.curveList_.append(curve)

	def addFb(self,fb):
		self.xValues_.append(fb)

	def asDict(self):
		curvedict = {}
		for curve in self.curveList_:
			curvedict[curve.bias_] = curve.points_[:]
		return {'xValues':self.xValues_, 'curves':curvedict}

	def __repr__(self):
		return str(self.asDict())

class Curve():
#plotting offset as a function of sq1FB, with each curve being a different sq1Bias
	def __init__(self,bias,points = []):
		self.bias_ = bias
		self.points_ = points[:]
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