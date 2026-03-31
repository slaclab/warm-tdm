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
from pathlib import Path

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

class WaveformCapture(pr.Device):
    def __init__(self, **kwargs):
#        rogue.interfaces.stream.Slave.__init__(self)
        pr.Device.__init__(self, **kwargs)

#        stream >> self

        self.add(pr.RemoteVariable(
            name = 'SelectedChannel',
            disp = '{:d}',
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

        self.add(pr.RemoteVariable(
            name = 'SampleFilterEn',
            descriptions = 'Capture only sampled samples',
            offset = 0x00,            
            bitSize = 1,
            bitOffset = 8,
            base = pr.Bool))


#         self.add(pr.LocalVariable(
#             name = 'WaveformState',
#             hidden = True,
#             value = 'Idle'))

        @self.command()
        def CaptureWaveform():
             self.WaveformTrigger()

        @self.command()
        def CaptureIterative():
            with self.root.updateGroup():
                startAll = self.AllChannels.get()
                startSel = self.SelectedChannel.get()
                self.AllChannels.set(False)
                for i in range(8):
                    #print(f'Capturing channel {i}')
                    self.SelectedChannel.set(i)
                    self.WaveformTrigger()
                    time.sleep(1)

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
            hidden = True,
            bitSize = 32*8,
            numValues = 8,
            valueBits = 32,
            valueStride = 32))

#         for i in range(8):
#             self.add(pr.LinkVariable(
#                 name = f'A[{i}]',
#                 guiGroup='AdcAverageRaw',
#                 disp = '0x{:08x}',
#                 mode = 'RO',
#                 dependencies = [self.AdcAverageRaw],
#                 linkedGet = lambda read, x=i: self.AdcAverageRaw.get(read=read, index=x)))



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


 #    def _acceptFrame(self, frame):
#         print(f'Got waveform frame')
#         self.WaveformState.set('Idle')



