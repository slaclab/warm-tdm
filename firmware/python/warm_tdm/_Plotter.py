import math
import rogue
import pyrogue as pr
import threading
import time

import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as patches
import matplotlib.path as path

from collections import deque

import multiprocessing as mp

from scipy import signal

#plt.ion()

class HistogramPlotter(object):
    def __call__(self, queue):
        self.queue = queue
        self.fig, self.ax = plt.subplots(8)
        self.fig.suptitle(self.title)
        self.ani = animation.FuncAnimation(self.fig, self.updateHists, interval=1000, blit=False)


        plt.show()

    def __init__(self, title='Channel Histograms'):
        self.title = title
#        self.positions = ['left': 0, 'right': 0, 'bottom': 0, 'top': 0} for _ in range(8)]
#         self.left = [0 for _ in range(8)]
#         self.right = [0 for _ in range(8)]
#         self.bottom = [0 for _ in range(8)]
#         self.top = [0 for _ in range(8)]

        self.barpath = [None for _ in range(8)]
        self.patch = [None for _ in range(8)]

    def updateHists(self, frame):
        patch = None
        if self.queue.empty() is False:
            adcs = self.queue.get()        

            means = adcs.mean(0)
            lows = adcs.min(0)
            highs = adcs.max(0)

            print(f'means - {means}')
            print(f'lows - {lows}')
            print(f'highs - {highs}')                        

            for i in range(8):
#                if highs[i] - lows[i] < 100:
#                    lows[i] = means[i] - 50
#                    highs[i] = means[i] + 51
#                    bins = list(range(lows[i], highs[i]))                
#                else:
#                    bins = 100

                n, b = np.histogram(adcs[:, i], list(range(lows[i]-10, highs[i]+10)))

                left = np.array(b[:-1])
                right = np.array(b[1:])
                bottom = np.zeros(len(left))
                top = bottom + n

                xy = np.array([[left, left, right, right], [bottom, top, top, bottom]]).T

                barpath = path.Path.make_compound_path_from_polys(xy)
                patch = patches.PathPatch(barpath)

                self.ax[i].clear()            
                self.ax[i].add_patch(patch)

                self.ax[i].text(0.1, 0.7, f'\u03C3: {np.std(adcs[:,i]):1.3f}', transform=self.ax[i].transAxes)

                self.ax[i].set_xlim(left[0], right[-1])
                self.ax[i].set_ylim(bottom.min(), top.max())

        return [patch] 
        
        
class StripchartPlotter(object):
    def __call__(self, queue):
        self.queue = queue

        self.fig, self.ax = plt.subplots(8, sharex=True)
        self.fig.suptitle('Stripcharts')

        # Add 2D lines to scope axes
        for i, (l, a) in enumerate(zip(self.lines, self.ax)):
            a.set_xlabel('time [s]')
            a.set_ylabel(f'Ch {i}')
            a.add_line(l)
            a.set_autoscaley_on(True)

#            a.set_autoscalex_on(True)
            #a.set_xlim(self.tdata[0], self.tdata[-1])
            if i != 7:
                a.get_xaxis().set_visible(False)

        
        self.ani = animation.FuncAnimation(self.fig, self.updateStripcharts, interval=1000, blit=True)


        plt.show()
        
    def __init__(self):
        self.lines = [Line2D([], [], animated=True) for i in range(8)]
        
    def updateStripcharts(self, frame):
        relim = False
        start = time.time()        
        if self.queue.empty() is False:
            voltages = self.queue.get()

            for i in range(8):
                self.lines[i].set_data([t*8.0E-9 for t in range(len(voltages))], voltages[:,i])

                self.ax[i].relim()
                self.ax[i].autoscale_view()

            self.fig.canvas.draw()

        return self.lines 

class FftPlotter(object):
    def __call__(self, queue, name):
        self.queue = queue

        self.fig, self.ax = plt.subplots(8, sharex=True)
        self.fig.suptitle(name)

        # Add 2D lines to scope axes
        for i, (l, a) in enumerate(zip(self.lines, self.ax)):
#            a.set_xlabel('Frequency')
            a.set_ylabel(f'Ch {i}')
            a.add_line(l)
            a.set_autoscaley_on(True)

#            a.set_autoscalex_on(True)
            #a.set_xlim(self.tdata[0], self.tdata[-1])
            #a.get_xaxis().set_visible(False)


        self.ani = animation.FuncAnimation(self.fig, self.updateFfts, interval=1000, blit=False)

        plt.show()

    def __init__(self):
        self.numSamples = 500
        self.tdata = deque([], self.numSamples)
        self.ydata = [deque([], self.numSamples) for _ in range(8)]
        self.lines = [Line2D(self.tdata, self.ydata[i], animated=True) for i in range(8)]


    def updateFfts(self, frame):
        if self.queue.empty() is False:
