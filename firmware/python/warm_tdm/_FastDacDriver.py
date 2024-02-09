import numpy as np

import pyrogue as pr

import warm_tdm

class FastDacMem(pr.Device):
    def __init__(self, size, amp, **kwargs):
        super().__init__(**kwargs)

        # Row FAS has different amp for each value
        # Other fast DACs have 1 amp for all values
        if isinstance(amp, list):
            assert len(amp) == size
            self.amps = amp
        else:
            self.amps = [amp for i in range(size)]
            
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

        for i in range(size):
            self.add(pr.LinkVariable(
                name = f'Current_[{i}]',
                guiGroup = 'Current_',
                dependencies = [self.Current],
                disp = '{:0.3f}',
                units = '\u03bcA',
                linkedGet = lambda read, x=i: self.Current.get(read=read, index=x),
                linkedSet = lambda write, value, x=i: self.Current.set(value=value, write=write, index=x)))

        for i in range(size):
            self.add(pr.LinkVariable(
                name = f'LoadVoltage_[{i}]',
                guiGroup = 'LoadVoltage_',
                dependencies = [self.Raw],
                disp = '{:0.3f}',
                units = 'mV',
                linkedGet = lambda read, x=i: 1.0e3 * self.amps[x].dacToLoadVoltage(self.Raw.get(read=read, index=x))))

        for i in range(size):
            self.add(pr.LinkVariable(
                name = f'Raw_[{i}]',
                guiGroup = 'Raw_',
                dependencies = [self.Raw],
                disp = self.Raw.disp,
                linkedGet = lambda read, x=i: self.Raw.get(read=read, index=x),
                linkedSet = lambda write, value, x=i: self.Raw.set(value=value, write=write, index=x)))
            
            

    def getCurrent(self, index, read):
        dacs = self.Raw.get(read=read, index=index)
        if index == -1:
            currents = [self.amps[i].dacToOutCurrent(dac) for i, dac in enumerate(dacs)]
            currents = np.array(currents, dtype=np.float64)
        else:
            currents = self.amps[index].dacToOutCurrent(dacs)

        return currents

    def setCurrent(self, value, index, write):
        if index == -1:
            dacs = [self.amps[i].outCurrentToDac(current) for i, current in enumerate(value)]
        else:
            dacs = self.amps[index].outCurrentToDac(value)

        self.Raw.set(index=index, write=write, value=dacs)

    def getVoltage(self, index, read):
        dacs = self.Raw.get(read=read, index=index)
        if index == -1:
            voltages = [self.amps[i].dacToOutVoltage(dac) for i, dac in enumerate(dacs)]
            voltages = np.array(voltages, dtype=np.float64)
        else:
            voltages = self.amps[index].dacToOutVoltage(dacs)

        return voltages

    def setVoltage(self, value, index, write):
        if index == -1:
            dacs = [self.amps[i].outVoltageToDac(voltage) for i, voltage in enumerate(value)]
        else:
            dacs = self.amps[index].outVoltageToDac(value)

        self.Raw.set(index=index, write=write, value=dacs)


class FastDacDriver(pr.Device):

    def __init__(self, shunt, rows, **kwargs):
        super().__init__(**kwargs)

        self.rows = rows
        
        # Create devices that hold amplifier configuration
        self.add(pr.ArrayDevice(
            name = 'AmpLoading',
            arrayClass = warm_tdm.FastDacAmplifierSE,
            number = 8,
            arrayArgs = [
                {'name': f'Amp[{i}]',
                 'defaults':  {
                     'Invert': True,
                     'ShuntR': shunt,
                     'FbR': 4.7e3}} for i in range(8)]))
        
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
                linkedGet = lambda x=col: self.AmpLoading.Amp[x].dacToOutCurrent(self.DacRawNow[x].value())))
            
        
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
                ret = self.AmpLoading.Amp[x].dacToOutCurrent(self.OverrideRaw[x].value()) 
                return ret

            def _overCurrentSet(value, index, write, x=col):
                self.OverrideRaw[x].set(self.AmpLoading.Amp[x].outCurrentToDac(value), write=write)

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
                ret = self.AmpLoading.Amp[x].dacToOutVoltage(self.OverrideRaw[x].value())
                #print(f'_overGet - OverrideRaw[{x}].value() = {self.OverrideRaw[x].value()} - voltage = {voltage}')
                return ret

            def _overVoltageSet(value, index, write, x=col):
                #print(f'Override[{x}].set()')
                self.OverrideRaw[x].set(self.AmpLoading.Amp[x].outVoltageToDac(value), write=write)

            self.add(pr.LinkVariable(
                name = f'OverrideVoltage[{col}]',
                dependencies = [self.OverrideRaw[col]],
                units = 'V',
                disp = '{:0.03f}',
                linkedGet = _overVoltageGet,
                linkedSet = _overVoltageSet))
            
        for col in range(8):

            self.add(FastDacMem(
                name = f'Column[{col}]',
                offset = col << 12,
                amp = self.AmpLoading.Amp[col],
                size = rows))
