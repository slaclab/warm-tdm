import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowFpgaBoard(pr.Device):
    def __init__(self, frontEndClass, num_wafers=1, num_row_selects=32, num_chip_selects=0, rows=256, ethPresent=True, **kwargs):
        super().__init__(**kwargs)

        self.forceCheckEach = True

        self.add(frontEndClass(
            name='AnalogFrontEnd'))

        self.add(warm_tdm.WarmTdmCore(
            name = 'WarmTdmCore',
            offset = 0x00000000,
            expand = True,
            disable_timing_tx = True,
            ethPresent = ethPresent,
            local_therm_channels = [9, 10, 1, 11, 0, 3],
            fe_therm_channels = [2, 8]))
        
        self.add(surf.protocols.ssi.SsiPrbsRx(
            enabled = False,
            hidden = True,
            offset = 0xC0200000))
        
        self.add(surf.protocols.ssi.SsiPrbsTx(
            enabled = False,
            hidden = True,
            offset = 0xC0201000))

        self.add(warm_tdm.RowDacDriver(
            name = 'RowDacDriver',
            offset = 0xC100_0000,
            frontEnd = self.AnalogFrontEnd,
            rows = rows,
            expand = True))

        @self.command()
        def ZeroFastDacs():
            # Drive every physical row-select line on this board to zero current.
            # In MANUAL mode each FasOff table write also actuates its addressed
            # physical output (the same path SetCosimTunePoints uses to leave the
            # FAS lines off), so writing all 32 FasOff entries to 0 uA zeroes the
            # outputs.  Honored only outside a timing run.  Provides a software
            # re-arm for the startup zeroing in case the one-shot firmware init
            # landed before the analog rails settled (no rail PGOOD on this board).
            driver = self.RowDacDriver
            driver.Mode.set(1, write=True)
            fasOff = driver.FasOff
            fasOff.Current.set(value=[0.0] * len(fasOff.amps), index=-1, write=True)


            
            



