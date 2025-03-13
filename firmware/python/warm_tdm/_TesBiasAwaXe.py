import pyrogue as pr


class TesBiasAwaXe(pr.Device):
    def __init__(self, awaXe, frontEnd, dac, **kwargs):
        super().__init__(**kwargs)
        
        self._frontEnd = frontEnd
        self._dac = dac
        self._awaXeDacs = [awaXe.Ch0Dac1800, awaXe.Ch1Dac1800]

        enumAwaXe = {'FEB': 'FEB',
                     'AwaXe': 'AwaXe'}
        enumFeb = {'FEB': 'FEB'}

        for i in range(8):
            self.add(pr.LocalVariable(
                name = f'TesBiasSrc[{i}]',
                value = 'AwaXe' if i<2 else 'FEB',
                enum = enumAwaXe if i<2 else enumFeb))
        
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
                dependencies = [self._dac.DacVoltage[2*i], self._dac.DacVoltage[2*i+1], self.Delatch[i]],
                linkedSet = self._setChannelFunc(i),
                linkedGet = self._getChannelFunc(i)))


    # TES Bias current 
    def _setChannelFunc(self, channel):
        def _setChannel(value, write, tesAmp=self._frontEnd.Channel[channel].TesBiasAmp):
            if self.TesBiasSrc[channel].get() == 'FEB':
                # Calculate the DAC voltages to drive
                vp, vn = tesAmp.outCurrentToDac(value, self.Delatch[channel].value())
                # Set the DAC voltages
                with self.root.updateGroup():
                    self._dac.DacVoltage[2*channel].set(vp)
                    self._dac.DacVoltage[2*channel+1].set(vn)
            elif self.TesBiasSrc[channel].get() == 'AwaXe':
                self._awaXeDacs[channel].set(value)
                
        return _setChannel

    def _getChannelFunc(self, channel):
        def _getChannel(read, tesAmp=self._frontEnd.Channel[channel].TesBiasAmp):
            if self.TesBiasSrc[channel].get() == 'FEB':            
                dacChannels = [self._dac.DacVoltage[2*channel], self._dac.DacVoltage[2*channel+1]]
                dacVp = dacChannels[0].value()
                dacVn = dacChannels[1].value()
                delatch = self.Delatch[channel].value()

                iout = tesAmp.dacToOutCurrent(dacVp, dacVn, delatch)
                return iout
            elif self.TesBiasSrc[channel].get() == 'AwaXe':
                return self._awaXeDacs[channel].get()
            
        return _getChannel
