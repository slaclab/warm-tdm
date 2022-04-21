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

def channel_iter(ch):
    if ch >= 8:
        return range(8)
    else:
        return [ch]

def array_iter(channel, array):
    if array.ndim == 1:
        yield (channel, array)
    else:
        for i in range(array.shape[1]):
            yield (i, array[:,i])

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
            with self.root.updateGroup():
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
        
        #self.hist_plotter = HistogramPlotter()
        #self.periodogram_plotter = PeriodogramPlotter()

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)

#         self.add(pr.LocalVariable(
#             name = 'RawData',
#             value = {},
#             mode = 'RO',
#             hidden = True))


        self.add(pr.LocalVariable(
            name='RmsNoise',
            value = np.zeros(8, np.float64),
            mode = 'RO'))


#         self.add(pr.LinkVariable(
#             name='HistogramPlot',
#             mode='RO',
#             dependencies = [self.RawData],
#             linkedGet = self._getHistPlot,
#             hidden=True))
            
#         self.add(pr.LinkVariable(
#             name='PeriodogramPlot',
#             mode='RO',
#             hidden=True,
#             dependencies = [self.RawData],
#             linkedGet=self._getPeriodigramPlot))


        self.add(MultiPlot(
            name='MultiPlot',
            mode='RO',
            hidden=True))



    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        print('_acceptFrame() - start')
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
#         self.RawData.set({
#             'channel': channel,
#             'decimation': decimation,
#             'adcs': adcs,
#             'voltages': voltages})

        self.MultiPlot.set(value=adcs, index=channel)


        print('_acceptFrame() - done')


#     def _getHistPlot(self, read):
#         print(f'_getHistPlot(read={read})')
#         rawData = self.RawData.value()
#         if rawData == {}:
#             return self.hist_plotter.fig

#         self.hist_plotter.update(rawData['channel'], rawData['adcs'])
#         print(f'_getHistPlot(read={read}) - Done')        
#         return self.hist_plotter.fig

#     def _getPeriodigramPlot(self, read):
#         print(f'_getPeriPlot(read={read})')        
#         rawData = self.RawData.value()
#         if rawData == {}:
#             return self.periodogram_plotter.fig

#         self.periodogram_plotter.update(rawData['channel'], rawData['voltages'])
#         print(f'_getPeriPlot(read={read}) - Done')                
#         return self.periodogram_plotter.fig

#     def _getMultiPlot(self, read):
#         print(f'_getPeriPlot(read={read})')        
#         rawData = self.RawData.value()
#         if rawData == {}:
#             return self.multi_plotter.fig

#         self.multi_plotter.update(rawData['channel'], rawData['adcs'], rawData['voltages'])
#         print(f'_getPeriPlot(read={read}) - Done')                
#         return self.multi_plotter.fig
    
                 

            
def plot_histogram_channel(ch, ax, adcs):
    print(f'plot_histogram_channel(ch={ch})')    
    mean = np.int32(adcs.mean())
    low = np.int32(adcs.min())
    high = np.int32(adcs.max())
    bins = np.arange(low-10, high+10, 1)
    rms = adcs.std()

    ax.clear()
    ax.hist(adcs, bins, histtype='bar', density=True)
    ax.yaxis.set_ticklabels([])
    ax.text(0.05, 0.8, f'\u03C3: {rms:1.3f}', transform=ax.transAxes)

    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')        
    if ch == 7:
        ax.set_xlabel('ADC counts')
    elif ch == 0:
        ax.set_title('ADC histograms')

def plot_psd_channel(ch, ax, voltages): 
    print(f'plot_psd_channel(ch={ch})')

    # Calculate the PSD
    freq=125.e6 # 125MHz
    mean_subtracted_TOD = voltages - np.mean(voltages)
    freqs,Pxx_den=scipy.signal.periodogram(mean_subtracted_TOD,freq,scaling='density')
    preamp_chain_gain=200.
    pxx = 1e9*np.sqrt(Pxx_den)/preamp_chain_gain


    # Plot the PSD
    ax.clear()
    ax.set_ylim(1e-3,100)
    ax.loglog(freqs, pxx, label='PSD')
    #ax.loglog(freqs,wiener(pxx,mysize=100),label='Wiener filtered PSD')
    ax.loglog(freqs,[3 for _ in freqs],label='3 nV/rt.Hz',color='r', linestyle='dashed')
    #ax.legend()

    #ax.text(0.05, 0.8, f'Ch {ch}', transform=ax.transAxes)        

    ax.xaxis.set_ticks_position('bottom')
    ax.yaxis.set_ticks_position('left')        
    if ch == 7:
        ax.set_xlabel('Frequency (Hz)')
    elif ch == 0:
        ax.set_title('PSD (nV/rt.Hz)')
    else:
        ax.xaxis.set_ticklabels([])
        
class HistogramPlotter(object):

    def __init__(self):

        self.fig = plt.Figure(tight_layout=True, figsize=(10,10))
        self.ax = self.fig.subplots(8, sharey=True ) #, constrained_layout=True)
        self.fig.suptitle('ADC Histograms')


    def histogram(self, data):
        mean = np.int32(data.mean())
        low = np.int32(data.min())
        high = np.int32(data.max())

        return np.histogram(data, np.arange(low-10, high+10, 1))
        

    def plot_histogram(self, ch, ax, n, b, rms):
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

        ax.text(0.1, 0.8, f'Ch {ch} \u03C3: {rms:1.3f}', transform=ax.transAxes)
        #ax.set_title(f'Channel {ch}')

        ax.set_xlabel('ADC counts')

      

    def update(self, channel, values):
        ax = self.ax.reshape(8)
        for ch, adcs in array_iter(channel, values):
            self.plot_histogram2(ax[ch], ch, adcs)
#            self.n[ch] , self.b[ch] = self.histogram(adcs)
            #rms = self.parent.RmsNoise.get(index=ch, read=False)
 #           self.plot_histogram(ch, ax[ch], self.n[ch], self.b[ch], adcs.std())
                
        #self.fig.canvas.draw()



class PeriodogramPlotter(object):

    def __init__(self):

        self.fig = plt.Figure(tight_layout=True, figsize=(10,10))
        self.ax = self.fig.subplots(8) #, sharex=True, sharey=True)
        self.fig.suptitle('PSD (nV/rt.Hz)')

        #self.freqs = [None for x in range(8)]
        #self.pxx = [None for x in range(8)]        

        #plt.show(block=False)
        

    def update(self, channel, values):
        ax = self.ax.reshape(8)
        for ch, voltages in array_iter(channel, values):
            #self.pxx[ch], self.freqs[ch] = self.periodogram(voltages)
            plot_psd_channel(ch, ax[ch], voltages) #self.freqs[ch], self.pxx[ch])



class MultiPlot(pr.BaseVariable):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
        self.fig = plt.Figure(tight_layout=True, figsize=(20,20))
        self.ax = self.fig.subplots(8, 2, sharey='col')
        #self.fig.suptitle('PSD (nV/rt.Hz)')

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)
        

    def set(self, value, index):
        channel = index
        adcs = value
        voltages = self.conv(adcs)

        # Do histograms
        for ch, ch_adcs in array_iter(channel, adcs):
            plot_histogram_channel(ch, self.ax[ch, 0], ch_adcs)

        for ch, ch_adcs in array_iter(channel, voltages):
            plot_psd_channel(ch, self.ax[ch, 1], ch_adcs)

        self._queueUpdate()

    def get(self, read, index=-1):
        return self.fig

#        self.fig.suptitle('Waveform Noise')            
        
    
