import pyrogue as pr
import rogue

import warm_tdm
import numpy as np


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

        self.conv = np.vectorize(self._conv)
        
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
        frame = data.view(np.unt16)

        # Process header
        channel = adcs[0]
        decimation = adcs[1]

        # Construct a view of the adc data
        adcs = data[8:].view(np.int16)
        adcs.resize(adc.size//8, 8)

        # Convert adc values to voltages
        voltages = self.conv(adcs)

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

        
