import pyrogue as pr

class Ad9106RowSelect(pr.Device):
    
    def __init__(self, index, dacDevice, dacChannel, fsRange=4.0e-3, dacLoad=100, gain=6, **kwargs):
        super().__init__(**kwargs)

        self.SRAM_START_ADDRS = [0x000, 0x400, 0x800, 0xC00]

        self._dacDevice = dacDevice
        self._dacChannel = dacChannel
        self._dacStopAddrVar = self._dacDevice.node(f'STOP_ADDR{dacChannel+1}')
        self._dacStartAddrVar = self._dacDevice.node(f'START_ADDR{dacChannel+1}')
        self._dacWaveSelVar = self._dacDevice.node(f'WAVE_SEL{dacChannel+1}')
        self._dacConstVar = self._dacDevice.node(f'DAC{dacChannel+1}_CONST')

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

        # Not sure if this is needed
        # could probably be a python variable
        self.add(pr.LocalVariable(
            name = 'RowNumber',
            mode = 'RO',
            value = index))

        self.add(pr.LinkVariable(
            name = 'Mode',
            value = 'Run',
            dependencies = [self._dacWaveSelVar, self._dacConstVar],
            linkedGet = self._getMode,
            linkedSet = self._setMode,
            enum = {
                'Run': 'Run',
                'Tune': 'Tune'}))

        self.add(pr.LinkVariable(
            name='Active',
            value = False,
            dependencies = [self._dacConstVar],
            linkedGet = lambda: self._active,
            linkedSet = self._setActive))
        
    def _setMode(self, *, value, write):
        self._mode = value
        if value == 'Run':
            self._dacWaveSelVar.setDisp('RAM', write=write)
        elif value == 'Force':
            self._dacConstVar.set(value=self.OffValue.value(), write=write)
            self._dacWaveSelVar.setDisp('Prestored', write=write)

    def _getMode(self):
        return self._mode

    def _setActive(self, *, value, write):
        self._active = value            
        setValue = self.OffValue.value() if value is False else self.OnValue.value()
        self._dacConstVar.set(value=setValue, write=write)

        
    def setReadoutList(self, readoutList):
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
            if rs == self.RowNumber.value():
                for j in range(i*16, i*16+16):
                    sramList[j] = self.OnValue.value() << 4

        # Determine where to write the list into SRAM
        start = self.SRAM_START_ADDRS[self._dacChannel]*4

#        print(f'Setting SRAM start=0x{start:0dx}, values = {[hex(x) for x in sramList]}')        
        self._dacDevice.SRAM.set(start, sramList, write=True)


# Each RowModule will instantiate this class to create
# an array of (48) RowSelect Devices
class RowSelectArray(pr.Device):
    def __init__(self, rowModule, **kwargs):
        super().__init__(**kwargs)

        self._rowList = []

        for j in range(12):
            for k in range(4):
                idx = len(self._rowList)
                rs = Ad9106RowSelect(
                    name = f'RowSelect[{idx}]',
                    index = idx,
                    dacDevice = rowModule.RowModuleDacs.Ad9106[j],
                    dacChannel = k)
                self.add(rs)
                self._rowList.append(rs)

    def setReadoutList(self, readoutList):
        for rs in self._rowList:
            rs.setReadoutList(readoutList)
                

