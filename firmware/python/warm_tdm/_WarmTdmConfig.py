import pyrogue as pr

import warm_tdm

class WarmTdmConfig(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name = 'AnaPwrEn',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'AnaPwrStatus',
            mode = 'RO',
            offset = 0x00,
            bitOffset = 1,
            bitSize = 1,
            enum = {
                0: 'Disabled',
                1: 'Enabled'}))

        self.add(pr.RemoteVariable(
            name = 'TempAlert',
            mode = 'RO',
            offset = 0x18,
            bitOffset = 0,
            bitSize = 1,
            enum = {
                0: 'True',
                1: 'False'}))

        self.add(pr.RemoteVariable(
            name = 'LedEn',
            mode = 'RW',
            offset = 0x14,
            bitOffset = 0,
            bitSize = 1,
            enum = {
                0: 'Disabled',
                1: 'Enabled'}))
        

        self.add(pr.RemoteVariable(
            name = 'AsicReset',
            offset = 0x20,
            bitOffset = 0,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'AdcFilterEn',
            offset = 0x24,
            bitSize = 8,
            base = pr.UInt,
            disp = '{:08b}'))

        # Software-assigned Group id stamped into the self-describing data-frame
        # header (header byte 2). 0 until the multi-Group model is defined
        # (issue #80); the register exists now so the meaning can be assigned
        # later without a firmware change.
        self.add(pr.RemoteVariable(
            name = 'GroupId',
            offset = 0x28,
            bitSize = 8,
            base = pr.UInt))

        # Read-only: the PGP ring address this board discovered at link-up (the
        # frame-header boardId). Software has no other view of it.
        self.add(pr.RemoteVariable(
            name = 'BoardId',
            mode = 'RO',
            offset = 0x2C,
            bitSize = 3,
            base = pr.UInt))
