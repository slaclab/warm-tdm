import pyrogue as pr

import surf
import scipy
#mport surf.dsp.fixed

import warm_tdm



class DataPath(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(surf.devices.analog_devices.Ad9681Readout(
            enabled = True,
            name = 'Ad9681Readout',
            offset = 0x00000000))

        for i in range(8):
            self.add(warm_tdm.AdcDsp(
                name = f'AdcDsp[{i}]',
                offset = (i+1) << 16,
                enabled = False))

        self.add(warm_tdm.WaveformCapture(
            offset = 9 << 16,
            enabled = True))

        self.add(AdcFilters(
            offset = (10 << 16),
            numberTaps = 127))

class AdcFilters(pr.Device):
    def __init__(self, numberTaps, **kwargs):
        super().__init__(**kwargs)

        for i in range(8):
            self.add(surf.dsp.fixed.FirFilterSingleChannel(
                name = f'FirFilter[{i}]',
                offset = i << 12,
                numberTaps = numberTaps,
                dataWordBitSize = 16))

        def setFirTaps(value, write):
            taps = scipy.signal.firwin(numberTaps, value, fs=125.0e6, window='hamming')
            print(f'Applying filter at {value} with taps {taps}')
            for i in range(8):
                self.FirFilter[i].Taps.set(taps, write=write)

        self.add(pr.LinkVariable(
            name = 'FilterCuttoffFreq',
            linkedSet = setFirTaps,
            value = 10.0e6))



        
