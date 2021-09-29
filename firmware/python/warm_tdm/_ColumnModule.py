import pyrogue as pr

import surf
import surf.devices.analog_devices

import warm_tdm

class ColumnModule(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True))

        self.add(warm_tdm.DataPath(
            offset = 0xC0300000,
            expand = True))

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
            name = 'SQ1Bais',
            offset = 0xC0400000))
            
        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1Fb',
            offset =0xC0500000))
        
        self.add(warm_tdm.FastDacDriver(
            name = 'SAFb',
            offset = 0xC0600000))
            
        self.add(surf.devices.analog_devices.Ad9681Config(
            enabled = True,
            offset = 0xC0200000))
