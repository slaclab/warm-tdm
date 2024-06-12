import pyrogue as pr


import warm_tdm

class Timing(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.TimingRx(
            offset = 0x00000))

        self.add(warm_tdm.TimingTx(
            offset = 0x10000))
