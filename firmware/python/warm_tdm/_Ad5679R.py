import pyrogue as pr
import numpy as np

class Ad5679R(pr.Device):
    def __init__(self, gain=1, **kwargs):
        super().__init__(**kwargs)

        self.gain = gain

        NOP_CMD        = 0b0000
        WR_INP_CMD     = 0b0001
        DAC_UPDATE_CMD = 0b0010
        WR_DAC_CMD     = 0b0011
        PWR_DOWN_CMD   = 0b0100
        LDAC_MASK_CMD  = 0b0101
        SOFT_RST_CMD   = 0b0110
        INT_REF_CMD    = 0b0111
        DCEN_CMD       = 0b1000
        RDBACK_CMD     = 0b1001
        WR_ALL_INP_CMD = 0b1010
        WR_ALL_DAC_CMD = 0b1011

        self.add(pr.RemoteCommand(
            name = "DacUpdate",
            offset = DAC_UPDATE_CMD << 6,
            bitSize = 16,
            bitOffset = 0,
            function = pr.RemoteCommand.touch))

        for i in range(16):
            self.add(pr.RemoteVariable(
                name = f'Inp[{i}]',
                mode = 'RW',
                offset = WR_INP_CMD << 6 | i << 2,
                bitSize = 16,
                bitOffset = 0,
                base = pr.UInt,
                hidden = False))

            self.add(pr.LinkVariable(
                name = f'InpVoltage[{i}]',
                mode = 'RW',
                disp = '{:1.3f}',
                units = 'V',
                dependencies = [self.Inp[i]],
                linkedSet = self._setVoltageFunc(self.Inp[i]),
                linkedGet = self._getVoltageFunc(self.Inp[i])))

        for i in range(16):
            self.add(pr.RemoteVariable(
                name = f'Dac[{i}]',
                mode = 'RW',
                offset = WR_DAC_CMD << 6 | i <<2,
                bitSize = 16,
                bitOffset = 0,
                base = pr.UInt))

            self.add(pr.LinkVariable(
                name = f'DacVoltage[{i}]',
                mode = 'RW',
                disp = '{:1.3f}',
                units = 'V',
                dependencies = [self.Dac[i]],
                linkedSet = self._setVoltageFunc(self.Dac[i]),
                linkedGet = self._getVoltageFunc(self.Dac[i])))

        @self.command()
        def ZeroVoltages():
            self.setVoltages(list(range(16)), [0 for x in range(16)])


    def _setVoltageFunc(self, chVar):
        def _setVoltage(value, write):
            value = np.clip(value, 0.0, 2.499)
            dacValue = int(round((value / (self.gain * 2.5)) * 2**16))
            chVar.set(value=dacValue, write=write)

        return _setVoltage

    def _getVoltageFunc(self, chVar):
        def _getVoltage(read):
            dacValue = chVar.get(read=read)
            return (dacValue / 2**16) * (self.gain * 2.5)

        return _getVoltage

    # This is broken
    def setVoltages(self, channels, voltages):
        # Set the input voltages
        for ch, v in zip(channels, voltages):
            self.InpVoltage[ch].set(v, write=True)

        # Load those voltages to the output
        value = 0;
        for ch in channels:
            value |= 2**ch
        self.DacUpdate(value)

        # For display only
        for ch, v in zip(channels, voltages):
            self.DacVoltage[ch].set(v, write=True)
