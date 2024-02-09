import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np

# class PidRowDebugger(pr.Device):
#     def __init__(self, row, **kwargs):
        

class PidDebugger(pr.DataReceiver):

    def __init__(self, col, fastDacDriver, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()
        
        super().__init__(memBase=self.mem, **kwargs)

        self.add(pr.RemoteVariable(
            name = 'Column',
            mode = 'RO',
            offset = 0 * 8,
            base = pr.UInt,
            bitSize = 3))

        self.add(pr.RemoteVariable(
            name = 'RowIndex',
            mode = 'RO',
            offset = 0,
            base = pr.UInt,
            bitOffset = 8,
            bitSize = 8))

        self.add(pr.RemoteVariable(
            name = 'AccumError',
            mode = 'RO',
            offset = 2 * 8,
            base = pr.Fixed(22, 0),
            bitSize = 22))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            mode = 'RO',
            offset = 4 * 8,
            base = pr.Fixed(22, 0),
            bitSize = 22))


        self.add(pr.RemoteVariable(
            name = 'Diff',
            mode = 'RO',
            offset = 5 * 8,
            base = pr.Fixed(22, 0),
            bitSize = 22))


        self.add(pr.RemoteVariable(
            name = 'PidResult',
            mode = 'RO',
            offset = 6 * 8,
            disp = '{:0.03f}',            
            base = pr.Fixed(40, 17),
            bitSize = 40))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPreRaw',
            mode = 'RO',
            offset = 3 * 8,
            base = pr.UInt,
            bitSize = 14))

        self.add(pr.LinkVariable(
            name = 'Sq1FbPre',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            dependencies = [self.Sq1FbPreRaw, self.Column],
            linkedGet = lambda: fastDacDriver.AmpLoading.Amp[self.Column.value()].dacToOutCurrent(self.Sq1FbPreRaw.value())))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPostRaw',
            mode = 'RO',
            offset = 8 * 8,
            base = pr.UInt,
            bitSize = 14))

        self.add(pr.LinkVariable(
            name = 'Sq1FbPost',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            dependencies = [self.Sq1FbPostRaw, self.Column],
            linkedGet = lambda: fastDacDriver.AmpLoading.Amp[self.Column.value()].dacToOutCurrent(self.Sq1FbPostRaw.value())))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps',
            mode = 'RO',
            offset = 7 * 8,
            base = pr.Int,
            bitSize = 8,
            bitOffset = 0))
        

    def process(self, frame):
        channel = frame.getChannel()
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)

        if raw[1] == self.row:
            # Overwrite the MemEmulate data with new frame
            for i, byte in enumerate(raw):
                self.mem._data[i] = byte

            self.readBlocks()
            self.checkBlocks()
        
