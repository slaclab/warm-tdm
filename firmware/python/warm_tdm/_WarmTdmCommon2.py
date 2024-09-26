import pyrogue as pr

import surf.axi
import surf.xilinx
import surf.devices.micron
import surf.devices.microchip
import surf.devices.nxp
import surf.devices.linear
import surf.devices.transceivers

import warm_tdm

class WarmTdmCommon2(pr.Device):
    def __init__(self, therm_channels, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.axi.AxiVersion(
            offset = 0x0000))

        print(f'Creating XADC with channels = {therm_channels}')
        self.add(surf.xilinx.Xadc(
            enabled = False,
            offset = 0x00001000,
            groups = ['NoConfig'],
            auxChannels = therm_channels))

        self.add(surf.devices.micron.AxiMicronN25Q(
            enabled = False,
            groups = ['NoConfig'],
            offset = 0x00002000))


        self.add(surf.devices.linear.Ltc4151(
            name = 'Ltc4151_Digital',
            enabled = False,
            groups = ['NoConfig'],
            senseRes = 0.02,
            offset = 0x0003000))

        self.add(surf.devices.linear.Ltc4151(
            name = 'Ltc4151_Analog',
            enabled = False,
            groups = ['NoConfig'],
            senseRes = 0.02,
            offset = 0x0003400)) # Check this

        # Amp Powerdown at 0x4000

        self.add(surf.devices.nxp.Sa56004x(
            enabled = False,
            groups = ['NoConfig'],
            offset = 0x140000))
        

        self.add(surf.devices.microchip.Axi24LC64FT(
            enabled = False,
            groups = ['NoConfig'],
            offset = 0x100000))

        self.add(surf.devices.transceivers.Sfp(
            name = 'SFP0',
            enabled = False,
            offset = 0x5000))

        self.add(surf.devices.transceivers.Sfp(
            name = 'SFP1',
            enabled = False,
            offset = 0x6000))
        

        self.add(warm_tdm.BoardTemp(
            xadc = self.Xadc,
            therm_channels = therm_channels,
            sa56004x = self.Sa56004x))
