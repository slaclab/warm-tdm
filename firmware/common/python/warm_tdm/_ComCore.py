import pyrogue as pr

import surf.protocols.pgp
import surf.protocols.ssi
import surf.protocols.rssi
import surf.ethernet.gige
import surf.ethernet.udp

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
        
        self.add(surf.protocols.rssi.RssiCore(
            name = "SRP RSSI",
            offset = 0x11000,
            expand = False))

        self.add(surf.protocols.rssi.RssiCore(
            name = "Data RSSI",
            offset = 0x12000,
            expand = False))
        
        self.add(surf.ethernet.udp.UdpEngine(
            offset = 0x10000,
            numSrv = 2))

        self.add(surf.ethernet.gige.GigEthGtx7(
            gtxe2_read_only = True,
            offset = 0x00000))


class ComCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.PgpCore(
            offset = 0x0000))

        self.add(warm_tdm.EthCore(
            offset = 0x00100000))
                 
