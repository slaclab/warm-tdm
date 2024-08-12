import pyrogue as pr


import warm_tdm

class Timing(pr.Device):
    def __init__(self, disable_tx=False, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.TimingRx(
            offset = 0x00000))

        self.add(warm_tdm.TimingTx(
            enabled = not disable_tx,
            offset = 0x10000))
