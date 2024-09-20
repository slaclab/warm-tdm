import pyrogue as pr

import warm_tdm

class WarmTdmCore2(pr.Device):
    def __init__(self, therm_channels, disable_timing_tx=False, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCommon2(
            offset = 0x00000000,
            expand = True,
            therm_channels=therm_channels))

        self.add(warm_tdm.Timing(
            offset = 0x01000000,
            disable_tx = disable_timing_tx,
            expand = True))

        self.add(warm_tdm.ComCore(
            offset = 0xA0000000,
            expand = True))
