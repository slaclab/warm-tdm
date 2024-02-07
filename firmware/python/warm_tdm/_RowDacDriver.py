import pyrogue as pr
import math
import numpy as np
import warm_tdm

class FasMem(pr.Device):
    def __init__(self, size, amps, **kwargs):
        super().__init__(**kwargs)

        assert size == len(amps)
        
        self.amps = amps

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
#                units = 'mV',
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

class RowDacDriver(pr.Device):
    def __init__(
            self,
            num_row_selects=32,
            num_chip_selects=0,
            **kwargs):
        super().__init__(**kwargs)

        def bits(number):
            if number < 2: return 1
            return int(math.ceil(math.log2(number)))

        self.chip_addr_bits = bits(num_chip_selects)
        self.row_addr_bits = bits(num_row_selects)
        self.rs_offset = 2**(self.row_addr_bits+2) # Two extra bits for AXI addressing
#        print(f'Offset: {self.rs_offset}')

        rowBoardIdBits = 8-(self.row_addr_bits + self.chip_addr_bits)


        # Channels 0 and 1 use differential amplifier configuration
        for i in range(2):
            self.add(warm_tdm.FastDacAmplifierDiff(
                name = f'Amp[{i}]',
                guiGroup = 'Amp_',
                hidden = False))

        for i in range(2, 32):
            self.add(warm_tdm.FastDacAmplifierSE(
                name = f'Amp[{i}]',
                guiGroup = 'Amp_',
                hidden = False))

        self.amps = [self.Amp[i] for i in range(32)]

        self.add(pr.RemoteVariable(
            name = 'Mode',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            enum = {
                0: 'TIMING',
                1: 'MANUAL'}))

        if rowBoardIdBits > 0:
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

        for i in range(max(num_chip_selects, 1)):
            self.add(FasMem(
                name = f'RowFasOn[{i}]',
                offset = 0x1000 + (self.rs_offset * i),
                size = num_row_selects,
                amps = self.amps[0:num_row_selects]))

            self.add(FasMem(
                name = f'RowFasOff[{i}]',
                offset = 0x2000 + (self.rs_offset * i),
                size = num_row_selects,
                amps = self.amps[0:num_row_selects]))

        if num_chip_selects > 0:
            self.add(FasMem(
                name = 'ChipFasOn',
                offset = 0x3000,
                size = num_chip_selects,
                amps = self.amps[num_row_selects:num_row_selects+num_chip_selects]))

            self.add(FasMem(
                name = 'ChipFasOff',
                offset = 0x4000,
                size = num_chip_selects,
                amps = self.amps[num_row_selects:num_row_selects+num_chip_selects]))
