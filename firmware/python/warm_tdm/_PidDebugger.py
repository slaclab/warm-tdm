import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np

class PidDebugger(pr.DataReceiver):

    def __init__(self, col, fastDacDriver, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()
        
        super().__init__(memBase=self.mem, **kwargs)

        self.add(pr.RemoteVariable(
            name = 'Column',
            mode = 'RO',
            offset = 0x00,
            base = pr.UInt,
            bitSize = 3))

        self.add(pr.RemoteVariable(
            name = 'AccumError',
            mode = 'RO',
            offset = 0x08*2,
            base = pr.Fixed(22, 0),
            bitSize = 22))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            mode = 'RO',
            offset = 0x10*2,
            base = pr.Fixed(22, 0),
            bitSize = 22))


        self.add(pr.RemoteVariable(
            name = 'Diff',
            mode = 'RO',
            offset = 0x14*2,
            base = pr.Fixed(22, 0),
            bitSize = 22))


        self.add(pr.RemoteVariable(
            name = 'PidResult',
            mode = 'RO',
            offset = 0x18*2,
            base = pr.Fixed(40, 17),
            bitSize = 40))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPreRaw',
            mode = 'RO',
            offset = 0x0C*2,
            base = pr.UInt,
            bitSize = 14))

        self.add(pr.LinkVariable(
            name = 'Sq1FbPre',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            dependencies = [self.Sq1FbPreRaw, self.Column],
            linkedGet = lambda: fastDacDriver._dacToSquidCurrent(self.Sq1FbPreRaw.value(), col)))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPostRaw',
            mode = 'RO',
            offset = 0x1C*2,
            base = pr.UInt,
            bitSize = 14))

        self.add(pr.LinkVariable(
            name = 'Sq1FbPost',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            dependencies = [self.Sq1FbPostRaw, self.Column],
            linkedGet = lambda: fastDacDriver._dacToSquidCurrent(self.Sq1FbPostRaw.value(), col)))
        

    def process(self, frame):
        channel = frame.getChannel()
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)

        # Overwrite the MemEmulate data with new frame
        for i, byte in enumerate(raw):
            self.mem._data[i] = byte

        self.readBlocks()
        self.checkBlocks()
        
