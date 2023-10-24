import pyrogue as pr

import surf.axi
import surf.xilinx
import surf.devices.micron
import surf.devices.microchip
import surf.devices.nxp
import surf.devices.linear

import warm_tdm

class WarmTdmCommon(pr.Device):
    def __init__(self, therm_channels, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.axi.AxiVersion(
            offset = 0x0000))

        self.add(surf.xilinx.Xadc(
            enabled = False,
            offset = 0x00001000,
            auxChannels = therm_channels))

        self.add(surf.devices.micron.AxiMicronN25Q(
            enabled = False,
            offset = 0x00002000))

        self.add(surf.devices.nxp.Sa56004x(
            enabled = False,
            offset = 0x00010000))

        self.add(surf.devices.linear.Ltc4151(
            name = 'Ltc4151_Digital',
            enabled = False,
            senseRes = 0.02,
            offset = 0x00010400))

        self.add(surf.devices.linear.Ltc4151(
            name = 'Ltc4151_Analog',
            enabled = False,
            senseRes = 0.02,            
            offset = 0x00010800))
        
        self.add(surf.devices.microchip.Axi24LC64FT(
            enabled = False,
            offset = 0x00080000))

        self.add(warm_tdm.Ad5263(
            enabled = False,
            hidden = True,
            offset = 0x000C0000))

        self.add(warm_tdm.BoardTemp(
            xadc = self.Xadc,
            sa56004x = self.Sa56004x))
