import pyrogue as pr
import math
import numpy as np
import warm_tdm

class RowDacDriver2(pr.Device):
    def __init__(
            self,
            frontEnd,
            **kwargs):
        super().__init__(**kwargs)

        self._frontEnd = frontEnd
        self.amps = [self._frontEnd.Amp[i] for i in range(32)]

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
            bitSize = 2,
            base = pr.UInt))

        self.add(pr.RemoteCommand(
            name = 'DacReset',
            offset = 0x08,
            bitSize = 1,
            function = pr.Command.touchOne))

        self.add(pr.RemoteVariable(
            name = 'ActivateRowIndex',
            offset = 0x10,
            bitSize = 8,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'DeActivateRowIndex',
            offset = 0x14,
            bitSize = 8,
            base = pr.UInt,
            disp = '{:d}'))
        

        self.add(pr.RemoteVariable(
            name = 'RowMap',
            offset = 0x1000,
            base = pr.UInt,
            numValues = 256,
            valueBits = 16,
            valueStride = 32))

        self.add(warm_tdm.FastDacMem(
            name = f'FasOn',
            offset = 0x4000,
            size = 32,
            amp = self.amps[0:32]))

        self.add(warm_tdm.FastDacMem(
            name = f'FasOff',
            offset = 0x5000,
            size = 32,
            amp = self.amps[0:32]))


