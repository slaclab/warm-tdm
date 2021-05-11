import pyrogue as pr


import warm_tdm

class TimingTx(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


#         self.add(pr.RemoteVariable(
#             name = 'EnOutput',
#             mode = 'RW',
#             offset = 0x30,
#             bitOffset = 0,
#             bitSize = 1,
#             base = pr.Bool))

        self.add(pr.RemoteCommand(
            name = 'StartRun',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 1,
            function = pr.Command.toggle))

        self.add(pr.RemoteCommand(
            name = 'EndRun',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 1,
            function = pr.Command.toggle))
        

        self.add(pr.RemoteVariable(
            name = 'RowPeriod',
            mode = 'RW',
            offset = 0x08,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'NumRows',
            mode = 'RW',
            offset = 0x0C,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'SampleStartTime',
            mode = 'RW',
            offset = 0x10,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))
        
        self.add(pr.RemoteVariable(
            name = 'SampleEndTime',
            mode = 'RW',
            offset = 0x10,
            bitOffset = 16,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'Running',
            mode = 'RO',
            offset = 0x30,
            bitOffset = 0,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'Sampling',
            mode = 'RO',
            offset = 0x30,
            bitOffset = 1,
            bitSize = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'RowNum',
            mode = 'RO',
            offset = 0x34,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'RowTime',
            mode = 'RO',
            offset = 0x38,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'RunTime',
            mode = 'RO',
            offset = 0x40,
            bitOffset = 0,
            bitSize = 64,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'ReadoutCount',
            mode = 'RO',
            offset = 0x48,
            bitOffset = 0,
            bitSize = 64,
            disp = '{:d}'))

