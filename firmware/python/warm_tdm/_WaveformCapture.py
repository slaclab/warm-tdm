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
import mpld3

def channel_iter(ch):
    if ch >= 8:
        return range(8)
    else:
        return [ch]

class WaveformCapture(pr.Device, rogue.interfaces.stream.Slave):
    def __init__(self, stream, **kwargs):
        rogue.interfaces.stream.Slave.__init__(self)
        pr.Device.__init__(self, **kwargs)

        stream >> self

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
            name = 'WaveformTrigger',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 1,
            hidden = True,
            function = pr.RemoteCommand.touchOne))

        self.add(pr.LocalVariable(
            name = 'WaveformState',
            hidden = True,
            value = 'Idle'))

        @self.command()
        def CaptureWaveform():
            self.WaveformState.set('Capture')
            self.WaveformTrigger()
            pr.VariableWait(self.WaveformState, lambda v: self.WaveformState.get() == 'Idle')

        @self.command()
        def CaptureIterative():
            startAll = self.AllChannels.get()
            startSel = self.SelectedChannel.get()
            self.AllChannels.set(False)
            for i in range(8):
                self.SelectedChannel.set(i)
                self.CaptureWaveform()

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

    def _acceptFrame(self, frame):
        self.WaveformState.set('Idle')

class WaveformCaptureReceiver(pr.Device, rogue.interfaces.stream.Slave):

    def __init__(self, live_plots=False, **kwargs):
        rogue.interfaces.stream.Slave.__init__(self)
        pr.Device.__init__(self, **kwargs)
        
        self._live_plots = live_plots
        if self._live_plots:
            self.hist_plotter = HistogramPlotter(self, title='Raw Histogram')
            self.periodogram_plotter = PeriodogramPlotter(self, title='Raw Noise')

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)

        self.add(pr.LocalVariable(
            name='RmsNoise',
            value = np.zeros(8, np.float64),
            mode = 'RO'))


        for i in range(8):
            self.add(pr.LocalVariable(
                name=f'PeriodogramX[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))

            self.add(pr.LocalVariable(
                name=f'PeriodogramY[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))

            self.add(pr.LocalVariable(
                name=f'HistogramX[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))


            self.add(pr.LocalVariable(
                name=f'HistogramY[{i}]',
                value = np.zeros(10),
                bulkOpEn = False))



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

        if channel >= 8:
            # Construct a view of the adc data
            adcs.resize(adcs.size//8, 8)
            self.RmsNoise.set(adcs.std(0))
        else:
            self.RmsNoise.set(value=adcs.std(), index=channel)


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

        if self._live_plots:
            self.hist_plotter.update(channel)
            self.periodogram_plotter.update(channel)
            
def plot_histogram(ch, ax, n, b, rms):
    left = b[:-1]
    right = b[1:]
    bottom = np.zeros(len(left))
    top = bottom + n
    xy = np.array([[left, left, right, right], [bottom, top, top, bottom]]).T

    barpath = path.Path.make_compound_path_from_polys(xy)
    patch = patches.PathPatch(barpath)
    ax.clear()
    ax.add_patch(patch)

    ax.set_xlim(left[0], right[-1])
    ax.set_ylim(bottom.min(), top.max())

    ax.text(0.1, 0.7, f'\u03C3: {rms:1.3f}', transform=ax.transAxes)
    ax.set_title(f'Channel {ch}')

    ax.set_xlabel('ADC counts')

def plot_periodogram(ch, ax, freqs, pxx):
    ax.clear()
    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('ASD (nV/rt.Hz)')

    ax.set_ylim(1e-3,100)

    ax.loglog(freqs, pxx, label='PSD')
    #ax.loglog(freqs,wiener(pxx,mysize=100),label='Wiener filtered PSD')
    ax.loglog(freqs,[3 for _ in freqs],label='3 nV/rt.Hz',color='r', linestyle='dashed')
    ax.legend()

    
class JupyterPlotter(object):

    def __init__(self, root):
        self.wc = root.Group.HardwareGroup.ColumnBoard[0].DataPath.WaveformCapture
        self.receiver = root.Group.HardwareGroup.WaveformCaptureReceiver

    def plots(self, channel, update=True):
        if update:
            startAll = self.wc.AllChannels.get()
            startSel = self.wc.SelectedChannel.get()
            self.wc.AllChannels.set(False)

            
        for ch in channel_iter(channel):
            if update:
                self.wc.SelectedChannel.set(ch)                
                self.wc.CaptureWaveform()

            mpld3.enable_notebook()

            #plt.rcParams['figure.figsize'] = [18,6]

            fig, ax = plt.subplots(1,2, figsize=(18,6))

            
            n,b = self.receiver.HistogramY[ch].get(), self.receiver.HistogramX[ch].get()
            rms = self.receiver.RmsNoise.get(index=ch)
            plot_histogram(ch, ax[0], n, b, rms)

            freqs = self.receiver.PeriodogramX[ch].get()
            pxx = self.receiver.PeriodogramY[ch].get()
            plot_periodogram(ch, ax[1], freqs, pxx)

            plt.suptitle(f'Channel {ch}')            
            plt.show()

        if update:
            self.wc.AllChannels.set(startAll)
            self.wc.SelectedChannel.set(startSel)
            

        
class HistogramPlotter(object):

    def __init__(self, receiver, title='Channel Histograms'):

        self.receiver = receiver
        self.title = title
        self.fig, self.ax = plt.subplots(8)
        self.fig.suptitle(self.title)

        plt.show(block=False)

    def draw(self, ax, channel):
        n = self.receiver.HistogramY[channel].get()
        b = self.receiver.HistogramX[channel].get()
        rms = self.receiver.RmsNoise.get(index=channel)
        plot_histogram(channel, ax, n, b, rms)

    def update(self, channel):
        for i in channel_iter(channel):
            self.draw(self.ax[i], i)
        
        self.fig.canvas.draw()                



class PeriodogramPlotter(object):

    def __init__(self, receiver, title='Noise'):

        self.receiver = receiver
        self.title = title
        self.fig, self.ax = plt.subplots(8)
        self.fig.suptitle(self.title)

        plt.show(block=False)

    def draw(self, ax, channel):
        freqs = self.receiver.PeriodogramX[channel].get()
        pxx = self.receiver.PeriodogramY[channel].get()
        plot_periodogram(channel, ax, freqs, pxx)
        

    def update(self, channel):
        for i in channel_iter(channel):
            self.draw(self.ax[i], i)

        self.fig.canvas.draw()            
