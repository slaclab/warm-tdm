import pyrogue as pr
import rogue

import scipy
import scipy.signal
import scipy.fftpack
from scipy.signal import wiener

import warm_tdm
import time
import os
import numpy as np
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as patches
import matplotlib.path as path
import datetime

class WaveformCapture(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name = 'SelectedChannel',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 3))

        self.add(pr.RemoteVariable(
            name = 'AllChannels',
            offset = 0x00,
            bitOffset = 3,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteCommand(
            name = 'CaptureWaveform',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 1,
            function = pr.RemoteCommand.toggle))

        @self.command()
        def CaptureIterative():
            startAll = self.AllChannels.get()
            startSel = self.SelectedChannel.get()
            self.AllChannels.set(False)
            for i in range(8):
                self.SelectedChannel.set(i)
                self.CaptureWaveform()
                time.sleep(.05)

            self.AllChannels.set(startAll)
            self.SelectedChannel.set(startSel)


        self.add(pr.RemoteCommand(
            name = 'ResetPedastals',
            offset = 0x04,
            bitOffset = 1,
            bitSize = 1,
            hidden = True,
            function = pr.RemoteCommand.toggle))

        self.add(pr.RemoteVariable(
            name = 'Decimation',
            offset = 0x08,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'Alpha',
            offset = 0x0C,
            bitSize = 4,
            bitOffset = 0,
            mode = 'RW',
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'BufferDepth',
            offset = 0x08,
            bitOffset = 16,
            bitSize = 14))


        self.add(pr.RemoteVariable(
            name = 'AdcAverageRaw',
            offset = 0x10,
            base = pr.Int,
            mode = 'RO',
            disp = '0x{:08x}',
            bitSize = 32*8,
            numValues = 8,
            valueBits = 32,
            valueStride = 32))



        def conv(value):
            return 2*(value >> 18)/2**14

        convVector = np.vectorize(conv)

        def _get(*, read, index, check):
            ret = self.AdcAverageRaw.get(read=read, index=index, check=check)
            if index == -1:
                ret = ret.astype(np.int32)
                return np.array([conv(v) for v in ret], np.float64)
            else:
                return conv(ret)

        self.add(pr.LinkVariable(
            name = 'AdcAverage',
            dependencies = [self.AdcAverageRaw],
            disp = '{:0.06f}',
            units = 'V',
            linkedGet = _get))

class WaveformCapturePyDM(pr.Device, rogue.interfaces.stream.Slave):

    def __init__(self, **kwargs):
        rogue.interfaces.stream.Slave.__init__(self)
        pr.Device.__init__(self, **kwargs)

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)

        self.add(pr.LocalVariable(
            name='RawPeriodogram',
#            hidden=True,
            bulkOpEn = False,
            value = [(np.zeros(10), np.zeros(10)) for _ in range(8)],
            mode='RO'))

        self.add(pr.LocalVariable(
            name='RawHistogram',
            #hidden=True,
            bulkOpEn = False,
            value = [(np.zeros(10), np.zeros(10)) for _ in range(8)],
            mode='RO'))


        for i in range(8):
            self.add(pr.LocalVariable(
                name=f'PeriodogramX[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))
                #hidden=True,
#                dependencies=[self.RawPeriodogram],
#                linkedGet=lambda ch=i: self.RawPeriodogram.value()[ch][1]))

            self.add(pr.LocalVariable(
                name=f'PeriodogramY[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))
                #hidden=True,
 #               dependencies=[self.RawPeriodogram],
 #               linkedGet=lambda ch=i: self.RawPeriodogram.value()[ch][0]))

            self.add(pr.LocalVariable(
                name=f'HistogramX[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))
                #hidden=True,
 #               dependencies=[self.RawHistogram],
 #               linkedGet=lambda ch=i: self.RawHistogram.value()[ch][1]))

            self.add(pr.LocalVariable(
                name=f'HistogramY[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))
                #hidden=True,
#                dependencies=[self.RawHistogram],
#                linkedGet=lambda ch=i: self.RawHistogram.value()[ch][0]))


    def histogram(self, data):
        mean = np.int32(data.mean())
        low = np.int32(data.min())
        high = np.int32(data.max())

        return np.histogram(data, np.arange(low-10, high+10, 1))

    def periodogram(self, data):
        freq=125.e6 # 125MHz
        mean_subtracted_TOD = data - np.mean(data)
        freqs,Pxx_den=scipy.signal.periodogram(mean_subtracted_TOD,freq,scaling='density')

        preamp_chain_gain=200.

        Pxx_den = 1e9*np.sqrt(Pxx_den)/preamp_chain_gain

        return (Pxx_den, freqs)



    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        data = frame.getNumpy(0, frame.getPayload())
        numBytes = data.size
        print(f'PyDM - Got Frame on channel {frame.getChannel()}: {numBytes} bytes')

        # Create a view of ADC values
        frame = data.view(np.uint16)

        # Process header
        channel = frame[0] & 0b1111
        decimation = frame[1]

        adcs = frame[8:].view(np.int16).copy()
        adcs = adcs//4

        if channel == 8:
            # Construct a view of the adc data
            adcs.resize(adcs.size//8, 8)

        # Convert adc values to voltages
        voltages = self.conv(adcs)

        #print(adcs)
        #print(voltages)

        if channel >= 8:
            for i in range(8):
                y,x = self.histogram(adcs[:,i])
                self.HistogramX[i].set(value=x)
                self.HistogramY[i].set(value=y)
                y,x = self.periodogram(voltages[:,i])
                self.PeriodogramX[i].set(value=x)
                self.PeriodogramY[i].set(value=y)

        else:
            y,x = self.histogram(adcs)
            self.HistogramX[channel].set(value=x)
            self.HistogramY[channel].set(value=y)
            y,x = self.periodogram(voltages)
            self.PeriodogramX[channel].set(value=x)
            self.PeriodogramY[channel].set(value=y)            

        print('PyDM - acceptFrame done')



class WaveformCaptureReceiver(rogue.interfaces.stream.Slave, pr.Device):

    def __init__(self, **kwargs):
        rogue.interfaces.stream.Slave.__init__(self)
        pr.Device.__init__(self, **kwargs)

        @self.command()
        def TestAll():
            frame =  np.random.normal(0, scale=150, size=(16000,8)).round().astype(np.int16)
            self.hist_plotter.updateHists(frame, 8)

        @self.command()
        def TestChannel(arg):
            frame = np.random.normal(0, scale=150, size=16000*8).round().astype(np.int16)
            self.hist_plotter.updateHists(frame, int(arg))


        self.conv = np.vectorize(self._conv)

#        self.hist_queue = mp.SimpleQueue()
        self.hist_plotter = HistogramPlotter(title='Raw Histogram')
        self.fft_plotter = ShawnPlotter(title='Raw Noise')
#        self.hist_plotter2 = HistogramPlotter(title='Subtracted Histogram')
#        self.fft_plotter2 = ShawnPlotter(title='Subtracted Noise')
 #       self.hist_process = mp.Process(
 #           target = self.hist_plotter, args=(self.hist_queue, ), daemon=True)


#        self.sub_hist_queue = mp.SimpleQueue()
        #self.sub_hist_plotter = HistogramPlotter(title='Subtracted Histogram')
#        self.sub_hist_process = mp.Process(
#            target = self.sub_hist_plotter, args=(self.sub_hist_queue, ), daemon=True)

#        self.hist_process.start()
#        self.sub_hist_process.start()


    def _conv(self, adc):
        return adc/2**13

    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        data = frame.getNumpy(0, frame.getPayload())
        numBytes = data.size
        print(f'Matplotlib - Got Frame on channel {frame.getChannel()}: {numBytes} bytes')

        # Create a view of ADC values
        frame = data.view(np.uint16)

        # Process header
        channel = frame[0] & 0b1111
        decimation = frame[1]

        adcs = frame[8:].view(np.int16).copy()
        adcs = adcs//4

        if channel == 8:
            # Construct a view of the adc data
            adcs.resize(adcs.size//8, 8)

        print('Matplotlib - saving')

        # Save the data to a file
        filepath = os.path.abspath(f'../data/CH_{channel}_' + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        np.save(filepath, data)

        # Convert adc values to voltages
        voltages = self.conv(adcs)

#        print(adcs)
#        print(voltages)

        print('Matplotlib - plotting')

        if channel == 8:

            # Determine pedastals
            adcChMeans = adcs.mean(0)
            voltageChMeans = voltages.mean(0)

            # Subtract pedastales
            normalizedAdcs = adcs - adcChMeans
            normalizedVoltages = voltages - voltageChMeans

            # Calculate common mode waveform
            commonVoltages = normalizedVoltages.mean(1)[:,np.newaxis]
            commonAdcs = normalizedAdcs.mean(1)[:,np.newaxis]

            # Subtract common mode waveform
            adjustedVoltages = voltages-commonVoltages
            adjustedAdcs = (adcs-commonAdcs).astype(int)

            self.hist_plotter.updateHists(adcs, channel)
            self.fft_plotter.updateFfts(voltages, channel)
            #self.hist_plotter2.updateHists(adjustedAdcs, channel)
            #self.fft_plotter2.updateFfts(adjustedVoltages, channel)
#            self.hist_queue.put((adcs, channel))
#            self.sub_hist_queue.put((adjustedAdcs, channel))


        else:

            self.hist_plotter.updateHists(adcs, channel)
            self.fft_plotter.updateFfts(voltages, channel)

        print('Matplotlib - acceptFrame done')



class HistogramPlotter(object):

    def __init__(self, title='Channel Histograms'):

        self.title = title
        self.fig, self.ax = plt.subplots(8)
        self.fig.suptitle(self.title)

        self.barpath = [None for _ in range(8)]
        self.patch = [None for _ in range(8)]


        plt.show(block=False)

    def drawHist(self, ax, data):
        mean = np.int32(data.mean())
        low = np.int32(data.min())
        high = np.int32(data.max())

        n, b = np.histogram(data, np.arange(low-10, high+10, 1))

        left = b[:-1]
        right = b[1:]
        bottom = np.zeros(len(left))
        top = bottom + n

        xy = np.array([[left, left, right, right], [bottom, top, top, bottom]]).T

        barpath = path.Path.make_compound_path_from_polys(xy)
        patch = patches.PathPatch(barpath)

        ax.clear()
        ax.add_patch(patch)

        ax.text(0.1, 0.7, f'\u03C3: {np.std(data):1.3f}', transform=ax.transAxes)

        ax.set_xlim(left[0], right[-1])
        ax.set_ylim(bottom.min(), top.max())

        self.fig.canvas.draw()


    def updateHists(self, frame, channel):
#        print(frame)
        if channel == 8:
            for i in range(8):
                self.drawHist(self.ax[i], frame[:,i])

        else:
            self.drawHist(self.ax[channel], frame)

        #plt.draw()

class FftPlotter(object):

    def __init__(self, title='Channel Relative Power'):

        self.title = title
        self.fig, self.ax = plt.subplots(8)
        self.fig.suptitle(self.title)
        plt.show(block=False)

    def drawFft(self, ax, data):
        ax.clear()
        N = data.size
        T = 8.0E-9
        freqs = np.fft.rfftfreq(N,T)
        yf = 20*np.log10(np.fft.rfft(data))
        ax.plot(freqs, yf)
        self.fig.canvas.draw()

    def updateFfts(self, frame, channel):
        if channel == 8:
            for i in range(8):
                self.drawFft(self.ax[i], frame[:,i])
        else:
            self.drawFft(self.ax[channel], frame)

class ShawnPlotter(object):

    def __init__(self, title='Noise'):

        self.title = title
        self.fig, self.ax = plt.subplots(8)
        self.fig.suptitle(self.title)

        plt.show(block=False)

    def drawFft(self, ax, data):
        ax.clear()

        print(f'RMS = {np.std(data):.3e} ADU')

        freq=125.e6 # 125MHz
        mean_subtracted_TOD = data - np.mean(data)
        freqs,Pxx_den=scipy.signal.periodogram(mean_subtracted_TOD,freq,scaling='density')

        preamp_chain_gain=200.

        ax.loglog(freqs,1e9*np.sqrt(Pxx_den)/preamp_chain_gain)
        ax.set_ylim(1e-3,100)

        ax.set_xlabel('Frequency (Hz)')
        ax.set_ylabel('ASD (nV/rt.Hz)')


        ax.plot([freqs[0],freqs[-1]],[3,3],label='3 nV/rt.Hz',color='r',linestyle='dashed')

        ax.loglog(freqs,wiener(1e9*np.sqrt(Pxx_den)/preamp_chain_gain,mysize=100),label='Wiener filtered')

        ax.legend()

        # check std
        print(f'RMS from periodogram = {np.sqrt(np.sum(Pxx_den)*(freqs[1]-freqs[0])):.3e} ADU')

        self.fig.canvas.draw()

    def updateFfts(self, frame, channel):
        if channel == 8:
            for i in range(8):
                self.drawFft(self.ax[i], frame[:,i])
        else:
            self.drawFft(self.ax[channel], frame)
