import pyrogue as pr

class Group(pr.Device):
    def __init__(self, rowMap, colMap, emulate=False, **kwargs):
        super().__init__(**kwargs)

        # Row map is a list of tuples containing (board, channel) values to map row indexes
        self._rowMap = rowMap

        # Col map is a list of tuples containing (board, channel) values to map col indexes
        self._colMap = colMap

        # Emulate flag
        self._emulate = emulate

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
        self.add(pr.LinkVariable(name='RowTuneEn',
                                 value=False,
                                 mode='RW',
                                 localSet=self._rowTuneEnSet,
                                 localGet=self._rowTuneEnGet,
                                 description="Row Tune Enable"))

        # Row Tune Channel
        self.add(pr.LinkVariable(name='RowTuneIndex',
                                 value=0,
                                 mode='RW',
                                 localSet=self._rowTuneIdxSet,
                                 localGet=self._rowTuneIdxGet,
                                 description="Row Tune Index"))

        # Row Tune Mode (On/Off)
        self.add(pr.LinkVariable(name='RowTuneMode',
                                 value=False,
                                 mode='RW',
                                 localSet=self._rowTuneModeSet,
                                 localGet=self._rowTuneModeGet,
                                 description="Row Tune Mode"))

        # TES Bias values, accessed with column index value
        self.add(pr.LinkVariable(name='TesBias',
                                 mode='RW',
                                 localSet=self._saBiasSet,
                                 localGet=self._saBiasGet))

        # SA Bias values, accessed with column index value
        self.add(pr.LinkVariable(name='SaBias',
                                 mode='RW',
                                 localSet=self._saBiasSet,
                                 localGet=self._saBiasGet))

        # SA Offset values, accessed with column index value
        self.add(pr.LinkVariable(name='SaOffset',
                                 mode='RW',
                                 localSet=self._saOffsetSet,
                                 localGet=self._saOffsetGet))

        # SA Out values, accessed with column index value
        self.add(pr.LinkVariable(name='SaOut',
                                 mode='RO',
                                 localGet=self._saOutGet))

        # SA FB values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='SaFb',
                                 mode='RW',
                                 localSet=self._saFbSet,
                                 localGet=self._saFbGet))

        # SQ1 Bias values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='Sq1Bias',
                                 mode='RW',
                                 localSet=self._sq1BiasSet,
                                 localGet=self._sq1BiasGet))

        # SQ1 Fb values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='Sq1Fb',
                                 mode='RW',
                                 localSet=self._sq1FbSet,
                                 localGet=self._sq1FbGet))

        # FAS Flux off values, accessed with row index
        self.add(pr.LinkVariable(name='FasFluxOff',
                                 mode='RW',
                                 localSet=self._fasFluxOffSet,
                                 localGet=self._fasFluxOffGet))

        # FAS Flux on values, accessed with row index
        self.add(pr.LinkVariable(name='FasFluxOn',
                                 mode='RW',
                                 localSet=self._fasFluxOnSet,
                                 localGet=self._fasFluxOnGet))

        # FLL Enable value
        self.add(pr.LinkVariable(name='FllEnable',
                                 mode='RW',
                                 localSet=self._fllEnableSet,
                                 localGet=self._fllEnableGet))

        if self._emulate:
            self._tuneEn     = False
            self._tuneIdx    = 0
            self._tuneMode   = False
            self._tesBias    = [0.0] * self._colMap
            self._saBias     = [0.0] * self._colMap
            self._saOffset   = [0.0] * self._colMap
            self._saOut      = [0.0] * self._colMap
            self._sq1Bias    = [[0.0] * self._rowMap] * self._colMap
            self._sq1Fb      = [[0.0] * self._rowMap] * self._colMap
            self._fasFluxOff = [[0.0] * self._rowMap] * self._colMap
            self._fasFluxOn  = [[0.0] * self._rowMap] * self._colMap
            self._fllEnable  = False


    # Set Row Tune Override
    def _rowTuneEnSet(self, value, write):

        if self._emulate is True:
            self._tuneEn = value

        else:
            for col in self.Hardware.ColumnBoard:
                col.RowTuneEn.set(value,write=write)

            for row in self.Hardware.RowBoard:
                row.RowTuneEn.set(value,write=write)


    # Get Row Tune Override
    def _rowTuneEnGet(self, read):

        if self._emulate is True:
            return self._tuneEn

        else:
            return self.Hardware.RowBoard[0].RowTuneEn.get(read=read)


    # Set Row Tune Index
    def _rowTuneIdxSet(self, value, write):

        if self._emulate is True:
            self._tuneIdx = value

        else:
            for col in self.Hardware.ColumnBoard:
                col.RowTuneIdx.set(value,write=write)

            for row in self.Hardware.RowBoard:
                row.RowTuneIdx.set(value,write=write)


    # Get Row Tune Index
    def _rowTuneIdxGet(self, read):

        if self._emulate is True:
            return self._tuneIdx

        else:
            return self.Hardware.RowBoard[0].RowTuneIdx.get(read=read)


    # Set Row Tune Mode
    def _rowTuneModeSet(self, value, write):

        if self._emulate is True:
            self._tuneMode = value

        else:
            for row in self.Hardware.RowBoard:
                row.RowTuneMode.set(value,write=write)


    # Get Row Tune Mode
    def _rowTuneModeGet(self, read):

        if self._emulate is True:
            return self._tuneMode

        else:
            return self.Hardware.RowBoard[0].RowTuneMode.get(read=read)


    # Set TES bias value, index is column
    def _tesBiasSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            if self._emulate is True:
                self._tesBias[index] = value
            else:
                self.Hardware.ColumnBoard[board].TesBias[chan].set(value=value,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._tesBias[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].TesBias[chan].set(value=value[idx],write=write)


    # Get TES bias value, index is column
    def _tesBiasGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._tesBias[index]
            else:
                return self.Hardware.ColumnBoard[board].TesBias[chan].get(read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._tesBias[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].TesBias[chan].value(read=read)

            return ret


    # Set SA Bias value, index is column
    def _saBiasSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                self._saBias[index] = value
            else:
                self.Hardware.ColumnBoard[board].SaBias[chan].set(value=value,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._saBias[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].SaBias[chan].set(value=value[idx],write=write)


    # Get SA Bias value, index is column
    def _saBiasGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._saBias[index]
            else:
                return self.Hardware.ColumnBoard[board].SaBias[chan].get(read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._saBias[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].SaBias[chan].value(read=read)

            return ret


    # Set SA Offset value, index is column
    def _saOffsetSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                self._saOffset[index] = value
            else:
                self.Hardware.ColumnBoard[board].SaOffset[chan].set(value=value,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._saOffset[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].SaOffset[chan].set(value=value[idx],write=write)


    # Get SA Offset value, index is column
    def _saOffsetGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._saOffset[index]
            else:
                return self.Hardware.ColumnBoard[board].SaOffset[chan].get(read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._saOffset[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].SaOffset[chan].value(read=read)

            return ret


    # Get SA Out value, index is column
    def _saOutGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._saOut[index]
            else:
                return self.Hardware.ColumnBoard[board].SaOut[chan].get(read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._saOut[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].SaOut[chan].value(read=read)

            return ret


    # Set SA Feedback value, index is (column, row) tuple
    def _saFbSet(self, value, write, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap(colIndex)

            if self._emulate is True:
                self._saFb[colIndex][rowIndex] = value
            else:
                self.Hardware.ColumnBoard[colBoard].SaFb[colChan].set(value=value,index=rowIndex,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap(colIndex)

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
            colBoard, colChan = self._colMap(colIndex)

            if self._emulate is True:
                return self._saFb[colIndex][rowIndex]
            else:
                return self.Hardware.ColumnBoard[colBoard].SaFb[colChan].get(index=rowIndex,read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._rowMap)] * len(self._colMap)

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap(colIndex)

                # Force reads
                if read is True:
                    self.Hardware.ColumnBoard[colBoard].SaFb[colChan].get()

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        ret[colIndex][rowIndex] = self._saFb[colIndex][rowIndex]
                    else:
                        ret[colIndex][rowIndex] = self.Hardware.ColumnBoard[colBoard].SaFb[colChan].get(index=rowIndex,read=False)

            return ret



    # Set SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasSet(self, value, write, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap(colIndex)

            if self._emulate is True:
                self._sq1Bias[colIndex][rowIndex] = value
            else:
                self.Hardware.ColumnBoard[colBoard].Sq1Bias[colChan].set(value=value,index=rowIndex,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap(colIndex)

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        self._sq1Bias[colIndex][rowIndex] = value[colIndex][rowIndex]
                    else:
                        self.Hardware.ColumnBoard[colBoard].Sq1Bias[colChan].set(value=value[colIndex][rowIndex],index=rowIndex,write=False)

                # Force writes
                if self._emulate is False and write is True:
                    self.Hardware.ColumnBoard[colBoard].Sq1Bias[colChan].write()


    # Get SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasGet(self, read, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap(colIndex)

            if self._emulate is True:
                return self._sq1Bias[colIndex][rowIndex]
            else:
                return self.Hardware.ColumnBoard[colBoard].Sq1Bias[colChan].get(index=rowIndex,read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._rowMap)] * len(self._colMap)

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap(colIndex)

                # Force reads
                if read is True:
                    self.Hardware.ColumnBoard[colBoard].Sq1Bias[colChan].get()

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        ret[colIndex][rowIndex] = self._sq1Bias[colIndex][rowIndex]
                    else:
                        ret[colIndex][rowIndex] = self.Hardware.ColumnBoard[colBoard].Sq1Bias[colChan].get(index=rowIndex,read=False)

            return ret


    # Set SQ1 FB value, index is (column, row) tuple
    def _sq1FbSet(self, value, write, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap(colIndex)

            if self._emulate is True:
                self._sq1Fb[colIndex][rowIndex] = value
            else:
                self.Hardware.ColumnBoard[colBoard].Sq1Fb[colChan].set(value=value,index=rowIndex,write=write)

        # Full array access
        else:

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap(colIndex)

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        self._sq1Fb[colIndex][rowIndex] = value[colIndex][rowIndex]
                    else:
                        self.Hardware.ColumnBoard[colBoard].Sq1Fb[colChan].set(value=value[colIndex][rowIndex],index=rowIndex,write=False)

                # Force writes
                if self._emulate is False and write is True:
                    self.Hardware.ColumnBoard[colBoard].Sq1Fb[colChan].write()


    # Get SQ1 FB value, index is (column, row) tuple
    def _sq1FbGet(self, read, index):

        # index access
        if index != -1:
            colIndex = index[0]
            rowIndex = index[1]
            colBoard, colChan = self._colMap(colIndex)

            if self._emulate is True:
                return self._sq1Fb[colIndex][rowIndex]
            else:
                return self.Hardware.ColumnBoard[colBoard].Sq1Fb[colChan].get(index=rowIndex,read=read)

        # Full array access
        else:
            ret = [[0.0] * len(self._rowMap)] * len(self._colMap)

            for colIndex in range(len(self._colMap)):
                colBoard, colChan = self._colMap(colIndex)

                # Force reads
                if read is True:
                    self.Hardware.ColumnBoard[colBoard].Sq1Fb[colChan].get()

                for rowIndex in range(len(self._rowMap)):

                    if self._emulate is True:
                        ret[colIndex][rowIndex] = self._sq1Fb[colIndex][rowIndex]
                    else:
                        ret[colIndex][rowIndex] = self.Hardware.ColumnBoard[colBoard].Sq1Fb[colChan].get(index=rowIndex,read=False)

            return ret


    # Set FAS Flux Off value, index is row
    def _fasFluxOffSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._rowMap(index)

            if self._emulate is True:
                self._fasFluxOff[index] = value
            else:
                self.Hardware.RowBoard[board].FasFluxOff[chan].set(value=value,write=write)

        # Full array access
        else:

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap(idx)

                if self._emulate is True:
                    self._fasFluxOff[idx] = value[idx]
                else:
                    self.Hardware.RowBoard[board].FasFluxOff[chan].set(value=value[idx],write=write)


    # Get FAS Flux value
    def _fasFluxOffGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._rowMap(index)

            if self._emulate is True:
                return self._fasFluxOff[index]
            else:
                return self.Hardware.RowBoard[board].FasFluxOff[chan].get(read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._rowMap)

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap(idx)

                if self._emulate is True:
                    ret[idx] = self._fasFluxOff[idx]
                else:
                    ret[idx] = self.Hardware.RowBoard[board].FasFluxOff[chan].get(read=read)

            return ret


    # Set FAS Flux Off value, index is row
    def _fasFluxOnSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._rowMap(index)

            if self._emulate is True:
                self._fasFluxOn[index] = value
            else:
                self.Hardware.RowBoard[board].FasFluxOn[chan].set(value=value,write=write)

        # Full array access
        else:

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap(idx)

                if self._emulate is True:
                    self._fasFluxOn[idx] = value[idx]
                else:
                    self.Hardware.RowBoard[board].FasFluxOn[chan].set(value=value[idx],write=write)


    # Get FAS Flux value
    def _fasFluxOnGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._rowMap(index)

            if self._emulate is True:
                return self._fasFluxOn[index]
            else:
                return self.Hardware.RowBoard[board].FasFluxOn[chan].get(read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._rowMap)

            for idx in range(len(self._rowMap)):
                board, chan = self._rowMap(idx)

                if self._emulate is True:
                    ret[idx] = self._fasFluxOn[idx]
                else:
                    ret[idx] = self.Hardware.RowBoard[board].FasFluxOn[chan].get(read=read)

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

