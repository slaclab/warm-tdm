import pyrogue as pr

import surf
import scipy
#mport surf.dsp.fixed

import warm_tdm



class DataPath(pr.Device):
    def __init__(self, timingTx, frontEnd, rows, **kwargs):
        super().__init__(**kwargs)

        for i in range(8):
            self.add(warm_tdm.AdcDsp(
                name = f'AdcDsp[{i}]',
                frontEnd = frontEnd,
                rows = rows,
                column = i,
                offset = (4 << 20) + (i << 16)))

        self.add(DownsampleFilters(
            offset = (5 << 20),
            timingTx = timingTx))

        self.add(warm_tdm.WaveformCapture(
            offset = 1 << 20,
            enabled = True,))

        self.add(AdcFilters(
            enabled = False,
            offset = (3 << 20),
            numberTaps = 61))

        self.add(EventBuilder(
            offset = 2 << 20))

        self.add(surf.devices.analog_devices.Ad9681Readout(
            enabled = True,
            name = 'Ad9681Readout',
            offset = 0x00000000))

class EventBuilder(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name = 'DaqReadoutCount',
            offset = 0,
            mode = 'RO',
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'RssCount',
            offset = 0x4,
            mode = 'RO',
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'BurnCount',
            offset = 0x8,
            mode = 'RO',
            bitSize = 32,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'DoneCols',
            offset = 0xC,
            mode = 'RO',
            bitSize = 8))
        

class AdcFilters(pr.Device):
    def __init__(self, numberTaps, **kwargs):
        super().__init__(**kwargs)

        self.filterFreq = 62.499999999e6

        for i in range(8):
            self.add(surf.dsp.fixed.FirFilterSingleChannel(
                name = f'FirFilter[{i}]',
                offset = i << 12,
                numberTaps = numberTaps,
                coeffWordBitSize = 25))

        def setFirTaps(value, write):
            self.filterFreq = value
            taps = scipy.signal.firwin(numberTaps, value, fs=125.0e6, window='hamming')
            print(f'Applying filter at {value} with taps {taps}')
            for i in range(8):
                self.FirFilter[i].Taps.set(taps, write=write)

        def _get(read):
            return self.filterFreq

        self.add(pr.LinkVariable(
            name = 'FilterCuttoffFreq',
            dependencies = [self.FirFilter[x].Taps for x in range(8)],
            linkedSet = setFirTaps,
            linkedGet = _get))

class BiquadFilterCoeffs(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.add(pr.RemoteVariable(
            name = f'B0',
            base = pr.Fixed(25, 23),
            bitSize = 25,
            offset = 0))

        self.add(pr.RemoteVariable(
            name = f'B1',
            base = pr.Fixed(25, 23),
            bitSize = 25,
            offset = 4))

        self.add(pr.RemoteVariable(
            name = f'B2',
            base = pr.Fixed(25, 23),
            bitSize = 25,
            offset = 8))

        self.add(pr.RemoteVariable(
            name = f'A1',
            base = pr.Fixed(25, 23),
            bitSize = 25,
            offset = 12))

        self.add(pr.RemoteVariable(
            name = f'A2',
            base = pr.Fixed(25, 23),
            bitSize = 25,
            offset = 16))


class BiquadFilter(pr.Device):
    def __init__(self, cascade=2, **kwargs):
        super().__init__(**kwargs)
        
        for i in range(cascade):
            self.add(BiquadFilterCoeffs(
                name = f'Coeffs[{i}]',
                offset = i * 32))
            
import scipy.signal

class DownsampleFilters(pr.Device):
    def __init__(self, timingTx=None, **kwargs):
        super().__init__(**kwargs)

        self.filterFreq = 120.0

        def _setFilters(value, write):
            self.filterFreq = value
            sr = timingTx.RowSequenceRate.get()*1.0e3
            sos = scipy.signal.butter(N=4, Wn=self.filterFreq / (sr / 2), output = 'sos')
            print('Coefficients for downsample filter')
            print(f'Sample Rate - {sr}')
            print(f'Filter Freq - {self.filterFreq}')
            print(sos)
            for i, coeff in enumerate(sos):
                for col in range(8):
                    self.Filter[col].Coeffs[i].B0.set(coeff[0], write=False)
                    self.Filter[col].Coeffs[i].B1.set(coeff[1], write=False)
                    self.Filter[col].Coeffs[i].B2.set(coeff[2], write=False)
                    self.Filter[col].Coeffs[i].A1.set(coeff[4], write=False)
                    self.Filter[col].Coeffs[i].A2.set(coeff[5], write=False)
                    
            if (write):        
                self.writeAndVerifyBlocks()

        def _get(read):
            return self.filterFreq

        for i in range(8):
            self.add(BiquadFilter(
                name = f'Filter[{i}]',
                cascade = 2,
                offset = i << 8))

        self.add(pr.LinkVariable(
            name = 'FilterCuttoffFreq',
            dependencies = [self.Filter[col].Coeffs[casc].B0 for col in range(8) for casc in range(2)],
            linkedSet = _setFilters,
            linkedGet = _get))        

            
            
