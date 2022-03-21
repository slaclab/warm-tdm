import numpy as np
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf

class CurveData():

    def __init__(self, xvalues):
        self.xValues_ = xvalues
        self.curveList_ = []
        self.bestCurve = None
        self.bestIndex = None
        self.biasOut = None
        self.offsetOut = None
        self.fbOut = None

    def update(self):
        # Find the best curve
        for i, curve in enumerate(self.curveList_):
            curve.updatePeak()
            if self.bestCurve is None or curve.peakheight > self.bestCurve.peakheight:
                self.bestCurve = curve
                self.bestIndex = i

        self.biasOut = self.bestCurve.bias
        self.offsetOut = (self.bestCurve.lowpoint + self.bestCurve.highpoint) / 2
        self.fbOut = (self.xValues_[self.bestCurve.lowindex] + self.xValues_[self.bestCurve.highindex]) / 2
            

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

    def addCurve(self,curve):
        self.curveList_.append(curve)

    def asDict(self):
        return {'xValues':np.array(self.xValues_,np.float32),
                'biasValues':np.array([c.bias for c in self.curveList_],np.float32),
                'curves':[np.array(c.points_,np.float32) for c in self.curveList_],
                'bestIndex' : self.bestIndex,
                'bestPeak' : self.bestCurve.peakheight,
                'biasOut':self.biasOut,
                'fbOut':self.fbOut,
                'offsetOut':self.offsetOut}

    def __repr__(self):
        return str(self.asDict())

class Curve():
    #plotting offset as a function of FB, with each curve being a different bias
    def __init__(self, bias, points=None):
        self.bias = bias
        self.points_ = [] if points is None else points
        self.lowindex = 0
        self.highindex = 0
        self.peakheight = 0

    def updatePeak(self):
        np_points = np.array(self.points_)

        self.lowindex = np.argmin(np_points)
        self.lowpoint = np_points[self.lowindex]
        self.highindex = np.argmax(np_points)
        self.highpoint = np_points[self.highindex]
        self.peakheight = self.highpoint - self.lowpoint

    def addPoint(self,point):
        self.points_.append(point)

    def __repr__(self):
        return(str(self.bias) + ": " + str(self.points_))
