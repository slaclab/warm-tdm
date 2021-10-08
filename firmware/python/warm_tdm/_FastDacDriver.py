import numpy as np

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

    def __init__(self, rfsadj=4.02E3, dacLoad=49.9, ampGain=4.7, **kwargs):
        super().__init__(**kwargs)

        self.iOutFs = (1.2 / rfsadj) * 32
        self.dacLoad = dacLoad
        self.ampGain = ampGain

        for i in range(8):
            self.add(pr.RemoteVariable(
                name = f'OverrideRaw[{i}]',
                offset = (8 << 8) + 4*i,
                base = pr.UInt,
                bitSize = 16))

        for i in range(8):

            def _overGet(index, read, x=i):
                voltage = self._dacToSquidVoltage(self.OverrideRaw[x].value())
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return voltage

            def _overSet(value, index, write, x=i):
                #print(f'Override[{x}].set()')
                self.OverrideRaw[x].set(self._squidVoltageToDac(value), write=write)

            self.add(pr.LinkVariable(
                name = f'Override[{i}]',
                dependencies = [self.OverrideRaw[i]],
#                value = 0.0,
                disp = '{:0.03f}',
                linkedGet = _overGet,
                linkedSet = _overSet))



        for i in range(8):
#             self.add(pr.MemoryDevice(
#                 name = f'Channel[{i}]',
#                 offset = i<<8,
#                 size = 64*4))



            self.add(pr.RemoteVariable(
                name = f'Column[{i}]',
                offset = i << 8,
                base = pr.UInt,
                mode = 'RW',
                bitSize = 32*64,
                numValues = 64,
                valueBits = 14,
                valueStride = 32))

        for i in range(8):

            self.add(pr.LinkVariable(
                name = f'ColumnVoltages[{i}]',
                dependencies = [self.Column[i]],
                disp = '{:0.03f}',                
                linkedGet = self._getVoltageFunc(i),
                linkedSet = self._setVoltageFunc(i)))

#             for j in range(64):
#                 self.add(pr.LinkVariable(
#                     name = f'Col{i}_Row[{j}]',
#                     guiGroup = f'ColumnVoltages[{i}]',
#                     disp = '{:0.03f}',
#                     dependencies = [self.Column[i]],
#                     linkedGet = self._getChannelFunc(i, j),
#                     linkedSet = self._setChannelFunc(i, j)))

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
        iOutA = (dac/16384) * self.iOutFs
        iOutB = ((16383-dac)/16384) * self.iOutFs
        current = (iOutA, iOutB)
#        print(f'_dacToCurrent({dac}) = {current}')
        return current

    def _dacToSquidVoltage(self, dac):
        current = self._dacToCurrent(dac)
        voltage = (current[0]-current[1]) * self.dacLoad * self.ampGain
#        print(f'_dacToSquidVoltage({dac}) = {voltage}')
        return voltage

    def _squidVoltageToDac(self, voltage):
        dacCurrent = voltage / (self.dacLoad * self.ampGain)
#        print(f'dacCurrent = {dacCurrent}')

        dac = int(((dacCurrent/self.iOutFs)*8192)+8191)
        dac = max(min(2**14-1, dac), 0)
#        print(f'_squidVoltageToDac({voltage}) = {dac}')
        return dac


    def _getChannelFunc(self, column, row):
        def _getChannel(read, index):
#            print(f'{self.path}._getChannel - Column[{column}].get(row={row}, read={read})')
            dacValue = self.Column[column].get(index=row, read=read)
            return self._dacToSquidVoltage(dacValue)
        return _getChannel

    def _setChannelFunc(self, column, row):
        def _setChannel(value, write, index):
            dacValue= self._squidVoltageToDac(value)
            #print(f'_setChannel - Column[{column}].set(value={dacValue}, index={row}, write={write}')
            self.Column[column].set(value=dacValue, index=row, write=write)
        return _setChannel

    def _getVoltageFunc(self, column):
        def _getVoltage(read, index):
            ret = self.Column[column].get(read=read, index=index)
            if index == -1:
                return np.vectorize(self._dacToSquidVoltage)(ret)
            else:
                return self._dacToSquidVoltage(ret)
        return _getVoltage

    def _setVoltageFunc(self, column):
        def _setVoltage(value, write, index):
            if index == -1:
                dacValue = np.array([self._squidVoltageToDac(v) for v in value], np.uint32)
            else:
                dacValue = self._squidVoltageToDac(value)
            self.Column[column].set(value=dacValue, index=index, write=write)
        return _setVoltage


