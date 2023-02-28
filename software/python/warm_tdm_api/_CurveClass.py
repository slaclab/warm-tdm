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
            label = f'{value:1.3f} - P-P: {peak:1.3f}'
            color = next(ax._get_lines.prop_cycler)['color']
            # Plot the curve
            ax.plot(xValues, curveDataDict['curves'][biasIndex], label=label, linewidth=linewidth, color=color)
            # Mark the max point
            ax.plot(curveDataDict['highIndexes'][biasIndex], curveDataDict['highPoints'][biasIndex], '^', color=color)
            # Mark the min point
            ax.plot(curveDataDict['lowIndexes'][biasIndex], curveDataDict['lowPoints'][biasIndex], 'v', color=color)            

        # Plot the calculated operating point
        #ax.plot(curveDataDict['xOut'], curveDataDict['yOut'], 's')
        ax.axhline(y=curveDataDict['yOut'], linestyle='--')

        # Plot a fitted sin wave
        if len(curveDataDict['sinfits']) > 0:
            bestIndex = curveDataDict['bestIndex']
            if len(curveDataDict['sinfits'][bestIndex]) > 0:
                A, w, p, c = curveDataDict['sinfits'][bestIndex]
                x = np.linspace(xValues.min(), xValues.max(), 5000)
                fitcurve = _sinfunc(x, A, w, p, c)
                ax.plot(x, fitcurve, '--')

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
                
        #self.bestfit = self.fit(self.bestCurve)

        if self.bestCurve is not None:
            self.biasOut = self.bestCurve.bias
            self.yOut = (self.bestCurve.lowpoint + self.bestCurve.highpoint) / 2
            self.xOut = (self.bestCurve.lowindex + self.bestCurve.highindex) / 2

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
            'sinfits': np.array([c.curvefit for c in self.curveList], np.float32),
            'bestIndex' : self.bestIndex,
            'bestPeak' : 0.0 if self.bestIndex is None else self.bestCurve.peakheight,
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
        self.lowindex = 0
        self.highindex = 0
        self.peakheight = 0
        self.curvefit = []

    def updatePeak(self, xValues):
        print(f'bias curve {self.bias} - updatePeak()')
        np_points = np.array(self.points)
        argmin = np_points.argmin()
        self.lowindex = xValues[argmin]
        self.lowpoint = np_points[argmin]
        argmax = np_points.argmax()
        self.highindex = xValues[argmax]
        self.highpoint = np_points[argmax]
        self.peakheight = self.highpoint - self.lowpoint
        
        print(f'{self.lowindex=}')
        print(f'{self.lowpoint=}')
        print(f'{self.highindex=}')
        print(f'{self.highpoint=}')
        print(f'{self.peakheight=}')
        #with np.printoptions(threshold=np.inf):
        #    print(xValues)
        #    print(np_points)

        ff = np.fft.fftfreq(xValues.size, xValues[1]-xValues[0])
        Fyy = abs(np.fft.fft(np_points))
        guess_period = 1.0/abs(ff[np.argmax(Fyy[1:])+1])
        guess_amp = np.std(np_points) * 2**0.5
        guess_offset = np.mean(np_points)
        guess = np.array([guess_amp, guess_period, 0, guess_offset])
        try:
            self.curvefit = scipy.optimize.curve_fit(_sinfunc, xValues, np_points, p0=guess)[0]
            print(f'{self.curvefit=}')            
        except RuntimeError:
            print('Could not fit curves')



    def addPoint(self, point):
        self.points.append(point)

    def __repr__(self):
        return(str(self.bias) + ": " + str(self.points))
