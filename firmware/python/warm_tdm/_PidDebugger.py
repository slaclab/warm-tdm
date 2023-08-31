import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np

class PidDebugger(pr.DataReceiver):

    def __init__(self, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()
        
        super().__init__(memBase=self.mem, **kwargs)

        self.add(pr.RemoteVariable(
            name = 'Column',
            offset = 0x00,
            base = pr.UInt,
            bitSize = 3))

        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x08,
            base = pr.Fixed(22, 0),
            bitSize = 22))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x10,
            base = pr.Fixed(22, 0),
            bitSize = 22))


        self.add(pr.RemoteVariable(
            name = 'Diff',
            offset = 0x14,
            base = pr.Fixed(22, 0),
            bitSize = 22))


        self.add(pr.RemoteVariable(
            name = 'PidResult',
            offset = 0x18,
            base = pr.Fixed(32, 8),
            bitSize = 32))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPre',
            offset = 0x0C,
            base = pr.Int,
            bitSize = 14))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPost',
            offset = 0x1C,
            base = pr.Int,
            bitSize = 14))

    def process(self, frame):
        channel = frame.getChannel()
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)

        print(f'Got PID Debug Frame of {fl} bytes for column {channel}')

        # Overwrite the MemEmulate data with new frame
        for i, byte in enumerate(raw):
            self.mem._data[i] = byte

        self.readBlocks()
        self.checkBlocks()
        
        print(raw)
