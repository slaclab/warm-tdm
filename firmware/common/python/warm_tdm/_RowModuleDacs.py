import pyrogue as pr

import warm_tdm

class RowModuleDacs(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        for i in range(12):
            self.add(warm_tdm.Ad9106(
                offset = i * 0x100000))
