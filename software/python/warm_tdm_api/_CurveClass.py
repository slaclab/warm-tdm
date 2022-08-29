import numpy as np
import scipy.optimize
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
        self.bestfit = None

    def fit(self, curve):
        np_points = np.array(curve.points_)
        x_values = np.array(self.xValues_)

        guess_freq = 1.0/26
        guess_amp = np.std(np_points) * 2.0**0.5
        guess_offset = np.mean(np_points)
        guess = np.array([guess_amp, 2*np.pi*guess_freq, 0., guess_offset])

        def sinfunc(t, A, w, p, c): return A*np.sin(w*t+p)+c
        popt, pcov = scipy.optimize.curve_fit(sinfunc, x_values, np_points, p0=guess)
        A, w, p, c = popt
        f = w/(2.0*np.pi)
        fitfunc = lambda t: A * np.sin(w*t + p) + c
        print( {"amp": A, "omega": w, "phase": p, "offset": c, "freq": f, "period": 1./f, "fitfunc": fitfunc, "maxcov": np.max(pcov), "rawres": (guess,popt,pcov)})
        return (A, w, p, c)
        

    def update(self):
        # Find the best curve
        for i, curve in enumerate(self.curveList_):
            curve.updatePeak()
            if self.bestCurve is None or curve.peakheight > self.bestCurve.peakheight:
                self.bestCurve = curve
                self.bestIndex = i
                
        self.bestfit = self.fit(self.bestCurve)

        self.biasOut = self.bestCurve.bias
        self.offsetOut = (self.bestCurve.lowpoint + self.bestCurve.highpoint) / 2
        self.fbOut = (self.xValues_[self.bestCurve.lowindex] + self.xValues_[self.bestCurve.highindex]) / 2
            

#     def plot(self):
#         self.update() #might not want to call this here
#         fig = plt.figure()
#         ax = fig.add_subplot(111)
#         for curveindex in range(len(self.curveList_)):
#             ax.plot(self.xValues_,self.curveList_[curveindex].points_) #plot the curves
#         ax.plot(self.xValues_[self.bestCurve.highindex_],self.bestCurve.points_[self.bestCurve.highindex_],"^") #plot the max point
#         ax.plot(self.xValues_[self.bestCurve.lowindex_],self.bestCurve.points_[self.bestCurve.lowindex_],"v")#plot the min point
#         ax.plot(self.fbOut,self.offsetOut,"s") #plot the midpoint
#         plt.show()

    def addCurve(self,curve):
        self.curveList_.append(curve)

    def asDict(self):
        return {'xValues':np.array(self.xValues_,np.float32),
                'biasValues':np.array([c.bias for c in self.curveList_],np.float32),
                'curves':[np.array(c.points_,np.float32) for c in self.curveList_],
                'peaks':np.array([c.peakheight for c in self.curveList_], np.float32),
                'bestIndex' : self.bestIndex,
                'bestPeak' : self.bestCurve.peakheight,
                'biasOut':self.biasOut,
                'fbOut':self.fbOut,
                'offsetOut':self.offsetOut,
                'bestfit': self.bestfit}

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
