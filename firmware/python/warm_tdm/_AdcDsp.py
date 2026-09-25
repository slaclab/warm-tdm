import pyrogue as pr

import surf.dsp.fixed

import scipy.signal
import numpy as np

import warm_tdm
import time
import numbers


def flux_reciprocal_registers(quantum):
    """Return (reciprocal, shift) for the integer MAC.

    Normalization fills the positive 18-bit multiplier operand. For every
    candidate the PID can produce, the wrap estimate is at most one jump low.
    Software writes these ordinary registers while PID is disabled and idle.
    """
    if isinstance(quantum, bool) or not isinstance(quantum, numbers.Integral) or not 0 <= quantum <= 8191:
        raise ValueError('FluxQuantumRaw must be an integer in 0..8191')
    quantum = int(quantum)
    if quantum == 0:
        return 0, 0
    shift = 16 + (quantum - 1).bit_length()
    return (1 << shift) // quantum, shift


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
            name = 'Sq1FbFull',
            dep = dsp.Sq1FbFull,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'Sq1FbFullValid',
            dep = dsp.Sq1FbFullValid,
            index = rowNum))

#         self.add(IndexedLinkVariable(
#             name = 'FilterResults',
#             dep = dsp.FilterResults,
#             index = rowNum))

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
    SQ1FB_FULL_BASE = pr.Fixed(38, 23)

    def __init__(self, frontEnd, column, rows=256, **kwargs):
        super().__init__(**kwargs)

        self.amp = frontEnd.Channel[column].SQ1FbAmp
        self.rows = rows

        self.add(pr.RemoteVariable(
            name = 'PidEnableRaw',
            offset = 0x00,
            base = pr.Bool,
            hidden = False,
            groups = ['NoConfig'],
            mode = 'RW',
            bitSize = 1,
            bitOffset = 0))

        self.add(pr.RemoteCommand(
            name = 'ClearPidState',
            description = 'Request a hardware scrub of the per-row PID state RAMs.',
            offset = 0x30,
            bitSize = 1,
            bitOffset = 0,
            function = pr.RemoteCommand.touchOne))

        self.add(pr.RemoteVariable(
            name = 'ControlBusy',
            description = 'A PID visit or state-clear sweep is active. '
                          'Does not include queued DAC writes.',
            offset = 0x34,
            base = pr.Bool,
            mode = 'RO',
            bitSize = 1,
            bitOffset = 0))

        def _enablePid(value, write):
            # Rising enable clears in hardware; disabling drains an accepted
            # visit. Rewriting enable must not force an unrelated full clear.
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
            name = 'RowEnableMask',
            offset = 0x60,
            base = pr.UInt,
            hidden = False,
            mode = 'RW',
            bitSize = 256,
            bitOffset = 0))
        
        self.add(pr.RemoteVariable(
            name = 'OutputMode',
            offset = 0x00,
            base = pr.UInt,
            hidden = False,
            mode = 'RW',
            bitSize = 2,
            bitOffset = 8,
            enum = {
                0: 'Sq1Fb',
                1: 'AccumError',
                2: 'RowSeqCount'}))
        

        self.add(pr.RemoteVariable(
            name = 'P_CoefRaw',
            offset = 0x04,
            base = AdcDsp.COEF_BASE,
            hidden = True,
            bitSize = AdcDsp.COEF_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'I_CoefRaw',
            offset = 0x08,
            base = AdcDsp.COEF_BASE,
            hidden = True,
            bitSize = AdcDsp.COEF_BASE.bitSize,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'D_CoefRaw',
            offset = 0x0C,
            base = AdcDsp.COEF_BASE,
            hidden = True,
            bitSize = AdcDsp.COEF_BASE.bitSize,
            bitOffset = 0))

        def _setCoef(dep, value, write):
            dep.set(value, write=write)

        self.add(pr.LinkVariable(
            name = 'P_Coef',
            base = AdcDsp.COEF_BASE,
            dependencies = [self.P_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.P_CoefRaw, value, write),
            linkedGet = self.P_CoefRaw.get))

        self.add(pr.LinkVariable(
            name = 'I_Coef',
            description = 'Changing I clears integral history after the active visit; '
                          'feedback and flux count are preserved.',
            base = AdcDsp.COEF_BASE,
            dependencies = [self.I_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.I_CoefRaw, value, write),
            linkedGet = self.I_CoefRaw.get))

        self.add(pr.LinkVariable(
            name = 'D_Coef',
            base = AdcDsp.COEF_BASE,
            dependencies = [self.D_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.D_CoefRaw, value, write),
            linkedGet = self.D_CoefRaw.get))

        self.add(pr.RemoteVariable(
            name = 'FluxQuantumRaw',
            description = 'DAC-code period in 0..8191; zero disables wrapping. '
                          'Raw clients must also program FluxReciprocalRaw and FluxReciprocalShift.',
            hidden = False,
            groups = ['NoConfig'],            
            offset = 0x40,
            base = pr.UInt,
            bitSize = 14,
            minimum = 0,
            maximum = 8191,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'FluxReciprocalRaw', offset = 0x48, bitSize = 17,
            base = pr.UInt, hidden = True, groups = ['NoConfig'],
            description = 'Software-computed normalized reciprocal; firmware trusts this value.'))
        self.add(pr.RemoteVariable(
            name = 'FluxReciprocalShift', offset = 0x4C, bitSize = 5,
            base = pr.UInt, hidden = True, groups = ['NoConfig'],
            description = 'Binary scale of FluxReciprocalRaw; computed in software.'))
        self.add(pr.RemoteVariable(
            name = 'FluxCountOverflow', offset = 0x54, bitOffset = 0, bitSize = 1,
            base = pr.Bool, mode = 'RO',
            description = 'Net count saturated; unwrapped history was lost. Cleared by full PID clear.'))

        def _setFluxQuantumRegisters(value, write):
            reciprocal, shift = flux_reciprocal_registers(value)
            if write and (self.PidEnableRaw.get(read=True) or self.ControlBusy.get(read=True)):
                raise RuntimeError('Disable PID and wait for ControlBusy before changing flux wrapping')
            self.FluxReciprocalRaw.set(reciprocal, write=write)
            self.FluxReciprocalShift.set(shift, write=write)
            self.FluxQuantumRaw.set(value, write=write)
            if write:
                deadline = time.monotonic() + 1.0
                while self.ControlBusy.get(read=True):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Integer flux configuration did not finish')
                    time.sleep(0.001)

        def _setFluxQuantum(value, write):
            # A quantum is a current DIFFERENCE, not an absolute DAC operating
            # point. Use the slope so zero remains zero for either polarity.
            if value < 0:
                raise ValueError('FluxQuantum must be a nonnegative period')
            dac = round(value / abs(self.amp.currentPerLsb()))
            if value > 0 and dac == 0:
                raise ValueError('FluxQuantum is too small to represent in DAC codes')
            if dac > 8191:
                raise ValueError('FluxQuantum exceeds the signed 14-bit positive range')
            _setFluxQuantumRegisters(dac, write)

        def _getFluxQuantum(read):
            dac = self.FluxQuantumRaw.get(read=read)
            if dac > 8191:
                raise ValueError('FluxQuantumRaw encodes an unsupported negative period')
            return dac * abs(self.amp.currentPerLsb())

        self.add(pr.LinkVariable(
            name = 'FluxQuantum',
            dependencies = [self.FluxQuantumRaw],
            units = u'\u03bcA',
            linkedSet = _setFluxQuantum,
            linkedGet = _getFluxQuantum))

        self.add(pr.RemoteVariable(
            name = 'PidDebugEnable',
            offset = 0x50,
            mode = 'RW',
            base = pr.Bool,
            bitSize = 1,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps_DBG',
            description = 'Signed net wrap count; saturates at -262144/+262143.',
            offset = 0x44,
            mode = 'RO',
            base = pr.Int,
            bitSize = 19,
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
            name = 'AccumError',
            offset = 0x1000,
            base = AdcDsp.ACCUM_BASE,
            mode = 'RO',
            numValues = rows,
            valueBits = AdcDsp.ACCUM_BASE.bitSize,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x2000,
            base = AdcDsp.ACCUM_BASE,
            mode = 'RW',
            numValues = rows,
            valueBits = AdcDsp.ACCUM_BASE.bitSize,
            valueStride = 32))


        self.add(pr.RemoteVariable(
            name = 'PidResults',
            offset = 0x3000,
            mode = 'RW',
            base = AdcDsp.RESULT_BASE,
            numValues = rows,
            valueBits = AdcDsp.RESULT_BASE.bitSize,
            valueStride = 64))


        self.add(pr.RemoteVariable(
            name = 'FluxJumps',
            description = 'Signed net wrap count per row; valid reconstruction requires -262144..262143.',
            offset = 0x6000,
            base = pr.Int,
            mode = 'RW',
            numValues = rows,
            valueBits = 19,
            valueStride = 32))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbFull',
            description = 'Retained post-wrap/clamp feedback in signed DAC-code units. '
                          'Only edit between visits with clearing complete; set Sq1FbFullValid to use it.',
            offset = 0x7000,
            base = AdcDsp.SQ1FB_FULL_BASE,
            mode = 'RW',
            groups = ['NoConfig'],
            numValues = rows,
            valueBits = AdcDsp.SQ1FB_FULL_BASE.bitSize,
            valueStride = 64))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbFullValid',
            description = 'When 0, the next enabled visit seeds Sq1FbFull from the applied DAC.',
            offset = 0x7004,
            bitOffset = 6,
            # Per-row array (one valid bit per row, strided 64 B inside each row's
            # Sq1FbFull slot). Typed pr.UInt, not pr.Bool: a Bool array has an enum
            # display, and PyDM's scalar-enum path cannot render an array value
            # (it tries enum.index('[enum, enum, ...]') and raises). UInt renders
            # the per-row 0/1 array cleanly, like the other per-row arrays here.
            base = pr.UInt,
            mode = 'RW',
            groups = ['NoConfig'],
            numValues = rows,
            valueBits = 1,
            valueStride = 64))

        self.add(RowPidStatusArray(
            name = 'RowPidStatus',
            groups = ['NoConfig'],            
            dsp = self,
            rows = rows))

        @self.command()
        def ClearPids():
            self.ClearPidState()

#         self.add(surf.dsp.fixed.FirFilterMultiChannel(
#             name = 'FirFilter',
#             offset = 0x6000,
#             numberTaps = 11,
#             coeffWordBitSize = 16))

#         self.filterFreq = 1000.0

#         def setFirTaps(value, write):
#             self.filterFreq = value
#             taps = scipy.signal.firwin(11, value, fs=7812.5, window='hamming')
#             #print(f'Applying filter at {value} with taps {taps}')
#             ftaps = np.array([int(np.round(x * 2**15)) for x in taps], dtype=np.uint16)
#             #print([f'{t:04x}' for t in ftaps])
#             self.FirFilter.Taps.set(taps, write=write)

#         self.add(pr.LinkVariable(
#             name = 'FilterCuttoffFreq',
#             linkedSet = setFirTaps,
#             linkedGet = lambda: self.filterFreq,
#             value = self.filterFreq))
