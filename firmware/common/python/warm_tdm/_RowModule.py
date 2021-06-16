import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowModule(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True))
        
        self.add(warm_tdm.RowModuleDacs(
            offset = 0xC1000000,
            enabled = False))

        self.add(surf.protocols.ssi.SsiPrbsRx(
            offset = 0xC0200000))
        
        self.add(surf.protocols.ssi.SsiPrbsTx(
            offset = 0xC0201000))
