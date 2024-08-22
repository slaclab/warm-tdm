import pyrogue as pr

import surf.dsp.fixed

import scipy.signal
import numpy as np

import warm_tdm

class IndexedLinkVariable(pr.LinkVariable):
    def __init__(self, dep, index, **kwargs):
        super().__init__(
            linkedGet=self._get,
#            linkedSet=self._set,
            **kwargs)
        
        self.dep = dep
        self.index = index

    def _get(self, *, read):
        return self.dep.get(read=read, index=self.index)

    def _set(self, *, value, write):
        self.dep.set(value=value, index=self.index, write=write)

class RowPidStatus(pr.Device):
    def __init__(self, dsp, rowNum, **kwargs):
        super().__init__(**kwargs)

        self.add(IndexedLinkVariable(
            name = 'AdcBaseline',
            dep = dsp.AdcBaselines,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'AccumError',
            dep = dsp.AccumError,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'SumAccum',
            dep = dsp.SumAccum,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'PidResults',
            dep = dsp.PidResults,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'FilterResults',
            dep = dsp.FilterResults,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'FluxJumps',
            dep = dsp.FluxJumps,
            index = rowNum))

class RowPidStatusArray(pr.Device):
    def __init__(self, dsp, numRows, **kwargs):
        super().__init__(**kwargs)

        for row in range(numRows):
            self.add(RowPidStatus(
                name = f'Row[{row}]',
                dsp = dsp,
                rowNum = row))

class AdcDsp(pr.Device):
    
    COEF_BASE = pr.Fixed(24, 23)
    ACCUM_BASE = pr.Fixed(18, 0)
    RESULT_BASE = pr.Fixed(48, 23)
        
    def __init__(self, frontEnd, column, numRows=256, **kwargs):
        super().__init__(**kwargs)



        numRows = 4

        self.amp = frontEnd.Channel[column].SQ1FbAmp

        self.add(pr.RemoteVariable(
            name = 'PidEnable',
            offset = 0x00,
            base = pr.Bool,
            mode = 'RW',
            bitSize = 1,
            bitOffset = 0))



        self.add(pr.RemoteVariable(
            name = 'P_Coef',
            offset = 0x04,
            base = AdcDsp.COEF_BASE,
            bitSize = AdcDsp.COEF_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'I_Coef',
            offset = 0x08,
            base = AdcDsp.COEF_BASE,
            bitSize = AdcDsp.COEF_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'D_Coef',
            offset = 0x0C,
            base = AdcDsp.COEF_BASE,
            bitSize = AdcDsp.COEF_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'FluxQuantumRaw',
            offset = 0x40,
            base = pr.Int,
            bitSize = 14,
            bitOffset = 0))

        def _set(value, write):
            dac = self.amp.outCurrentToDac(value)
            # Convert inverted offset binary to 2s complement
            dac = (dac & 0x2000) | (~dac & 0x1fff)
            self.FluxQuantumRaw.set(dac, write=write)

        def _get(read):
            dac = self.FluxQuantumRaw.get(read=read)
            dac = (dac & 0x2000) | (~dac & 0x1fff)            
            current = self.amp.dacToOutCurrent(dac)
            return current
            
        self.add(pr.LinkVariable(
            name = 'FluxQuantum',
            dependencies = [self.FluxQuantumRaw],
            units = u'\u03bcA',            
            linkedSet = _set,
            linkedGet = _get))

        self.add(pr.RemoteVariable(
            name = 'PidDebugEnable',
            offset = 0x50,
            mode = 'RW',
            base = pr.Bool,
            bitSize = 1,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps_DBG',
            offset = 0x44,
            mode = 'RO',
            base = pr.Int,
            bitSize = 8,
            bitOffset = 0,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'AccumError_DBG',
            mode = 'RO',
            offset = 0x10,
            base = AdcDsp.ACCUM_BASE,
            bitSize = AdcDsp.ACCUM_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'LastAccum_DBG',
            mode = 'RO',
            offset = 0x14,
            base = AdcDsp.ACCUM_BASE,
            bitSize = AdcDsp.ACCUM_BASE.bitSize,
            bitOffset = 0))
        
        self.add(pr.RemoteVariable(
            name = 'SumAccum_DBG',
            mode = 'RO',
            offset = 0x18,
            base = AdcDsp.ACCUM_BASE,
            bitSize = AdcDsp.ACCUM_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'PidResult_DBG',
            mode = 'RO',
            offset = 0x20,
            base = AdcDsp.RESULT_BASE,
            bitSize = AdcDsp.RESULT_BASE.bitSize,
            bitOffset = 0))
        
        self.add(pr.RemoteVariable(
            name = 'Sq1Fb_DBG',
            mode = 'RO',
            offset = 0x28,
            base = pr.Int,
            bitSize = 14,
            bitOffset = 0))
        
        
        self.add(pr.RemoteVariable(
            name = 'AdcBaselines',
            offset = 0x1000,
            base = pr.Int,
            mode = 'RW',
            numValues = numRows,
            valueBits = 14,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x2000,
            base = AdcDsp.ACCUM_BASE,
            mode = 'RO',
            numValues = numRows,
            valueBits = AdcDsp.ACCUM_BASE.bitSize,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x3000,
            base = AdcDsp.ACCUM_BASE,
            mode = 'RW',
            numValues = numRows,
            valueBits = AdcDsp.ACCUM_BASE.bitSize,
            valueStride = 32))
        

        self.add(pr.RemoteVariable(
            name = 'PidResults',
            offset = 0x4000,
            mode = 'RW',
            base = AdcDsp.RESULT_BASE,
            numValues = numRows,
            valueBits = AdcDsp.RESULT_BASE.bitSize,
            valueStride = 64))
        
        
        self.add(pr.RemoteVariable(
            name = 'FilterResults',
            offset = 0x5000,
            mode = 'RO',
            base = AdcDsp.RESULT_BASE,
            numValues = numRows,
            valueBits = AdcDsp.RESULT_BASE.bitSize,
            valueStride = 64))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps',
            offset = 0x7000,
            base = pr.Int,            
            mode = 'RW',
            numValues = numRows,
            valueBits = 8,
            valueStride = 32))

        self.add(RowPidStatusArray(
            name = 'RowPidStatus',
            dsp = self,
            numRows = numRows))

        @self.command()
        def ClearPids():
            blank = [0 for x in range(numRows)]
            self.SumAccum.set(blank)
            self.PidResults.set(blank)
            self.FluxJumps.set(blank)

        self.add(surf.dsp.fixed.FirFilterMultiChannel(
            name = 'FirFilter',
            offset = 0x6000,
            numberTaps = 11,
            coeffWordBitSize = 16))

        self.filterFreq = 1000.0
        
        def setFirTaps(value, write):
            self.filterFreq = value
            taps = scipy.signal.firwin(11, value, fs=7812.5, window='hamming')
            #print(f'Applying filter at {value} with taps {taps}')
            ftaps = np.array([int(np.round(x * 2**15)) for x in taps], dtype=np.uint16)
            #print([f'{t:04x}' for t in ftaps])
            self.FirFilter.Taps.set(taps, write=write)

        self.add(pr.LinkVariable(
            name = 'FilterCuttoffFreq',
            linkedSet = setFirTaps,
            linkedGet = lambda: self.filterFreq,
            value = self.filterFreq))
        
