import pyrogue as pr
import warm_tdm
import warm_tdm_api
import numpy as np

from ._GroupVariables import (GroupLinkVariable, GroupArrayLinkVariable,
                              FastDacVariable, GroupBroadcastVariable,
                              PidGainVariable)


class Group(pr.Device):

    def col_iter(self):
        """Yield (board, channel) for all columns in order."""
        for board in range(self.config.columnBoards):
            for chan in range(8):
                yield (board, chan)

    def _cable_r_nodes(self):
        """Find every AFE cable-resistance model node across all boards.

        These are ``pr.LocalVariable``s named ``CableR`` that hold the roundtrip
        cryostat cable resistance used by the front-end gain/conversion math --
        client-side model state, not a hardware register. Every AFE amplifier
        (column ``Channel[*].{SAAmp,SAFbAmp,SQ1BiasAmp,SQ1FbAmp,TesBiasAmp}``,
        row ``Amp[*]``) exposes one, so a single anchored ``find`` over the
        HardwareGroup collects them all regardless of front-end class or channel
        count. The ``CableR$`` anchor keeps this from also matching the Group's
        own ``CableResistance`` broadcast variable (``find`` regex-matches names).

        This backs the ``CableResistance`` broadcast variable (issue #83, G3).
        """
        return self.HardwareGroup.find(typ=pr.LocalVariable, name='CableR$')

    def makeGuiGroup(self, arrVar):
        for i in range(self.config.numColumns):
            self.add(pr.LinkVariable(
                name = f'_{arrVar.name}[{i}]',
                mode = arrVar.mode,
                disp = arrVar.disp,
                units = arrVar.units,
                guiGroup = arrVar.name,
                dependencies = [arrVar],
                groups = ['NoConfig'],
                linkedGet = lambda read, x=i: arrVar.get(read=read, index=x),
                linkedSet = None if arrVar.mode == 'RO' else lambda value, write, x=i: arrVar.set(value, write=write, index=x)))

    def __init__(self,
                 colBoardClass,
                 colFeClass,
                 rowBoardClass,
                 rowFeClass,
                 groupConfig,
                 groupId,
                 num_row_selects=32,
                 num_chip_selects=0,
                 dataWriter=None,
                 simulation=False,
                 emulate=False,
                 useFloatPid=False,
                 **kwargs):
        """
        Warm TDM Device
        Parameters
        ----------
        groupConfig : warm_tdm_api.GroupConfig
            Group configuration
        simulation: bool
           Flag to determine if simulation mode is enabled
        emulate: bool
           Flag to determine if emulation mode should be used
        """

        super().__init__(groups='DocApi',
                         description = "Interface to a WarmTDM 'Flange Group' consisting of multiple Row and Column boards."
                                       "This class contains the top level configuration variables as well as a number of tuning and run control processes.",
                         **kwargs)

        self.config = groupConfig

        # NOTE (wtj-cleanup-sw): useFloatPid and the RTL row-sizing *generics*
        # (ROW_ADDR_BITS_G) are NOT wired on this branch. The floating-point PID
        # path (_AdcDspFp) and coherent RTL row-sizing live on the deferred
        # firmware track and are not present in this firmware/python tree, so we
        # drop useFloatPid from this call. config.maxRows IS threaded into the
        # HardwareGroup as the single source of truth: it caps both the RowMap
        # RAM sizing below and the number of firmware row indices mapped into
        # Rogue variables (AdcDsp/SAFb arrays), which map the first maxRows
        # strided entries of the 256-deep firmware address space.
        if useFloatPid:
            self._log.warning("useFloatPid=True requested, but the floating-point "
                              "PID firmware is not available on this branch. Ignoring; "
                              "using fixed-point firmware.")

        self.add(warm_tdm.HardwareGroup(
            groupId=groupId,
            dataWriter=dataWriter,
            simulation=simulation,
            emulate=emulate,
            host=groupConfig.host,
            colBoards=groupConfig.columnBoards,
            colBoardClass=colBoardClass,
            colFeClass=colFeClass,
            rowBoards=groupConfig.rowBoards,
            rowBoardClass=rowBoardClass,
            rowFeClass=rowFeClass,
            num_row_selects=num_row_selects,
            num_chip_selects=num_chip_selects,
            rowAddrBits=groupConfig.rowAddrBits,
            maxRows=groupConfig.maxRows,
            groups=['Hardware'],
            expand=True))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

        ############################################
        # Local Variables describing configuration
        ############################################

        self.add(pr.LocalVariable(
            name='NumRowBoards',
            description='Number of row boards in the Group.',
            value=self.config.rowBoards,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='MaxRows',
            description='Maximum number of row indices (row address space = '
                        'maxRows = 2**ROW_ADDR_BITS_G). Static; the active row '
                        'count is len(RowIndexOrderList).',
            value=self.config.maxRows,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumnBoards',
            description='Number of column boards in the Group.',
            value=self.config.columnBoards,
            mode='RO',
            groups='TopApi'))

        self.add(pr.LocalVariable(
            name='NumColumns',
            description='Total number of columns in the Group. NumColumnBoards * 8.',
            value=self.config.numColumns,
            mode='RO',
            groups='TopApi'))

        ##################################
        # RowMap configuration
        ##################################

        self._rowMap = []
        def _setRowMap(value):
            # value is the logical->physical row map: value[i] is the physical
            # (rs/cs) address for logical row i. Its length is the number of
            # active logical rows, which cannot exceed the configured maxRows
            # (the logical row address space / RowMap RAM depth).
            if len(value) > self.config.maxRows:
                raise ValueError(
                    f'RowMap has {len(value)} logical rows but maxRows is '
                    f'{self.config.maxRows}. Reduce the row map or start with a '
                    f'larger --maxRows (must be <= 2**ROW_ADDR_BITS_G of the '
                    f'deployed firmware).')

            self._rowMap = value

            ram = [0x8080 for x in range(self.config.maxRows)]

            for i, row in enumerate(value):
                valueRs = (row['rsBoard'] << 5) | row['rsAddr']
                valueCs = 0x80
                if 'csAddr' in row:
                    valueCs = (row['csBoard'] << 5) | row['csAddr']

                ram[i] = valueCs << 8 | valueRs

            for rowBoard in self.HardwareGroup.RowBoard.values():
                rowBoard.RowDacDriver.RowMap.set(value=ram, write=True)

        def _getRowMap():
            return self._rowMap

        self.add(pr.LocalVariable(
            name = 'RowMap',
            localSet = _setRowMap,
            localGet = _getRowMap))

        @self.command()
        def RowMap1x32():
            d = [{'rsBoard': 0, 'rsAddr': x} for x in range(32)]
            self.RowMap.set(d)

        @self.command()
        def RowMap6x10():
            d = [{'rsBoard': 0, 'rsAddr': rs, 'csBoard':0, 'csAddr':cs } for cs in range(10, 16) for rs in range(10)]
            self.RowMap.set(d)

        @self.command()
        def RowMap8x10():
            d = [{'rsBoard': 0, 'rsAddr': rs, 'csBoard':0, 'csAddr':cs } for cs in range(10, 18) for rs in range(10)]
            self.RowMap.set(d)

        @self.command()
        def RowMap7x10():
            d = [{'rsBoard': 0, 'rsAddr': rs, 'csBoard':0, 'csAddr':cs } for cs in range(10, 17) for rs in range(10)]
            self.RowMap.set(d)

        @self.command()
        def RowMap2x6x10():
            d = [{'rsBoard': 0, 'rsAddr': rs + (split*16), 'csBoard':0, 'csAddr': cs + (split * 16)} for split in range(2) for cs in range(10, 16) for rs in range(10)]
            self.RowMap.set(d)

        if groupConfig.columnBoards > 0:
            self.add(pr.LinkVariable(
                name = 'RowIndexOrderList',
                groups = ['NoConfig'],
                variable = self.HardwareGroup.ReadoutList))

        ##################################
        # Tuning enables
        ##################################

        _numCols = 8 if self.config.columnBoards == 0 else self.config.numColumns
        if simulation:
            # The RTL sim model only exercises a single column; enabling the
            # rest would tune against columns that produce no meaningful data.
            _value = np.zeros(_numCols, bool)
            _value[0] = True
        else:
            _value = np.ones(_numCols, bool)
        self.add(pr.LocalVariable(
            name='ColTuneEnable',
            description='Array of booleans which enable the tuning of each column.'
                        'Total length = ColumnBoards * 8.',
            value=_value,
            # Seeded with an ndarray, but the documented workflow and scripts set
            # it from a plain Python bool list (group.ColTuneEnable.set([True]*8));
            # allow both rather than forcing callers to wrap in np.array.
            typeCheck=False,
            groups='TopApi',
            mode='RW'))

        ##################################
        # Row board access variables
        ##################################

        # Hidden: driven only by the tuning algorithms (_Tuning.py), never
        # invoked manually from the GUI.
        def _setRowIndex(name, value):
            variables = [
                getattr(board.RowDacDriver, name)
                for board in self.HardwareGroup.RowBoard.values()]
            warm_tdm_api.stageAndCommit(
                *[(variable, value) for variable in variables])

        @self.command(hidden=True)
        def ActivateRowIndex(arg):
            _setRowIndex('ActivateRowIndex', arg)

        @self.command(hidden=True)
        def DeactivateRowIndex(arg):
            _setRowIndex('DeactivateRowIndex', arg)

        self.rowSelectedVars = []

        #####################################
        # Column board access variables
        #####################################

        if self.config.columnBoards > 0:

            self.add(GroupLinkVariable(
                name='SaBiasVoltage',
                description='SaBias value for each column. 1D array with total length = ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].SaBiasOffset.BiasVoltage[chan]
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupLinkVariable(
                name='SaBiasCurrent',
                description='SaBias current for each column. 1D array with total length = ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].SaBiasOffset.BiasCurrent[chan]
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupLinkVariable(
                name='SaOffset',
                description='SaOffset value for each column. 1D array with total length = ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].SaBiasOffset.OffsetVoltage[chan]
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupArrayLinkVariable(
                name='SaOutAdc',
                description='Current ADC value in Volts for each column. Total length = ColumnBoards * 8.',
                mode = 'RO',
                config=self.config,
                dependencies = [self.HardwareGroup.ColumnBoard[board].DataPath.WaveformCapture.AdcAverage
                                for board in range(self.config.columnBoards)],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupArrayLinkVariable(
                name='SaOut',
                description='Current SA_OUT value in mV for each column before amplifier gain, adjusted for current offset value.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].SaOut
                                for board in range(self.config.columnBoards)],
                config = self.config,
                mode = 'RO',
                disp = '{:0.03f}',
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupArrayLinkVariable(
                name='SaOutNorm',
                description='Current SA_OUT value in mV for each column before amplifier gain, not adjusted for current offset value.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].SaOutNorm
                                for board in range(self.config.columnBoards)],
                config = self.config,
                mode = 'RO',
                disp = '{:0.03f}',
                tuneEnVar = self.ColTuneEnable))

            self.add(FastDacVariable(
                name='SaFbCurrent',
                description='SaFb value for each column/row used during readout. 2D array indexed by (col, row).',
                config = self.config,
                hidden = False,
                dependencies = [self.HardwareGroup.ColumnBoard[board].SAFb.Column[chan].Current
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupArrayLinkVariable(
                name='SaFbForceCurrent',
                description='SaFb value for each column used during tuning. 1D array with total length ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].SaFbForceCurrent
                                for board in range(self.config.columnBoards)],
                config = self.config,
                tuneEnVar = self.ColTuneEnable))

            self.add(FastDacVariable(
                name='SaFbVoltage',
                description='SaFb voltage for each column/row. 2D array indexed by (col, row).',
                config = self.config,
                hidden = True,
                dependencies = [self.HardwareGroup.ColumnBoard[board].SAFb.Column[chan].Voltage
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(FastDacVariable(
                name='Sq1BiasCurrent',
                description='Sq1Bias value for each column/row used during readout. 2D array indexed by (col, row).',
                config = self.config,
                hidden = False,
                dependencies = [self.HardwareGroup.ColumnBoard[board].SQ1Bias.Column[chan].Current
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupArrayLinkVariable(
                name='Sq1BiasForceCurrent',
                description='Sq1Bias value for each column used during tuning. 1D array with total length ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].Sq1BiasForceCurrent
                                for board in range(self.config.columnBoards)],
                config = self.config,
                tuneEnVar = self.ColTuneEnable))

            self.add(FastDacVariable(
                name='Sq1BiasVoltage',
                description='Sq1Bias voltage for each column/row. 2D array indexed by (col, row).',
                config = self.config,
                hidden = True,
                dependencies = [self.HardwareGroup.ColumnBoard[board].SQ1Bias.Column[chan].Voltage
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(FastDacVariable(
                name='Sq1FbCurrent',
                description='Sq1Fb value for each column/row used during readout. 2D array indexed by (col, row).',
                config = self.config,
                hidden = False,
                dependencies = [self.HardwareGroup.ColumnBoard[board].SQ1Fb.Column[chan].Current
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            self.add(GroupArrayLinkVariable(
                name='Sq1FbForceCurrent',
                description='Sq1Fb value for each column used during tuning. 1D array with total length ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].Sq1FbForceCurrent
                                for board in range(self.config.columnBoards)],
                config = self.config,
                tuneEnVar = self.ColTuneEnable))

            self.add(FastDacVariable(
                name='Sq1FbVoltage',
                description='Sq1Fb voltage for each column/row. 2D array indexed by (col, row).',
                config = self.config,
                hidden = True,
                dependencies = [self.HardwareGroup.ColumnBoard[board].SQ1Fb.Column[chan].Voltage
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            # AdcDsp coefficients multiply the sum of the ADC errors in the row
            # sample window.  Present window-independent gains on the mean error
            # at Group scope, where the effective coordinator TimingTx is known.
            # A low-level AdcDsp on a non-coordinator board cannot reliably infer
            # that timing configuration from its own dormant TimingTx registers.
            _pid_timing_tx = self.HardwareGroup.ColumnBoard[0].WarmTdmCore.Timing.TimingTx
            _pid_dsps = [self.HardwareGroup.ColumnBoard[board].DataPath.AdcDsp[chan]
                         for board, chan in self.col_iter()]

            self.add(pr.LinkVariable(
                name = 'PidSampleCount',
                description = 'ADC samples accumulated per row visit by the '
                              'coordinator timing window.',
                mode = 'RO',
                groups = ['TopApi', 'NoConfig'],
                dependencies = [_pid_timing_tx.SampleCount],
                disp = '{:d}',
                linkedGet = _pid_timing_tx.SampleCount.get))

            for name, field, description in (
                    ('PidP_Gain', 'P_Coef',
                     'Window-normalized proportional gain on mean ADC error.'),
                    ('PidI_Gain', 'I_Coef',
                     'Window-normalized integral gain on accumulated mean ADC error.'),
                    ('PidD_Gain', 'D_Coef',
                     'Window-normalized derivative gain on mean ADC-error differences.')):
                self.add(PidGainVariable(
                    name = name,
                    description = description,
                    coefficient_dependencies = [getattr(dsp, field) for dsp in _pid_dsps],
                    sample_count = _pid_timing_tx.SampleCount,
                    disp = '{:0.8f}'))

            self.add(GroupLinkVariable(
                name = 'TesBias',
                description='TesBias value for each column. 1D array with total length ColumnBoards * 8.',
                dependencies = [self.HardwareGroup.ColumnBoard[board].TesBias.BiasCurrent[chan]
                                for board, chan in self.col_iter()],
                tuneEnVar = self.ColTuneEnable))

            @self.command()
            def ZeroSaBias():
                zero_cols = np.zeros(self.config.numColumns, np.float64)
                self.SaBiasCurrent.set(zero_cols)
                self.SaOffset.set(zero_cols)

            @self.command()
            def ZeroSaFb():
                self.SaFbForceCurrent.set(np.zeros(self.config.numColumns, np.float64))

            # TMP: seed the known SA tune point (SaBias=55, SaFb=41) so sim/bench
            # runs can jump straight to a locked bias without a full SaTune.
            # Per tuning-enabled column, set the per-column SaBias and write SaFb
            # only for the rows enabled for tuning/readout (RowIndexOrderList).
            @self.command()
            def TmpSetSaTunePoint():
                colTuneEnable = np.asarray(self.ColTuneEnable.value(), dtype=bool)
                tuneRows = [int(r) for r in self.RowIndexOrderList.value()]
                with self.root.updateGroup():
                    for col in range(self.config.numColumns):
                        if not colTuneEnable[col]:
                            continue
                        self.SaBiasCurrent.set(index=col, value=55.0)
                        for row in tuneRows:
                            self.SaFbCurrent.set(index=(col, row), value=41.0)
                # Run the SA offset PID loop to null SaOut at the seeded SaBias,
                # matching what saTune() does after setting the bias point.
                warm_tdm_api.saOffset(group=self)

            @self.command()
            def ZeroSq1Bias():
                self.Sq1BiasForceCurrent.set(np.zeros(self.config.numColumns, np.float64))

            @self.command()
            def ZeroSq1Fb():
                self.Sq1FbForceCurrent.set(np.zeros(self.config.numColumns, np.float64))

            @self.command()
            def ZeroDacs():
                zero_cols = np.zeros(self.config.numColumns, np.float64)
                self.Sq1FbForceCurrent.set(zero_cols)
                self.Sq1BiasForceCurrent.set(zero_cols)
                self.SaFbForceCurrent.set(zero_cols)
                self.SaBiasCurrent.set(zero_cols)
                self.SaOffset.set(zero_cols)

            # Accumulator for the settings a simulation cosim run needs before
            # tuning. Add further sim-only setup here as the cosim grows.
            @self.command()
            def SimCosimSetup():
                # 1x32 logical row map.
                self.RowMap1x32()
                # Enable 8 rows (0-7). RowIndexOrderList drives both the muxed
                # readout (NumRows/row order) and the rows sq1Tune iterates, so
                # this is the single knob for "rows in the mux" and "rows tuned".
                self.RowIndexOrderList.set(list(range(8)))
                rowBoards = list(self.HardwareGroup.RowBoard.values())
                # Drive every FAS on-current to 163 uA on all row boards.
                for rowBoard in rowBoards:
                    driver = rowBoard.RowDacDriver
                    driver.Mode.set(1, write=True)
                    fasOn = driver.FasOn
                    fasOn.Current.set(value=[163.0] * len(fasOn.amps), index=-1, write=True)
                # In MANUAL mode, table writes also drive their addressed
                # physical output. Write every FasOff entry only after every
                # FasOn entry so setup leaves all FAS rows physically off.
                for rowBoard in rowBoards:
                    fasOff = rowBoard.RowDacDriver.FasOff
                    fasOff.Current.set(value=[0.0] * len(fasOff.amps), index=-1, write=True)
                # Seed the known SA tune point (also runs the SA offset PID loop).
                # Runs after the row list is set so it writes SaFb for exactly the
                # enabled rows.
                self.TmpSetSaTunePoint()

            self.columnSelectedVars = [
                self.ColTuneEnable,
                self.SaBiasVoltage,
                self.SaBiasCurrent,
                self.SaOffset,
                self.SaOutAdc,
                self.SaOut,
                self.SaOutNorm,
                self.SaFbForceCurrent,
                self.Sq1BiasForceCurrent,
                self.Sq1FbForceCurrent,
                self.TesBias,
                self.PidP_Gain,
                self.PidI_Gain,
                self.PidD_Gain
            ]

            for var in self.columnSelectedVars:
                self.makeGuiGroup(var)

            self.rowColumnSelectedVars = [
                self.SaFbCurrent,
                self.Sq1BiasCurrent,
                self.Sq1FbCurrent]

            self.add(warm_tdm_api.ConfigSelect(self, groups=['NoDoc', 'NoConfig']))

            #############################################
            # Tuning and diagnostic Processes
            #############################################
            self.add(warm_tdm_api.SaOffsetProcess(config=self.config))
            self.add(warm_tdm_api.SaOffsetSweepProcess(config=self.config, group=self))
            self.add(warm_tdm_api.SaTuneProcess(config=self.config))
            self.add(warm_tdm_api.Sq1TuneProcess(config=self.config, groups=['NoDoc']))
            self.add(warm_tdm_api.FasTuneProcess(
                config=self.config, groups=['NoDoc']))
            self.add(warm_tdm_api.Sq1DiagProcess(groups=['NoDoc']))
            self.add(warm_tdm_api.TesRampProcess(groups=['NoDoc']))
            self.add(warm_tdm_api.TesBiasWaveformProcess(groups=['NoDoc']))
            self.add(warm_tdm_api.SaStripChartProcess(groups=['NoDoc']))

        #####################################
        # Cross-board convenience variables
        #####################################

        # Roundtrip cryostat cable resistance, broadcast to every AFE amp's
        # CableR model node (issue #83, G3 -- graduated from the operations-layer
        # set_cryo_resistance helper). These are model LocalVariables, so there
        # is no hardware transaction and no tune-enable gating.
        self.add(GroupBroadcastVariable(
            name = 'CableResistance',
            description = 'Roundtrip cryostat cable resistance, broadcast to every '
                          'AFE amplifier cable-resistance model node on all boards.',
            units = 'Ω',
            disp = '{:0.1f}',
            empty_value = 0.0,
            dependencies = self._cable_r_nodes()))

        # Power-supply synchronization, broadcast to every board's TimingTx
        # (issue #83, G4 -- graduated from operations set_ps_synch/check_ps_synch).
        # Synchronized => PwrSyncA/B/C = OSC (2), PwrSyncEn = 1; unsynchronized =>
        # all LOW (0), PwrSyncEn = 0. get() reports True only if all four are in
        # the synchronized state on the representative board. A TimingTx node
        # exists on every board (added unconditionally in WarmTdmCore2).
        #
        # This one drives FOUR heterogeneous fields per board (three enums + a
        # bool) with an AND-reduce on get, so it stays a custom LinkVariable --
        # GroupBroadcastVariable only covers the homogeneous one-value/many-
        # identical-deps case (see CableResistance / LedEnable).
        _timing_tx = self.HardwareGroup.find(typ=warm_tdm.TimingTx)

        # PwrSync* are 2-bit enums: 0 = LOW, 2 = OSC (see _TimingTx.py). Enum
        # RemoteVariables take the raw value on set(); OSC drives the sync
        # oscillator on all three, LOW parks them.
        _PWR_OSC, _PWR_LOW = 2, 0

        def _set_ps_synch(*, value, write):
            level = _PWR_OSC if value else _PWR_LOW
            for tx in _timing_tx:
                tx.PwrSyncA.set(level, write=write)
                tx.PwrSyncB.set(level, write=write)
                tx.PwrSyncC.set(level, write=write)
                tx.PwrSyncEn.set(bool(value), write=write)

        def _get_ps_synch(*, read):
            if not _timing_tx:
                return False
            tx = _timing_tx[0]
            return (tx.PwrSyncA.get(read=read) == _PWR_OSC
                    and tx.PwrSyncB.get(read=False) == _PWR_OSC
                    and tx.PwrSyncC.get(read=False) == _PWR_OSC
                    and tx.PwrSyncEn.get(read=False) is True)

        # LinkVariable dependencies must be Variables (not the TimingTx Devices),
        # so depend on the individual PwrSync* nodes we broadcast to.
        _ps_deps = [v for tx in _timing_tx
                    for v in (tx.PwrSyncA, tx.PwrSyncB, tx.PwrSyncC, tx.PwrSyncEn)]

        self.add(pr.LinkVariable(
            name = 'PowerSupplySynchronized',
            description = 'When set, synchronize all boards\' supply switchers to '
                          'the timing domain (PwrSync A/B/C = OSC, PwrSyncEn on); '
                          'clear to free-run them (all LOW, PwrSyncEn off).',
            # NoConfig: the underlying TimingTx PwrSync* vars already serialize.
            groups = ['TopApi', 'NoConfig'],
            dependencies = _ps_deps,
            linkedSet = _set_ps_synch,
            linkedGet = _get_ps_synch))

        # Status-LED enable, broadcast to every board's WarmTdmConfig.LedEn
        # (issue #83, G6 -- graduated from operations disable_leds; now a
        # two-way toggle rather than one-directional). LedEn is a 1-bit enum
        # (0 = Disabled, 1 = Enabled); the value_map exposes it as a plain bool.
        self.add(GroupBroadcastVariable(
            name = 'LedEnable',
            description = 'Enable/disable the status-blink LEDs on all boards.',
            value_map = {False: 0, True: 1},
            empty_value = False,
            dependencies = self.HardwareGroup.find(typ=pr.RemoteVariable, name='LedEn$')))
