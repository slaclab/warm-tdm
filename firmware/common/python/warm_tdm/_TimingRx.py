import pyrogue as pr


import warm_tdm

class TimingRx(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name = "RxClockFrequencyRaw",
            mode = 'RO',
            offset = 0x30,
            bitOffset = 0,
            bitSize = 32,
            hidden = True))

        self.add(pr.LinkVariable(
            name = "RxClockFrequency",
            mode = "RO",
            disp = '{:0.2f}',
            units = 'MHz',
            dependencies = [self.RxClockFrequencyRaw],
            linkedGet = lambda: self.RxClockFrequencyRaw.value()*1.0E-6))

        self.add(pr.RemoteVariable(
            name = 'UserDelay',
            mode = 'RW',
            offset = 0x00,
            bitOffset = 0,
            bitSize = 5,
            disp = '{:d}')) # need to hit bit 5 to load

        self.add(pr.RemoteVariable(
            name = 'AlignerDelay',
            mode = 'RO',
            offset = 0x00,
            bitOffset = 8,
            bitSize = 5,
            disp = '{:d}'))

        self.add(pr.RemoteCommand(
            name = 'RealignGearbox',
            offset = 0x04,
            bitOffset = 0,
            bitSize = 1,
            function = pr.RemoteCommand.toggle))

        self.add(pr.RemoteVariable(
            name = 'LockedFallCount',
            mode = 'RO',
            offset = 0x10,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'LockedSync',
            mode = 'RO',
            offset = 0x10,
            bitOffset = 16,
            bitSize = 1,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'ErrorDetCount',
            mode = 'RO',
            offset = 0x14,
            bitOffset = 0,
            bitSize = 16,
            disp = '{:d}'))

        self.add(pr.RemoteCommand(
            name = 'ResetErrorCounts',
            offset = 0x1C,
            bitOffset = 0,
            bitSize = 1,
            function = pr.RemoteCommand.toggle))
            
        self.add(pr.RemoteVariable(
            name = 'ReadoutDebug0',
            mode = 'RO',
            disp = '{:010b}',
            offset = 0x20,
            bitOffset = 0,
            bitSize = 10))

        self.add(pr.RemoteVariable(
            name = 'ReadoutDebug1',
            mode = 'RO',
            disp = '{:010b}',            
            offset = 0x20,
            bitOffset = 10,
            bitSize = 10))

        self.add(pr.RemoteVariable(
            name = 'ReadoutDebug2',
            mode = 'RO',
            disp = '{:010b}',            
            offset = 0x20,
            bitOffset = 20,
            bitSize = 10))

        self.add(pr.RemoteVariable(
            name = 'MinEyeWidth',
            mode = 'RW',
            offset = 0x40,
            bitOffset = 0,
            bitSize = 8))

        @self.command()
        def ReadDebug():
            for x in range(5000):
                value = self.ReadoutDebug0.get(read=True)
                if value != 0x17c and value != 0x283:
                    print(f'Bad value: {value:x}')

        
