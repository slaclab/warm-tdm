import numpy as np
import scipy.optimize
import sys

def plotCurveDataDict(ax, curveDataDict, ax_title, xlabel, ylabel, legend_title):
        ax.clear()
        ax.set_title(ax_title)        
        ax.set_ylabel(ylabel)
        ax.set_xlabel(xlabel)
        ax.legend(title=legend_title)

        xValues = curves['xValues']

        # Plot each curve with heavier line for curve with highest amplitude
        for biasIndex, value in enumerate(curves['biasValues']):
            linewidth = 1.0
            if biasIndex == curves['bestIndex']:
                linewidth = 2.0
            peak = curves['peaks'][biasIndex] 
            label = f'{value:1.3f} - P-P: {peak:1.3f}'
            color = next(ax._get_lines.prop_cycler)['color']
            # Plot the curve
            ax.plot(xValues, curves['curves'][biasIndex], label=label, linewidth=linewidth, color=color)
            # Mark the max point
            ax.plot(curves['highIndexes'][biasIndex], curves['highPoints'][biasIndex], '^', color=color)
            # Mark the min point
            ax.plot(curves['lowIndexes'][biasIndex], curves['lowPoints'][biasIndex], 'v', color=color)            

        # Plot the calculated operating point
        ax.plot(curves['xOut'], curves['yOut'], 's')

        # Plot a fitted sin wave
        bestIndex = curves['bestIndex']
        A, w, p, c = curves['sinfits'][bestIndex]
        fitcurve = A * np.sin(xValues * w + p) + c
        ax.plot(xValues, fitcurve, '--')
    

class CurveData():

    def __init__(self, xValues):
        self.xValues = xValues
        self.curveList = []
        
        self.bestCurve = None
        self.bestIndex = None
        self.biasOut = None
        self.yOut = None
        self.xOut = None
        #self.bestfit = None

#     def sinfit(self, curveIndex):
#         np_points = np.array(curve.points_)
#         x_values = np.array(self.xValues_)

#         guess_freq = 1.0/26
#         guess_amp = np.std(np_points) * 2.0**0.5
#         guess_offset = np.mean(np_points)
#         guess = np.array([guess_amp, 2*np.pi*guess_freq, 0., guess_offset])


#         popt, pcov = scipy.optimize.curve_fit(sinfunc, x_values, np_points, p0=guess)
#         A, w, p, c = popt
#         f = w/(2.0*np.pi)
#         fitfunc = lambda t: A * np.sin(w*t + p) + c
#         print( {"amp": A, "omega": w, "phase": p, "offset": c, "freq": f, "period": 1./f, "fitfunc": fitfunc, "maxcov": np.max(pcov), "rawres": (guess,popt,pcov)})
#         return (A, w, p, c)
        

    def update(self):
        # Find the best curve
        for i, curve in enumerate(self.curveList):
            curve.updatePeak()
            if self.bestCurve is None or curve.peakheight > self.bestCurve.peakheight:
                self.bestCurve = curve
                self.bestIndex = i
                
        #self.bestfit = self.fit(self.bestCurve)

        self.biasOut = self.bestCurve.bias
        self.yOut = (self.bestCurve.lowpoint + self.bestCurve.highpoint) / 2
        self.xOut = (self.xValues_[self.bestCurve.lowindex] + self.xValues_[self.bestCurve.highindex]) / 2
            

#     def plot(self):
#         self.update() #might not want to call this here
#         fig = plt.figure()
#         ax = fig.add_subplot(111)
#         for curveindex in range(len(self.curveList_)):
#             ax.plot(self.xValues_,self.curveList_[curveindex].points_) #plot the curves
#         ax.plot(self.xValues_[self.bestCurve.highindex_],self.bestCurve.points_[self.bestCurve.highindex_],"^") #plot the max point
#         ax.plot(self.xValues_[self.bestCurve.lowindex_],self.bestCurve.points_[self.bestCurve.lowindex_],"v")#plot the min point
#         ax.plot(self.xOut,self.yOut,"s") #plot the midpoint
#         plt.show()

    def addCurve(self,curve):
        self.curveList.append(curve)

    def asDict(self):
        self.update()
        return {
            'xValues': self.xValues,
            'biasValues': np.array([c.bias for c in self.curveList], np.float32),
            'curves': [np.array(c.points, np.float32) for c in self.curveList],
            'peaks': np.array([c.peakheight for c in self.curveList], np.float32),
            'lowIndexes': np.array([c.lowindex for c in self.curveList], np.float32),
            'lowPoints': np.array([c.lowpoint for c in self.curveList], np.float32),
            'highIndexes': np.array([c.highindex for c in self.curveList], np.float32),
            'highPoints': np.array([c.highpoint for c in self.curveList], np.float32),
            'sinfits': np.array([c.curvefit for c in curveList], np.float32),
            'bestIndex' : self.bestIndex,
            'bestPeak' : self.bestCurve.peakheight,
            'biasOut': self.biasOut,
            'xOut': self.xOut,
            'yOut': self.yOut,
            # 'bestfit': self.bestfit}
        }
    
    def __repr__(self):
        return str(self.asDict())

def _sinfunc(t, A, w, p, c): return A*np.sin(w*t+p)+c

class Curve():
    #plotting offset as a function of FB, with each curve being a different bias

    def __init__(self, bias, numPoints, parent):
        self.bias = bias
        self.points = np.zeros(numPoints, float)
        self.index = 0
        self.lowindex = 0
        self.highindex = 0
        self.peakheight = 0
        self.curvefit = []

    def updatePeak(self):
        self.lowindex = self.points.argmin()
        self.lowpoint = self.points[self.lowindex]
        self.highindex = self.points.argmin()
        self.highpoint = self.points[self.highindex]
        self.peakheight = self.highpoint - self.lowpoint
        self.curvefit = scipy.optimize.curvefit(_sinfunc, self.parent.xValues, self.points)[0]

    def addPoint(self, point):
        self.points[self.index] = point
        self.index += 1

    def __repr__(self):
        return(str(self.bias) + ": " + str(self.points))
