import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf

class CurveData():

    def __init__(self,xvalues = [],curves = []):
        self.xValues_ = xvalues[:]
        self.curveList_ = curves[:]
        self.bestCurve = None
        self.biasOut = None
        self.offsetOut = None
        self.fbOut = None

    def update(self):
        self.maxPeak()
        self.midPoint()

    def maxPeak(self):
        self.updateCurves()
        for curve in self.curveList_:
            if self.bestCurve is None or curve.peakheight_ > self.bestCurve.peakheight_:
                self.bestCurve = curve
        self.biasOut = self.bestCurve.bias_

    def updateCurves(self):
        for curve in self.curveList_:
            curve.updatePeak()

    def populateXValues(self,low,high,step):
        for xvalue in np.arange(low,high,step):
            self.addFb(xvalue)

    def plot(self):
        self.update() #might not want to call this here
        fig = plt.figure()
        ax = fig.add_subplot(111)
        for curveindex in range(len(self.curveList_)):
            ax.plot(self.xValues_,self.curveList_[curveindex].points_) #plot the curves
        ax.plot(self.xValues_[self.bestCurve.highindex_],self.bestCurve.points_[self.bestCurve.highindex_],"^") #plot the max point
        ax.plot(self.xValues_[self.bestCurve.lowindex_],self.bestCurve.points_[self.bestCurve.lowindex_],"v")#plot the min point
        ax.plot(self.fbOut,self.offsetOut,"s") #plot the midpoint
        plt.show()

    def midPoint(self):
        curve = self.bestCurve
        midY = (curve.points_[curve.highindex_] + curve.points_[curve.lowindex_]) / 2
        self.offsetOut = midY
        midX = (curve.highindex_ + curve.lowindex_) / 2
        self.fbOut = midX

    def addCurve(self,curve):
        self.curveList_.append(curve)

    def addFb(self,fb):
        self.xValues_.append(fb)

    def asDict(self):
        return {'xValues':np.array(self.xValues_,np.float32),
                'biasValues':np.array([c.bias_ for c in self.curveList_],np.float32),
                'curves':[np.array(c.points_,np.float32) for c in self.curveList_],
                'biasOut':self.biasOut,
                'fbOut':self.fbOut,
                'offsetOut':self.offsetOut}

    def __repr__(self):
        return str(self.asDict())

class Curve():
    #plotting offset as a function of FB, with each curve being a different bias
    def __init__(self,bias,points = []):
        self.bias_ = bias
        self.points_ = points[:]
        self.lowindex_ = 0
        self.highindex_ = 0
        self.peakheight_ = 0
        self.midpoint_ = 0 #not used

    def updatePeak(self):
        self.lowindex_ = self.points_.argmin()
        self.highindex_ = self.points_.argmax()
        #for i in range(len(self.points_)):
        #    if self.points_[i] < self.points_[self.lowindex_]:
        #        self.lowindex_ = i
        #    elif self.points_[i] > self.points_[self.highindex_]:
        #        self.highindex_ = i
        self.peakheight_ = self.points_[self.highindex_] - self.points_[self.lowindex_]

    def addPoint(self,point):
        self.points_ = np.append(self.points_,point)
        #self.points_.append(point)

    def __repr__(self):
        return(str(self.bias_) + ": " + str(self.points_))

