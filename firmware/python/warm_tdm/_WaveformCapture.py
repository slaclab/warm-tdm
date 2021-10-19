import pyrogue as pr
import rogue

import warm_tdm
import time
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
            linkedGet = _get))

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
 #       self.hist_process = mp.Process(
 #           target = self.hist_plotter, args=(self.hist_queue, ), daemon=True)
        

#        self.sub_hist_queue = mp.SimpleQueue()        
        self.sub_hist_plotter = HistogramPlotter(title='Subtracted Histogram')
#        self.sub_hist_process = mp.Process(
#            target = self.sub_hist_plotter, args=(self.sub_hist_queue, ), daemon=True)

#        self.hist_process.start()
#        self.sub_hist_process.start()
        
        
    def _conv(self, adc):
        return (adc//4)/2**13
    
    def _acceptFrame(self, frame):
        if frame.getError():
            print('Frame Error!')
            return

        data = frame.getNumpy(0, frame.getPayload())
        numBytes = data.size
        print(f'Got Frame on channel {frame.getChannel()}: {numBytes} bytes')

        # Create a view of ADC values
        frame = data.view(np.uint16)

        # Process header
        channel = frame[0] & 0b1111
        decimation = frame[1]

        adcs = data[8:].view(np.int16).copy()
        
        if channel == 8:
            # Construct a view of the adc data
            adcs.resize(adcs.size//8, 8)

        # Save the data to a file
        filepath = os.path.abspath(f'CH_{channel}_' + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        np.save(filepath, data)

        # Convert adc values to voltages
        voltages = self.conv(adcs)

#        print(adcs)
#        print(voltages)

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
            self.sub_hist_plotter.updateHists(adjustedAdcs, channel)
#            self.hist_queue.put((adcs, channel))
#            self.sub_hist_queue.put((adjustedAdcs, channel))

        else:

            self.hist_plotter.updateHists(adcs, channel)


        
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
