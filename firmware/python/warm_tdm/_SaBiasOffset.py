import pyrogue as pr

class SaBiasOffset(pr.Device):
    def __init__(self, dac, **kwargs):
        super().__init__(**kwargs)
        
        self._dac = dac

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'Bias[{i}]',
                variable = self._dac.DacVoltage[i]))


        for i in range(8):            
            self.add(pr.LinkVariable(
                name = f'Offset[{i}]',
                variable = self._dac.DacVoltage[i+8]))

#     def _setChannelFunc(self, channel):
#         def _setChannel(value, write):
#             dacChannel = self._dac.DacVoltage[channel]
#             dacValue = value * 15e3
#             dacChannel.set(dacValue, write=write)
#         return _setChannel

#     def _getChannelFunc(self, channel):
#         def _setChannel(read):
#             dacChannel = self._dac.DacVoltage[channel]
#             dacValue = dacChannel.get(read=read)
#             return dacValue / 15e3
#         return _getChannel
    
