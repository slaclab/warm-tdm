import numpy as np

import pyrogue as pr

import warm_tdm

class FastDacDriver(pr.Device):

    def __init__(self,
                 rfsadj=[2.0E3]*8,
                 dacLoad=[25.0]*8,
                 ampGain=[-4.7]*8,
                 outResistance=[4.0e3]*8,
                 waveformTrigger=None,
                 **kwargs):
        super().__init__(**kwargs)

        rows = 256

        print(rfsadj)
        self.iOutFs = [1.2 / r * 32 for r in rfsadj.values()]
        self.dacLoad = dacLoad
        self.ampGain = ampGain
        self.outResistance = outResistance
        self._waveformTrigger = waveformTrigger

        self.add(pr.LocalVariable(
            name = 'TriggerWaveform',
            value = False))
        

        for i in range(8):
            self.add(pr.RemoteVariable(
                name = f'OverrideRaw[{i}]',
                offset = (8 << 12) + 4*i,
                base = pr.UInt,
                bitSize = 16))

            def _setOverride(value, write, ch=i):
                if self.TriggerWaveform.get():
                    self._waveformTrigger()
                self.OverrideRaw[ch].set(value, write=write)
                
            self.add(pr.LinkVariable(
                name = f'Override[{i}]',
                hidden = True,
                dependencies = [self.OverrideRaw[i]],
                linkedSet = _setOverride,
                linkedGet = lambda read, ch=i: self.OverrideRaw[ch].get(read=read),
                mode = 'RW'))
            

        for i in range(8):

            ####################
            # Current Conversion
            ####################
            def _overCurrentGet(index, read, x=i):
                ret = self._dacToSquidCurrent(self.Override[x].value(), x) * 1.0e6
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return ret

            def _overCurrentSet(value, index, write, x=i):
                #print(f'Override[{x}].set()')
                self.Override[x].set(self._squidCurrentToDac(value*1.0e-6, x), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideCurrent[{i}]',
                dependencies = [self.Override[i]],
                units = u'\u03bcA',
                disp = '{:0.03f}',
                linkedGet = _overCurrentGet,
                linkedSet = _overCurrentSet))

        for i in range(8):
            ####################
            # Voltage Conversion
            ####################
            def _overVoltageGet(index, read, x=i):
                ret = self._dacToSquidVoltage(self.Override[x].value(), x)
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return ret

            def _overVoltageSet(value, index, write, x=i):
                #print(f'Override[{x}].set()')
                self.Override[x].set(self._squidVoltageToDac(value, x), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideVoltage[{i}]',
                dependencies = [self.Override[i]],
                units = 'V',
                disp = '{:0.03f}',
                linkedGet = _overVoltageGet,
                linkedSet = _overVoltageSet))
            


        for i in range(8):

            self.add(pr.RemoteVariable(
                name = f'ColumnRaw[{i}]',
                offset = i << 12,
                base = pr.UInt,
                mode = 'RW',
                bitSize = 32*rows,
                numValues = rows,
                valueBits = 14,
                valueStride = 32))

        for i in range(8):

            self.add(pr.LinkVariable(
                name = f'ColumnCurrents[{i}]',
                dependencies = [self.ColumnRaw[i]],
                disp = '{:0.03f}',
                units = u'\03bcA',
                linkedGet = self._getCurrentFunc(i),
                linkedSet = self._setCurrentFunc(i)))
            
        for i in range(8):
            self.add(pr.LinkVariable(
                name = f'ColumnVoltages[{i}]',
                dependencies = [self.ColumnRaw[i]],
                disp = '{:0.03f}',
                units = 'V',
                linkedGet = self._getVoltageFunc(i),
                linkedSet = self._setVoltageFunc(i)))

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

    def _dacToCurrent(self, dac, column):
        iOutA = (dac/16384) * self.iOutFs[column]
        iOutB = ((16383-dac)/16384) * self.iOutFs[column]
        current = (iOutA, iOutB)
#        print(f'_dacToCurrent({dac}) = {current}')
        return current

    def _dacToSquidVoltage(self, dac, column):
        current = self._dacToCurrent(dac, column)
        voltage = (current[0]-current[1]) * self.dacLoad[column] * self.ampGain[column]
#        print(f'_dacToSquidVoltage({dac}) = {voltage}')
        return voltage

    def _dacToSquidCurrent(self, dac, column):
        return self._dacToSquidVoltage(dac, column) / self.outResistance[column]


    def _squidVoltageToDac(self, voltage, column):
        dacCurrent = voltage / (self.dacLoad[column] * self.ampGain[column])
#        print(f'dacCurrent = {dacCurrent}')

        dac = int(((dacCurrent/self.iOutFs[column])*8192)+8191)
        dac = max(min(2**14-1, dac), 0)
#        print(f'_squidVoltageToDac({voltage}) = {dac}')
        return dac

    def _squidCurrentToDac(self, current, column):
        return self._squidVoltageToDac(current * self.outResistance[column], column)
    


#     def _getChannelFunc(self, column, row):
#         def _getChannel(read, index):
# #            print(f'{self.path}._getChannel - Column[{column}].get(row={row}, read={read})')
#             dacValue = self.Column[column].get(index=row, read=read)
#             return self._dacToSquidVoltage(dacValue)
#         return _getChannel

#     def _setChannelFunc(self, column, row):
#         def _setChannel(value, write, index):
#             dacValue= self._squidVoltageToDac(value)
#             #print(f'_setChannel - Column[{column}].set(value={dacValue}, index={row}, write={write}')
#             self.Column[column].set(value=dacValue, index=row, write=write)
#         return _setChannel

    def _getVoltageFunc(self, column):
        def _getVoltage(read, index):
            ret = self.ColumnRaw[column].get(read=read, index=index)
            if index == -1:
                return np.vectorize(self._dacToSquidVoltage)(ret, column)
            else:
                return self._dacToSquidVoltage(ret, column)
        return _getVoltage

    def _setVoltageFunc(self, column):
        def _setVoltage(value, write, index):
            if index == -1:
                dacValue = np.array([self._squidVoltageToDac(v, column) for v in value], np.uint32)
            else:
                dacValue = self._squidVoltageToDac(value, column)
            self.ColumnRaw[column].set(value=dacValue, index=index, write=write)
        return _setVoltage

    def _getCurrentFunc(self, column):
        def _getCurrent(read, index):
            ret = self.ColumnRaw[column].get(read=read, index=index)
            if index == -1:
                return np.vectorize(self._dacToSquidCurrent)(ret, column)
            else:
                return self._dacToSquidCurrent(ret, column)
        return _getCurrent

    def _setCurrentFunc(self, column):
        def _setCurrent(value, write, index):
            if index == -1:
                dacValue = np.array([self._squidCurrentToDac(v, column) for v in value], np.uint32)
            else:
                dacValue = self._squidCurrentToDac(value, column)
            self.ColumnRaw[column].set(value=dacValue, index=index, write=write)
        return _setCurrent

