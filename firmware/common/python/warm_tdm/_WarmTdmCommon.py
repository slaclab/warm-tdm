import pyrogue as pr

import surf.axi
import surf.xilinx
import surf.devices.micron
import surf.devices.microchip

import warm_tdm

class WarmTdmCommon(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.axi.AxiVersion(
            offset = 0x0000))

        self.add(surf.xilinx.Xadc(
            offset = 0x00001000,
            auxChannels = [0, 1, 8, 9]))

        self.add(surf.devices.micron.AxiMicronN25Q(
            offset = 0x00002000))

        self.add(surf.devices.nxp.Sa56004x(
            offset = 0x00010000))

        self.add(surf.devices.microchip.Axi24LC64FT(
            offset = 0x00020000))