#            print('FFT got new data')
            voltages = self.queue.get()
#            print(voltages)

            N = len(voltages)
            T = 8.0E-9

            freqs = np.fft.rfftfreq(N, T)[:50]
#            print('freqs')
#            print(freqs)

#            yf = [np.abs(np.fft.rfft(voltages[:,ch])[:50]) * T * 2 for ch in range(8)]
            yf = [np.abs(np.fft.rfft(voltages[:,ch])[:50]) for ch in range(8)]
#            print(yf[0])

            for i in range(8):
                self.lines[i].set_data(freqs, yf[i])
                self.ax[i].relim()
                self.ax[i].autoscale_view()

        self.fig.canvas.draw()

        return self.lines


            
class Scope(rogue.interfaces.stream.Slave, pr.Device):

    def __init__(self, **kwargs):
        rogue.interfaces.stream.Slave.__init__(self)
        pr.Device.__init__(self, **kwargs)

        fs = 250.0
        f0 = 60.0
        Q = 5.0

        self.b, self.a = signal.iirnotch(f0, Q, fs)
        self.zi = [signal.lfilter_zi(self.b, self.a) for x in range(8)]

        if plt.get_backend() == "macOSX":
            mp.set_start_method('forkserver')

#         self.strip_queue = mp.SimpleQueue()
#         self.strip_plotter = StripchartPlotter()

        self.hist_queue = mp.SimpleQueue()
        self.hist_plotter = HistogramPlotter(title='Raw Histogram')

        self.sub_hist_queue = mp.SimpleQueue()
        self.sub_hist_plotter = HistogramPlotter(title='Subtracted Histogram')
        

#        self.fft_queue = mp.SimpleQueue()
#        self.fft_plotter = FftPlotter()

#         self.fft_queue1 = mp.SimpleQueue()
#         self.fft_plotter1 = FftPlotter()
        

#         self.strip_process = mp.Process(
#             target = self.strip_plotter, args=(self.strip_queue, ), daemon=True)

        self.hist_process = mp.Process(
            target = self.hist_plotter, args=(self.hist_queue, ), daemon=True)

        self.sub_hist_process = mp.Process(
            target = self.sub_hist_plotter, args=(self.sub_hist_queue, ), daemon=True)
        

 #       self.fft_process = mp.Process(
 #           target = self.fft_plotter, args=(self.fft_queue, 'Filtered FFT'), daemon=True)

#         self.fft_process1 = mp.Process(
#             target = self.fft_plotter1, args=(self.fft_queue1, 'Normal FFT'), daemon=True)
        
        
#        self.strip_process.start()
        self.hist_process.start()
        self.sub_hist_process.start()
#        self.fft_process.start()
#        self.fft_process1.start()        

        @self.command()
        def Relim():
            self.queue.put('Relim')
        
    def _conv(self, adc):
        return (adc//4)/2**13
    
    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        ba = bytearray(frame.getPayload())
        frame.read(ba, 0)
        numBytes = len(ba)
        print(f'Got Frame on channel {frame.getChannel()}: {numBytes} bytes')
        adcs = np.frombuffer(ba, dtype=np.int16)
        voltages = np.array([self._conv(adc) for adc in adcs], dtype=np.float64)
        adcs.resize(numBytes//16, 8)
        voltages.resize(numBytes//16, 8)
        print('Got {len(adcs)} samples')
        print(adcs)
        print(voltages)        

        # Determine pedastals
        adcChMeans = adcs.mean(0)
        voltageChMeans = voltages.mean(0)

        # Subtract pedastales
        normalizedAdcs = adcs - adcChMeans
        normalizedVoltages = voltages - voltageChMeans

        # Calculate common mode waveform
        commonVoltages = normalizedVoltages.mean(1)[:,np.newaxis]
        commonAdcs = normalizedAdcs.mean(1)[:,np.newaxis]
        print(commonVoltages)

        # Subtract common mode waveform
        adjustedVoltages = voltages-commonVoltages
        adjustedAdcs = (adcs-commonAdcs).astype(int)
        print(adjustedAdcs)

        
        #self.strip_queue.put(voltages)
        self.hist_queue.put(adcs)
        self.sub_hist_queue.put(adjustedAdcs)
#        self.fft_queue.put(filt)
        #self.fft_queue1.put(voltages)        
        
