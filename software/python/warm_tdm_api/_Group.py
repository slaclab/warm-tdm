import pyrogue as pr

class Group(pr.Device):
    def __init__(self, rowMap, colMap, rowOrder=None, colEnable=None, emulate=False, **kwargs):
        super().__init__(**kwargs)

        # Row map is a list of tuples containing (board, channel) values to map row indexes
        self._rowMap = rowMap

        # Col map is a list of tuples containing (board, channel) values to map col indexes
        self._colMap = colMap

        # If row order is not passed, assume map order
        if rowOrder is None:
            self._rowOrder = [i for i in range(len(self._rowMap))]
        else:
            self._rowOrder = rowOrder

        # If col enable is not passed, assume all are enabled
        if colEnable is None:
            self._colEnable = [True] * len(self._rowMap)
        else:
            self._colEnable = colEnable

        # Emulate flag
        self._emulate = emulate

        # Row Map
        self.add(pr.LocalVariable(name='RowMap',
                                  localGet=lambda: self._rowMap,
                                  mode='RO',
                                  description="Row Map"))

        # Col Map
        self.add(pr.LocalVariable(name='ColMap',
                                  localGet=lambda: self._colMap,
                                  mode='RO',
                                  description="Column Map"))

        # Row Order
        self.add(pr.LocalVariable(name='RowOrder',
                                  localGet=lambda: self._rowOrder,
                                  mode='RO',
                                  description="Row Order"))

        # Col Enable
        self.add(pr.LocalVariable(name='ColEnable',
                                  localGet=lambda: self._colEnable,
                                  mode='RO',
                                  description="Column Enable"))

        # Number of columns supported in this group
        self.add(pr.LocalVariable(name='NumColumns',
                                  value=len(self._colMap),
                                  mode='RO',
                                  description="Number of columns"))

        # Number of rows supported in this group
        self.add(pr.LocalVariable(name='NumRows',
                                  value=len(self._rowMap),
                                  mode='RO',
                                  description="Number of rows"))

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
                                  value=[True] * len(self._rowMap),
                                  mode='RW',
                                  description="Tune enable for each row"))

        # Tuning column enables
        self.add(pr.LocalVariable(name='ColTuneEnable',
                                  value=[True] * len(self._colMap),
                                  mode='RW',
                                  description="Tune enable for each column"))

        # Low offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SA FB Tuning"))

        # High offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SA FB Tuning"))

        # Step size for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for SA FB Tuning"))

        # Low offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SA Bias Tuning"))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SA Bias Tuning"))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for SA Bias Tuning"))

        # Low offset for Fas FLux Tuning
        self.add(pr.LocalVariable(name='FasFluxLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for Fas Flux Tuning"))

        # High offset for Fas Flux Tuning
        self.add(pr.LocalVariable(name='FasFluxHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for Fas Flux Tuning"))

        # Step size for Fas Flux Tuning
        self.add(pr.LocalVariable(name='FasFluxStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for Fas Flux Tuning"))

        # Low offset for SQ1 FB Tuning
        self.add(pr.LocalVariable(name='Sq1FbLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SQ1 FB Tuning"))

        # High offset for SQ1 FB Tuning
        self.add(pr.LocalVariable(name='Sq1FbHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SQ1 FB Tuning"))

        # Step size for SQ1 FB Tuning
        self.add(pr.LocalVariable(name='Sq1FbStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for SQ1 FB Tuning"))

        # Low offset for SQ1 Bias Tuning
        self.add(pr.LocalVariable(name='Sq1BiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SQ1 Bias Tuning"))

        # High offset for SQ1 Bias Tuning
        self.add(pr.LocalVariable(name='Sq1BiasHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SQ1 Bias Tuning"))

        # Step size for SQ1 Bias Tuning
        self.add(pr.LocalVariable(name='Sq1BiasStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for SQ1 Bias Tuning"))

        # Low offset for TES Bias Ramping
        self.add(pr.LocalVariable(name='TesBiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for TES Bias Ramping"))

        # High offset for SQ1 Bias Ramping
        self.add(pr.LocalVariable(name='TesBiasHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SQ1 Bias Ramping"))

        # Step size for SQ1 Bias Ramping
        self.add(pr.LocalVariable(name='TesBiasStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for SQ1 Bias Ramping"))

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

        # FLL Enable value
        self.add(pr.LinkVariable(name='FllEnable',
                                 mode='RW',
                                 typeStr='bool',
                                 linkedSet=self._fllEnableSet,
                                 linkedGet=self._fllEnableGet,
                                 description=""))

        # SA Tuning Results
        self.add(pr.LocalVariable(name='SaTuneOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From SA Tuning"))

        # FAS Tuning Results
        self.add(pr.LocalVariable(name='FasTuneOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From FAS Tuning"))

        # SQ1 Tuning Results
        self.add(pr.LocalVariable(name='Sq1TuneOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From SQ1 Tuning"))

        # SQ1 Diagnostic Results
        self.add(pr.LocalVariable(name='Sq1DiagOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From SQ1 Diagnostic"))

        # TES Diagnostic Results
        self.add(pr.LocalVariable(name='TesDiagOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From Tes Diagnostic"))

        # Initialize System
        self.add(pr.LocalCommand(name='Init',
                                 function=self._init,
                                 description="Initialize System"))

        if self._emulate:
            self._forceEn    = False
            self._forceIdx   = 0
            self._tesBias    = [0.0] * len(self._colMap)
            self._saBias     = [0.0] * len(self._colMap)
            self._saOffset   = [0.0] * len(self._colMap)
            self._saOut      = [0.0] * len(self._colMap)
            self._sq1Bias    = [[0.0] * len(self._rowMap)] * len(self._colMap)
            self._sq1Fb      = [[0.0] * len(self._rowMap)] * len(self._colMap)
            self._saFb       = [[0.0] * len(self._rowMap)] * len(self._colMap)
            self._fasFluxOff = [0.0] * len(self._rowMap)
            self._fasFluxOn  = [0.0] * len(self._rowMap)
            self._fllEnable  = False


    # Set Row Tune Override
    def _rowForceEnSet(self, value, write):

        if self._emulate is True:
            self._forceEn = value

        else:
            for col in self.Hardware.ColumnBoard:
                col.RowForceEn.set(value,write=write)

            for row in self.Hardware.RowBoard:
                row.RowForceEn.set(value,write=write)


    # Get Row Tune Override
    def _rowForceEnGet(self, read):

        if self._emulate is True:
            return self._forceEn

        else:
            return self.Hardware.RowBoard[0].RowForceEn.get(read=read)


    # Set Row Tune Index
    def _rowForceIdxSet(self, value, write):

        if self._emulate is True:
            self._forceIdx = value

        else:
            for col in self.Hardware.ColumnBoard:
                col.RowTuneIdx.set(value,write=write)

            for row in self.Hardware.RowBoard:
                row.RowTuneIdx.set(value,write=write)


    # Get Row Tune Index
    def _rowForceIdxGet(self, read):

        if self._emulate is True:
            return self._forceIdx

        else:
            return self.Hardware.RowBoard[0].RowTuneIdx.get(read=read)

    def __colSetLoopHelper(self, value, index):
        # Construct a generator to loop over
        if index != -1:
            return ((idx, self._colMap[idx], val) for idx, val in zip(range(index, index+1), [value]))
        else:
            return ((idx, self._colMap[idx], val) for idx, val in enumerate(value))

    def __colGetLoopHelper(self, index):
        # Construct a generator to loop over

        if index != -1:
            ra = range(index, index+1)
        else:
            ra = range(len(self._colMap))

        return ((idx, self._colMap[idx]) for idx in ra)



    # Set TES bias value, index is column
    def _tesBiasSet(self, value, write, index):
        for idx, (board, chan), val in self.__colSetLoopHelper(value, index):
            #print(f"Tes set {idx}, {board}, {chan}, {val}")

            if self._emulate is True:
                self._tesBias[idx] = val
            else:
                self.Hardware.ColumnBoard[board].TesBias.BiasCurrent[chan].set(value=value,write=write)



    # Get TES bias value, index is column
    def _tesBiasGet(self, read, index):
        ret = [0.0] * len(self._colMap)

        for idx, (board, chan) in self.__colGetLoopHelper(index):
            if self._emulate is True:
                ret[idx] = self._tesBias[idx]
            else:
                ret[idx] = self.Hardware.ColumnBoard[board].TesBias.BiasCurrent[chan].value(read=read)

            print(f"Tes get {idx}, {board}, {chan}, {ret[idx]}")

        if index != -1:
            return ret[index]
        else:
            return ret


    # Set SA Bias value, index is column
    def _saBiasSet(self, value, write, index):
        for idx, (board, chan), val in self.__colSetLoopHelper(value, index):
            if self._emulate is True:
                self._saBias[idx] = val
            else:
                self.Hardware.ColumnBoard[board].SaBiasOffset.Bias[chan].set(value=val, write=write)


    # Get SA Bias value, index is column
    def _saBiasGet(self, read, index):
        ret = [0.0] * len(self._colMap)

        for idx, (board, chan) in self.__colGetLoopHelper(index):
            if self._emulate is True:
                ret[idx] = self._saBias[idx]
            else:
                ret[idx] = self.Hardware.ColumnBoard[board].SaBiasOffset.Bias[chan].value(read=read)

        if index != -1:
            return ret[index]
        else:
            return ret


    # Set SA Offset value, index is column
    def _saOffsetSet(self, value, write, index):
        for idx, (board, chan), val in self.__colSetLoopHelper(value, index):
            if self._emulate is True:
                self._saOffset[idx] = val
            else:
                self.Hardware.ColumnBoard[board].SaBiasOffset.Offset[chan].set(value=val, write=write)


    # Get SA Offset value, index is column
    def _saOffsetGet(self, read, index):
        ret = [0.0] * len(self._colMap)

        for idx, (board, chan) in self.__colGetLoopHelper(index):
            if self._emulate is True:
                ret[idx] = self._saOffset[idx]
            else:
                ret[idx] = self.Hardware.ColumnBoard[board].SaBiasOffset.Offset[chan].value(read=read)

        if index != -1:
            return ret[index]
        else:
            return ret



    # Get SA Out value, index is column
    def _saOutGet(self, read, index):
        ret = [0.0] * len(self._colMap)

        for idx, (board, chan) in self.__colGetLoopHelper(index):
            if self._emulate is True:
                ret[idx] = self._saOut[idx]
            else:
                ret[idx] = self.Hardware.ColumnBoard[board].DataPath.Ad9681Readout.AdcVoltage[chan].get(read=read)

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
            colBoard, colChan = self._colMap[colIndex]

            if self._emulate is True:
                self._saFb[colIndex][rowIndex] = value
            else:
                self.Hardware.ColumnBoard[colBoard].SaFb[colChan].set(value=value,index=rowIndex,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap[colIndex]

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        self._saFb[colIndex][rowIndex] = value[colIndex][rowIndex]

                    else:
                        self.Hardware.ColumnBoard[colBoard].SaFb[colChan].set(value=value[colIndex][rowIndex],index=rowIndex,write=False)

                # Force writes
                if self._emulate is False and write is True:
                    self.Hardware.ColumnBoard[colBoard].SaFb[colChan].write()


    # Get SA Feedback value, index is (column, row) tuple
    def _saFbGet(self, read, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap[colIndex]

            if self._emulate is True:
                return self._saFb[colIndex][rowIndex]
            else:
                return self.Hardware.ColumnBoard[colBoard].SaFb[colChan].get(index=rowIndex,read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._rowMap)] * len(self._colMap)

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap[colIndex]

                # Force reads
                if read is True:
                    self.Hardware.ColumnBoard[colBoard].SaFb[colChan].get()

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        ret[colIndex][rowIndex] = self._saFb[colIndex][rowIndex]
                    else:
                        ret[colIndex][rowIndex] = self.Hardware.ColumnBoard[colBoard].SaFb[colChan].get(index=rowIndex,read=False)

            return ret




    # Set per row value, index is (column, row) tuple
    def _fastDacSet(self, name, value, write, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap[colIndex]

            if self._emulate is True:
                self._sq1Bias[colIndex][rowIndex] = value
            else:
                self.Hardware.ColumnBoard[colBoard].node(name).ChannelVoltage[colChan].set(value=value,index=rowIndex,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap[colIndex]

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        self._sq1Bias[colIndex][rowIndex] = value[colIndex][rowIndex]
                    else:
                        self.Hardware.ColumnBoard[colBoard].node(name).ChannelVoltage[colChan].set(value=value[colIndex][rowIndex],index=rowIndex,write=False)

                # Force writes
                if self._emulate is False and write is True:
                    self.Hardware.ColumnBoard[colBoard].node(name).ChannelVoltage[colChan].write()


    # Get per row value, index is (column, row) tuple
    def _fastDacGet(self, name, read, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap[colIndex]

            if self._emulate is True:
                return self._sq1Bias[colIndex][rowIndex]
            else:
                return self.Hardware.ColumnBoard[colBoard].node(name).ChannelVoltage[colChan].get(index=rowIndex,read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._rowMap)] * len(self._colMap)

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap[colIndex]

                # Force reads
                if read is True:
                    self.Hardware.ColumnBoard[colBoard].node(name).ChannelVoltage[colChan].get()

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        ret[colIndex][rowIndex] = self._sq1Bias[colIndex][rowIndex]
                    else:
                        ret[colIndex][rowIndex] = self.Hardware.ColumnBoard[colBoard].node(name).ChannelVoltage[colChan].get(index=rowIndex,read=False)

            return ret

    # Set SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasSet(self, value, write, index):
        self._fastDacSet('Sq1Bias', value, write, index)

    # Get SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasGet(self, read, index):
        return self._fastDacGet('Sq1Bias', read, index)


    # Set SQ1 FB value, index is (column, row) tuple
    def _sq1FbSet(self, value, write, index):
        self._fastDacSet('Sq1Fb', value, write, index)


    # Get SQ1 FB value, index is (column, row) tuple
    def _sq1FbGet(self, read, index):
        return self._fastDacGet('Sq1Fb', read, index)


    # Set FAS Flux Off value, index is row
    def _fasFluxOffSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._rowMap[index]

            if self._emulate is True:
                self._fasFluxOff[index] = value
            else:
                self.Hardware.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.set(value=value, write=write)

        # Full array access
        else:

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap[idx]

                if self._emulate is True:
                    self._fasFluxOff[idx] = value[idx]
                else:
                    self.Hardware.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.set(value=value[idx], write=write)


    # Get FAS Flux value
    def _fasFluxOffGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._rowMap[index]

            if self._emulate is True:
                return self._fasFluxOff[index]
            else:
                self.Hardware.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.get(index=index, read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._rowMap)

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap[idx]

                if self._emulate is True:
                    ret[idx] = self._fasFluxOff[idx]
                else:
                    ret[idx] = self.Hardware.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].OffValue.get(index=idx, read = read)

            return ret


    # Set FAS Flux Off value, index is row
    def _fasFluxOnSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._rowMap[index]

            if self._emulate is True:
                self._fasFluxOn[index] = value
            else:
                self.Hardware.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].ActiveValue.set(value=value, write=write)

        # Full array access
        else:

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap[idx]

                if self._emulate is True:
                    self._fasFluxOn[idx] = value[idx]
                else:
                    self.Hardware.RowBoard[board].RowSelectMap.LogicalRowSelect[chan].ActiveValue.set(value=value[idx],write=write)


    # Get FAS Flux value
    def _fasFluxOnGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._rowMap[index]

            if self._emulate is True:
                return self._fasFluxOn[index]
            else:
                return self.Hardware.RowBoard[board].FasFluxOn[chan].get(index= index, read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._rowMap)

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap[idx]

                if self._emulate is True:
                    ret[idx] = self._fasFluxOn[idx]
                else:
                    ret[idx] = self.Hardware.RowBoard[board].FasFluxOn[chan].get(index=index, read=read)

            return ret


    # Set FLL Enable value
    def _fllEnableSet(self, value, write):

        if self._emulate is True:
            self._fllEnable = value

        else:
            for col in self.Hardware.ColumnBoard:
                col.FllEnable.set(value,write=write)

    # Get FLL Enable value
    def _fllEnableGet(self, read):

        if self._emulate is True:
            return self._fllEnable

        else:
            return self.Hardware.ColumnBoard[0].FllEnable.get(read=read)

    # Init system
    def _init(self):

        # Local defaults
        #self.LoadConfig("defaults.yml")
        pass

        # Disable FLL
        self.FllEnable.set(value=False)

        # Drive high TES bias currents?????
        pass

