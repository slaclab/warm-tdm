import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowFpgaBoard(pr.Device):
    def __init__(self, frontEndClass, num_row_selects=32, num_chip_selects=0, **kwargs):
        super().__init__(**kwargs)

        self.forceCheckEach = True

        self.add(frontEndClass(
            name='AnalogFrontEnd'))

        self.add(warm_tdm.WarmTdmCore2(
            name = 'WarmTdmCore',
            offset = 0x00000000,
            expand = True,
            disable_timing_tx = True,
            local_therm_channels = [9, 10, 1, 11, 0, 3],
            fe_therm_channels = [2, 8]))
        
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
            frontEnd = self.AnalogFrontEnd,
            num_row_selects = num_row_selects,
            num_chip_selects = num_chip_selects,
            expand = True))



