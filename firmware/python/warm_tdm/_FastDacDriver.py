import pyrogue as pr

import warm_tdm

class DacMemory(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(64):
            self.add(pr.RemoteVariable(
                name = f'Row[{i}]',
                offset = i*4,
                bitSize = 16,
                mode = 'RW'))
                

                
class FastDacDriver(pr.Device):
    
    def __init__(self, rfsadj=4.02E3, dacLoad=49.9, ampGain=6.0, **kwargs):
        super().__init__(**kwargs)

        self.iOutFs = (1.2 / rfsadj) * 32
        self.dacLoad = dacLoad
        self.ampGain = ampGain

        for i in range(8):
#             self.add(pr.MemoryDevice(
#                 name = f'Channel[{i}]',
#                 offset = i<<8,
#                 size = 64*4))

            self.add(pr.RemoteVariable(
                name = f'OverrideRaw[{i}]',
                offset = (8 << 8) + 4*i,
                base = pr.UInt,
                bitSize = 16))

            self.add(pr.LinkVariable(
                name = f'Override[{i}]',
                dependencies = [self.OverrideRaw[i]],
                linkedGet = lambda index, read: self._dacToSquidVoltage(self.OverrideRaw[i].value),
                linkedSet = lambda valuem, index, read: self.OverrideRaw[i].set(self._squidVoltageToDac(value))))
                

            self.add(pr.RemoteVariable(
                name = f'Column[{i}]',
                offset = i << 8,
                base = pr.UInt,
                mode = 'RW',
                bitSize = 32*64,
                numValues = 64,
                valueBits = 14,
                valueStride = 32))

            for j in range(64):
                self.add(pr.LinkVariable(
                    name = f'Col{i}_Row[{j}]',
                    guiGroup = f'ColumnVoltages[{i}]',
                    linkedGet = self._getChannelFunc(i, j),
                    linkedSet = self._setChannelFunc(i, j)))

        @self.command()
        def RamTest():
            for i in range(8):
                self.Channel[i].set(0, [(i<<6)+j for j in range(64)], write=False)
#                for j in range(64):
#                    value = (i<<6)+j
#                    print(f'Writing {value:x} to Ch {i} Row {j}')
#                    self.Channel[i].Row[j].set(j, value, write=False)
#                    self.Channel[i].set(j, [value], write=False)

            self.writeAndVerifyBlocks()
            
    def _dacToCurrent(self, dac):
        return ((dac/16384)-8192)*self.iOutFs

    def _dacToSquidVoltage(self, dac):
        self._dacToCurrent(dac) * self.dacLoad * self.ampGain

    def _squidVoltageToDac(self, voltage):
        dacCurrent = voltage / (self.dacLoad * self.ampGain)
        dac = ((dacCurrent/self.iOutFs)+8192)*16384
        return dac


    def _getChannelFunc(self, column, row):
        def _getChannel(index, read):
            dacValue = self.Column[column].get(row, read)
            return self._dacToSquidVoltage(dacValue)
        return _getChannel

    def _setChannelFunc(self, column, row):
        def _setChannel(value, index, write):
            dacValue= self._squidVoltageToDac(value)
            self.Column[column].set(dacValue, row, write)
        return _setChannel
    

