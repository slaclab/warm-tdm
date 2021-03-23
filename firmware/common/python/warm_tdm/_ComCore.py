import pyrogue as pr

import surf.protocols.pgp
import surf.protocols.ssi

import warm_tdm

class PgpCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.protocols.pgp.Pgp2bAxi(
            offset=0x00000000))

        #GTX

class EthCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ComCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.PgpCore(
            offset = 0x0000))

        self.add(warm_tdm.EthCore(
            offset = 0x00100000))
                 
