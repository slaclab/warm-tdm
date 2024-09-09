import pyrogue as pr
import numpy as np

class SaBiasOffset(pr.Device):
    def __init__(self, dac, frontEnd, waveformTrigger, **kwargs):
        super().__init__(**kwargs)

        self.shunt = 15.0e3

        self._dac = dac
        self._amps = [frontEnd.Channel[x].SAAmp for x in range(8)]
        self._waveformTrigger = waveformTrigger

        self.add(pr.LocalVariable(
            name = 'TriggerWaveform',
            groups = ['NoConfig'],
            value = False))


        for i in range(8):
            def _setBias(value, write, ch=i):
                if self.TriggerWaveform.get():
                    self._waveformTrigger()
                self._dac.DacVoltage[ch].set(value, write=write)

            self.add(pr.LinkVariable(
                name = f'BiasVoltage[{i}]',
                groups = ['NoConfig'],                
                dependencies = [self._dac.DacVoltage[i]],
                linkedSet = _setBias,
                linkedGet = lambda read, ch=i: self._dac.DacVoltage[ch].get(read=read),
                mode = 'RW',
                disp = '{:0.03f}',
                units = 'V'))


        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'OffsetVoltage[{i}]',
                variable = self._dac.DacVoltage[i+8],
                units = 'V'))


        for i in range(8):
            def biasCurrentGet(read, ch=i):
                return self._amps[ch].saBiasCurrent(self.BiasVoltage[ch].get(read=read)) * 1.0e6

            def biasCurrentSet(value, write, ch=i):
                self.BiasVoltage[ch].set(self._amps[ch].saBiasDacVoltage(value/1.0e6), write=write)
            
            self.add(pr.LinkVariable(
                name = f'BiasCurrent[{i}]',
                dependencies = [self.BiasVoltage[i]],
                linkedGet = biasCurrentGet,
                linkedSet = biasCurrentSet,
                disp = '{:0.01f}',
                units = u'\u03bcA'))

        self.add(pr.LinkVariable(
            name = 'OffsetVoltageArray',
            hidden = True,
            groups = ['NoConfig'],            
            dependencies = [x for x in self.OffsetVoltage.values()],
            linkedGet = lambda read, index: self.OffsetVoltage[index].get(read) if index != -1 else np.array([x.get(read=read) for x in self.OffsetVoltage.values()])))

        @self.command()
        def SetAllVoltage(arg):
            for bias, offset in zip(self.BiasVoltage.values(), self.OffsetVoltage.values()):
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
