import pyrogue as pr

import warm_tdm

class RowDacDriver(pr.Device):
    def __init__(
            self,
            num_row_selects=32,
            num_chip_selects=0,
            rfsadj=2.0e3,
            dacLoad=24.9,
            ampGain=5.02,
            shuntResistance=1.0e3,
            **kwargs):
        super().__init__(**kwargs)

        self.iOutFs = 1.2 / rfsdaj * 32
        self.dacLoad = dacLoad
        self.ampGain = ampGain
        self.outResistance = outResistance
        
        
        rowBoardIdBits = 8-(num_row_selects + num_chip_selects)

        self.add(pr.RemoteVariable(
            name = 'Mode',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            enum = {
                0: 'TIMING',
                1: 'MANUAL'}))

        self.add(pr.RemoteVariable(
            name = 'RowBoardId',
            offset = 0x04,
            bitOffset = 0,
            bitSize = rowBoardIdBits,
            base = pr.UInt))

        self.add(pr.RemoteCommand(
            name = 'DacReset',
            offset = 0x08,
            bitSize = 1,
            function = pr.Command.touchOne))

        self.add(pr.RemoteVariable(
            name = 'RowFasOnRaw',
            offset = 0x100,
            base = pr.UInt,
            bitSize = num_row_selects * 32,
            numValues = num_row_selects,
            valueBits = 14,
            valueStride = 32))

        self.add(pr.LinkVariable(
            name = 'RowFasOnVoltage',
            dependencies = [self.RowFasOnRaw],
            disp = '{:0.3f}',
            units = 'V',
            linkedGet = self._getVoltageFunc(self.RowFasOnRaw),
            linkedSet = self._setVoltageFunc(self.RowFasOnRaw)))

    def _dacToCurrent(self, dac):
        iOutA = (dac/16384) * self.iOutFs
        iOutB = ((16383-dac)/16384) * self.iOutFs
        current = (iOutA, iOutB)
#        print(f'_dacToCurrent({dac}) = {current}')
        return current

    def _currentToDac(self, current):
                 
    
    def _dacToFasVoltage(self, dac):
        current = self._dacToCurrent(dac)
        voltage = (current[0]-current[1]) * self.dacLoad * self.ampGain
        return voltage

    def _dacToFasCurrent(self, dac):
        return self._dacToSquidVoltage(dac) / self.shuntResistance

    def getVoltageFunc(self, raw):
        def getVoltage(read, index):
            ret = self.raw.get(read=read, index=index)
            if index == -1:
                np.vectorize(self._dacToFasVoltage)(ret)
            else:
                return self._dacToFasVoltage(ret)
                 
