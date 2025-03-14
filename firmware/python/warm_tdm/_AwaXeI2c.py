import pyrogue as pr
from functools import partial

class AwaXeI2c(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        def _dacToCurrent(dac, scale):
            """ Convert DAC value to current in uA """
            return (1e6) * scale * dac/(2**8-1)

        def _currentToDac(current, scale):
            """ Convert current in uA to DAC units """
            return (current/(scale * 1e6)) * (2**8-1)

        def _getCurrent(var, read, scale):
            return _dacToCurrent(var.dependencies[0].get(read=read), scale)

        def _setCurrent(var, value, write, scale):
            var.dependencies[0].set(value=_currentToDac(value, scale), write=write)

        for col in range(2):

            self.add(pr.RemoteVariable(
                name = f'Ch{col}Dac1800Raw',
                offset = col * 0x10,
                bitOffset = 0,
                bitSize = 8,
                base = pr.UInt))
            
            print('Raw', self.find(name=f'Ch{col}Dac1800Raw'))
            
            self.add(pr.LinkVariable(
                name = f'Ch{col}Dac1800',
                dependencies = self.find(name=f'Ch{col}Dac1800Raw'),
                units = u'\u03bcA',
                disp = '{:0.03f}',
                linkedGet = partial(_getCurrent, scale=1.8e-3),
                linkedSet = partial(_setCurrent, scale=1.8e-3)))

            for pos, dac in enumerate(['A', 'B', 'C', 'D']):

                varName = f'Ch{col}Dac300{dac}'
                varNameRaw = f'Ch{col}Dac300{dac}Raw'

                self.add(pr.RemoteVariable(
                    name = varNameRaw,
                    offset = 0x20 + (0x10 * col) + (0x4 * pos),
                    bitOffset = 0,
                    bitSize = 8,
                    base = pr.UInt))

                print('Raw', self.find(name=varNameRaw))                

                self.add(pr.LinkVariable(
                    name = varName,
                    dependencies = self.find(name=varNameRaw),
                    units = u'\u03bcA',
                    disp = '{:0.03f}',
                    linkedGet = partial(_getCurrent, scale=300e-6),
                    linkedSet = partial(_setCurrent, scale=300e-6)))
