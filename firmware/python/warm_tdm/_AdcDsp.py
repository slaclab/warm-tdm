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
    def __init__(self, dsp, rows, **kwargs):
        super().__init__(**kwargs)

        for row in range(rows):
            self.add(RowPidStatus(
                name = f'Row[{row}]',
                dsp = dsp,
                rowNum = row))

class AdcDsp(pr.Device):

    COEF_BASE = pr.Fixed(24, 23)
    ACCUM_BASE = pr.Fixed(18, 0)
    RESULT_BASE = pr.Fixed(48, 23)

    def __init__(self, frontEnd, column, rows=256, **kwargs):
        super().__init__(**kwargs)

        self.amp = frontEnd.Channel[column].SQ1FbAmp
        self.rows = rows

        self.add(pr.RemoteVariable(
            name = 'PidEnableRaw',
            offset = 0x00,
            base = pr.Bool,
            hidden = True,
            groups = ['NoConfig'],
            mode = 'RW',
            bitSize = 1,
            bitOffset = 0))

        def _enablePid(value, write):
            self.ClearPids()
            self.PidEnableRaw.set(value, write=write)

        self.add(pr.LinkVariable(
            name = 'PidEnable',
            groups = ['NoConfig'],
            base = pr.Bool,
            enum = {
                False: 'False',
                True: 'True'},
            dependencies = [self.PidEnableRaw],
            linkedSet = _enablePid,
            linkedGet = self.PidEnableRaw.get))

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
            groups = ['NoConfig'],            
            offset = 0x40,
            base = pr.UInt,
            bitSize = 14,
            bitOffset = 0))

        def _set(value, write):
            print(f'Set flux quanta to {value}')
            dac = self.amp.outCurrentToDac(value)
            print(f'Initial dac value {dac} - 0x{dac:x}')
            # Convert inverted offset binary to 2s complement
            if self.amp.Invert.value() == True:
                dac = (dac & 0x2000) | (~dac & 0x1fff)
            else:
                dac = (dac ^ 0x2000) 
            print(f'Converted dac value {dac} - 0x{dac:x}')
            self.FluxQuantumRaw.set(dac, write=write)

        def _get(read):
            dac = self.FluxQuantumRaw.get(read=read)
            if self.amp.Invert.value() == True:
                dac = (dac & 0x2000) | (~dac & 0x1fff)
            else:
                dac = (dac ^ 0x2000)
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
            numValues = rows,
            valueBits = 14,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x2000,
            base = AdcDsp.ACCUM_BASE,
            mode = 'RO',
            numValues = rows,
            valueBits = AdcDsp.ACCUM_BASE.bitSize,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x3000,
            base = AdcDsp.ACCUM_BASE,
            mode = 'RW',
            numValues = rows,
            valueBits = AdcDsp.ACCUM_BASE.bitSize,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'PidResults',
            offset = 0x4000,
            mode = 'RW',
            base = AdcDsp.RESULT_BASE,
            numValues = rows,
            valueBits = AdcDsp.RESULT_BASE.bitSize,
            valueStride = 64))


        self.add(pr.RemoteVariable(
            name = 'FilterResults',
            offset = 0x5000,
            mode = 'RO',
            base = AdcDsp.RESULT_BASE,
            numValues = rows,
            valueBits = AdcDsp.RESULT_BASE.bitSize,
            valueStride = 64))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps',
            offset = 0x7000,
            base = pr.Int,
            mode = 'RW',
            numValues = rows,
            valueBits = 8,
            valueStride = 32))

        self.add(RowPidStatusArray(
            name = 'RowPidStatus',
            groups = ['NoConfig'],            
            dsp = self,
            rows = rows))

        @self.command()
        def ClearPids():
            blank = [0 for x in range(self.rows)]
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
