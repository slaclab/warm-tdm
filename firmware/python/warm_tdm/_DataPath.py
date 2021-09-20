import pyrogue as pr

import surf
#mport surf.dsp.fixed

import warm_tdm



class DataPath(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.devices.analog_devices.Ad9681Readout(
            enabled = True,
            offset = 0x00000000))

        for i in range(8):
            self.add(warm_tdm.AdcDsp(
                name = f'AdcDsp[{i}]',
                offset = (i+1) << 16,
                enabled = False))

#         for i in range(8):
#             self.add(surf.dsp.fixed.FirFilterSingleChannel(
#                 name = f'FirFilter[{i}]',
#                 offset = (i+1) << 8,
#                 numberTaps = 21,
#                 dataWordBitSize = 16))


        
