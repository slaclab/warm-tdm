import pyrogue as pr

import surf
import surf.devices.analog_devices

import warm_tdm

class ColumnModule(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCommon(
            offset = 0x00000000))

        self.add(warm_tdm.Timing(
            offset = 0x00100000))

        self.add(warm_tdm.ComCore(
            offset = 0xA0000000))

        self.add(warm_tdm.DataPath(
            offset = 0x00300000))

        self.add(warm_tdm.Ad5679R(
            name = 'SaBiasDac',
            offset = 0x00700000))
        
        self.add(warm_tdm.Ad5679R(
            name = 'TesBiasDac',
            offset = 0x00701000))

        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1BaisDac',
            offset = 0x00400000))
            
        self.add(warm_tdm.FastDacDriver(
            name = 'SQ1FbDac',
            offset =0x00500000))
        
        self.add(warm_tdm.FastDacDriver(
            name = 'SAFbDac',
            offset = 0x00600000))

        
            
        self.add(surf.devices.analog_devices.Ad9681Config(
            offset = 0x00200000))
