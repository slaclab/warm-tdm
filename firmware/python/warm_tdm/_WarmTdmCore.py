import pyrogue as pr

import warm_tdm

class WarmTdmCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCommon(
            offset = 0x00000000,
            expand = True))

        self.add(warm_tdm.Timing(
            offset = 0x00100000,
            expand = True))

        self.add(warm_tdm.ComCore(
            offset = 0xA0000000))
