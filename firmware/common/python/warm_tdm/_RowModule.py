import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowModule(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCommon(
            offset = 0x00000000))

        self.add(warm_tdm.Timing(
            offset = 0x00100000))

        self.add(warm_tdm.RowModuleDacs(
            offset = 0x01000000,
            enabled = True))

        self.add(warm_tdm.ComCore(
            offset = 0xA0000000))

        self.add(surf.protocols.ssi.SsiPrbsRx(
            offset = 0x00200000))
        
        self.add(surf.protocols.ssi.SsiPrbsTx(
            offset = 0x00201000))
