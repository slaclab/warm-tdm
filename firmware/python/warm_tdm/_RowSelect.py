import pyrogue as pr

class PhysicalRowSelect(pr.Device):
    
    def __init__(self, index, dacDevice, dacChannel, fsRange=4.0e-3, dacLoad=100, gain=6, **kwargs):
        super().__init__(**kwargs)

        self.SRAM_START_ADDRS = [0x000, 0x400, 0x800, 0xC00]

        self._dacDevice = dacDevice
        self._dacChannel = dacChannel
        self._dacStopAddrVar = self._dacDevice.node(f'STOP_ADDR{dacChannel+1}')
        self._dacStartAddrVar = self._dacDevice.node(f'START_ADDR{dacChannel+1}')

        # These assume certain DAC gain settings
        def convVoltage(adc):
            pass

        def convAdc(voltage):
            pass

        self.add(pr.LocalVariable(
            name = 'OnValue',
            disp = '0x{:04x}',
            value = 0x7ff))

        self.add(pr.LocalVariable(
            name = 'OffValue',
            disp = '0x{:04x}',            
            value = 0x800))

        self.add(pr.LocalVariable(
            name = 'LogicalRow',
            value = index))
        

    def configure(self, readoutList):
        # Set the channel start and stop SRAM addrs
        readoutRows = len(readoutList)
        self._dacStartAddrVar.set(self.SRAM_START_ADDRS[self._dacChannel], write=True)
        #self._dacStopAddrVar.set(self.SRAM_START_ADDRS[self._dacChannel] + readoutRows - 1, write=True)
        self._dacStopAddrVar.set(self.SRAM_START_ADDRS[self._dacChannel] + 1024 - 1, write=True)        
        self._dacDevice.PATTERN_PERIOD.set(1024, write=True)
        self._dacDevice.HOLD.set(0, write=True)  # Hold each sample for 16 cycles      

        # initialize the SRAM to always off
        sramList = [self.OffValue.value() << 4 for i in range(1024)]

        # Turn on the row select as indicated by the readout list
        for i, rs in enumerate(readoutList):
            if rs == self.VirtualRow.value():
                for j in range(i*16, i*16+16):
                    sramList[j] = self.ActiveValue.value() << 4

        # Determine where to write the list into SRAM
        start = self.SRAM_START_ADDRS[self._dacChannel]*4

#        print(f'Setting SRAM start=0x{start:0dx}, values = {[hex(x) for x in sramList]}')        
        self._dacDevice.SRAM.set(start, sramList, write=True)



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

            
