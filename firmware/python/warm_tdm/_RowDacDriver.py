import pyrogue as pr
import math
import numpy as np
import warm_tdm

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

        self.add(pr.RemoteVariable(
            name = 'ActivateRowIndex',
            offset = 0x10,
            bitSize = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DeactivateRowIndex',
            offset = 0x14,
            bitSize = 8,
            base = pr.UInt))
        

        self.add(pr.RemoteCommand(
            name = 'DacReset',
            offset = 0x08,
            bitSize = 1,
            function = pr.Command.touchOne))

        for i in range(max(num_chip_selects, 1)):
            self.add(warm_tdm.FastDacMem(
                name = f'RowFasOn[{i}]',
                offset = 0x1000 + (self.rs_offset * i),
                size = num_row_selects,
                amp = self.amps[0:num_row_selects]))

            self.add(warm_tdm.FastDacMem(
                name = f'RowFasOff[{i}]',
                offset = 0x2000 + (self.rs_offset * i),
                size = num_row_selects,
                amp = self.amps[0:num_row_selects]))

        if num_chip_selects > 0:
            self.add(warm_tdm.FastDacMem(
                name = 'ChipFasOn',
                offset = 0x3000,
                size = num_chip_selects,
                amp = self.amps[num_row_selects:num_row_selects+num_chip_selects]))

            self.add(warm_tdm.FastDacMem(
                name = 'ChipFasOff',
                offset = 0x4000,
                size = num_chip_selects,
                amp = self.amps[num_row_selects:num_row_selects+num_chip_selects]))
