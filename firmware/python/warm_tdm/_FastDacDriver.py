import numpy as np

import pyrogue as pr

import warm_tdm

class FastDacMem(pr.Device):
    def __init__(self, size, amp, **kwargs):
        super().__init__(**kwargs)

        self.amp = amp

        self.add(pr.RemoteVariable(
            name = f'Raw',
            offset = kwargs['offset'],
            base = pr.UInt,
            numValues = size,
            valueBits = 14,
            valueStride = 32))

        self.add(pr.LinkVariable(
            name = f'Current',
            dependencies = [self.Raw],
            disp = '{:0.3f}',
            units = '\u03bcA',
            linkedGet = self.getCurrent,
            linkedSet = self.setCurrent))

        self.add(pr.LinkVariable(
            name = f'Voltage',
            dependencies = [self.Raw],
            disp = '{:0.3f}',
            units = 'V',
            linkedGet = self.getVoltage,
            linkedSet = self.setVoltage))

    def getCurrent(self, index, read):
        dacs = self.Raw.get(read=read, index=index)
        if index == -1:
            currents = [self.amp.dacToOutCurrent(dac) for dac in dacs]
            currents = np.array(currents, dtype=np.float64)
        else:
            currents = self.amp.outCurrentToDac(dac)

        return currents

    def setCurrent(self, value, index, write):
        if index == -1:
            dacs = [self.amp.outCurrentToDac(current) for current in value]
        else:
            dacs = self.amp.outCurrentToDac(value)

        self.Raw.set(index=index, write=write, value=dacs)

    def getVoltage(self, index, read):
        dacs = self.Raw.get(read=read, index=index)
        if index == -1:
            voltages = [self.amp.dacToOutVoltage(dac) for dac in dacs]
            voltages = np.array(voltages, dtype=np.float64)
        else:
            voltages = self.amp.outVoltageToDac(dacs)

        return voltages

    def setVoltage(self, value, index, write):
        if index == -1:
            dacs = [self.amp.outVoltageToDac(voltage) for voltage in value]
        else:
            dacs = self.amp.outVoltageToDac(value)

        self.Raw.set(index=index, write=write, value=dacs)



class FastDacDriver(pr.Device):

    def __init__(self, rows, **kwargs):
        super().__init__(**kwargs)

        self.rows = rows
        
        # Create devices that hold amplifier configuration
        for i in range(8):
            self.add(warm_tdm.FastDacAmplifierSE(
                name = f'Amp[{i}]',
                hidden = True))

        

        for col in range(8):
            self.add(pr.RemoteVariable(
                name = f'DacRawNow[{col}]',
                offset = (9 << 12) + 4*col,
                mode = 'RO',
                base = pr.UInt,
                bitSize = 14))

        for col in range(8):
            self.add(pr.LinkVariable(
                name = f'DacCurrentNow[{col}]',
                dependencies = [self.DacRawNow[col]],
                mode = 'RO',
                units = u'\u03bcA',
                disp = '{:0.03f}',
                pollInterval = 1,
                linkedGet = lambda x=col: self.Amp[x].dacToOutCurrent(self.DacRawNow[x].value())))
            
        
        for col in range(8):
            self.add(pr.RemoteVariable(
                name = f'OverrideRaw[{col}]',
                offset = (8 << 12) + 4*col,
                base = pr.UInt,
                bitSize = 16))

        for col in range(8):

            ####################
            # Current Conversion
            ####################
            def _overCurrentGet(index, read, x=col):
                ret = self.Amp[x].dacToOutCurrent(self.OverrideRaw[x].value()) 
                return ret

            def _overCurrentSet(value, index, write, x=col):
                self.OverrideRaw[x].set(self.Amp[x].outCurrentToDac(value), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideCurrent[{col}]',
                dependencies = [self.OverrideRaw[col]],
                units = u'\u03bcA',
                disp = '{:0.03f}',
                linkedGet = _overCurrentGet,
                linkedSet = _overCurrentSet))

        for col in range(8):
            ####################
            # Voltage Conversion
            ####################
            def _overVoltageGet(index, read, x=col):
                ret = self.Amp[x].dacToOutCurrent(self.OverrideRaw[x].value())
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return ret

            def _overVoltageSet(value, index, write, x=col):
                #print(f'Override[{x}].set()')
                self.OverrideRaw[x].set(self.Amp[x].outVoltageToDac(value), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideVoltage[{col}]',
                dependencies = [self.OverrideRaw[col]],
                units = 'V',
                disp = '{:0.03f}',
                linkedGet = _overVoltageGet,
                linkedSet = _overVoltageSet))
            


        for col in range(8):

            self.add(FastDacMem(
                name = f'ColumnRaw[{col}]',
                offset = col << 12,
                amp = self.Amp[col],
                size = rows))
