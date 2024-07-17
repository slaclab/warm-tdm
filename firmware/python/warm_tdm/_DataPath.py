import pyrogue as pr

import surf
import scipy
#mport surf.dsp.fixed

import warm_tdm



class DataPath(pr.Device):
    def __init__(self, frontEnd, **kwargs):
        super().__init__(**kwargs)

        for i in range(8):
            self.add(warm_tdm.AdcDsp(
                name = f'AdcDsp[{i}]',
                frontEnd = frontEnd,
                column = i,
                offset = (i+1) << 16))

        self.add(warm_tdm.WaveformCapture(
            offset = 9 << 16,
            enabled = True,))

        self.add(AdcFilters(
            enabled = False,
            offset = (10 << 16),
            numberTaps = 41))

        self.add(surf.devices.analog_devices.Ad9681Readout(
            enabled = True,
            name = 'Ad9681Readout',
            offset = 0x00000000))


class AdcFilters(pr.Device):
    def __init__(self, numberTaps, **kwargs):
        super().__init__(**kwargs)

        self.filterFreq = 62.49999e6

        for i in range(8):
            self.add(surf.dsp.fixed.FirFilterSingleChannel(
                name = f'FirFilter[{i}]',
                offset = i << 12,
                numberTaps = numberTaps,
                coeffWordBitSize = 25))

        def setFirTaps(value, write):
            self.filterFreq = value
            taps = scipy.signal.firwin(numberTaps, value, fs=125.0e6, window='hamming')
            #print(f'Applying filter at {value} with taps {taps}')
            for i in range(8):
                self.FirFilter[i].Taps.set(taps, write=write)

        self.add(pr.LinkVariable(
            name = 'FilterCuttoffFreq',
            linkedSet = setFirTaps,
            linkedGet = lambda: self.filterFreq,
            value = self.filterFreq))



        
