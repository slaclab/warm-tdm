import pyrogue as pr

import surf.axi
import surf.xilinx
import surf.devices.micron
import surf.devices.microchip
import surf.devices.nxp

import warm_tdm

class WarmTdmCommon(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.axi.AxiVersion(
            offset = 0x0000))

        self.add(surf.xilinx.Xadc(
            enabled = False,
            offset = 0x00001000,
            auxChannels = [0, 1, 8, 9]))

        self.add(surf.devices.micron.AxiMicronN25Q(
            enabled = False,
            offset = 0x00002000))

        self.add(surf.devices.nxp.Sa56004x(
            enabled = False,
            offset = 0x00010000))

        self.add(surf.devices.microchip.Axi24LC64FT(
            enabled = False,
            offset = 0x00080000))

        self.add(warm_tdm.Ad5263(
            enabled = False,
            offset = 0x000C0000))