class WaveformCaptureReceiver(pr.DataReceiver):

    def __init__(self, captureDev, amplifiers, **kwargs):
        super().__init__(**kwargs)

        self.amplifiers = amplifiers

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)
        cols = list(range(8))

        tmpAdc = np.array(np.random.default_rng().normal(1, 20, (8,0x2000)), dtype=np.int32)
        tmpVoltage = self.conv(tmpAdc)
        tmpAmpVin = np.zeros_like(tmpVoltage)

        for ch in range(len(tmpAmpVin)):
            for sample in range(len(tmpAmpVin[0])):
                tmpAmpVin[ch][sample] = tmpVoltage[ch][sample] / 200.0

        self.add(pr.LocalVariable(
            name = 'RawData',
            value = {ch: {'ADC Counts': (tmpAdc[ch], np.zeros_like(tmpAdc[ch])),
                          'V@ADC': (tmpVoltage[ch], np.zeros_like(tmpVoltage[ch])),
                          'V@AmpIn': (tmpAmpVin[ch], np.zeros_like(tmpAmpVin[ch]))} for ch in range(8)},
            mode = 'RO',
            groups = ['NoStream'],
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


        src_enum = {
                0: 'ADC Counts',
                1: 'V@ADC',
                2: 'V@AmpIn'}

        self.add(pr.LocalVariable(
            name = 'HistogramSrc',
            enum = src_enum,
            value = 0))

        self.add(pr.LocalVariable(
            name = 'PSDSrc',
            enum = src_enum,
            value = 2))

        self.add(pr.LocalVariable(
            name = 'WaveformSrc',
            enum = src_enum,
            value = 2))

        self.add(pr.LocalVariable(
            name='RmsNoiseRaw',
            value = tmpAdc.std(1),
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
                name = f'RmsNoiseVADC[{i}]',
                mode = 'RO',
                units = u'\u03bcV',
                disp = '{:0.3f}',
                guiGroup = 'RmsNoiseVADC',
                dependencies = [self.RmsNoiseRaw],
                linkedGet = lambda read, ch=i: 1.0e6*_conv(self.RmsNoiseRaw.get(read=read, index=ch))))

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'RmsNoiseAmpIn[{i}]',
                mode = 'RO',
                units = u'\u03bcV',
                disp = '{:0.3f}',
                guiGroup = 'RmsNoiseAmpInX',
                dependencies = [self.RmsNoiseVADC[i]],
                linkedGet = lambda read, ch=i: self.amplifiers[ch].ampVin(self.RmsNoiseVADC[ch].get(read=read), 0.0)))

        for i in range(8):
            def _getPkPk(read, x=i):
                d = self.RawData.value()
                v = d[x]['V@AmpIn'][0]
                #v = np.array([self.loading.ampVin(a, 0.0, x) for a in v])
                r = v.max()-v.min()
                return r*1.0e6

            self.add(pr.LinkVariable(
                name = f'PkPkAmpIn[{i}]',
                mode = 'RO',
                units = u'\u03bcV',
                disp = '{:0.3f}',
                guiGroup = 'PkPkAmpIn',
                dependencies = [self.RawData],
                linkedGet = _getPkPk))

            def _getAvg(read, x=i):
                d = self.RawData.value()
                v = d[x]['V@AmpIn'][0]
                #v = np.array([self.loading.ampVin(a, 0.0, x) for a in v])
                r = v.mean()
                return r*1.0e6

            self.add(pr.LinkVariable(
                name = f'AvgAmpIn[{i}]',
                units = u'\u03bcV',
                disp = '{:0.3f}',
                guiGroup = 'AvgAmpIn',
                dependencies = [self.RawData],
                linkedGet = _getAvg))

            self.add(pr.LinkVariable(
                name = f'AmpInConvFactor[{i}]',
#                units = u'\u03bcV/ADC',
 #               disp = '{:0.3f}',
                mode = 'RO',
                guiGroup = 'AmpInConvFactor',
                variable = self.amplifiers[i].AmpInConvFactor))


        self.add(MultiPlot(
            name='MultiPlot',
            mode='RO',
            parent = self,
            hidden=True))

        self.add(pr.LocalVariable(
            name = 'SaveData',
            value = False))

        self.add(pr.LocalVariable(
            name = 'LastSavedFileName',
            value = ''))

        @self.command()
        def CaptureAndWait():
            self.Updated.set(False)
            self.captureDev.CaptureWaveform()
            while self.Updated.get() == False:
                time.sleep(.1)

    def process(self, frame):
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
        markers = adcs & 0x3        
        adcs = adcs//4

        # Bits 0 and 1 indicate a marker

        print(f'{adcs=}')
        print(f'{markers=}')

        with self.root.updateGroup():
            if channel >= 8:
                # Construct a view of the adc data
                adcs.resize(adcs.size//8, 8)
                markers.resize(markers.size//8, 8)
                self.RmsNoiseRaw.set(adcs.std(0))
            else:
                self.RmsNoiseRaw.set(value=adcs.std(), index=channel)

            #adcs = adcs[5000:]

            voltages = self.conv(adcs)
            ampVin = np.zeros_like(voltages)

            d = self.RawData.value()

            if channel >= 8:
                for sample in range(len(voltages)):
                    for ch in range(len(voltages[0])):
                        ampVin[sample, ch] = self.amplifiers[ch].ampVin(voltages[sample, ch], 0.0)

                d = {ch: {
                    'ADC Counts': (adcs[:, ch], markers[:, ch]),
                    'V@ADC': (voltages[:, ch], markers[:, ch]),
                    'V@AmpIn': (ampVin[:, ch], markers[:, ch])}
                     for ch in range(8)}

            else:
                #print(f'Setting data for channel {channel}')
                for sample in range(len(voltages)):
                    ampVin[sample] = self.amplifiers[channel].ampVin(voltages[sample], 0.0)

                d[channel]['ADC Counts'] = (adcs, markers)
                d[channel]['V@ADC'] = (voltages, markers)
                d[channel]['V@AmpIn'] = (ampVin, markers)

            #print(d)
            self.RawData.set(d)

            if self.SaveData.value():
                timestr = time.strftime("%Y%m%d-%H%M%S")
                filename = Path(f'../data/Waveform_{timestr}.npy').resolve()
                np.save(filename, self.RawData.value())
                self.LastSavedFileName.set(str(filename))


def plot_waveform_channel(ch, ax, values, src, multi_channel):
    ax.clear()
    markers = values[1]
    
    if src == 'ADC Counts':
        units = src
        plt_values = values[0]
    else:
        units = f'{src} - \u03bcV'
        plt_values = values[0] * 1.0e6

    if not multi_channel:
        ax.set_title(f'Channel {ch} waveform')
        ax.set_xlabel('Sample number')
        ax.set_ylabel(units)
    else:
        if ch == 7:
            ax.set_xlabel(units)
        elif ch == 0:
            ax.set_title(f'Waveforms')

    ax.plot(plt_values)

    # Plot the markers as vlines
    firstSamples = np.where(markers == 1)[0]
    lastSamples = np.where(markers == 2)[0]
    rowStrobes = np.where(markers == 3)[0]

    print(f'{markers=}')
    print(f'{firstSamples=}')    
    print(f'{lastSamples=}')    
    print(f'{rowStrobes=}')
    

    ymin = plt_values.min()
    ymax = plt_values.max()

    ax.vlines(firstSamples, ymin=ymin, ymax=ymax, color='g')
    ax.vlines(lastSamples, ymin=ymin, ymax=ymax, color='r')
    ax.vlines(rowStrobes,  ymin=ymin, ymax=ymax, color='b')

def plot_histogram_channel(ch, ax, values, src, multi_channel):
    ax.clear()
    plot_values = values[0]

    if src == 'ADC Counts':
        low = int(plot_values.min())
        high = int(plot_values.max())
        edges = np.arange(low - 10, high + 10, 1)
        counts, edges = np.histogram(plot_values, bins=edges)
        units = src
        ax.stairs(counts, edges)
    else:
        values_uv = np.asarray(plot_values, dtype=np.float32) * 1.0e6
        counts, edges = np.histogram(values_uv, bins=50)
        units = f'{src} - ?V'
        ax.stairs(counts, edges, fill=True)

    if multi_channel:
        ax.tick_params(axis='y', labelleft=False)
        if ch == 7:
            ax.set_xlabel(units)
        elif ch == 0:
            ax.set_title('Histograms')
    else:
        ax.set_ylabel('Number of samples')
        ax.set_xlabel(units)
        ax.set_title(f'Channel {ch} Histogram')


def plot_psd_channel(ch, ax, values, src, multi_channel):
    plot_values = np.asarray(values[0], dtype=np.float32)
    freq = 125.0e6
    mean_subtracted = plot_values - plot_values.mean()
    freqs, pxx_den = scipy.signal.periodogram(mean_subtracted, freq, scaling='density')
    pxx = 1e9 * np.sqrt(pxx_den)

    ax.clear()
    ax.set_ylim(1e-3, 1000)
    ax.loglog(freqs, pxx)
    ax.axhline(1.0, color='r', linestyle='dashed')

    if multi_channel:
        if ch == 7:
            ax.set_xlabel('Frequency (Hz)')
        elif ch == 0:
            ax.set_title(f'PSD (nV/rt.Hz) - {src}')
        else:
            ax.tick_params(axis='x', labelbottom=False)
    else:
        ax.set_ylabel('nV/rt.Hz')
        ax.set_xlabel('Frequency (Hz)')
        ax.set_title(f'Channel {ch} PSD (nV/rt.Hz) - {src}')


class MultiPlot(pr.LinkVariable):

    def __init__(self, parent, **kwargs):
        super().__init__(
            linkedGet = self.linkedGet,
            dependencies = [
                parent.PlotHistogram,
                parent.PlotPSD,
                parent.PlotWaveform,
                parent.RawData,
                parent.PlotColumn,
                parent.HistogramSrc,
                parent.PSDSrc,
                parent.WaveformSrc],
            **kwargs)

        self.plotEnables = [parent.PlotHistogram, parent.PlotPSD, parent.PlotWaveform]

        self.plot_functions = {
            parent.PlotHistogram: (plot_histogram_channel, parent.HistogramSrc),
            parent.PlotPSD: (plot_psd_channel, parent.PSDSrc),
            parent.PlotWaveform: (plot_waveform_channel, parent.WaveformSrc)}


#        self.fig = None

        def _conv(adc):
            return adc/2**13

        self.conv = np.vectorize(_conv)


    def linkedGet(self, read, index=-1):
        fig = plt.Figure(tight_layout=True, figsize=(20,20))

        enabled_plot_functions = {
            k: v for k, v in self.plot_functions.items()
            if k.get(read=read) is True
        }
        num_plots = len(enabled_plot_functions)
        data = self.parent.RawData.get(read=read)

        if self.parent.PlotColumn.getDisp(read=read) == 'All':
            plot_index = 1
            for ch in range(8):
                for func in enabled_plot_functions.values():
                    ax = fig.add_subplot(8, num_plots, plot_index)
                    src = func[1].getDisp(read=read)
                    func[0](ch, ax, data[ch][src], src, multi_channel=True)
                    plot_index += 1
        else:
            ch = self.parent.PlotColumn.get(read=read)
            for plot_index, func in enumerate(enabled_plot_functions.values(), start=1):
                ax = fig.add_subplot(num_plots, 1, plot_index)
                src = func[1].getDisp(read=read)
                func[0](ch, ax, data[ch][src], src, multi_channel=False)

        return fig


