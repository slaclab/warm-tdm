import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf


class CurveData():
	def __init__(self,xvalues,curves):
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
	def plot(self):
		pass


class Curve():
	def __init__(self,sq1Fb,points):
		self.sq1Fb_ = sq1Fb
		self.points_ = points
		self.lowindex_ = 0
		self.highindex_ = 0
		self.peakheight_ = 0
	def updatePeak(self):
		for i in range(len(self.points_)):
			if self.points_[i] < self.points_[self.lowindex_]:
				self.lowindex_ = i
			elif self.points_[i] > self.points_[self.highindex_]:
				self.highindex_ = i
		self.peakheight_ = self.points_[self.highindex_] - self.points_[self.lowindex_]