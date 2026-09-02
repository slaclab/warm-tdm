import pyrogue as pr

import warm_tdm


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
            if write:
                self.ClearPidState()
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

        def _setCoef(dep, value, write, *, clearState=False):
            dep.set(value, write=write)
            if write and clearState:
                self.ClearPidState()

        self.add(pr.LinkVariable(
            name = 'P_Coef',
            dependencies = [self.P_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.P_CoefRaw, value, write),
            linkedGet = self.P_CoefRaw.get))

        self.add(pr.LinkVariable(
            name = 'I_Coef',
            dependencies = [self.I_CoefRaw],
            linkedSet = lambda value, write: _setCoef(self.I_CoefRaw, value, write, clearState=True),
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
            name = 'WrapMultiplier',
            value = 1,
            mode = 'RW',
            minimum = 1,
            description = 'Number of physical flux quanta per wrap period. '
                          'Higher values reduce flux jump frequency. '
                          'DAC range must accommodate WrapMultiplier * FluxQuantum.'))

        self.add(pr.LocalVariable(
            name = 'PhysicalFluxQuantumDac',
            value = 0.0,
            mode = 'RO',
            hidden = True))

        def _setFluxQuantum(value, write):
            dac = self.amp.outCurrentToDac(value)
            if self.amp.Invert.value():
                dac = dac ^ 0x3fff
            dac = dac ^ 0x2000
            self.PhysicalFluxQuantumDac.set(float(dac))
            N = self.WrapMultiplier.value()
            wrapPeriod = float(dac) * N
            self.FluxQuantumFpRaw.set(wrapPeriod, write=write)
            if wrapPeriod != 0:
                self.InvFluxQuantumFpRaw.set(1.0 / wrapPeriod, write=write)

        def _getFluxQuantum(read):
            fq = self.FluxQuantumFpRaw.get(read=read)
            N = self.WrapMultiplier.value()
            if N > 0:
                dac = int(fq / N)
            else:
                dac = int(fq)
            if self.amp.Invert.value():
                dac = dac ^ 0x3fff
            dac = dac ^ 0x2000
            return self.amp.dacToOutCurrent(dac)

        self.add(pr.LinkVariable(
            name = 'FluxQuantum',
            dependencies = [self.FluxQuantumFpRaw, self.WrapMultiplier],
            units = u'μA',
            linkedSet = _setFluxQuantum,
            linkedGet = _getFluxQuantum))

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