#                 base = pr.UInt,
#                 mode = 'RW',
#                 bitSize = 32*rows,
#                 numValues = rows,
#                 valueBits = 14,
#                 valueStride = 32))

            
#         for col in range(8):
#             self.add(pr.LinkVariable(
#                 name = f'ColumnVoltages[{col}]',
#                 dependencies = [self.ColumnRaw[col]],
#                 disp = '{:0.03f}',
#                 units = 'V',
#                 linkedGet = self._getVoltageFunc(col),
#                 linkedSet = self._setVoltageFunc(col)))

#         for col in range(8):

#             self.add(pr.LinkVariable(
#                 name = f'ColumnCurrents[{col}]',
#                 dependencies = [self.ColumnVoltages[col]],
#                 disp = '{:0.03f}',
#                 units = u'\u03bcA',
#                 linkedGet = self._getCurrentFunc(col),
#                 linkedSet = self._setCurrentFunc(col)))
            

#         @self.command()
#         def RamTest():
#             for col in range(8):
#                 self.Channel[col].set(0, [(col<<6)+j for j in range(64)], write=False)
# #                for j in range(64):
# #                    value = (i<<6)+j
# #                    print(f'Writing {value:x} to Ch {i} Row {j}')
# #                    self.Channel[i].Row[j].set(j, value, write=False)
# #                    self.Channel[i].set(j, [value], write=False)

#             self.writeAndVerifyBlocks()

#     def _dacToCurrent(self, dac, column):
#         iOutFs = self.IOutFs[column].value()
#         iOutA = (dac/16384) * iOutFs
#         iOutB = ((16383-dac)/16384) * iOutFs
#         current = (iOutA, iOutB)
# #        print(f'_dacToCurrent({dac}) = {current}')
#         return current

#     def _dacToSquidVoltage(self, dac, column):
#         current = self._dacToCurrent(dac, column)
#         voltage = (current[0]-current[1]) * self.dacLoad_deps[column].value() * self.ampGain_deps[column].value()
# #        print(f'_dacToSquidVoltage({dac}) = {voltage}')
#         return voltage

#     def _dacToSquidCurrent(self, dac, column):
#         return self._dacToSquidVoltage(dac, column) / self.outResistance_deps[column].value() * 1e6


#     def _squidVoltageToDac(self, voltage, column):
#         dacCurrent = voltage / (self.dacLoad_deps[column].value() * self.ampGain_deps[column].value())
# #        print(f'dacCurrent = {dacCurrent}')

#         dac = int(((dacCurrent/self.IOutFs[column].value())*8192)+8191)
#         dac = max(min(2**14-1, dac), 0)
# #        print(f'_squidVoltageToDac({voltage}) = {dac}')
#         return dac

#     def _squidCurrentToDac(self, current, column):
#         return self._squidVoltageToDac(current * 1e-6 * self.outResistance_deps[column].value(), column)
    


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

#     def _getVoltageFunc(self, column):
#         def _getVoltage(read, index):
#             ret = self.ColumnRaw[column].get(read=read, index=index)
#             if index == -1:
#                 return np.vectorize(self._dacToSquidVoltage)(ret, column)
#             else:
#                 return self._dacToSquidVoltage(ret, column)
#         return _getVoltage

#     def _setVoltageFunc(self, column):
#         def _setVoltage(value, write, index):
#             if index == -1:
#                 dacValue = np.array([self._squidVoltageToDac(v, column) for v in value], np.uint32)
#             else:
#                 dacValue = self._squidVoltageToDac(value, column)
#             self.ColumnRaw[column].set(value=dacValue, index=index, write=write)
#         return _setVoltage

#     def _getCurrentFunc(self, column):
#         def _getCurrent(read, index):
#             ret = self.ColumnRaw[column].get(read=read, index=index)
#             if index == -1:
#                 return np.vectorize(self._dacToSquidCurrent)(ret, column)
#             else:
#                 return self._dacToSquidCurrent(ret, column)
#         return _getCurrent

#     def _setCurrentFunc(self, column):
#         def _setCurrent(value, write, index):
#             if index == -1:
#                 dacValue = np.array([self._squidCurrentToDac(v, column) for v in value], np.uint32)
#             else:
#                 dacValue = self._squidCurrentToDac(value, column)
#             self.ColumnRaw[column].set(value=dacValue, index=index, write=write)
#         return _setCurrent

