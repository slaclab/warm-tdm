import pyrogue as pr

import warm_tdm

class DacMemory(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(64):
            self.add(pr.RemoteVariable(
                name = f'Row[{i}]',
                offset = i*4,
                bitSize = 16,
                mode = 'RW'))
                

                
class FastDacDriver(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(8):
            self.add(pr.MemoryDevice(
                name = f'Channel[{i}]',
                offset = i<<8,
                size = 64*4))
                
#             self.add(DacMemory(
#                 name = f'Channel[{i}]',
#                 offset = i<<8))

        @self.command()
        def RamTest():
            for i in range(8):
                self.Channel[i].set(0, [(i<<6)+j for j in range(64)], write=False)
#                for j in range(64):
#                    value = (i<<6)+j
#                    print(f'Writing {value:x} to Ch {i} Row {j}')
#                    self.Channel[i].Row[j].set(j, value, write=False)
#                    self.Channel[i].set(j, [value], write=False)

            self.writeAndVerifyBlocks()

