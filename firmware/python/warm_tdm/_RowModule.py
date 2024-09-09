import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowModule(pr.Device):
    def __init__(self, num_row_selects=32, num_chip_selects=0, **kwargs):
        super().__init__(**kwargs)

        self.forceCheckEach = True

        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True,
            disable_timing_tx = True,
            therm_channels = [3, 11, 4, 12]))
        
        self.add(surf.protocols.ssi.SsiPrbsRx(
            enabled = False,
            hidden = True,
            offset = 0xC0200000))
        
        self.add(surf.protocols.ssi.SsiPrbsTx(
            enabled = False,
            hidden = True,
            offset = 0xC0201000))

        self.add(warm_tdm.RowDacDriver(
            offset = 0xC100_0000,
            num_row_selects = num_row_selects,
            num_chip_selects = num_chip_selects,
            expand = True))



