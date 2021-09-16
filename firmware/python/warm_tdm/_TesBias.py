import pyrogue as pr

class TesBias(pr.Device):
    def __init__(self, dac, **kwargs):
        super().__init__(**kwargs)
        
        self._dac = dac

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'BiasCurrent[{i}]',
                disp = '{:1.3f}',                
                units = 'mA',
                dependencies = [self._dac.DacVoltage[i], self._dac.DacVoltage[i+8]],
                linkedSet = self._setChannelFunc(i),
                linkedGet = self._getChannelFunc(i)))


    def _setChannelFunc(self, channel):
        def _setChannel(value, write):
            #dacChannels = [self._dac.InpVoltage[channel], self._dac.InpVoltage[channel+8]]
            v1 = value  / .5
            
            if v1 > 0:
                self._dac.setVoltages([channel, channel+8], [v1, 0])
            else:
                self._dac.setVoltages([channel, channel+8], [0, -1*v1])
                
        return _setChannel

    def _getChannelFunc(self, channel):
        def _getChannel(read):
            dacChannels = [self._dac.DacVoltage[channel], self._dac.DacVoltage[channel+8]]
            dacValues = [dacChannels[0].value(), dacChannels[1].value()]
            print(dacValues)
            v1 = dacValues[0] - dacValues[1]
            iOut = (v1*.5)
            return iOut
        return _getChannel
    
