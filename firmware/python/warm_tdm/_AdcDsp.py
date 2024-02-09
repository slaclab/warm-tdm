import pyrogue as pr

import surf.dsp.fixed

import scipy.signal
import numpy as np

import warm_tdm

class IndexedLinkVariable(pr.LinkVariable):
    def __init__(self, dep, index,
                 linkedGet=self._get,
                 linkedSet=self._set,
                 **kwargs):
        
        self.dep = dep
        self.index = index

    def _get(self, *, read, index):
        return dep.read(read=read, index=index)

    def _set(self, *, value, index, write):
        dep.set(value=value, index=index, write=write)

class RowPidStatus(pr.Device):
    def __init__(self, dsp, rowNum, **kwargs):

        self.add(pr.IndexedLinkVariable(
            name = 'AdcBaseline',
            dep = dsp.AdcBaselines,
            index = rowNum))

        self.add(pr.IndexedLinkVariable(
            name = 'AccumError',
            dep = dsp.AccumError,
            index = rowNum))

        self.add(pr.IndexedLinkVariable(
            name = 'SumAccum',
            dep = dsp.SumAccum,
            index = rowNum))

        self.add(pr.IndexedLinkVariable(
            name = 'PidResults',
            dep = dsp.PidResults,
            index = rowNum))

        self.add(pr.IndexedLinkVariable(
            name = 'FilterResults',
            dep = dsp.FilterResults,
            index = rowNum))

        self.add(pr.IndexedLinkVariable(
            name = 'FluxJumps',
            dep = dsp.FluxJumps,
            index = rowNum))

class RowPidStatusArray(pr.Device):
    def __init__(self, dsp, numRows, **kwargs):

        for row in range(numRows):
            self.add(RowPidStatus(
                name = f'Row[{row}]',
                dsp = dsp,
                rowNum = row))

class AdcDsp(pr.Device):
    def __init__(self, column, numRows=256, **kwargs):
        super().__init__(**kwargs)

        ACCUM_BITS = 22
#        COEF_BITS = 10
#        SUM_BITS = 18
        RESULT_BITS = 32

        COEF_BASE = pr.Fixed(18, 17)

        numRows = 4

        self.add(pr.RemoteVariable(
            name = 'PidEnable',
            offset = 0x00,
            base = pr.Bool,
            mode = 'RW',
            bitSize = 1,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'AccumShift',
            offset = 0x00,
            base = pr.UInt,
            mode = 'RW',
            bitSize = 4,
            bitOffset = 16))

        self.add(pr.RemoteVariable(
            name = 'P_Coef',
            offset = 0x04,
            base = COEF_BASE,
            bitSize = 18,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'I_Coef',
            offset = 0x08,
            base = COEF_BASE,
            bitSize = 18,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'D_Coef',
            offset = 0x0C,
            base = COEF_BASE,
            bitSize = 18,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'FluxQuantumRaw',
            offset = 0x40,
            base = pr.Int,
            bitSize = 14,
            bitOffset = 0))

        def _set(value, write):
            amp = self.parent.parent.SQ1Fb.Amp[column]
            dac = amp.outCurrentToDac(value)
            # Convert inverted offset binary to 2s complement
            dac = (dac & 0x2000) | (~dac & 0x1fff)
            self.FluxQuantumRaw.set(dac, write=write)

        def _get(read):
            amp = self.parent.parent.SQ1Fb.Amp[column]
            dac = self.FluxQuantumRaw.get(read=read)
            dac = (dac & 0x2000) | (~dac & 0x1fff)            
            current = amp.dacToOutCurrent(dac)
            return current
            
        self.add(pr.LinkVariable(
            name = 'FluxQuantum',
            dependencies = [self.FluxQuantumRaw],
            units = u'\u03bcA',            
            linkedSet = _set,
            linkedGet = _get))

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
            base = pr.Fixed(22, 0),
            bitSize = 22,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'LastAccum_DBG',
            mode = 'RO',
            offset = 0x14,
            base = pr.Fixed(22, 0),
            bitSize = 22,
            bitOffset = 0))
        
        self.add(pr.RemoteVariable(
            name = 'SumAccum_DBG',
            mode = 'RO',
            offset = 0x18,
            base = pr.Fixed(22, 0),
            bitSize = 22,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'PidResult_DBG',
            mode = 'RO',
            offset = 0x20,
            base = pr.Fixed(40, 17),
            bitSize = 40,
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
#            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 14,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x2000,
            base = pr.Int,
            mode = 'RO',
#            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = ACCUM_BITS,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x3000,
            base = pr.Int,
            mode = 'RW',
#            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = ACCUM_BITS,
            valueStride = 32))
        

        self.add(pr.RemoteVariable(
            name = 'PidResults',
            offset = 0x4000,
            mode = 'RW',
#            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 40, #RESULT_BITS,
            valueStride = 64))
        
        
        self.add(pr.RemoteVariable(
            name = 'FilterResults',
            offset = 0x5000,
            mode = 'RO',
#            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 40, #16,
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
            name = 'RowPidStatus'))

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
        
