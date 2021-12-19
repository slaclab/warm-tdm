import pyrogue as pr

import surf
import surf.protocols.ssi

import warm_tdm

class RowModule(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.WarmTdmCore(
            offset = 0x00000000,
            expand = True))
        
        self.add(warm_tdm.RowModuleDacs(
            offset = 0xC1000000,
            expand = True,
            enabled = True))

        self.add(surf.protocols.ssi.SsiPrbsRx(
            hidden = True,
            offset = 0xC0200000))
        
        self.add(surf.protocols.ssi.SsiPrbsTx(
            hidden = True,
            offset = 0xC0201000))

        self.add(warm_tdm.RowSelectArray(rowModule=self))

        @self.command()
        def Run():
            for i, dac in self.RowModuleDacs.Ad9106.items():
                dac.RUN.set(1, write=True)
            self.WarmTdmCore.Timing.TimingTx.StartRun()

        @self.command()
        def Stop():
            self.WarmTdmCore.Timing.TimingTx.EndRun()            
            for i, dac in self.RowModuleDacs.Ad9106.items():
                dac.RUN.set(0, write=True)

