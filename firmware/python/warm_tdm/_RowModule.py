import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowModule(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True,
            therm_channels = [3, 11, 4, 12))
        
        self.add(surf.protocols.ssi.SsiPrbsRx(
            hidden = True,
            offset = 0xC0200000))
        
        self.add(surf.protocols.ssi.SsiPrbsTx(
            hidden = True,
            offset = 0xC0201000))

        self.add(warm_tdm.RowDacDriver(
            offset = 0xC100_0000,
            num_row_selects = 32,
            num_chip_selects = 0,
            expand = True))



