import pyrogue as pr
import numpy as np

class SaBiasOffset2(pr.Device):
    def __init__(self, saBiasDac, saOffsetDac, frontEnd, **kwargs):
        super().__init__(**kwargs)

        self.shunt = 15.0e3

        self._biasDac = saBiasDac
        self._offsetDac = saOffsetDac
        self._amps = [frontEnd.Channel[x].SAAmp for x in range(8)]

        # Create Link Variables to DAC P and N channels for each column
        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'BiasVoltageP[{i}]',
                groups = ['NoConfig'],
                dependencies = [self._biasDac.DacVoltage[2*i]],
                linkedSet = lambda value, write, ch=i: self._biasDac.DacVoltage[2*ch].set(value, write=write),
                linkedGet = lambda read, ch=i: self._biasDac.DacVoltage[2*ch].get(read=read),
                hidden = True,
                mode = 'RW',
                disp = '{:0.03f}',
                units = 'V'))

            self.add(pr.LinkVariable(
                name = f'BiasVoltageN[{i}]',
                groups = ['NoConfig'],
                dependencies = [self._biasDac.DacVoltage[2*i+1]],
                linkedSet = lambda value, write, ch=i: self._biasDac.DacVoltage[2*ch+1].set(value, write=write),
                linkedGet = lambda read, ch=i: self._biasDac.DacVoltage[2*ch+1].get(read=read),
                hidden = True,
                mode = 'RW',
                disp = '{:0.03f}',
                units = 'V'))

            def biasVoltageGet(read, ch=i):
                vp = self.BiasVoltageP[ch].get(read=read)
                # vn = self.BiasVoltageN[ch].get(read=read)
                return vp*2 #vp-vn

            def biasVoltageSet(value, write, ch=i):
                vp = 0.5 * value
                vn = 0
                vp = np.clip(vp, 0, 2.5)
                self.BiasVoltageP[ch].set(vp, write=write)
                #self.BiasVoltageN[ch].set(vn, write=write)

            self.add(pr.LinkVariable(
                name = f'BiasVoltage[{i}]',
                dependencies = [self.BiasVoltageP[i], self.BiasVoltageN[i]],
                linkedGet = biasVoltageGet,
                linkedSet = biasVoltageSet,
                disp = '{:0.01f}',
                units = u'\u03bcA'))


        # Create SA Bias Current LinkVariables that use SA front end amplifier properties
        # to convert between current and DAC values
        for i in range(8):
            def biasCurrentGet(read, ch=i):
                vp = self.BiasVoltageP[ch].get(read=read)
                #vn = self.BiasVoltageN[ch].get(read=read)
                vn = 0
                return self._amps[ch].saBiasCurrent(vp, vn) * 1.0e6

            def biasCurrentSet(value, write, ch=i):
                vp, vn = self._amps[ch].saBiasDacVoltage(value/1.0e6)
                self.BiasVoltageP[ch].set(vp, write=write)
                #self.BiasVoltageN[ch].set(vn, write=write)

            self.add(pr.LinkVariable(
                name = f'BiasCurrent[{i}]',
                dependencies = [self.BiasVoltageP[i], self.BiasVoltageN[i]],
                linkedGet = biasCurrentGet,
                linkedSet = biasCurrentSet,
                disp = '{:0.01f}',
                units = u'\u03bcA'))

        # Create Offset Voltage Link Variables for P and N DAC channels
        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'OffsetVoltageP[{i}]',
                groups = ['NoConfig'],
                dependencies = [self._offsetDac.DacVoltage[2*i]],
                linkedSet = lambda value, write, ch=i: self._offsetDac.DacVoltage[2*ch].set(value, write=write),
                linkedGet = lambda read, ch=i: self._offsetDac.DacVoltage[2*ch].get(read=read),
                hidden = True,
                mode = 'RW',
                disp = '{:0.03f}',
                units = 'V'))

            self.add(pr.LinkVariable(
                name = f'OffsetVoltageN[{i}]',
                groups = ['NoConfig'],
                dependencies = [self._offsetDac.DacVoltage[2*i+1]],
                linkedSet = lambda value, write, ch=i: self._offsetDac.DacVoltage[2*ch+1].set(value, write=write),
                linkedGet = lambda read, ch=i: self._offsetDac.DacVoltage[2*ch+1].get(read=read),
                hidden = True,
                mode = 'RW',
                disp = '{:0.03f}',
                units = 'V'))


            def _set(value, write, ch=i):
                vp = 0.5 * value
                vn = 0
                vp = np.clip(vp, 0, 2.5)

                self.OffsetVoltageP[ch].set(vp, write=write)
                #self.OffsetVoltageN[ch].set(vn, write=write)

            def _get(read, ch=i):
                vp = self.OffsetVoltageP[ch].get(read=read)
                #vn = self.OffsetVoltageN[ch].get(read=read)
                return vp*2#vp-vn

            self.add(pr.LinkVariable(
                name = f'OffsetVoltage[{i}]',
                groups = ['NoConfig'],
                dependencies = [self.OffsetVoltageP[i], self.OffsetVoltageN[i]],
                disp = '{:0.03f}',
                linkedGet = _get,
                linkedSet = _set))


        self.add(pr.LinkVariable(
            name = 'OffsetVoltageArray',
            hidden = True,
            groups = ['NoConfig'],
            dependencies = [x for x in self.OffsetVoltage.values()],
            linkedGet = lambda read, index: self.OffsetVoltage[index].get(read) if index != -1 else np.array([x.get(read=read) for x in self.OffsetVoltage.values()])))

        self.add(pr.LinkVariable(
            name = 'OffsetVoltagePArray',
            hidden = True,
            groups = ['NoConfig'],
            dependencies = [x for x in self.OffsetVoltageP.values()],
            linkedGet = lambda read, index: self.OffsetVoltageP[index].get(read) if index != -1 else np.array([x.get(read=read) for x in self.OffsetVoltageP.values()])))

        self.add(pr.LinkVariable(
            name = 'OffsetVoltageNArray',
            hidden = True,
            groups = ['NoConfig'],
            dependencies = [x for x in self.OffsetVoltageN.values()],
            linkedGet = lambda read, index: self.OffsetVoltageN[index].get(read) if index != -1 else np.array([x.get(read=read) for x in self.OffsetVoltageN.values()])))


        @self.command()
        def SetAllVoltage(arg):
            for bias, offset in zip(self.BiasVoltage.values(), self.OffsetVoltage.values()):
                bias.set(arg, write=False)
                offset.set(arg, write=False)

            self.writeAndVerifyBlocks()
            self._biasDac.writeAndVerifyBlocks()
            self._offsetDac.writeAndVerifyBlocks()
