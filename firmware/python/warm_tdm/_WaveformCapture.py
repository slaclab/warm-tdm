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

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'A[{i}]',
                guiGroup='AdcAverageRaw',
                disp = '0x{:08x}',
                mode = 'RO',
                dependencies = [self.AdcAverageRaw],
                linkedGet = lambda read, x=i: self.AdcAverageRaw.get(read=read, index=x)))
                


        # Convert fixed point average to volts at ADC
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

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'V[{i}]',
                guiGroup='AdcAverage',
                disp = '{:0.06f}',
                mode = 'RO',
                dependencies = [self.AdcAverage],
                linkedGet = lambda read, x=i: self.AdcAverage.get(read=read, index=x)))
        

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

        tmpAdc = np.array(np.random.default_rng().normal(1, 20, (8,0x2000)), dtype=np.int)
        tmpVoltage = self.conv(tmpAdc)
        
        self.add(pr.LocalVariable(
            name = 'RawData',
            value = {ch: {'adcs': tmpAdc[ch], 'voltages': tmpVoltage[ch]} for ch in range(8)},
            mode = 'RO',
            hidden = True))

        self.add(pr.LocalVariable(
            name = 'PlotColumn',
            value = -1,
            enum = {
                -1: 'All',
                0: '0',
                1: '1',
                2: '2',
                3: '3',
                4: '4',
                5: '5',
                6: '6',
                7: '7'}))

        self.add(pr.LocalVariable(
            name = 'PlotHistogram',
            value = True))

        self.add(pr.LocalVariable(
            name = 'PlotPSD',
            value = True))

        self.add(pr.LocalVariable(
            name = 'PlotWaveform',
            value = False))
                 

        self.add(pr.LocalVariable(
            name='RmsNoiseRaw',
            value = np.array([tmpAdc.std() for i in range(8)]),
            hidden = True,
            disp = '{:0.3f}',
            units = 'ADC',
            mode = 'RO'))

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'RmsNoiseAdc[{i}]',
                mode = 'RO',
                units = 'ADC',
                disp = '{:0.3f}',                
                guiGroup = 'RmsNoiseAdc',
                dependencies = [self.RmsNoiseRaw],
                linkedGet = lambda read, ch=i: self.RmsNoiseRaw.get(read=read, index=ch)))

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'RmsNoiseV[{i}]',
                mode = 'RO',
                units = 'uV',
                disp = '{:0.3f}',                
                guiGroup = 'RmsNoiseV',
                dependencies = [self.RmsNoiseRaw],
                linkedGet = lambda read, ch=i: 1.0e6*_conv(self.RmsNoiseRaw.get(read=read, index=ch))))
            
        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'SaOutNoise[{i}]',
                mode = 'RO',
                units = 'uV',
                disp = '{:0.3f}',
                guiGroup = 'SaOutNoise',
                dependencies = [self.RmsNoiseRaw],
                linkedGet = lambda read, ch=i: (1.0e6/200)*_conv(self.RmsNoiseRaw.get(read=read, index=ch))))

        for i in range(8):
            def _get(read, x=i):
                d = self.RawData.get(read=read)
                v = d[x]['voltages']
                r = v.max()-v.min()
                return (r*1.0e3)/200
            
            self.add(pr.LinkVariable(
                name = f'SaOutPkPk[{i}]',
                mode = 'RO',
                units = 'mV',
                disp = '{:0.3f}',                
                guiGroup = 'SaOutPkPk',
                dependencies = [self.RawData],
                linkedGet = _get))


        self.add(MultiPlot(
            name='MultiPlot',
            mode='RO',
            histEnVar = self.PlotHistogram,
            psdEnVar = self.PlotPSD,
            waveEnVar = self.PlotWaveform,
            rawDataVar = self.RawData,
            colVar = self.PlotColumn,            
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
            self.RmsNoiseRaw.set(adcs.std(0))
        else:
            self.RmsNoiseRaw.set(value=adcs.std(), index=channel)


        # Convert adc values to voltages
        voltages = self.conv(adcs)
        

        #print(adcs)
        #print(voltages)
        d = self.RawData.get()
        
        if channel >= 8:
            d = {ch: {
                'adcs': adcs[ch],
                'voltages': voltages[ch]}
                 for ch in range(8)}
            pkpk = [max(voltages[ch])-min(voltages[ch]) for ch in range(8)]
            self.SaOutPkPk.set(pkpk)
        else:
            d[channel]['adcs'] = adcs
            d[channel]['voltages'] = voltages
        self.RawData.set(d)


            

        #self.MultiPlot.set(value=adcs, index=channel)

        print('_acceptFrame() - done')



                 
def plot_waveform_channel(ch, ax, voltages):
    ax.clear()
    ax.plot(voltages)
            
def plot_histogram_channel(ch, ax, adcs):
    print(f'plot_histogram_channel(ch={ch})')    
    mean = np.int32(adcs.mean())
    low = np.int32(adcs.min())
    high = np.int32(adcs.max())
    bins = np.arange(low-10, high+10, 1)
    rms = adcs.std()

    ax.clear()
    ax.hist(adcs, bins, histtype='bar')#, density=True)
    ax.yaxis.set_ticklabels([])
#    ax.text(0.05, 0.8, f'\u03C3: {rms:1.3f}, pk-pk: {high-low} ADC', transform=ax.transAxes)
#    ax.text(0.05, 0.5, f'\u03C3: {(1.0e3*rms)/(200*2**13):1.3f}, pk-pk: {(1.0e3*(high-low))/(200*2**13):1.3f} mV', transform=ax.transAxes)    

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
    ax.set_ylim(1e-3,1000)
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
        



class MultiPlot(pr.LinkVariable):

    def __init__(self, histEnVar, psdEnVar, waveEnVar, rawDataVar, colVar, **kwargs):
        super().__init__(
            linkedGet = self.linkedGet,
            dependencies = [histEnVar, psdEnVar, waveEnVar, rawDataVar, colVar],
            **kwargs)

        self.PlotHistogram = histEnVar
        self.PlotPSD = psdEnVar
        self.PlotWaveform = waveEnVar
        self.RawData = rawDataVar
        self.PlotColumn = colVar
        self.plotEnables = [histEnVar, psdEnVar, waveEnVar]

        self.plot_functions = {
            histEnVar: (plot_histogram_channel, 'adcs'),
            psdEnVar: (plot_psd_channel, 'voltages'),
            waveEnVar: (plot_waveform_channel, 'voltages')}
    

        self.fig = None
        #self.fig.suptitle('PSD (nV/rt.Hz)')

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)
        

    def linkedGet(self, read, index=-1):
        print(f'MultiPlot.linkedGet({read=}, {index=})')
        #if read is False and self.fig is not None:
        #    print('Return previous fig')
        #    return self.fig
        
        if self.fig is not None:
            print('Closing old plot')
            plt.close(self.fig)

        print('Regenerate figure')
        self.fig = plt.Figure(tight_layout=True, figsize=(20,20))

        enabled_plot_functions = {k:v  for k,v in self.plot_functions.items() if k.get(read=read) is True}
        print(f'{enabled_plot_functions=}')
        num_plots = len(enabled_plot_functions)
        print(f'{num_plots}')
        data = self.RawData.get(read=read)

        if self.PlotColumn.getDisp(read=read) == 'All':
            index = 1
            for ch in range(8):
                for func in enabled_plot_functions.values():
                    ax = self.fig.add_subplot(8, num_plots, index)
                    func[0](ch, ax, data[ch][func[1]])
                    index += 1
        else:
            ch = self.PlotColumn.get(read=read)            
            for index, func in enumerate(enabled_plot_functions.values()):
                ax = self.fig.add_subplot(num_plots, 1, index+1)
                func[0](ch, ax, data[ch][func[1]])

        return self.fig

        
    
