import pyrogue as pr

class SaBiasOffset(pr.Device):
    def __init__(self, dac, resistor=15e3, **kwargs):
        super().__init__(**kwargs)
        
        self._dac = dac

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'Bias[{i}]',
                variable = self._dac.DacVoltage[i],
                units = 'V'))


        for i in range(8):            
            self.add(pr.LinkVariable(
                name = f'Offset[{i}]',
                variable = self._dac.DacVoltage[i+8],
                units = 'V'))

        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'BiasCurrent[{i}]',
                dependencies = [self.Bias[i]],
                linkedGet = lambda read, ch=i: self.Bias[ch].get(read=read) * 1000 / resistor,
                linkedSet = lambda value, write, ch=i: self.Bias[ch].set( (value/1000.0)*resistor  , write=write),
                units = 'mA'))

        @self.command()
        def SetAll(arg):
            for bias, offset in zip(self.Bias.values(), self.Offset.values()):
                bias.set(arg, write=False)
                offset.set(arg, write=False)

            self.writeAndVerifyBlocks()
            self._dac.writeAndVerifyBlocks()



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
    
