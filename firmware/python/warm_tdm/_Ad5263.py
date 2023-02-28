import pyrogue as pr

class Ad5263(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(4):
            self.add(pr.RemoteVariable(
                name = f'RDAC{i+1}',
                offset = i*4 << 5,
                bitOffset = 0,
                bitSize = 8,
                disp = '{:d}'))
