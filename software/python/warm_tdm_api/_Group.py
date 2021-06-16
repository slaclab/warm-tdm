import pyrogue as pr

class Group(pr.Device):
    def __init__(self, rowMap, colMap, **kwargs):
        super().__init__(**kwargs)

        # Row map is a list of tuples containing (board, channel) values to map row indexes
        self._rowMap = rowMap

        # Col map is a list of tuples containing (board, channel) values to map col indexes
        self._colMap = colMap


        # Number of columns supported in this group
        self.add(pr.LocalVariable(name='numColumns', value=len(self._colMap), mode='RO',description="Number of columns"))

        # Number of rows supported in this group
        self.add(pr.LocalVariable(name='numRows', value=len(self._rowMap), mode='RO',description="Number of rows"))

        # TES Bias values, accessed with index value
        self.add(pr.LinkVariable(name='tesBias', value=[0.0]*32, mode='RW',
                                 localSet=self._tesBiasSet,
                                 localGet=self._tesBiasGet))











    # Set TES bias value
    def _tesBiasSet(self, value, write, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            self.Hardware.ColumnBoard[board].TesBias.set(value=value,index=chan,write=write)

        # Full array access
        else:

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                self.Hardware.ColumnBoard[board].TesBias.set(value=value[idx],index=chan,write=False)

            # Force writes
            if write is True:
                for col in self.Hardware.ColumnBoard:
                    col.TesBias.write()


    # Get TES bias value
    def _tesBiasGet(self, read, index):

        # index access
        if index != -1:
            board, chan = self._colMap(index)
            return self.Hardware.ColumnBoard[board].TesBias.get(index=chan,read=read)

        # Full array access
        else:
            ret = [0.0] * len(self._colMap)

            # Force reads
            if read is True:
                for col in self.Hardware.ColumnBoard:
                    col.TesBias.get()

            for idx in range(len(self._colMap)):
                board, chan = self._colMap(idx)

                ret[idx] = self.Hardware.ColumnBoard[board].TesBias.value(index=chan)

            return ret


