import pyrogue as pr

class TesBias(pr.Device):
    def __init__(self, dac, **kwargs):
        super().__init__(**kwargs)
        
        self._dac = dac

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'BiasCurrent[{i}]',
                dependencies = [self._dac.DacVoltage[i], self._dac.DacVoltage[i+8]],
                linkedSet = self._setChannelFunc(i),
                linkedGet = self._getChannelFunc(i)))


    def _setChannelFunc(self, channel):
        def _setChannel(value, write):
            #dacChannels = [self._dac.InpVoltage[channel], self._dac.InpVoltage[channel+8]]
            v1 = ((value * 1000) / .5)
            
            if v1 > 0:
                self._dac.setVoltages([i, i+8], [v1, 0])
            else:
                self._dac.setVoltages([i, i+8], [0, v1])
                
        return _setChannel

    def _getChannelFunc(self, channel):
        def _getChannel(read):
            dacChannels = [self._dac.DacVoltage[channel], self._dac.DacVoltage[channel]]
            dacValues = [dacChannels[0].get(read=read), dacChannels[1].get(read=read)]
            v1 = dacValues[0] - dacValues[1]
            iOut = (v1*.5) / 1000
            return iOut
        return _getChannel
    
