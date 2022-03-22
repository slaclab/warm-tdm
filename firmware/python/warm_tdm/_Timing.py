import pyrogue as pr


import warm_tdm

class Timing(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.TimingRx(
            offset = 0x000))

#         self.add(warm_tdm.TimingTx(
#             offset = 0x100))
