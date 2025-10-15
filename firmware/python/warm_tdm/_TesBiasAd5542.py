import pyrogue as pr


class TesBiasAd5542(pr.Device):
    def __init__(self, frontEnd, **kwargs):
        super().__init__(**kwargs)
        
        self._frontEnd = frontEnd

        self._vref = 2.5

        # Raw dac registers
        for col in range(8):
            self.add(pr.RemoteVariable(
                name = f'Dac[{col}]',
                mode = 'WO',
                offset = col << 2,
                bitSize = 16,
                base = pr.UInt))

        for col in range(8):
            self.add(pr.LinkVariable(
                name = f'DacVoltage[{col}]',
                mode = 'WO',
                dependencies = [self.Dac[col]],
                units = 'V',
                linkedGet = lambda read, x=col: ((self._vref * self.Dac[x].value()) / 65536)-self._vref,
                linkedSet = lambda value, write, x=col: 65535 * ((value + self._vref) / self._vref)))
                     
            

        # Add Delatch registers
        for i in range(8):
            self.add(pr.RemoteVariable(
                name = f'Delatch[{i}]',
                offset = 0,
                bitOffset = i,
                bitSize = 1,
                base = pr.Bool))

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'BiasCurrent[{i}]',
                disp = '{:1.3f}',                
                units = '\u03bcA',
                dependencies = [self.DacVoltage[i]],
                linkedSet = self._setChannelFunc(i),
                linkedGet = self._getChannelFunc(i)))


    # TES Bias current 
    def _setChannelFunc(self, channel):
        def _setChannel(value, write, tesAmp=self._frontEnd.Channel[channel].TesBiasAmp):
            # Calculate the DAC voltages to drive
            vp, vn = tesAmp.outCurrentToDac(value, False)
            # Set the DAC voltages
            self.DacVoltage[channel].set(vp)
            
        return _setChannel

    def _getChannelFunc(self, channel):
        def _getChannel(read, tesAmp=self._frontEnd.Channel[channel].TesBiasAmp):
            dacChannel = self.DacVoltage[channel]
            dacVp = dacChannel.value()
            dacVn = 0
            delatch = False

            iout = tesAmp.dacToOutCurrent(dacVp, dacVn, delatch)
            return iout
        return _getChannel
