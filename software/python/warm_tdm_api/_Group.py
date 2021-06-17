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

        # TES Bias values, accessed with index value
        self.add(pr.LinkVariable(name='TesBias',
                                 mode='RW',
                                 localSet=self._saBiasSet,
                                 localGet=self._saBiasGet))

        # SA Bias values, accessed with index value
        self.add(pr.LinkVariable(name='SaBias',
                                 mode='RW',
                                 localSet=self._saBiasSet,
                                 localGet=self._saBiasGet))

        # SA Offset values, accessed with index value
        self.add(pr.LinkVariable(name='SaOffset',
                                 mode='RW',
                                 localSet=self._saOffsetSet,
                                 localGet=self._saOffsetGet))

        # SA Out values, accessed with index value
        self.add(pr.LinkVariable(name='SaOut',
                                 mode='RO',
                                 localGet=self._saOutGet))

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

        # FAS Flux off values, accessed with index tuple (column, row)
        self.add(pr.LinkVariable(name='FasFluxOff',
                                 mode='RW',
                                 localSet=self._fasFluxOffSet,
                                 localGet=self._fasFluxOffGet))

        # FAS Flux on values, accessed with index tuple (column, row)
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
            self._tesBias    = [0.0] * self._colMap
            self._saBias     = [0.0] * self._colMap
            self._saOffset   = [0.0] * self._colMap
            self._saOut      = [0.0] * self._colMap
            self._sq1Bias    = [[0.0] * self._rowMap] * self._colMap
            self._sq1Fb      = [[0.0] * self._rowMap] * self._colMap
            self._fasFluxOff = [[0.0] * self._rowMap] * self._colMap
            self._fasFluxOn  = [[0.0] * self._rowMap] * self._colMap
            self._fllEnable  = False


    # Set TES bias value, index is column
    def _tesBiasSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            if self._emulate is True:
                self._tesBias[index] = value
            else:
                self.Hardware.ColumnBoard[board].TesBias.set(value=value,index=chan,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._tesBias[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].TesBias.set(value=value[idx],index=chan,write=False)

            # Force writes
            if self._emulate is False and write is True:
                for col in self.Hardware.ColumnBoard:
                    col.TesBias.write()


    # Get TES bias value, index is column
    def _tesBiasGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._tesBias[index]
            else:
                return self.Hardware.ColumnBoard[board].TesBias.get(index=chan,read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if self._emulate is False and read is True:
                for col in self.Hardware.ColumnBoard:
                    col.TesBias.get()

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._tesBias[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].TesBias.value(index=chan)

            return ret


    # Set SA Bias value, index is column
    def _saBiasSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                self._saBias[index] = value
            else:
                self.Hardware.ColumnBoard[board].SaBias.set(value=value,index=chan,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._saBias[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].SaBias.set(value=value[idx],index=chan,write=False)

            # Force writes
            if self._emulate is False and write is True:
                for col in self.Hardware.ColumnBoard:
                    col.SaBias.write()


    # Get SA Bias value, index is column
    def _saBiasGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._saBias[index]
            else:
                return self.Hardware.ColumnBoard[board].SaBias.get(index=chan,read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if self._emulate is False and read is True:
                for col in self.Hardware.ColumnBoard:
                    col.SaBias.get()

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._saBias[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].SaBias.value(index=chan)

            return ret


    # Set SA Offset value, index is column
    def _saOffsetSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                self._saOffset[index] = value
            else:
                self.Hardware.ColumnBoard[board].SaOffset.set(value=value,index=chan,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._saOffset[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].SaOffset.set(value=value[idx],index=chan,write=False)

            # Force writes
            if self._emulate is False and write is True:
                for col in self.Hardware.ColumnBoard:
                    col.SaOffset.write()


    # Get SA Offset value, index is column
    def _saOffsetGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._saOffset[index]
            else:
                return self.Hardware.ColumnBoard[board].SaOffset.get(index=chan,read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if self._emulate is False and read is True:
                for col in self.Hardware.ColumnBoard:
                    col.SaOffset.get()

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._saOffset[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].SaOffset.value(index=chan)

            return ret


    # Get SA Out value, index is column
    def _saOutGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)

            if self._emulate is True:
                return self._saOut[index]
            else:
                return self.Hardware.ColumnBoard[board].SaOut.get(index=chan,read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if self._emulate is False and read is True:
                for col in self.Hardware.ColumnBoard:
                    col.SaOut.get()

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    ret[idx] = self._saOut[idx]
                else:
                    ret[idx] = self.Hardware.ColumnBoard[board].SaOut.value(index=chan)

            return ret


    # Set SQ1 Bias value, index is (column, row) tuple
    def _sq1BiasSet(self, value, write, index):

        # index access
        if index != -1:
            rowBoard, rowChan = self._colMap(index)

            if self._emulate is True:
                self._sq1Bias[index] = value
            else:
                self.Hardware.ColumnBoard[board].Sq1Bias.set(value=value,index=chan,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                if self._emulate is True:
                    self._sq1Bias[idx] = value[idx]
                else:
                    self.Hardware.ColumnBoard[board].Sq1Bias.set(value=value[idx],index=chan,write=False)

            # Force writes
            if self._emulate is False and write is True:
                for col in self.Hardware.ColumnBoard:
                    col.Sq1Bias.write()


    # Get SQ1 Bias value
    def _sq1BiasGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # return self.Hardware.ColumnBoard[board].Sq1Bias.get(index=chan,read=read)
            return self._sq1Bias[index]

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if read is True:
                for col in self.Hardware.ColumnBoard:
                    # col.Sq1Bias.get()
                    pass

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # ret[idx] = self.Hardware.ColumnBoard[board].Sq1Bias.value(index=chan)
                ret[idx] = self._sq1Bias[idx]

            return ret


    # Set SQ1 Fb value
    def _sq1FbSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # self.Hardware.ColumnBoard[board].Sq1Fb.set(value=value,index=chan,write=write)
            self._sq1Fb[index] = value

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # self.Hardware.ColumnBoard[board].Sq1Fb.set(value=value[idx],index=chan,write=False)
                self._sq1Fb[idx] = value[idx]

            # Force writes
            if write is True:
                for col in self.Hardware.ColumnBoard:
                    # col.Sq1Fb.write()
                    pass


    # Get SQ1 Fb value
    def _sq1FbGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # return self.Hardware.ColumnBoard[board].Sq1Fb.get(index=chan,read=read)
            return self._sq1Fb[index]

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if read is True:
                for col in self.Hardware.ColumnBoard:
                    # col.Sq1Fb.get()
                    pass

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # ret[idx] = self.Hardware.ColumnBoard[board].Sq1Fb.value(index=chan)
                ret[idx] = self._sq1Fb[idx]

            return ret


    # Set FAS Flux Off value
    def _fasFluxOffSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # self.Hardware.ColumnBoard[board].FasFluxOff.set(value=value,index=chan,write=write)
            self._fasFluxOff[index] = value

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # self.Hardware.ColumnBoard[board].FasFluxOff.set(value=value[idx],index=chan,write=False)
                self._fasFluxOff[idx] = value[idx]

            # Force writes
            if write is True:
                for col in self.Hardware.ColumnBoard:
                    # col.FasFluxOff.write()
                    pass


    # Get FAS Flux value
    def _fasFluxOffGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # return self.Hardware.ColumnBoard[board].FasFluxOff.get(index=chan,read=read)
            return self._fasFluxOff[index]

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if read is True:
                for col in self.Hardware.ColumnBoard:
                    # col.FasFluxOff.get()
                    pass

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # ret[idx] = self.Hardware.ColumnBoard[board].FasFluxOff.value(index=chan)
                ret[idx] = self._fasFluxOff[idx]

            return ret


    # Set FAS Flux On value
    def _fasFluxOnSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # self.Hardware.ColumnBoard[board].FasFluxOn.set(value=value,index=chan,write=write)
            self._fasFluxOn[index] = value

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # self.Hardware.ColumnBoard[board].FasFluxOn.set(value=value[idx],index=chan,write=False)
                self._fasFluxOn[idx] = value[idx]

            # Force writes
            if write is True:
                for col in self.Hardware.ColumnBoard:
                    # col.FasFluxOn.write()
                    pass


    # Get FAS Flux value
    def _fasFluxOnGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # return self.Hardware.ColumnBoard[board].FasFluxOn.get(index=chan,read=read)
            return self._fasFluxOn[index]

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if read is True:
                for col in self.Hardware.ColumnBoard:
                    # col.FasFluxOn.get()
                    pass

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # ret[idx] = self.Hardware.ColumnBoard[board].FasFluxOn.value(index=chan)
                ret[idx] = self._fasFluxOn[idx]

            return ret


    # Set FLL Enable value
    def _fllEnableSet(self, value, write):

        for idx in range(len(self._colMap)):
            board, chan = self._colMap(idx)

            # self.Hardware.ColumnBoard[board].FasFluxOn.set(value=value[idx],index=chan,write=False)
            self._fasFluxOn[idx] = value[idx]

        # Force writes
        if write is True:
            for col in self.Hardware.ColumnBoard:
                # col.FasFluxOn.write()
                pass


    # Get FLL Enable value
    def _fllEnableGet(self, read):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            # return self.Hardware.ColumnBoard[board].FasFluxOn.get(index=chan,read=read)
            return self._fasFluxOn[index]

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if read is True:
                for col in self.Hardware.ColumnBoard:
                    # col.FasFluxOn.get()
                    pass

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                # ret[idx] = self.Hardware.ColumnBoard[board].FasFluxOn.value(index=chan)
                ret[idx] = self._fasFluxOn[idx]

            return ret





