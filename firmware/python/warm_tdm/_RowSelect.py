import pyrogue as pr

class PhysicalRowSelect(pr.Device):


    
    def __init__(self, index, dacDevice, dacChannel, **kwargs):
        super().__init__(**kwargs)

        self.SRAM_START_ADDRS = [0x000, 0x400, 0x800, 0xC00]

        self._dacDevice = dacDevice
        self._dacChannel = dacChannel
        self._dacStopAddrVar = self._dacDevice.node(f'STOP_ADDR{dacChannel+1}')
        self._dacStartAddrVar = self._dacDevice.node(f'START_ADDR{dacChannel+1}')

        self.add(pr.LocalVariable(
            name = 'ActiveValue',
            value = 31))

        self.add(pr.LocalVariable(
            name = 'OffValue',
            value = 1))

        self.add(pr.LocalVariable(
            name = 'VirtualRow',
            value = index))
        

    def configure(self, readoutList):
        # Set the channel start and stop SRAM addrs
        readoutRows = len(readoutList)
        self._dacStartAddrVar.set(self.SRAM_START_ADDRS[self._dacChannel], write=True)
        self._dacStopAddrVar.set(self.SRAM_START_ADDRS[self._dacChannel] + readoutRows, write=True)

        # initialize the SRAM to always off
        sramList = [self.OffValue.value() for i in range(readoutRows)]

        # Turn on the row select as indicated by the readout list
        for i, rs in enumerate(readoutList):
            if rs == self.VirtualRow.value():
                sramList[i] = self.ActiveValue.value()

        # Determine where to write the list into SRAM
        start = self.SRAM_START_ADDRS[self._dacChannel]*4

        print(f'Setting SRAM start={start}, values = {sramList}')        
        self._dacDevice.SRAM.set(start, sramList, write=True)


    def setDacSram(self):
        # Create list of sequence values with everything set to OffValue at first
        values = [self.OffValue.value() for x in range(64)]

        print(f'Sequence: {self.Sequence.value()}')

        # Set the Sequence index to the active value
        values[self.Sequence.value()] = self.ActiveValue.value()

        # Determine where to write the list into SRAM
        start = self.SRAM_START_ADDRS[self._dacChannel]*4

        # Set the configuration
        print(f'Setting SRAM start={start}, values = {values}')
        self._dacDevice.SRAM.set(start, values, write=True)
        

#    def writeBlocks(self, **kwargs):
#        print(f'{self.path}.writeBlocks()')
#        self.setDacSram()

class RowSelectArray(pr.Device):
    def __init__(self, rowModules, **kwargs):
        """ This class maps an array of RowSelects to each physical DAC channel"""
        super().__init__(**kwargs)

        self._rowList = []

        for i, rowModule in enumerate(rowModules):
            for j in range(12):
                for k in range(4):
                    rs = PhysicalRowSelect(
                        name = f'RowSelect_{i}_{j}_{k}',
                        index = len(self._rowList),
                        dacDevice = rowModule.RowModuleDacs.Ad9106[j],
                        dacChannel = k)
                    self.add(rs)
                    self._rowList.append(rs)

    def configure(self, readoutList):
        for rs in self._rowList:
            rs.configure(readoutList)
                

class RowSelectMap(pr.Device):
    def __init__(self, rowSelectArray, numLogicalRows, **kwargs):
        """This class maps an array of logical RowSelects to each physical RowSelect"""
        super().__init__(**kwargs)

        self.rowSelectArray = rowSelectArray
        self.numLogicalRows = numLogicalRows

        for i in range(numLogicalRows):
            self.add(pr.LinkVariable(
                name = f'RowSelect[{i}]',
                type = tuple,
                linkedSet = self._rowSetFunc(i),
                linkedGet = self._rowGetFunc(i)))

        self.LogicalRowSelect = [None for x in range(numLogicalRows)]


    def _rowSetFunc(self, row):
        def _rowSet(value, index, write):
            i,j,k = value
            physicalRowSelect = self.rowSelectArray.node(f'RowSelect_{i}_{j}_{k}')
            physicalRowSelect.Sequence.set(row)
            self.LogicalRowSelect[row] = physicalRowSelect

            
