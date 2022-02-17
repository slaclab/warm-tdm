import pyrogue as pr

import surf
import surf.devices.analog_devices

import numpy as np

import warm_tdm

class ColumnModule(pr.Device):
    def __init__(self, waveform_stream, rows=64, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True))

        self.add(warm_tdm.DataPath(
            offset = 0xC0300000,
            expand = True,
            waveform_stream = waveform_stream))

        self.add(warm_tdm.Ad5679R(
            name = 'SaBiasDac',
            hidden = False,
            offset = 0xC0700000))

        self.add(warm_tdm.SaBiasOffset(
            dac = self.SaBiasDac))

        self.add(warm_tdm.Ad5679R(
            name = 'TesBiasDac',
            hidden = False,
            offset = 0xC0701000))

        self.add(warm_tdm.TesBias(
            dac = self.TesBiasDac))


        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Bias',
            offset = 0xC0400000,
            rows = rows))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Fb',
            offset =0xC0500000,
            rows = rows))

        self.add(warm_tdm.FastDacDriver(
            name = 'SAFb',
            offset = 0xC0600000,
            rows = rows))

        self.add(surf.devices.analog_devices.Ad9681Config(
            enabled = True,
            offset = 0xC0200000))

#         self.add(pr.RemoteVariable(
#             name = f'TestRam',
#             offset = 0xC0800000,
#             base = pr.UInt,
#             mode = 'RW',
#             bitSize = 8*2**14,
#             numValues = 1024*4,
#             valueBits = 32,
#             valueStride = 32))

#         @self.command()
#         def SetTestRam(arg):
#             print(arg)
#             offset, size = arg
# #            ram = np.linspace(0, 2**32-1, 2**13-25, endpoint=False, dtype=np.uint32)
#             ram = np.linspace(0, 2**32-1, size, endpoint=False, dtype=np.uint32)            
#             self.TestRam.set(value=ram, index=offset, write=True)


        @self.command()
        def AllFastDacs(arg):
            for v in self.SAFb.Override.values():
                v.set(value=arg, write=True)

            for v in self.SQ1Fb.Override.values():
                v.set(value=arg, write=True)

            for v in self.SQ1Bias.Override.values():
                v.set(value=arg, write=True)
                

        @self.command()
        def InitDacAdc():
            self.Ad9681Config.enable.set(True)
            self.Ad9681Config.ReadDevice()
            self.Ad9681Config.InternalPdwnMode.setDisp('Full Power Down')
            self.Ad9681Config.InternalPdwnMode.setDisp('Chip Run')
            self.Ad9681Config.InternalPdwnMode.setDisp('Digital Reset')
            self.Ad9681Config.InternalPdwnMode.setDisp('Chip Run')

            self.SaBiasDac.ZeroVoltages()
            self.TesBiasDac.ZeroVoltages()
            
