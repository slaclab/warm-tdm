import pyrogue as pr
import warm_tdm
import warm_tdm_api


class Group(pr.Device):
    def __init__(self, groupConfig, simulation=False, emulate=False, **kwargs):
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

        super().__init__(**kwargs)

        # Configuration
        self._config = groupConfig

        # Row Map
        self.add(pr.LocalVariable(name='RowMap',
                                  localGet=lambda: self._config.rowMap,
                                  mode='RO',
                                  typeStr='PhysicalMap[]',
                                  description="Row Map"))

        # Col Map
        self.add(pr.LocalVariable(name='ColumnMap',
                                  localGet=lambda: self._config.columnMap,
                                  mode='RO',
                                  typeStr='PhysicalMap[]',
                                  description="Column Map"))

        # Row Order
        self.add(pr.LocalVariable(name='RowOrder',
                                  localGet=lambda: self._config.rowOrder,
                                  mode='RO',
                                  typeStr='int[]',
                                  description="Row Order"))

        # Col Enable
        self.add(pr.LocalVariable(name='ColumnEnable',
                                  localGet=lambda: self._config.columnEnable,
                                  mode='RO',
                                  typeStr='bool[]',
                                  description="Column Enable"))

        # Number of columns supported in this group
        self.add(pr.LocalVariable(name='NumColumns',
                                  value=len(self._config.columnMap),
                                  mode='RO',
                                  description="Number of columns"))

        self.add(pr.LocalVariable(name='NumColumnBoards',
                                  value=self._config.columnBoards,
                                  mode='RO',
                                  description="Number of column boards"))

        # Number of rows supported in this group
        self.add(pr.LocalVariable(name='NumRows',
                                  value=len(self._config.rowMap),
                                  mode='RO',
                                  description="Number of rows"))

        self.add(pr.LocalVariable(name='NumRowBoards',
                                  value=self._config.rowBoards,
                                  mode='RO',
                                  description="Number of row boards"))

        # Enable Row Tune Override
        self.add(pr.LinkVariable(name='RowForceEn',
                                 value=False,
                                 mode='RW',
                                 typeStr='bool',
                                 linkedSet=self._rowForceEnSet,
                                 linkedGet=self._rowForceEnGet,
                                 description="Row Tune Enable"))

        # Row Tune Channel
        self.add(pr.LinkVariable(name='RowForceIndex',
                                 value=0,
                                 mode='RW',
                                 typeStr='int',
                                 linkedSet=self._rowForceIdxSet,
                                 linkedGet=self._rowForceIdxGet,
                                 description="Row Tune Index"))

        # Tuning row enables
        self.add(pr.LocalVariable(name='RowTuneEnable',
                                  value=[True] * len(self._config.rowMap),
                                  mode='RW',
                                  description="Tune enable for each row"))

        # Tuning column enables
        self.add(pr.LocalVariable(name='ColTuneEnable',
                                  value=[True] * len(self._config.columnMap),
                                  mode='RW',
                                  description="Tune enable for each column"))

        # FLL Enable value
        self.add(pr.LinkVariable(name='FllEnable',
                                 value=False,
                                 mode='RW',
                                 typeStr='bool',
                                 linkedSet=self._fllEnableSet,
                                 linkedGet=self._fllEnableGet,
                                 description="FLL Enable Control"))

        # TES Bias values, accessed with column index value
        self.add(pr.LinkVariable(name='TesBias',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._tesBiasSet,
                                 linkedGet=self._tesBiasGet,
                                 description=""))

        # SA Bias values, accessed with column index value
        self.add(pr.LinkVariable(name='SaBias',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._saBiasSet,
                                 linkedGet=self._saBiasGet,
                                 description=""))

        # SA Offset values, accessed with column index value
        self.add(pr.LinkVariable(name='SaOffset',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._saOffsetSet,
                                 linkedGet=self._saOffsetGet,
                                 description=""))

        # SA Out values, accessed with column index value
        self.add(pr.LinkVariable(name='SaOut',
                                 mode='RO',
                                 typeStr='double[]',
                                 linkedGet=self._saOutGet,
                                 description=""))

        # SA FB values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='SaFb',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._saFbSet,
                                 linkedGet=self._saFbGet,
                                 description=""))

        # SQ1 Bias values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='Sq1Bias',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._sq1BiasSet,
                                 linkedGet=self._sq1BiasGet,
                                 description=""))

        # SQ1 Fb values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='Sq1Fb',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._sq1FbSet,
                                 linkedGet=self._sq1FbGet,
                                 description=""))

        # FAS Flux off values, accessed with row index
        self.add(pr.LinkVariable(name='FasFluxOff',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._fasFluxOffSet,
                                 linkedGet=self._fasFluxOffGet,
                                 description=""))

        # FAS Flux on values, accessed with row index
        self.add(pr.LinkVariable(name='FasFluxOn',
                                 mode='RW',
                                 typeStr='double[]',
                                 linkedSet=self._fasFluxOnSet,
                                 linkedGet=self._fasFluxOnGet,
                                 description=""))

        # Initialize System
        self.add(pr.LocalCommand(name='Init',
                                 function=self._init,
                                 description="Initialize System"))

        self.add(warm_tdm_api.SaTuneProcess())
        self.add(warm_tdm_api.Sq1TuneProcess())
        self.add(warm_tdm_api.FasTuneProcess())
        self.add(warm_tdm_api.Sq1DiagProcess())
        self.add(warm_tdm_api.TesRampProcess())

        self.add(warm_tdm.HardwareGroup(simulation=simulation, emulate=emulate, expand=True))

    def __colSetLoopHelper(self, value, index):
        # Construct a generator to loop over
        if index != -1:
            return ((idx, self._config.columnMap[idx].board, self._config.columnMap[idx].channel, val) for idx, val in zip(range(index, index+1), [value]))
        else:
            return ((idx, self._config.columnMap[idx].board, self._config.columnMap[idx].channel, val) for idx, val in enumerate(value))

    def __colGetLoopHelper(self, index):
        # Construct a generator to loop over

        if index != -1:
            ra = range(index, index+1)
        else:
            ra = range(len(self._config.columnMap))

        return ((idx, self._config.columnMap[idx].board, self._config.columnMap[idx].channel) for idx in ra)

    # Set Row Tune Override
    def _rowForceEnSet(self, value, write):

        for col in self.HardwareGroup.ColumnBoard:
            #col.RowForceEn.set(value,write=write)  # Waiting on force variables
            pass

        for row in self.HardwareGroup.RowBoard:
            #row.RowForceEn.set(value,write=write)  # Waiting on force variables
            pass

    # Get Row Tune Override
    def _rowForceEnGet(self, read):

        #return self.HardwareGroup.RowBoard[0].RowForceEn.get(read=read) # Waiting on force variables
        return False

    # Set Row Tune Index
    def _rowForceIdxSet(self, value, write):

        for col in self.HardwareGroup.ColumnBoard:
            pass
            #col.RowTuneIdx.set(value,write=write) # Waiting on force variables

        for row in self.HardwareGroup.RowBoard:
            pass
            #row.RowTuneIdx.set(value,write=write) # Waiting on force variables

    # Get Row Tune Index
    def _rowForceIdxGet(self, read):

        #return self.HardwareGroup.RowBoard[0].RowTuneIdx.get(read=read) # Waiting on force variables
        return 0

    # Set TES bias value, index is column
    def _tesBiasSet(self, value, write, index):
        for idx, board, chan, val in self.__colSetLoopHelper(value, index):

            self.HardwareGroup.ColumnBoard[board].TesBias.BiasCurrent[chan].set(value=value, write=write)

    # Get TES bias value, index is column
    def _tesBiasGet(self, read, index):
        ret = [0.0] * len(self._config.columnMap)

        for idx, board, chan in self.__colGetLoopHelper(index):
            ret[idx] = self.HardwareGroup.ColumnBoard[board].TesBias.BiasCurrent[chan].get(read=read)

        if index != -1:
            return ret[index]
        else:
            return ret

    # Set SA Bias value, index is column
    def _saBiasSet(self, value, write, index):
        for idx, board, chan, val in self.__colSetLoopHelper(value, index):
            self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Bias[chan].set(value=val, write=write)

    # Get SA Bias value, index is column
    def _saBiasGet(self, read, index):
        ret = [0.0] * len(self._config.columnMap)

        for idx, board, chan in self.__colGetLoopHelper(index):
            ret[idx] = self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Bias[chan].get(read=read)

        if index != -1:
            return ret[index]
        else:
            return ret

    # Set SA Offset value, index is column
    def _saOffsetSet(self, value, write, index):
        for idx, board, chan, val in self.__colSetLoopHelper(value, index):
            self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Offset[chan].set(value=val, write=write)

    # Get SA Offset value, index is column
    def _saOffsetGet(self, read, index):
        ret = [0.0] * len(self._config.columnMap)

        for idx, board, chan in self.__colGetLoopHelper(index):
            ret[idx] = self.HardwareGroup.ColumnBoard[board].SaBiasOffset.Offset[chan].get(read=read)

        if index != -1:
            return ret[index]
        else:
            return ret

    # Get SA Out value, index is column
    def _saOutGet(self, read, index):
        ret = [0.0] * len(self._config.columnMap)

        for idx, board, chan in self.__colGetLoopHelper(index):
            ret[idx] = self.HardwareGroup.ColumnBoard[board].DataPath.Ad9249Readout.AdcVoltage[chan].get(read=read)

        if index != -1:
            return ret[index]
        else:
            return ret

    # Set SA Feedback value, index is (column, row) tuple
    def _saFbSet(self, value, write, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard = self._config.columnMap[colIndex].board
            colChan = self._config.columnMap[colIndex].channel

            self.HardwareGroup.ColumnBoard[colBoard].SAFb.node(f'Col{colChan}_Row[{rowIndex}]').set(value=value,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._config.columnMap)):
                colBoard = self._config.columnMap[colIndex].board
                colChan = self._config.columnMap[colIndex].channel

                for rowIndex in range(len(self._config.rowMap)):
                    self.HardwareGroup.ColumnBoard[colBoard].SAFb.node(f'Col{colChan}_Row[{rowIndex}]').set(value=value[colIndex][rowIndex],write=False)

                # Force writes
                if write is True:
                    self.HardwareGroup.ColumnBoard[colBoard].SAFb.Column[colChan].write()

    # Get SA Feedback value, index is (column, row) tuple
    def _saFbGet(self, read, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard = self._config.columnMap[colIndex].board
            colChan = self._config.columnMap[colIndex].channel

            return self.HardwareGroup.ColumnBoard[colBoard].SAFb.node(f'Col{colChan}_Row[{rowIndex}]').get(read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._config.rowMap)] * len(self._config.columnMap)

            for colIndex in range(len(self._config.columnMap)):
                colBoard = self._config.columnMap[colIndex].board
                colChan = self._config.columnMap[colIndex].channel

                # Force reads
                if read is True:
                    self.HardwareGroup.ColumnBoard[colBoard].SAFb.Column[colChan].get()

                for rowIndex in range(len(self._config.rowMap)):

                    ret[colIndex][rowIndex] = self.HardwareGroup.ColumnBoard[colBoard].SAFb.node(f'Col{colChan}_Row[{rowIndex}]').get(read=False)

            return ret

    # Set per row value, index is (column, row) tuple
    def _fastDacSet(self, name, value, write, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard = self._config.columnMap[colIndex].board
            colChan = self._config.columnMap[colIndex].channel

            self.HardwareGroup.ColumnBoard[colBoard].node(name).node(f'Col{colChan}_Row[{rowIndex}]').set(value=value,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._config.columnMap)):
                colBoard = self._config.columnMap[colIndex].board
                colChan = self._config.columnMap[colIndex].channel

                for rowIndex in range(len(self._config.rowMap)):

                    self.HardwareGroup.ColumnBoard[colBoard].node(name).node(f'Col{colChan}_Row[{rowIndex}]').set(value=value[colIndex][rowIndex],write=False)

                # Force writes
                if write is True:
                    self.HardwareGroup.ColumnBoard[colBoard].node(name).Column[colChan].write()

    # Get per row value, index is (column, row) tuple
    def _fastDacGet(self, name, read, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard = self._config.columnMap[colIndex].board
            colChan = self._config.columnMap[colIndex].channel

            return self.HardwareGroup.ColumnBoard[colBoard].node(name).node(f'Col{colChan}_Row[{rowIndex}]').get(read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._config.rowMap)] * len(self._config.columnMap)

            for colIndex in range(len(self._config.columnMap)):
                colBoard = self._config.columnMap[colIndex].board
                colChan = self._config.columnMap[colIndex].channel

                # Force reads
                if read is True:
                    self.HardwareGroup.ColumnBoard[colBoard].node(name).Column[colChan].get()

                for rowIndex in range(len(self._config.rowMap)):

                    ret[colIndex][rowIndex] = self.HardwareGroup.ColumnBoard[colBoard].node(name).node(f'Col{colChan}_Row[{rowIndex}]').get(read=False)

            return ret

    # Set SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasSet(self, value, write, index):
        self._fastDacSet('SQ1Bais', value, write, index)

    # Get SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasGet(self, read, index):
        return self._fastDacGet('SQ1Bais', read, index)

    # Set SQ1 FB value, index is (column, row) tuple
    def _sq1FbSet(self, value, write, index):
        self._fastDacSet('SQ1Fb', value, write, index)

    # Get SQ1 FB value, index is (column, row) tuple
    def _sq1FbGet(self, read, index):
        return self._fastDacGet('SQ1Fb', read, index)

    # Set FAS Flux Off value, index is row
    def _fasFluxOffSet(self, value, write, index):

        # index access
        if index != -1:
            board = self._config.rowMap[index].board
            chan = self._config.rowMap[index].channel

            #self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.set(value=value, write=write)

        # Full array access
        else:

            for idx in range(len(self._config.rowMap)):
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.set(value=value[idx], write=write)

    # Get FAS Flux value
    def _fasFluxOffGet(self, read, index):

        # index access
        if index != -1:
            board = self._config.rowMap[index].board
            chan = self._config.rowMap[index].channel

            #return self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.get(index=index, read=read)
            return 0.0

        # Full array access
        else:
            ret = [0.0] * len(self._config.rowMap)

            for idx in range(len(self._config.rowMap)):
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #ret[idx] = self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.get(index=idx, read = read) #BEN
                ret[idx] = 0.0

            return ret

    # Set FAS Flux Off value, index is row
    def _fasFluxOnSet(self, value, write, index):

        # index access
        if index != -1:
            board = self._config.rowMap[index].board
            chan = self._config.rowMap[index].channel

            #return self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].ActiveValue.set(value=value, write=write)

        # Full array access
        else:

            for idx in range(len(self._config.rowMap)):
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #self.HardwareGroup.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].ActiveValue.set(value=value[idx],write=write)

    # Get FAS Flux value
    def _fasFluxOnGet(self, read, index):

        # index access
        if index != -1:
            board = self._config.rowMap[index].board
            chan = self._config.rowMap[index].channel

            #return self.HardwareGroup.RowBoard[board].FasFluxOn[chan].get(index= index, read=read)
            return 0.0

        # Full array access
        else:
            ret = [0.0] * len(self._config.rowMap)

            for idx in range(len(self._config.rowMap)):
                board = self._config.rowMap[index].board
                chan = self._config.rowMap[index].channel

                #ret[idx] = self.HardwareGroup.RowBoard[board].FasFluxOn[chan].get(index=index, read=read) #BEN
                ret[idx] = 0.0

            return ret

    # Set FLL Enable value
    def _fllEnableSet(self, value, write):

        for col in self.HardwareGroup.ColumnBoard:
            pass
            #col.FllEnable.set(value,write=write) # Does not exist yet

    # Get FLL Enable value
    def _fllEnableGet(self, read):

        #return self.HardwareGroup.ColumnBoard[0].FllEnable.get(read=read) # Does not exist yet
        return False

    # Init system
    def _init(self):

        # Local defaults
        #self.LoadConfig("defaults.yml")
        pass

        # Disable FLL
        self.FllEnable.set(value=False)

        # Drive high TES bias currents?????
        pass

