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
                mode = 'RW',
                offset = 0x1000 + (col << 2),
                bitSize = 16,
                base = pr.UInt))

        for col in range(8):
            self.add(pr.LinkVariable(
                name = f'DacVoltage[{col}]',
                mode = 'RW',
                dependencies = [self.Dac[col]],
                units = 'V',
                disp = '{:1.3f}',
                linkedGet = lambda read, x=col: ((2*self._vref * self.Dac[x].get(read=read)) / 65536)-self._vref,
                linkedSet = lambda value, write, x=col: self.Dac[x].set(65535 * ((value + self._vref) / (2*self._vref)), write=write)))

        # LDAC Register
        self.add(pr.RemoteVariable(
            name = 'LDAC_L',
            offset = 0x104,
            bitOffset = 0,
            bitSize = 1,
            hidden = True,
            groups = ['NoConfig', 'NoState', 'NoStream'],
            base = pr.UInt))

        # Add Delatch registers
        for i in range(8):
            self.add(pr.RemoteVariable(
                name = f'Delatch[{i}]',
                offset = 0x100,
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
            vp, vn = tesAmp.outCurrentToDac(value, self.Delatch[channel].value())
            # Really should build a different amp model for this instead of this quick and dirty fix
            dacVoltage = vp-vn
            # Set the DAC voltages
            self.DacVoltage[channel].set(dacVoltage)

        return _setChannel

    def _getChannelFunc(self, channel):
        def _getChannel(read, tesAmp=self._frontEnd.Channel[channel].TesBiasAmp):
            dacChannel = self.DacVoltage[channel]
            dacVp = dacChannel.value()
            dacVn = 0
            delatch = self.Delatch[channel].value()

            iout = tesAmp.dacToOutCurrent(dacVp, dacVn, delatch)
            return iout
        return _getChannel

    def writeBlocks(self, **kwargs):
        if variable is not None and variable.name == 'LDAC_L':
            pr.startTransaction(variable._block, type=rim.Write, **kwargs)            
        else:
            super().writeBlocks(**kwargs)
            self.LDAC_L.set(0)
            self.LDAC_L.set(1)
