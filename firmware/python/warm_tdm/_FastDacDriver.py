import numpy as np

import pyrogue as pr

import warm_tdm

class FastDacDriver(pr.Device):

    def __init__(self,
                 typ,
                 loading,                 
                 waveformTrigger=None,
                 **kwargs):
        super().__init__(**kwargs)

        rows = 1

        self._waveformTrigger = waveformTrigger

        self.rfsadj_deps = loading.deps(typ, 'FSADJ_R')
        self.dacLoad_deps = loading.deps(typ, 'DAC_LOAD_R')
        self.ampGain_deps = loading.deps(typ, 'AMP_GAIN')
        self.outResistance_deps = loading.deps(typ, 'SHUNT_R')

        for col in range(8):
            self.add(pr.LinkVariable(
                name = f'IOutFs[{col}]',
                mode = 'RO',
                hidden = True,
                dependencies = [self.rfsadj_deps[col]],
                linkedGet = lambda read, i=col: 1.2 / self.rfsadj_deps[i].get(read=read) * 32))
            

        self.add(pr.LocalVariable(
            name = 'TriggerWaveform',
            value = False))
        

        for col in range(8):
            self.add(pr.RemoteVariable(
                name = f'OverrideRaw[{col}]',
                offset = (8 << 12) + 4*col,
                base = pr.UInt,
                bitSize = 16))

            def _setOverride(value, write, ch=col):
                if self.TriggerWaveform.get():
                    self._waveformTrigger()
                self.OverrideRaw[ch].set(value, write=write)
                
            self.add(pr.LinkVariable(
                name = f'Override[{col}]',
                hidden = True,
                dependencies = [self.OverrideRaw[col]],
                linkedSet = _setOverride,
                linkedGet = lambda read, ch=col: self.OverrideRaw[ch].get(read=read),
                mode = 'RW'))
            

        for col in range(8):

            ####################
            # Current Conversion
            ####################
            def _overCurrentGet(index, read, x=col):
                ret = self._dacToSquidCurrent(self.Override[x].value(), x) 
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return ret

            def _overCurrentSet(value, index, write, x=col):
                #print(f'Override[{x}].set()')
                self.Override[x].set(self._squidCurrentToDac(value, x), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideCurrent[{col}]',
                dependencies = [self.Override[col]],
                units = u'\u03bcA',
                disp = '{:0.03f}',
                linkedGet = _overCurrentGet,
                linkedSet = _overCurrentSet))

        for col in range(8):
            ####################
            # Voltage Conversion
            ####################
            def _overVoltageGet(index, read, x=col):
                ret = self._dacToSquidVoltage(self.Override[x].value(), x)
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return ret

            def _overVoltageSet(value, index, write, x=col):
                #print(f'Override[{x}].set()')
                self.Override[x].set(self._squidVoltageToDac(value, x), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideVoltage[{col}]',
                dependencies = [self.Override[col]],
                units = 'V',
                disp = '{:0.03f}',
                linkedGet = _overVoltageGet,
                linkedSet = _overVoltageSet))
            


        for col in range(8):

            self.add(pr.RemoteVariable(
                name = f'ColumnRaw[{col}]',
                offset = col << 12,
                base = pr.UInt,
                mode = 'RW',
                bitSize = 32*rows,
                numValues = rows,
                valueBits = 14,
                valueStride = 32))

            
        for col in range(8):
            self.add(pr.LinkVariable(
                name = f'ColumnVoltages[{col}]',
                dependencies = [self.ColumnRaw[col]],
                disp = '{:0.03f}',
                units = 'V',
                linkedGet = self._getVoltageFunc(col),
                linkedSet = self._setVoltageFunc(col)))

        for col in range(8):

            self.add(pr.LinkVariable(
                name = f'ColumnCurrents[{col}]',
                dependencies = [self.ColumnVoltages[col]],
                disp = '{:0.03f}',
                units = u'\u03bcA',
                linkedGet = self._getCurrentFunc(col),
                linkedSet = self._setCurrentFunc(col)))
            

        @self.command()
        def RamTest():
            for col in range(8):
                self.Channel[col].set(0, [(col<<6)+j for j in range(64)], write=False)
#                for j in range(64):
#                    value = (i<<6)+j
#                    print(f'Writing {value:x} to Ch {i} Row {j}')
#                    self.Channel[i].Row[j].set(j, value, write=False)
#                    self.Channel[i].set(j, [value], write=False)

            self.writeAndVerifyBlocks()

    def _dacToCurrent(self, dac, column):
        iOutFs = self.IOutFs[column].value()
        iOutA = (dac/16384) * iOutFs
        iOutB = ((16383-dac)/16384) * iOutFs
        current = (iOutA, iOutB)
#        print(f'_dacToCurrent({dac}) = {current}')
        return current

    def _dacToSquidVoltage(self, dac, column):
        current = self._dacToCurrent(dac, column)
        voltage = (current[0]-current[1]) * self.dacLoad_deps[column].value() * self.ampGain_deps[column].value()
#        print(f'_dacToSquidVoltage({dac}) = {voltage}')
        return voltage

    def _dacToSquidCurrent(self, dac, column):
        return self._dacToSquidVoltage(dac, column) / self.outResistance_deps[column].value() * 1e6


    def _squidVoltageToDac(self, voltage, column):
        dacCurrent = voltage / (self.dacLoad_deps[column].value() * self.ampGain_deps[column].value())
#        print(f'dacCurrent = {dacCurrent}')

        dac = int(((dacCurrent/self.IOutFs[column].value())*8192)+8191)
        dac = max(min(2**14-1, dac), 0)
#        print(f'_squidVoltageToDac({voltage}) = {dac}')
        return dac

    def _squidCurrentToDac(self, current, column):
        return self._squidVoltageToDac(current * 1e-6 * self.outResistance_deps[column].value(), column)
    


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

