import pyrogue as pr

import warm_tdm

class WarmTdmCore(pr.Device):
    def __init__(self, therm_channels, disable_timing_tx=False, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCommon(
            offset = 0x00000000,
            expand = True,
            therm_channels=therm_channels))

        self.add(warm_tdm.Timing(
            offset = 0x00100000,
            disable_tx = disable_timing_tx,
            expand = True))

        self.add(warm_tdm.ComCore(
            offset = 0xA0000000,
            expand = True))
