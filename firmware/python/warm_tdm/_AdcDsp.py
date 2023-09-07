import pyrogue as pr

import surf.dsp.fixed

import scipy.signal
import numpy as np

import warm_tdm




class AdcDsp(pr.Device):
    def __init__(self, numRows=256, **kwargs):
        super().__init__(**kwargs)

        ACCUM_BITS = 22
        COEF_BITS = 10
#        SUM_BITS = 18
        RESULT_BITS = 32

        COEF_BASE = pr.Fixed(18, 16)

        numRows = 1

        self.add(pr.RemoteVariable(
            name = 'PllEnable',
            offset = 0x00,
            base = pr.Bool,
            mode = 'RW',
            bitSize = 1,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'P_Coef',
            offset = 0x04,
            base = COEF_BASE,
            bitSize = 10,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'I_Coef',
            offset = 0x08,
            base = COEF_BASE,
            bitSize = 10,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'D_Coef',
            offset = 0x0C,
            base = COEF_BASE,
            bitSize = 10,
            bitOffset = 0))

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
            offset = 0x1C,
            base = pr.Fixed(32, 8),
            bitSize = 32,
            bitOffset = 0))
        
        self.add(pr.RemoteVariable(
            name = 'Sq1Fb_DBG',
            mode = 'RO',
            offset = 0x20,
            base = pr.Int,
            bitSize = 14,
            bitOffset = 0))
        
        
        self.add(pr.RemoteVariable(
            name = 'AdcBaselines',
            offset = 0x1000,
            base = pr.Int,
            mode = 'RW',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 14,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x2000,
            base = pr.Int,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = ACCUM_BITS,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x3000,
            base = pr.Int,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = ACCUM_BITS,
            valueStride = 32))
        

        self.add(pr.RemoteVariable(
            name = 'PidResults',
            offset = 0x4000,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = RESULT_BITS,
            valueStride = 32))
        
        
        self.add(pr.RemoteVariable(
            name = 'FilterResults',
            offset = 0x5000,
            mode = 'RO',
            bitSize = 32*numRows,
            numValues = numRows,
            valueBits = 16,
            valueStride = 32))

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
        
