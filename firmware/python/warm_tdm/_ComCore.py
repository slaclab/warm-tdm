import pyrogue as pr

import surf.protocols.pgp
import surf.protocols.ssi
import surf.protocols.rssi
import surf.protocols.batcher
import surf.ethernet.gige
import surf.ethernet.udp

import warm_tdm

class PgpCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.protocols.pgp.Pgp2bAxi(
            name = 'Pgp2bAxi[0]',
            writeEn = False,            
            offset=0x00000000,
            errorCountBits=16))

        #GTX
        self.add(surf.xilinx.Gtxe2Channel(
            name = 'Gtxe2Channel[0]',
            enabled = False,
            hidden = True,
            groups = ['NoConfig'],            
            offset = 0x0001000))

#         self.add(surf.protocols.pgp.Pgp2bAxi(
#             name = 'Pgp2bAxi[1]',
#             offset=0x00002000,
#             writeEn = False,
#             errorCountBits=16))

#         #GTX
#         self.add(surf.xilinx.Gtxe2Channel(
#             name = 'Gtxe2Channel[1]',
#             enabled = False,
#             hidden = True,
#             offset = 0x0003000))
        

class EthCore(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.add(surf.protocols.rssi.RssiCore(
            enabled = False,
            name = "SRP_RSSI",
            groups = ['NoConfig'],
            offset = 0x11000,
            expand = False))

        self.add(surf.protocols.rssi.RssiCore(
            enabled = False,
            name = "Data_RSSI",
            groups = ['NoConfig'],            
            offset = 0x12000,
            expand = False))
        
        self.add(surf.ethernet.udp.UdpEngine(
            enabled = False,
            offset = 0x10000,
            groups = ['NoConfig'],            
            numSrv = 2))

        self.add(surf.ethernet.gige.GigEthGtx7(
            enabled = False,
            gtxe2_read_only = True,
            groups = ['NoConfig'],            
            offset = 0x00000))

        self.add(surf.protocols.batcher.AxiStreamBatcherAxil(
            offset = 0x13000))


class ComCore(pr.Device):
    def __init__(self, ethPresent=True, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.PgpCore(
            enabled = False,
            offset = 0x0000))

        # The RTL generates the Ethernet register block only for ring address
        # zero (the coordinator); on other boards the AXI-Lite window is absent
        # and returns DECERR. Mirror that here by not instantiating the EthCore
        # subtree at all on non-coordinators, so the host tree never issues
        # transactions to registers that do not exist.
        if ethPresent:
            self.add(warm_tdm.EthCore(
                offset = 0x00100000))
                 
