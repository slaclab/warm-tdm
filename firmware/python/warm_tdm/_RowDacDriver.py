import pyrogue as pr
import math
import numpy as np

class RowSelectAmplifierC01(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name = 'FSADJ',
            value = 2.0e3,
            units = '\u03A9'))

        self.add(pr.LinkVariable(
            name = 'IOUTFS',
            units = 'A',
            linkedGet = lambda: 1.2 / self.FSADJ.value() * 32))

        self.add(pr.LocalVariable(
            name = 'LoadR',
            value = 24.9,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'InputR',
            value = 1.0e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'FbR',
            value = 4.02e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'FilterR',
            value = 49.9 * 3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'ShuntR',
            value = 1.0e3,
            units = '\u03A9'))

        self.add(pr.LocalVariable(
            name = 'CableR',
            value = 100.0,
            units = '\u03A9'))

        self.add(pr.LinkVariable(
            name = 'Gain',
            dependencies = [self.FbR, self.InputR],
            linkedGet = self.gain))

        self.add(pr.LinkVariable(
            name = 'OutR',
            dependencies = [self.FilterR, self.ShuntR, self.CableR],
            units = '\u03A9',
            linkedGet = self.rout))

    def gain(self):
        return self.FbR.value() / self.InputR.value()

    def rout(self):
        return self.FilterR.value() + self.ShuntR.value() + self.CableR.value()

    def dacToOutVoltage(self, dac):
        iOutFs = self.IOUTFS.value()
        iOutA = (dac/16384) * iOutFs
        iOutB = ((16383-dac)/16384) * iOutFs
        dacCurrent = (iOutA, iOutB)

        gain = self.gain()
        load = self.LoadR.value()

        vin = [iOutA * load, iOutB * load]

        vout = (vin[0] - vin[1]) * gain
        return vout

    def dacToOutCurrent(self, dac):
        """ Calculate output current in uA """
        vout = self.dacToOutVoltage(dac)
        iout = vout / self.rout()
        return iout * 1e6

    def outVoltageToDac(self, voltage):
        print(f'outVoltageToDac({voltage=})')
        gain = self.gain()
        load = self.LoadR.value()
        ioutfs = self.IOUTFS.value()
        vin = voltage / gain
        iin = vin / load
        iina = (iin + ioutfs) / 2
        dac =  int((iina / ioutfs) * 16384)
        print(f'{gain=}, {load=}, {ioutfs=}, {vin=}, {iin=}, {iina=}, {dac=}')
        return int(dac)

    def outCurrentToDac(self, current):
        vout = current * 1e-6 * self.rout()
        return self.outVoltageToDac(vout)


class RowSelectDiffAmplifierC01(RowSelectAmplifierC01):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def gain(self):
        return 2 * self.FbR.value() / self.InputR.value()

    def rout(self):
        return (2 * self.FilterR.value()) + (2 * self.ShuntR.value()) + self.CableR.value()

class FasMem(pr.Device):
    def __init__(self, num_selects, amps, **kwargs):
        super().__init__(**kwargs)

        self.amps = amps

        self.add(pr.RemoteVariable(
            name = f'Raw',
            offset = kwargs['offset'],
            base = pr.UInt,
#            bitSize = num_row_selects * 32,
            numValues = num_selects,
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
            currents = [self.amps[i].dacToOutCurrent(dac) for i, dac in enumerate(dacs)]
            currents = np.array(currents, dtype=np.float64)
        else:
            currents = self.amps[index].outCurrentToDac(dac)

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
            voltages = self.amps[index].outVoltageToDac(dacs)

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
#             if number == 0 or number == 1:
#                 return number
#             else:
#                 l2 = math.log2(number)
#                 if math.ceil(l2) == math.floor(l2):
#                     l2 = l2 + 1
#                 return int(math.ceil(l2))

        self.chip_addr_bits = bits(num_chip_selects)
        self.row_addr_bits = bits(num_row_selects)
        self.rs_offset = 2**(self.row_addr_bits+2) # Two extra bits for AXI addressing
        print(f'Offset: {self.rs_offset}')

        rowBoardIdBits = 8-(self.row_addr_bits + self.chip_addr_bits)



        # Channels 0 and 1 use differential amplifier configuration
        for i in range(2):
            self.add(RowSelectDiffAmplifierC01(
                name = f'Amp[{i}]',
                hidden = True))

        for i in range(2, 32):
            self.add(RowSelectAmplifierC01(
                name = f'Amp[{i}]',
                hidden = True))

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
                num_selects = num_row_selects,
                amps = self.amps[0:num_row_selects]))

            self.add(FasMem(
                name = f'RowFasOff[{i}]',
                offset = 0x2000 + (self.rs_offset * i),
                num_selects = num_row_selects,
                amps = self.amps[0:num_row_selects]))

        if num_chip_selects > 0:
            self.add(FasMem(
                name = 'ChipFasOn',
                offset = 0x3000,
                num_selects = num_chip_selects,
                amps = self.amps[num_row_selects:num_row_selects+num_chip_selects]))

            self.add(FasMem(
                name = 'ChipFasOff',
                offset = 0x4000,
                num_selects = num_chip_selects,
                amps = self.amps[num_row_selects:num_row_selects+num_chip_selects]))
