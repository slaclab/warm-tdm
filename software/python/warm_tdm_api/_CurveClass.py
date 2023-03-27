import numpy as np
import scipy.optimize
import sys

def _sinfunc(t, A, w, p, c):
        return A*np.sin((2*np.pi/w)*t+p)+c

def plotCurveDataDict(ax, curveDataDict, ax_title, xlabel, ylabel, legend_title):
        ax.clear()
        ax.set_title(ax_title)        
        ax.set_ylabel(ylabel)
        ax.set_xlabel(xlabel)
        ax.grid(True)

        # Special case for CurveData with no curves
        if len(curveDataDict['biasValues']) == 0:
            ax.text(.5, .5, 'Not Tuned', ha='center', va='center', fontsize=28)
            return

        xValues = curveDataDict['xValues']

        # Plot each curve with heavier line for curve with highest amplitude
        for biasIndex, value in enumerate(curveDataDict['biasValues']):
                
            linewidth = 1.0
            if biasIndex == curveDataDict['bestIndex']:
                linewidth = 2.0
            peak = curveDataDict['peaks'][biasIndex]
            phinot = curveDataDict['phinots'][biasIndex]
            label = f'{value:1.3f} - P-P: {peak:1.3f} - $\phi_o$: {phinot:.2f}'
            color = next(ax._get_lines.prop_cycler)['color']
            # Plot the curve
            ax.plot(xValues, curveDataDict['curves'][biasIndex], label=label, linewidth=linewidth, color=color)
            # Mark the max point
            ax.plot(*curveDataDict['highPoints'][biasIndex], '^', color=color)
            # Mark the min point
            ax.plot(*curveDataDict['lowPoints'][biasIndex], 'v', color=color)

        # Plot the calculated operating point
        ax.plot(curveDataDict['xOut'], curveDataDict['yOut'], 's', label='Tune Point')
        ax.axhline(y=curveDataDict['yOut'], linestyle='--')
        ax.axvline(x=curveDataDict['xOut'], linestyle='--')

        ax.legend(title=legend_title)
    

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

    def update(self):
        # Find the best curve
        for i, curve in enumerate(self.curveList):
            curve.updatePeak(self.xValues)
            if self.bestCurve is None or curve.peakheight > self.bestCurve.peakheight:
                self.bestCurve = curve
                self.bestIndex = i
                
        if self.bestCurve is not None:
            self.biasOut = self.bestCurve.bias
            self.yOut = self.bestCurve.max_slope_point[1]
            self.xOut = self.bestCurve.max_slope_point[0]

    def addCurve(self,curve):
        self.curveList.append(curve)

    def asDict(self):
        self.update()
        return {
            'xValues': self.xValues,
            'biasValues': np.array([c.bias for c in self.curveList], np.float32),
            'curves': [np.array(c.points, np.float32) for c in self.curveList],
            'peaks': np.array([c.peakheight for c in self.curveList], np.float32),
            'phinots': np.array([c.phinot for c in curveList], np.float32),
            'minSlopePoints': np.array([c.min_slope_point for c in curveList], np.float32),
            'maxSlopePoints': np.array([c.max_slope_point for c in curveList], np.float32),
            'lowPoints': np.array([c.lowpoint for c in self.curveList], np.float32),
            'highPoints': np.array([c.highpoint for c in self.curveList], np.float32),
            'bestIndex' : self.bestIndex,
#            'bestPeak' : 0.0 if self.bestIndex is None else self.bestCurve.peakheight,
            'biasOut': self.biasOut,
            'xOut': self.xOut,
            'yOut': self.yOut,
            # 'bestfit': self.bestfit}
        }
    
    def __repr__(self):
        return str(self.asDict())



class Curve():
    #plotting offset as a function of FB, with each curve being a different bias

    def __init__(self, bias):
        self.bias = bias
        self.points = [] #np.zeros(parent.xValues.size, float)

        # Calculated curve parameters
        self.phinot = 0.0
        self.peakheight = 0
        self.min_slope_point = 0
        self.max_slope_point = 0
        self.lowindex = 0
        self.highindex = 0        
        self.curvefit = []

    def updatePeak(self, xValues):
        print(f'bias curve {self.bias} - updatePeak()')
        np_points = np.array(self.points)

        # Use FFT to find phy_not
        ff = np.fft.fftfreq(xValues.size, xValues[1]-xValues[0])
        Fyy = abs(np.fft.fft(np_points))
        self.phinot = 1.0/abs(ff[np.argmax(Fyy[1:])+1])

        # Slice the curve for 1.25 phy_not
        # This finds min and max slope points closest to x=0
        slice_low = xValues.searchsorted(0)
        slice_high = xValues.searchsorted(self.phi_not*1.25)
        x_sliced = xValues[slice_low:slice_high]
        y_sliced = np_points[slice_low:slice_high]
        y_prime = np.gradient(y_sliced, x_sliced)
        self.min_slope_point = (x_sliced[y_prime.argmin()], y_sliced[y_prime.min()])
        self.max_slope_point = (x_sliced[y_prime.argmax()], y_sliced[y_prime.max()])
        
        argmin = y_sliced.argmin()
        self.lowpoint = (x_sliced[argmin], y_sliced[argmin])
        argmax = y_sliced.argmax()
        self.highpoint = (x_sliced[argmax], y_sliced[argmax])
        self.peakheight = np_points.max() - np_points.min()

        print(f'Processed curve for bias={self.bias:.2f}')
        print(f'{self.phinot=:.2f}')
        print(f'{self.min_slope_point=}')
        print(f'{self.max_slope_point=}')
        print(f'{self.lowpoint=}')
        print(f'{self.highpoint=}')
        print(f'{self.peakheight=}')
        #with np.printoptions(threshold=np.inf):
        #    print(xValues)
        #    print(np_points)



    def addPoint(self, point):
        self.points.append(point)

    def __repr__(self):
        return(str(self.bias) + ": " + str(self.points))
