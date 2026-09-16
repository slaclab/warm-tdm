import pyrogue as pr

import warm_tdm
from ._PidFpConfig import float32, flux_period_registers


class IndexedLinkVariable(pr.LinkVariable):
    def __init__(self, dep, index, **kwargs):
        super().__init__(
            linkedGet=self._get,
            **kwargs)

        self.dep = dep
        self.index = index

    def _get(self, *, read):
        return self.dep.get(read=read, index=self.index)


class RowPidStatusFp(pr.Device):
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
            name = 'Sq1FbFull',
            dep = dsp.Sq1FbFull,
            index = rowNum))

        self.add(IndexedLinkVariable(
            name = 'FluxJumps',
            dep = dsp.FluxJumps,
            index = rowNum))


class RowPidStatusFpArray(pr.Device):
    def __init__(self, dsp, rows, **kwargs):
        super().__init__(**kwargs)

        for row in range(rows):
            self.add(RowPidStatusFp(
                name = f'Row[{row}]',
                dsp = dsp,
                rowNum = row))


class AdcDspFp(pr.Device):

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

        self.add(pr.RemoteCommand(
            name = 'ClearPidState',
            offset = 0x30,
            bitSize = 1,
            bitOffset = 0,
            function = pr.RemoteCommand.touchOne))

        def _enablePid(value, write):
            # Rising enable clears in RTL. Disable drains an accepted visit;
            # it must not abort the visit with a software-generated full clear.
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
                0: 'Sq1FbFull',
                1: 'AccumError',
                2: 'RowSeqCount',
                3: 'NewSumAccum'}))

        # PID Coefficients - IEEE 754 float32
        self.add(pr.RemoteVariable(
            name = 'P_CoefRaw',
            offset = 0x04,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0,
            hidden = True,
            mode = 'RW'))

        self.add(pr.RemoteVariable(
            name = 'I_CoefRaw',
            offset = 0x08,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0,
            hidden = True,
            mode = 'RW'))

        def _setCoef(dep, value, write):
            # RTL handles I changes at a visit boundary and clears only S.
            dep.set(float32(value), write=write)

        self.add(pr.LinkVariable(
            name = 'P_Coef',
            dependencies = [self.P_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.P_CoefRaw, value, write),
            linkedGet = self.P_CoefRaw.get))

        self.add(pr.LinkVariable(
            name = 'I_Coef',
            dependencies = [self.I_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.I_CoefRaw, value, write),
            linkedGet = self.I_CoefRaw.get))

        # Flux quantum raw registers (hidden)
        self.add(pr.RemoteVariable(
            name = 'FluxQuantumFpRaw',
            offset = 0x40,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0,
            hidden = True,
            mode = 'RW'))

        self.add(pr.RemoteVariable(
            name = 'InvFluxQuantumFpRaw',
            offset = 0x44,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0,
            hidden = True,
            mode = 'RW'))

        self.add(pr.LocalVariable(
            name = 'WrapMultiplierRaw',
            value = 1,
            hidden = True,
            groups = ['NoConfig'],
            mode = 'RW',
            minimum = 1))

        self.add(pr.LocalVariable(
            name = 'PhysicalFluxQuantumDac',
            value = 0.0,
            mode = 'RO',
            hidden = True))

        def _configureFluxQuantum(value, multiplier, write):
            quantum, period, reciprocal = flux_period_registers(
                value, self.amp.currentPerLsb(), multiplier)
            if write and (self.PidEnableRaw.get(read=True) or
                          self.ControlBusy.get(read=True) or self.DacWriteBusy.get(read=True)):
                raise RuntimeError('Disable PID and wait for ControlBusy and DacWriteBusy '
                                   'to clear before changing flux wrapping')
            # Processing is quiescent: the two register writes cannot be used
            # by an in-flight visit. Always update both, including zero.
            self.FluxQuantumFpRaw.set(period, write=write)
            self.InvFluxQuantumFpRaw.set(reciprocal, write=write)
            self.WrapMultiplierRaw.set(multiplier)
            self.PhysicalFluxQuantumDac.set(quantum)

        def _setFluxQuantum(value, write):
            _configureFluxQuantum(value, self.WrapMultiplierRaw.value(), write)

        def _getFluxQuantum(read):
            fq = self.FluxQuantumFpRaw.get(read=read)
            return fq / self.WrapMultiplierRaw.value() * abs(self.amp.currentPerLsb())

        def _setWrapMultiplier(value, write):
            _configureFluxQuantum(_getFluxQuantum(read=write), value, write)

        self.add(pr.LinkVariable(
            name = 'WrapMultiplier',
            base = pr.UInt,
            minimum = 1,
            dependencies = [self.WrapMultiplierRaw],
            description = 'Physical quanta per centered wrap. Change only with PID '
                          'disabled and both busy indicators clear; then clear/reseed PID.',
            linkedSet = _setWrapMultiplier,
            linkedGet = self.WrapMultiplierRaw.get))

        self.add(pr.LinkVariable(
            name = 'FluxQuantum',
            dependencies = [self.FluxQuantumFpRaw, self.WrapMultiplierRaw],
            description = 'Physical period as a current difference; zero disables wrapping. '
                          'Configure while PID is disabled and drained, then clear/reseed.',
            units = u'μA',
            linkedSet = _setFluxQuantum,
            linkedGet = _getFluxQuantum))

        for name, bit in (('ControlBusy', 0), ('DacWriteBusy', 1)):
            self.add(pr.RemoteVariable(
                name=name, offset=0x34, bitOffset=bit, bitSize=1,
                mode='RO', base=pr.Bool, groups=['NoConfig']))
        self.add(pr.RemoteCommand(
            name='ResetCounters', offset=0x38, bitSize=1,
            function=pr.RemoteCommand.touchOne))
        for name, offset, description in (
                ('MissedVisitCount', 0x80, 'Enabled visits arriving while the calculation is busy.'),
                ('DiscardedVisitCount', 0x84, 'Visits intentionally ignored during disable or state clearing.'),
                ('DacOverflowCount', 0x88, 'Feedback writes lost because the DAC FIFO was full.'),
                ('DacErrorCount', 0x8C, 'DAC AXI writes completed with an error response.')):
            self.add(pr.RemoteVariable(
                name=name, offset=offset, bitSize=32, mode='RO', base=pr.UInt,
                description=description, groups=['NoConfig']))

        # Debug readbacks (all float except accumError which is integer)
        self.add(pr.RemoteVariable(
            name = 'AccumErrorInt_DBG',
            mode = 'RO',
            offset = 0x10,
            base = pr.Int,
            bitSize = 22,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'SumAccumFp_DBG',
            mode = 'RO',
            offset = 0x18,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbNewFp_DBG',
            mode = 'RO',
            offset = 0x20,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbFullFp_DBG',
            mode = 'RO',
            offset = 0x28,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbInt_DBG',
            mode = 'RO',
            offset = 0x2C,
            base = pr.Int,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'PidDebugEnable',
            offset = 0x50,
            mode = 'RW',
            base = pr.Bool,
            bitSize = 1,
            bitOffset = 0))

        # Per-row RAM arrays
        self.add(pr.RemoteVariable(
            name = 'AccumError',
            offset = 0x1000,
            base = pr.Float,
            mode = 'RO',
            numValues = rows,
            valueBits = 32,
            valueStride = 32))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            offset = 0x2000,
            base = pr.Float,
            mode = 'RW',
            numValues = rows,
            valueBits = 32,
            valueStride = 32))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbFull',
            offset = 0x3000,
            base = pr.Float,
            mode = 'RW',
            numValues = rows,
            valueBits = 32,
            valueStride = 32))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps',
            offset = 0x4000,
            base = pr.Int,
            mode = 'RW',
            numValues = rows,
            valueBits = 32,
            valueStride = 32))

        self.add(RowPidStatusFpArray(
            name = 'RowPidStatus',
            groups = ['NoConfig'],
            dsp = self,
            rows = rows))

        @self.command()
        def ClearPids():
            self.ClearPidState()
