import pyrogue as pr
import rogue.interfaces.memory as rim

from collections import OrderedDict as odict

class Ad9106(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Register Offsets
        SPICONFIG = 0x00 *4
        POWERCONFIG = 0x01*4
        CLOCKCONFIG = 0x02*4
        REFADJ = 0x03*4
        DAC4AGAIN = 0x04*4
        DAC3AGAIN = 0x05*4
        DAC2AGAIN = 0x06*4
        DAC1AGAIN = 0x07*4
        DACxRANGE = 0x08*4
        DAC4RSET = 0x09*4
        DAC3RSET = 0x0A*4
        DAC2RSET = 0x0B*4
        DAC1RSET = 0x0C*4
        CALCONFIG = 0x0D*4
        COMPOFFSET = 0x0E*4
        RAMUPDATE = 0x1D*4
        PAT_STATUS = 0x1E*4
        PAT_TYPE = 0x1F*4
        PATTERN_DLY = 0x20*4
        DAC4DOF = 0x22*4
        DAC3DOF = 0x23*4
        DAC2DOF = 0x24*4
        DAC1DOF = 0x25*4
        WAV4_3CONFIG = 0x26*4
        WAV2_1CONFIG = 0x27*4
        PAT_TIMEBASE = 0x28*4
        PAT_PERIOD = 0x29*4
        DAC4_3PATx = 0x2A*4
        DAC2_1PATx = 0x2B*4
        DOUT_START_DLY = 0x2C*4
        DOUT_CONFIG = 0x2D*4
        DAC4_CST = 0x2E*4
        DAC3_CST = 0x2F*4
        DAC2_CST = 0x30*4
        DAC1_CST = 0x31*4
        DAC4_DGAIN = 0x32*4
        DAC3_DGAIN = 0x33*4
        DAC2_DGAIN = 0x34*4
        DAC1_DGAIN = 0x35*4
        SAW4_3CONFIG = 0x36*4
        SAW2_1CONFIG = 0x37*4
        DDS_TW32 = 0x3E*4
        DDS_TW1 = 0x3F*4
        DDS4_PW = 0x40*4
        DDS3_PW = 0x41*4
        DDS2_PW = 0x42*4
        DDS1_PW = 0x43*4
        TRIG_TW_SEL = 0x44*4
        DDSx_CONFIG = 0x45*4
        TW_RAM_CONFIG = 0x47*4
        START_DLY4 = 0x50*4
        START_ADDR4 = 0x51*4
        STOP_ADDR4 = 0x52*4
        DDS_CYC4 = 0x53*4
        START_DLY3 = 0x54*4
        START_ADDR3 = 0x55*4
        STOP_ADDR3 = 0x56*4
        DDS_CYC3 = 0x57*4
        START_DLY2 = 0x58*4
        START_ADDR2 = 0x59*4
        STOP_ADDR2 = 0x5A*4
        DDS_CYC2 = 0x5B*4
        START_DLY1 = 0x5C*4
        START_ADDR1 = 0x5D*4
        STOP_ADDR1 = 0x5E*4
        DDS_CYC1 = 0x5F*4
        CFG_ERROR = 0x60*4

        SRAM_DATA = 0x6000*4

        # SPICONFIG
        self.add(pr.RemoteVariable(
            name = 'LSBFIRST',
            mode = 'RW',
            offset = SPICONFIG,
            bitSize = 1,
            bitOffset = 15,
            hidden = True,
            base = pr.UInt,
            enum = {
                0: 'MSB First',
                1: 'LSB First'}))

        self.add(pr.RemoteVariable(
            name = 'SPI3WIRE',
            mode = 'RW',
            offset = SPICONFIG,
            bitSize = 1,
            bitOffset = 14,
            base = pr.UInt,
            enum = {
                0: '4-wire SPI',
                1: '3-wire SPI'}))

        self.add(pr.RemoteCommand(
            name = 'RESET',
            description = 'Executes software reset of SPI and controllers, reloads default register values, except for Register 0x00. ',
            offset = SPICONFIG,
            bitSize = 1,
            bitOffset = 13,
            base = pr.UInt,
            function = pr.RemoteCommand.toggle))

        self.add(pr.RemoteVariable(
            name = 'DOUBLESPI',
            description = '0 - SPI port has only one data line and can be used as a 3-wire or 4-wire interface. 1 - The SPI port has two data lines',
            mode = 'RW',
            offset = SPICONFIG,
            bitSize = 1,
            bitOffset = 12,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'SPI_DRV',
            mode = 'RW',
            offset = SPICONFIG,
            bitSize = 1,
            bitOffset = 11,
            base = pr.UInt,
            enum = {
                0: 'Single',
                1: 'Two-time'}))

        self.add(pr.RemoteVariable(
            name = 'DOUT_EN',
            description = 'Enable DOUT signal on SDO/SDI2/DOUT pin',
            mode = 'RW',
            offset = SPICONFIG,
            bitSize = 1,
            bitOffset = 10,
            base = pr.UInt,
            enum = {
                0: 'SDO/SDI2',
                1: 'DOUT'}))


        # POWERCONFIG
        self.add(pr.RemoteVariable(
            name = 'CLK_LDO_STAT',
            description = 'Flag indicating the 1.8V on-chip CLDO regulator is on',
            mode = 'RO',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 11,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DIG1_LDO_STAT',
            description = 'Flag indicating DVDD1 LDO is on',
            mode = 'RO',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 10,
            pollInterval = 5,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DIG2_LDO_STAT',
            description = 'Flag indicating DVDD2 LDO is on',
            mode = 'RO',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 9,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'PDN_LDO_CLK',
            description = 'Disables the 1.8V on-chip CLDO regulator. An external supply is required.',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 8,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'PDN_LDO_DIG1',
            description = 'Disables the DVDD1 LDO. An external supply is required.',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 7,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'PDN_LDO_DIG2',
            description = 'Disables the DVDD2 LDO. An external supply is required.',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 6,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'REF_PDN',
            description = 'Disables 10kOhm resistor that creates REFIO voltage.',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 5,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'REF_EXT',
            description = 'Power down main BG reference including DAC bias.',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 4,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC1_SLEEP',
            description = 'Disables DAC1 output current',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC2_SLEEP',
            description = 'Disables DAC2 output current',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 2,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC3_SLEEP',
            description = 'Disables DAC3 output current',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 1,
            base = pr.Bool))


        self.add(pr.RemoteVariable(
            name = 'DAC4_SLEEP',
            description = 'Disables DAC4 output current',
            mode = 'RW',
            offset = POWERCONFIG,
            bitSize = 1,
            bitOffset = 0,
            base = pr.Bool))

        #CLOCKCONFIG

        self.add(pr.RemoteVariable(
            name = 'DIS_CLK1',
            description = 'Disables the analog clock to DAC1 out of the clock distribution block.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 11,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DIS_CLK2',
            description = 'Disables the analog clock to DAC2 out of the clock distribution block.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 10,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DIS_CLK3',
            description = 'Disables the analog clock to DAC3 out of the clock distribution block.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 9,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DIS_CLK4',
            description = 'Disables the analog clock to DAC4 out of the clock distribution block.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 8,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DIS_DCLK',
            description = 'Disables the clock to core digital block.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 7,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'CLK_SLEEP',
            description = 'Enables a very low power clock mode.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 6,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'CLK_PDN',
            description = 'Disables and powers down main clock receiver. No clocks are active in the device.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 5,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'EPS',
            description = 'Enables Power Save (EPS).',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 4,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC1_INV_CLK',
            description = 'Cannot use EPS when using this bit. Inverts the clock inside DAC Core 1 allowing 180 deg. phase shift in DAC1 update timing.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC2_INV_CLK',
            description = 'Cannot use EPS when using this bit. Inverts the clock inside DAC Core 2 allowing 180 deg. phase shift in DAC2 update timing.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 2,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC3_INV_CLK',
            description = 'Cannot use EPS when using this bit. Inverts the clock inside DAC Core 3 allowing 180 deg. phase shift in DAC3 update timing.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC4_INV_CLK',
            description = 'Cannot use EPS when using this bit. Inverts the clock inside DAC Core 4 allowing 180 deg. phase shift in DAC4 update timing.',
            mode = 'RW',
            offset = CLOCKCONFIG,
            bitSize = 1,
            bitOffset = 0,
            base = pr.Bool))


        # REFADJ
        self.add(pr.RemoteVariable(
            name = 'BGDR',
            description = 'Adjusts the BG 10kOhm resistor from 8 kOhm to 12 kOhm, changes BG voltage from 800 mV to 1.2 V, respectively.',
            mode = 'RW',
            offset = REFADJ,
            bitSize = 6,
            bitOffset = 0,
            base = pr.UInt))

        # DACAGAIN
        self.add(pr.RemoteVariable(
            name = 'DAC1_GAIN_CAL',
            description = 'DAC1 analog gain calibration output',
            mode = 'RO',
            hidden = True,
            offset = DAC1AGAIN,
            bitSize = 7,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC2_GAIN_CAL',
            description = 'DAC2 analog gain calibration output',
            mode = 'RO',
            hidden = True,
            offset = DAC2AGAIN,
            bitSize = 7,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC3_GAIN_CAL',
            description = 'DAC3 analog gain calibration output',
            mode = 'RO',
            hidden = True,
            offset = DAC3AGAIN,
            bitSize = 7,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC4_GAIN_CAL',
            description = 'DAC4 analog gain calibration output',
            mode = 'RO',
            hidden = True,
            offset = DAC4AGAIN,
            bitSize = 7,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC1_GAIN',
            description = 'DAC1 analog gain control while not in calibration mode - twos complement.',
            mode = 'RW',
            offset = DAC1AGAIN,
            bitSize = 7,
            bitOffset = 0,
            base = pr.Int))

        self.add(pr.RemoteVariable(
            name = 'DAC2_GAIN',
            description = 'DAC3 analog gain control while not in calibration mode - twos complement.',
            mode = 'RW',
            offset = DAC2AGAIN,
            bitSize = 7,
            bitOffset = 0,
            base = pr.Int))

        self.add(pr.RemoteVariable(
            name = 'DAC3_GAIN',
            description = 'DAC3 analog gain control while not in calibration mode - twos complement.',
            mode = 'RW',
            offset = DAC3AGAIN,
            bitSize = 7,
            bitOffset = 0,
            base = pr.Int))

        self.add(pr.RemoteVariable(
            name = 'DAC4_GAIN',
            description = 'DAC4 analog gain control while not in calibration mode - twos complement.',
            mode = 'RW',
            offset = DAC4AGAIN,
            bitSize = 7,
            bitOffset = 0,
            base = pr.Int))


        # DACxRANGE
        self.add(pr.RemoteVariable(
            name = 'DAC1_GAIN_RNG',
            description = 'DAC1 gain range control.',
            mode = 'RW',
            offset = DACxRANGE,
            bitSize = 2,
            bitOffset = 0,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC2_GAIN_RNG',
            description = 'DAC2 gain range control.',
            mode = 'RW',
            offset = DACxRANGE,
            bitSize = 2,
            bitOffset = 2,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC3_GAIN_RNG',
            description = 'DAC3 gain range control.',
            mode = 'RW',
            offset = DACxRANGE,
            bitSize = 2,
            bitOffset = 4,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC4_GAIN_RNG',
            description = 'DAC4 gain range control.',
            mode = 'RW',
            offset = DACxRANGE,
            bitSize = 2,
            bitOffset = 6,
            base = pr.UInt))

        #FSADJ
        self.add(pr.RemoteVariable(
            name = 'DAC1_RSET_EN',
            description = 'For write, enable the internal RSET1 resistor for DAC1; for read, RSET1 for DAC1 is enabled during calibration mode',
            mode = 'RW',
            offset = DAC1RSET,
            bitSize = 1,
            bitOffset = 15,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC2_RSET_EN',
            description = 'For write, enable the internal RSET2 resistor for DAC2; for read, RSET2 for DAC2 is enabled during calibration mode',
            mode = 'RW',
            offset = DAC2RSET,
            bitSize = 1,
            bitOffset = 15,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC3_RSET_EN',
            description = 'For write, enable the internal RSET3 resistor for DAC3; for read, RSET3 for DAC3 is enabled during calibration mode',
            mode = 'RW',
            offset = DAC3RSET,
            bitSize = 1,
            bitOffset = 15,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC4_RSET_EN',
            description = 'For write, enable the internal RSET4 resistor for DAC4; for read, RSET4 for DAC4 is enabled during calibration mode',
            mode = 'RW',
            offset = DAC4RSET,
            bitSize = 1,
            bitOffset = 15,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DAC1_RSET_CAL',
            description = 'Digital control value of RSET1 resistor for DAC1 after calibration',
            mode = 'RO',
            hidden = True,
            offset = DAC1RSET,
            bitSize = 5,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC2_RSET_CAL',
            description = 'Digital control value of RSET2 resistor for DAC2 after calibration',
            mode = 'RO',
            hidden = True,
            offset = DAC2RSET,
            bitSize = 5,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC3_RSET_CAL',
            description = 'Digital control value of RSET3 resistor for DAC3 after calibration',
            mode = 'RO',
            hidden = True,
            offset = DAC3RSET,
            bitSize = 5,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC4_RSET_CAL',
            description = 'Digital control value of RSET4 resistor for DAC4 after calibration',
            mode = 'RO',
            hidden = True,
            offset = DAC4RSET,
            bitSize = 5,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC1_RSET',
            description = 'Digital control to set the value f RSET1 resistor in DAC1',
            mode = 'RW',
            offset = DAC1RSET,
            bitSize = 5,
            bitOffset = 0,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC2_RSET',
            description = 'Digital control to set the value f RSET2 resistor in DAC2',
            mode = 'RW',
            offset = DAC2RSET,
            bitSize = 5,
            bitOffset = 0,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC3_RSET',
            description = 'Digital control to set the value f RSET3 resistor in DAC3',
            mode = 'RW',
            offset = DAC3RSET,
            bitSize = 5,
            bitOffset = 0,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DAC4_RSET',
            description = 'Digital control to set the value f RSET4 resistor in DAC4',
            mode = 'RW',
            offset = DAC4RSET,
            bitSize = 5,
            bitOffset = 0,
            base = pr.UInt))


        # CALCONFIG
        self.add(pr.RemoteVariable(
            name = 'COMP_OFFSET_OF',
            description = 'Compenstation offset calibration value overflow',
            mode = 'RO',
            hidden = True,
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 14,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'COMP_OFFSET_UF',
            description = 'Compenstation offset calibration value underflow',
            mode = 'RO',
            hidden = True,
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 13,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'RSET_CAL_OF',
            description = 'RSETx calibration value overflow',
            mode = 'RO',
            hidden = True,
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 12,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'RSET_CAL_UF',
            description = 'RSETx calibration value underflow',
            mode = 'RO',
            hidden = True,
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 11,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'GAIN_CAL_OF',
            description = 'Gain calibration value overflow',
            mode = 'RO',
            hidden = True,
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 10,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'GAIN_CAL_UF',
            description = 'Gain calibration value underflow',
            mode = 'RO',
            hidden = True,
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 9,
            base = pr.UInt))

        self.add(pr.RemoteCommand(
            name = 'CAL_RESET',
            description = 'Pulse this bit high and low to reset the calibration results',
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 8,
            function = pr.RemoteCommand.toggle))

        self.add(pr.RemoteVariable(
            name = 'CAL_MODE_EN',
            description = 'Enables the gain calibration circuitry',
            mode = 'RW',
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 6,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'CAL_MODE',
            description = 'Flag indicating calibration is being used',
            mode = 'RO',
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 7,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'COMP_CAL_RNG',
            description = 'Offset calibration range',
            mode = 'RW',
            offset = CALCONFIG,
            bitSize = 2,
            bitOffset = 4,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'CAL_CLK_EN',
            description = 'Enables the calibration clock to calibration circuitry',
            mode = 'RW',
            offset = CALCONFIG,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'CAL_CLK_DIV',
            description = 'Sets the divider from DAC clock to calibration clock',
            mode = 'RW',
            offset = CALCONFIG,
            bitSize = 3,
            bitOffset = 0,
            base = pr.UInt))


        # COMPOFFSET
        self.add(pr.RemoteVariable(
            name = 'COMP_OFFSET_CAL',
            description = 'The result of the offset calibration for the comparator',
            mode = 'RO',
            hidden = True,
            offset = COMPOFFSET,
            bitSize = 7,
            bitOffset = 8,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'CAL_FIN',
            description = 'Flag indicating calibration is completed',
            mode = 'RO',
            hidden = True,
            offset = COMPOFFSET,
            bitSize = 1,
            bitOffset = 1,
            base = pr.Bool))

        self.add(pr.RemoteCommand(
            name = 'START_CAL',
            description = 'Start a calibration cycle',
            offset = COMPOFFSET,
            bitSize = 1,
            bitOffset = 0,
            function = pr.RemoteCommand.toggle))

        def nonBlockingTouch(cmd, arg):
            print(f'Sending nonblocking touch command for {cmd.path}')
            cmd._set(1, -1)
            pr.startTransaction(cmd._block, type=rim.Write, forceWr=True, checkEach=False, variable=cmd, index=-1)

        # RAMUPDATE
        self.add(pr.RemoteCommand(
            name = 'RAMUPDATE',
            description = 'Update all SPI settings with new configuration',
            offset = RAMUPDATE,
            bitSize = 1,
            bitOffset = 0,
            function = pr.RemoteCommand.touchOne))


        # PAT_STATUS
        self.add(pr.RemoteVariable(
            name = 'BUF_READ',
            description = 'Read back from updated buffer',
            mode = 'RW',
            offset = PAT_STATUS,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool,
            bulkOpEn=False))

        self.add(pr.RemoteVariable(
            name = 'MEM_ACCESS',
            description = 'Memory SPI access enable.',
            mode = 'RW',
            bulkOpEn = False,
            offset = PAT_STATUS,
            bitSize = 1,
            bitOffset = 2,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'PATTERN',
            description = 'Status of pattern being played',
            mode = 'RO',
            bulkOpEn = False,
            offset = PAT_STATUS,
            bitSize = 1,
            bitOffset = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'RUN',
            description = 'Allows the pattern generation and stop pattern after trigger.',
            mode = 'RW',
            bulkOpEn = False,
            offset = PAT_STATUS,
            bitSize = 1,
            bitOffset = 0,
            base = pr.Bool))


        # PAT_TYPE
        self.add(pr.RemoteVariable(
            name = 'PATTERN_RPT',
            description = 'Setting this bit allows the pattern to repeat the number of times defined in DAC4_3PATx and DAC2_1PATx',
            mode = 'RW',
            offset = PAT_TYPE,
            bitSize = 1,
            bitOffset = 0,
            enum = {
                0: 'Continuous',
                1: 'Register'}))

        # PATTERN_DLY
        self.add(pr.RemoteVariable(
            name = 'PATTERN_DELAY',
            description = 'Time between trigger low and pattern start in number of DAC clock cycles +1. Minimum = 14. Maximum = 65535. Increment 1.',
            mode = 'RW',
            offset = PATTERN_DLY,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt,
#            value = 14,
            disp = '{:d}'))

        # PAT_TIMEBASE
        self.add(pr.RemoteVariable(
            name = 'HOLD',
            description = 'Number of times the DAC value holds the sample (0 = DAC holds for one sample)',
            mode = 'RW',
            offset = PAT_TIMEBASE,
            bitSize = 4,
            bitOffset = 8,
            base = pr.UInt,
#            value = 1,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'PAT_PERIOD_BASE',
            description = 'Number of DAC clock periods per PATTERN_PERIOD_LSB',
            mode = 'RW',
            offset = PAT_TIMEBASE,
            bitSize = 4,
            bitOffset = 4,
            base = pr.UInt,
#            value = 1,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'START_DELAY_BASE',
            description = 'Number of DAC clock periods per STASRT_DELAYxLSB',
            mode = 'RW',
            offset = PAT_TIMEBASE,
            bitSize = 4,
            bitOffset = 0,
            base = pr.UInt,
#            value = 1,
            disp = '{:d}'))

        # PAT_PERIOD
        self.add(pr.RemoteVariable(
            name = 'PATTERN_PERIOD',
            description = '',
            mode = 'RW',
#            value = 0x8000,
            offset = PAT_PERIOD,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))



        # DAC1DOF
        self.add(pr.RemoteVariable(
            name = 'DAC1_DIG_OFFSET',
            description = 'DAC1 digital offset',
            mode = 'RW',
            offset = DAC1DOF,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC2DOF
        self.add(pr.RemoteVariable(
            name = 'DAC2_DIG_OFFSET',
            description = 'DAC2 digital offset',
            mode = 'RW',
            offset = DAC2DOF,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC3DOF
        self.add(pr.RemoteVariable(
            name = 'DAC3_DIG_OFFSET',
            description = 'DAC3 digital offset',
            mode = 'RW',
            offset = DAC3DOF,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC4DOF
        self.add(pr.RemoteVariable(
            name = 'DAC4_DIG_OFFSET',
            description = 'DAC4 digital offset',
            mode = 'RW',
            offset = DAC4DOF,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))


        self.add(pr.RemoteVariable(
            name = 'PRESTORE_SEL1',
            description = '',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 2,
            bitOffset = 4,
            base = pr.UInt,
            enum = {
                0: 'Constant',
                1: 'Sawtooth',
                2: 'Pseudorandom',
                3: 'DDS1'}))

        self.add(pr.RemoteVariable(
            name = 'PRESTORE_SEL2',
            description = '',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 2,
            bitOffset = 12,
            base = pr.UInt,
            enum = {
                0: 'Constant',
                1: 'Sawtooth',
                2: 'Pseudorandom',
                3: 'DDS2'}))

        self.add(pr.RemoteVariable(
            name = 'PRESTORE_SEL3',
            description = '',
            mode = 'RW',
            offset = WAV4_3CONFIG,
            bitSize = 2,
            bitOffset = 4,
            base = pr.UInt,
            enum = {
                0: 'Constant',
                1: 'Sawtooth',
                2: 'Pseudorandom',
                3: 'DDS3'}))

        self.add(pr.RemoteVariable(
            name = 'PRESTORE_SEL4',
            description = '',
            mode = 'RW',
            offset = WAV4_3CONFIG,
            bitSize = 2,
            bitOffset = 12,
            base = pr.UInt,
            enum = {
                0: 'Constant',
                1: 'Sawtooth',
                2: 'Pseudorandom',
                3: 'DDS4'}))


        self.add(pr.RemoteVariable(
            name = 'WAVE_SEL1',
            description = '',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 2,
            bitOffset = 0,
            base = pr.UInt,
            enum = {
                0: 'RAM',
                1: 'Prestored',
                2: 'Prestored w/ START_DELAY1 and PATTERN_PERIOD',
                3: 'Prestored moduled by RAM'}))

        self.add(pr.RemoteVariable(
            name = 'WAVE_SEL2',
            description = '',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 2,
            bitOffset = 8,
            base = pr.UInt,
            enum = {
                0: 'RAM',
                1: 'Prestored',
                2: 'Prestored w/ START_DELAY2 and PATTERN_PERIOD',
                3: 'Prestored moduled by RAM'}))

        self.add(pr.RemoteVariable(
            name = 'WAVE_SEL3',
            description = '',
            mode = 'RW',
            offset = WAV4_3CONFIG,
            bitSize = 2,
            bitOffset = 0,
            base = pr.UInt,
            enum = {
                0: 'RAM',
                1: 'Prestored',
                2: 'Prestored w/ START_DELAY3 and PATTERN_PERIOD',
                3: 'Prestored moduled by RAM'}))

        self.add(pr.RemoteVariable(
            name = 'WAVE_SEL4',
            description = '',
            mode = 'RW',
            offset = WAV4_3CONFIG,
            bitSize = 2,
            bitOffset = 8,
            base = pr.UInt,
            enum = {
                0: 'RAM',
                1: 'Prestored',
                2: 'Prestored w/ START_DELAY4 and PATTERN_PERIOD',
                3: 'Prestored moduled by RAM'}))


        self.add(pr.RemoteVariable(
            name = 'MASK_DAC3',
            description = 'Mask DAC3 and DAC3_CONST value',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'MASK_DAC4',
            description = 'Mask DAC4 and DAC4_CONST value',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 1,
            bitOffset = 11,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'CH1_ADD',
            description = 'Add DAC1 and DAC3, output at DAC1',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 1,
            bitOffset = 2,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'CH2_ADD',
            description = 'Add DAC2 and DAC4, output ad DAC2',
            mode = 'RW',
            offset = WAV2_1CONFIG,
            bitSize = 1,
            bitOffset = 10,
            base = pr.Bool))


        self.add(pr.RemoteVariable(
            name = 'DAC1_REPEAT_CYCLE',
            description = 'Number of DAC1 pattern repeat cycles + 1',
            mode = 'RW',
#            value = 0x1,
            offset = DAC2_1PATx,
            bitSize = 8,
            bitOffset = 0,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'DAC2_REPEAT_CYCLE',
            description = 'Number of DAC2 pattern repeat cycles + 1',
            mode = 'RW',
#            value = 0x1,
            offset = DAC2_1PATx,
            bitSize = 8,
            bitOffset = 8,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'DAC3_REPEAT_CYCLE',
            description = 'Number of DAC3 pattern repeat cycles + 1',
            mode = 'RW',
#            value = 0x1,
            offset = DAC4_3PATx,
            bitSize = 8,
            bitOffset = 0,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'DAC4_REPEAT_CYCLE',
            description = 'Number of DAC4 pattern repeat cycles + 1',
            mode = 'RW',
            offset = DAC4_3PATx,
            bitSize = 8,
            bitOffset = 8,
            base = pr.UInt,
            disp = '{:d}'))


        # DAC1_CST
        self.add(pr.RemoteVariable(
            name = 'DAC1_CONST',
            description = 'Most significant byte of DAC1 constant value',
            mode = 'RW',
            offset = DAC1_CST,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC2_CST
        self.add(pr.RemoteVariable(
            name = 'DAC2_CONST',
            description = 'Most significant byte of DAC2 constant value',
            mode = 'RW',
            offset = DAC2_CST,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC3_CST
        self.add(pr.RemoteVariable(
            name = 'DAC3_CONST',
            description = 'Most significant byte of DAC3 constant value',
            mode = 'RW',
            offset = DAC3_CST,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC4_CST
        self.add(pr.RemoteVariable(
            name = 'DAC4_CONST',
            description = 'Most significant byte of DAC4 constant value',
            mode = 'RW',
            offset = DAC4_CST,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))


        # DAC1_DGAIN
        self.add(pr.RemoteVariable(
            name = 'DAC1_DIG_GAIN',
            description = 'DAC1 digital gain range +2 to -2',
            mode = 'RW',
            offset = DAC1_DGAIN,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC2_DGAIN
        self.add(pr.RemoteVariable(
            name = 'DAC2_DIG_GAIN',
            description = 'DAC2 digital gain range +2 to -2',
            mode = 'RW',
            offset = DAC2_DGAIN,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC3_DGAIN
        self.add(pr.RemoteVariable(
            name = 'DAC3_DIG_GAIN',
            description = 'DAC3 digital gain range +2 to -2',
            mode = 'RW',
            offset = DAC3_DGAIN,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # DAC4_DGAIN
        self.add(pr.RemoteVariable(
            name = 'DAC4_DIG_GAIN',
            description = 'DAC4 digital gain range +2 to -2',
            mode = 'RW',
            offset = DAC4_DGAIN,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'SAW_STEP1',
            description = 'Number of samples per step for DAC1',
            mode = 'RW',
#            value = 1,
            offset = SAW2_1CONFIG,
            bitSize = 6,
            bitOffset = 2,
            base = pr.UInt,
            disp = '{:d}'))

        # SAW2_1CONFIG
        self.add(pr.RemoteVariable(
            name = 'SAW_STEP2',
            description = 'Number of samples per step for DAC2',
            mode = 'RW',
#            value = 1,
            offset = SAW2_1CONFIG,
            bitSize = 6,
            bitOffset = 10,
            base = pr.UInt,
            disp = '{:d}'))

        self.add(pr.RemoteVariable(
            name = 'SAW_STEP3',
            description = 'Number of samples per step for DAC3',
            mode = 'RW',
#            value = 1,
            offset = SAW4_3CONFIG,
            bitSize = 6,
            bitOffset = 2,
            base = pr.UInt,
            disp = '{:d}'))

        # SAW4_3CONFIG
        self.add(pr.RemoteVariable(
            name = 'SAW_STEP4',
            description = 'Number of samples per step for DAC4',
            mode = 'RW',
#            value = 1,
            offset = SAW4_3CONFIG,
            bitSize = 6,
            bitOffset = 10,
            base = pr.UInt,
            disp = '{:d}'))


        self.add(pr.RemoteVariable(
            name = 'SAW_TYPE1',
            description = 'The type of sawtooth (positive, negative, triangle) for DAC1',
            mode = 'RW',
            offset = SAW2_1CONFIG,
            bitSize = 2,
            bitOffset = 0,
            base = pr.UInt,
            enum = {
                0: 'Ramp Up',
                1: 'Ramp Down',
                2: 'Triangle',
                3: 'Zero'}))

        self.add(pr.RemoteVariable(
            name = 'SAW_TYPE2',
            description = 'The type of sawtooth (positive, negative, triangle) for DAC2',
            mode = 'RW',
            offset = SAW2_1CONFIG,
            bitSize = 2,
            bitOffset = 8,
            base = pr.UInt,
            enum = {
                0: 'Ramp Up',
                1: 'Ramp Down',
                2: 'Triangle',
                3: 'Zero'}))

        self.add(pr.RemoteVariable(
            name = 'SAW_TYPE3',
            description = 'The type of sawtooth (positive, negative, triangle) for DAC3',
            mode = 'RW',
            offset = SAW4_3CONFIG,
            bitSize = 2,
            bitOffset = 0,
            base = pr.UInt,
            enum = {
                0: 'Ramp Up',
                1: 'Ramp Down',
                2: 'Triangle',
                3: 'Zero'}))


        self.add(pr.RemoteVariable(
            name = 'SAW_TYPE4',
            description = 'The type of sawtooth (positive, negative, triangle) for DAC4',
            mode = 'RW',
            offset = SAW4_3CONFIG,
            bitSize = 2,
            bitOffset = 8,
            base = pr.UInt,
            enum = {
                0: 'Ramp Up',
                1: 'Ramp Down',
                2: 'Triangle',
                3: 'Zero'}))


        # START_DLY1
        self.add(pr.RemoteVariable(
            name = 'START_DELAY1',
            description = 'Start Delay of DAC1',
            mode = 'RW',
            disp = '0x{:04x}',
            offset = START_DLY1,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # START_ADDR1
        self.add(pr.RemoteVariable(
            name = 'START_ADDR1',
            description = 'RAM address where DAC1 starts to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = START_ADDR1,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # STOP_ADDR1
        self.add(pr.RemoteVariable(
            name = 'STOP_ADDR1',
            description = 'RAM address where DAC1 stops to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = STOP_ADDR1,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))


        # START_DLY2
        self.add(pr.RemoteVariable(
            name = 'START_DELAY2',
            description = 'Start Delay of DAC2',
            mode = 'RW',
            disp = '0x{:04x}',
            offset = START_DLY2,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # START_ADDR2
        self.add(pr.RemoteVariable(
            name = 'START_ADDR2',
            description = 'RAM address where DAC2 starts to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = START_ADDR2,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # STOP_ADDR2
        self.add(pr.RemoteVariable(
            name = 'STOP_ADDR2',
            description = 'RAM address where DAC2 stops to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = STOP_ADDR2,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # START_DLY3
        self.add(pr.RemoteVariable(
            name = 'START_DELAY3',
            description = 'Start Delay of DAC3',
            mode = 'RW',
            disp = '0x{:04x}',
            offset = START_DLY3,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # START_ADDR3
        self.add(pr.RemoteVariable(
            name = 'START_ADDR3',
            description = 'RAM address where DAC3 starts to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = START_ADDR3,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # STOP_ADDR3
        self.add(pr.RemoteVariable(
            name = 'STOP_ADDR3',
            description = 'RAM address where DAC3 stops to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = STOP_ADDR3,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))



        # START_DLY4
        self.add(pr.RemoteVariable(
            name = 'START_DELAY4',
            description = 'Start Delay of DAC4',
            mode = 'RW',
            disp = '0x{:04x}',
            offset = START_DLY4,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # START_ADDR4
        self.add(pr.RemoteVariable(
            name = 'START_ADDR4',
            description = 'RAM address where DAC4 starts to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = START_ADDR4,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))

        # STOP_ADDR4
        self.add(pr.RemoteVariable(
            name = 'STOP_ADDR4',
            description = 'RAM address where DAC4 stops to read waveform',
            mode = 'RW',
            disp = '0x{:03x}',
            offset = STOP_ADDR4,
            bitSize = 12,
            bitOffset = 4,
            base = pr.UInt))



        # DDS_CYC1
        self.add(pr.RemoteVariable(
            name = 'DDS_CYC1',
            description = 'Number of sine wave cycles when DDS prestored waveform with start and stop delays is selected for DAC1 output',
            mode = 'RW',
#            value = 1,
            offset = DDS_CYC1,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS_CYC2
        self.add(pr.RemoteVariable(
            name = 'DDS_CYC2',
            description = 'Number of sine wave cycles when DDS prestored waveform with start and stop delays is selected for DAC2 output',
            mode = 'RW',
#            value = 1,
            offset = DDS_CYC2,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS_CYC3
        self.add(pr.RemoteVariable(
            name = 'DDS_CYC3',
            description = 'Number of sine wave cycles when DDS prestored waveform with start and stop delays is selected for DAC3 output',
            mode = 'RW',
#            value = 1,
            offset = DDS_CYC3,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS_CYC4
        self.add(pr.RemoteVariable(
            name = 'DDS_CYC4',
            description = 'Number of sine wave cycles when DDS prestored waveform with start and stop delays is selected for DAC4 output',
            mode = 'RW',
#            value = 1,
            offset = DDS_CYC4,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))


        # DDS_TW32
        self.add(pr.RemoteVariable(
            name = 'DDSTW_MSB',
            description = 'DDS tuning word MSB',
            mode = 'RW',
            offset = DDS_TW32,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS_TW1
        self.add(pr.RemoteVariable(
            name = 'DDSTW_LSB',
            description = 'DDS tuning word LSB',
            mode = 'RW',
            offset = DDS_TW1,
            bitSize = 8,
            bitOffset = 8,
            base = pr.UInt))

        # DDS4_PW
        self.add(pr.RemoteVariable(
            name = 'DDS4_PHASE',
            description = 'DDS4 phase offset',
            mode = 'RW',
            offset = DDS4_PW,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS3_PW
        self.add(pr.RemoteVariable(
            name = 'DDS3_PHASE',
            description = 'DDS3 phase offset',
            mode = 'RW',
            offset = DDS3_PW,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS2_PW
        self.add(pr.RemoteVariable(
            name = 'DDS2_PHASE',
            description = 'DDS2 phase offset',
            mode = 'RW',
            offset = DDS2_PW,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # DDS1_PW
        self.add(pr.RemoteVariable(
            name = 'DDS1_PHASE',
            description = 'DDS1 phase offset',
            mode = 'RW',
            offset = DDS1_PW,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt))

        # TRIG_TW_SEL
        self.add(pr.RemoteVariable(
            name = 'TRIG_DELAY_EN',
            description = 'Enable start delay as trigger delay for all four channels',
            mode = 'RW',
            offset = TRIG_TW_SEL,
            bitSize = 1,
            bitOffset = 1,
            base = pr.Bool))

        # DDSx_CONFIG
        self.add(pr.RemoteVariable(
            name = 'DDS_COS_EN1',
            description = 'Enable DDS1 cosine output of DDS instead of sine wave',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DDS_COS_EN2',
            description = 'Enable DDS2 cosine output of DDS instead of sine wave',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 7,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DDS_COS_EN3',
            description = 'Enable DDS3 cosine output of DDS instead of sine wave',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 11,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DDS_COS_EN4',
            description = 'Enable DDS4 cosine output of DDS instead of sine wave',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 15,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DDS_MSB_EN1',
            description = 'Enable the clock for the RAM address. Increment is coming from the DDS1 MSB. Default is coming from DAC clock',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 2,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DDS_MSB_EN2',
            description = 'Enable the clock for the RAM address. Increment is coming from the DDS2 MSB. Default is coming from DAC clock',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 6,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DDS_MSB_EN3',
            description = 'Enable the clock for the RAM address. Increment is coming from the DDS3 MSB. Default is coming from DAC clock',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 10,
            base = pr.Bool))


        self.add(pr.RemoteVariable(
            name = 'DDS_MSB_EN4',
            description = 'Enable the clock for the RAM address. Increment is coming from the DDS4 MSB. Default is coming from DAC clock',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 14,
            base = pr.Bool))


        self.add(pr.RemoteVariable(
            name = 'TW_MEM_EN',
            description = 'Enable DDS tuning word input coming from RAM reading using START_ADDR1. Because tuning word is 24 bits and RAM data is 12 bits, 12 bits are set to 0s depending on the value of the TW_MEM_SHIFT bits in TW_RAM_CONFIG register. Default is coming from the SPI map, DDSTW.',
            mode = 'RW',
            offset = DDSx_CONFIG,
            bitSize = 1,
            bitOffset = 0,
            base = pr.Bool))

        # TW_RAM_CONFIG
        self.add(pr.RemoteVariable(
            name = 'TW_MEM_SHIFT',
            description = 'TW_MEM_EN must be set to true to use this variable',
            mode = 'RW',
            offset = TW_RAM_CONFIG,
            bitSize = 4,
            bitOffset = 0,
            base = pr.UInt,
            enum = {
                0x00 : "(RAM[11:0],12'b0)",
                0x01 : "(DDSTW[23],RAM[11:0],11'b0)",
                0x02 : "(DDSTW[23:22],RAM[11:0],10'b0)",
                0x03 : "(DDSTW[23:21],RAM[11:0],9'b0)",
                0x04 : "(DDSTW[23:20],RAM[11:0],8'b0)",
                0x05 : "(DDSTW[23:19],RAM[11:0],7'b0)",
                0x06 : "(DDSTW[23:18],RAM[11:0],6'b0)",
                0x07 : "(DDSTW[23:17],RAM[11:0],5'b0)",
                0x08 : "(DDSTW[23:16],RAM[11:0],3'b0)",
                0x09 : "(DDSTW[23:15],RAM[11:0],4'b0)",
                0x0A : "(DDSTW[23:14],RAM[11:0],2'b0)",
                0x0B : "(DDSTW[23:13],RAM[11:0],1'b0)",
                0x0C : "(DDSTW[23:12],RAM[11:0])",
                0x0D : "(DDSTW[23:11],RAM[11:1])",
                0x0E : "(DDSTW[23:10],RAM[11:2])",
                0x0F : "(DDSTW[23:9],RAM[11:3])",
                0x10 : "(DDSTW[23:8],RAM[11:4])"}))

        # DOUT_CONFIG
        self.add(pr.RemoteVariable(
            name = 'DOUT_VAL',
            description = 'Manually sets DOUT signal value, only valid when DOUT_MODE = 0',
            mode = 'RW',
            offset = DOUT_CONFIG,
            bitSize = 1,
            bitOffset = 5,
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'DOUT_MODE',
            description = 'Sets different enable signal mode',
            mode = 'RW',
            offset = DOUT_CONFIG,
            bitSize = 1,
            bitOffset = 4,
            base = pr.UInt,
            enum = {
                0: 'DOUT_VAL',
                1: 'DOUT_START/DOUT_STOP'}))

        self.add(pr.RemoteVariable(
            name = 'DOUT_STOP',
            description = 'Time between pattern end and DOUT signal low in number of DAC clock cycles',
            mode = 'RW',
            offset = DOUT_CONFIG,
            bitSize = 4,
            bitOffset = 0,
            base = pr.UInt))

        # DOUT_START_DLY
        self.add(pr.RemoteVariable(
            name = 'DOUT_START',
            description = 'Time between trigger low and DOUT signal high in number of DAC clock cycles. Minimum=3, Maximum=65535, Increment=1',
            mode = 'RW',
            offset = DOUT_START_DLY,
            bitSize = 16,
            bitOffset = 0,
            base = pr.UInt,
#            value = 3,
            disp = '{:d}'))



        # CFG_ERROR
        self.add(pr.RemoteCommand(
            name = 'ERROR_CLEAR',
            description = 'Clears all errors',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 15,
            base = pr.UInt,
            function = pr.RemoteCommand.touchOne))

        self.add(pr.RemoteVariable(
            name = 'DOUT_START_LG_ERR',
            description = 'When DOUT_START is larger than pattern delay, this error is toggled',
            mode = 'RO',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 5,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'PAT_DLY_SHORT_ERR',
            description = 'When pattern delay value is smaller than default value, this error is toggled.',
            mode = 'RO',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 4,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'DOUT_START_SHORT_ERR',
            description = 'When DOUT_START value is smaller than default value, this error is toggled.',
            mode = 'RO',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 3,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'PERIOD_SHORT_ERR',
            description = 'When period register setting value is smaller than pattern play cycle, this error is toggled',
            mode = 'RO',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 2,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'ODD_ADDR_ERR',
            description = 'When memory pattern play is not even in length in trigger delay mode, this error flag is toggled',
            mode = 'RO',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 1,
            base = pr.Bool))

        self.add(pr.RemoteVariable(
            name = 'MEM_READ_ERR',
            description = 'When there is a memory read conflict, this error flag is toggled',
            mode = 'RO',
            offset = CFG_ERROR,
            bitSize = 1,
            bitOffset = 0,
            base = pr.Bool))

#         for i in range(4):
#             self.add(pr.RemoteVariable(
#                 name = f'SRAM[{i}]',
#                 offset = SRAM_DATA + i*2**12,
#                 base = pr.UInt,
#                 bitSize = 32* 2**10,
#                 bitOffset = 4,
#                 numValues = 2**10,
#                 valueBits = 12,
#                 valueStride = 32))

        self.add(Ad9106Sram(
            dac = self,
            enabled=True,
            name = 'SRAM',
            description = 'SRAM for waveforms',
            offset = SRAM_DATA,
            size = 2**12<<2,
            base = pr.UInt,
            wordBitSize = 12,
            stride = 4))

        # Don't need RAMUPDATE if writing to BUF_READ, MEM_ACCESS or RUN
        self.NON_BUFFERED = [self.BUF_READ, self.MEM_ACCESS, self.RUN]

        @self.command()
        def LoadSRAM(arg):
            self.SRAM.set(0, [arg for x in range(16)], write=True)

        @self.command()
        def LoadSRAMInc(arg):
            self.SRAM.set(0, [x for x in range(0, arg*4, 4)], write=True)

        @self.command()
        def SramSawtooth():
            self.START_ADDR1.set(0x000, write=False)
            self.START_ADDR2.set(0x400, write=False)
            self.START_ADDR3.set(0x800, write=False)
            self.START_ADDR4.set(0xc00, write=False)

            self.STOP_ADDR1.set(0x3ff, write=False)
            self.STOP_ADDR2.set(0x7ff, write=False)
            self.STOP_ADDR3.set(0xbff, write=False)
            self.STOP_ADDR4.set(0xfff, write=False)

            self.writeAndVerifyBlocks()

            self.SRAM.set(0, [x<<4 for x in range(2**12)], write=True)


    def writeBlocks(self, *, force=False, recurse=True, variable=None, checkEach=False, index=-1, **kwargs):

        checkEach = checkEach or self.forceCheckEach



        if variable is not None:
            pr.startTransaction(variable._block, type=rim.Write, forceWr=force, checkEach=checkEach, variable=variable, index=index, **kwargs)
            if variable not in self.NON_BUFFERED:
                print("single RAMUPDATE")
                self.RAMUPDATE() #.set(1, write=True)

        else:
 #           self.BUF_READ.set(0, write=True)
            for block in self._blocks:
                if block.bulkOpEn:
                    pr.startTransaction(block, type=rim.Write, forceWr=force, checkEach=checkEach, **kwargs)

            if recurse:
                for key,value in self.devices.items():
                    value.writeBlocks(force=force, recurse=True, checkEach=checkEach, **kwargs)

            print('bulk ramupdate')
            self.RAMUPDATE() #.set(1, write=True)




class Ad9106Sram(pr.MemoryDevice):
    def __init__(self, dac, **kwargs):
        super().__init__(**kwargs)
        self._dac = dac

    # Terrible hack to account for bitOffset=4
    def _setDict(self, d, writeEach, modes,incGroups,excGroups,keys):
        # Parse comma separated values at each offset (key) in d
        with self._txnLock:
            for offset, values in d.items():
                self._setValues[offset] = [self._base.fromString(s)<<4 for s in values.split(',')]

    def writeBlocks(self, **kwargs):
        print(f'{self.path}.writeBlocks()')
        # BUF_READ must be set to 0 before writing to SRAM
        if self.enable.get() and len(self._setValues) > 0:
            print('Setting BUF_READ and MEM_ACCESS for write to SRAM')
            for i in self._setValues.keys():
                a = [hex(x) for x in self._setValues[i]]
                print(f'setValues = 0x{i:03x} (0x6{i>>2:03x}) - {a}')
            self._dac.BUF_READ.set(0, write=False)
            self._dac.MEM_ACCESS.set(1, write=True)
            print('Done MEM_ACCESS = 1 and BUF_READ = 1')
#            queueVariable(self._dac.BUF_READ, 0)

            print('super writeblocks')
            super().writeBlocks(**kwargs)
            print('super writeblocks done')

            print('Setting BUF_READ and MEM_ACCESS = 0')
            self._dac.BUF_READ.set(0, write=False)
            self._dac.MEM_ACCESS.set(0, write=True)
            print('Done setting BUF_READ and MEM_ACCESS = 0')


    def verifyBlocks(self, **kwargs):
        # BUF_READ must be set to 1 before reading from SRAM
 #       save = self._dac.BUF_READ.value()
        #queueVariable(self._dac.BUF_READ, 1)
        #self._dac.BUF_READ.post(1)
        if self.enable.get() is not True:
            return

        print(f'Verify {self.path}')
        self._dac.BUF_READ.set(1, write=False)
        print('Done BUF_READ = 1')
        self._dac.MEM_ACCESS.set(1, write=True)
        print('Done MEM_ACCESS = 1')
        super().verifyBlocks(**kwargs)
        print('Done super')

        #print(self._verValues)

        self._dac.BUF_READ.set(0, write=False)
        self._dac.MEM_ACCESS.set(0, write=True)

#     def readBlocks(self, **kwargs):
#         if self.enable.get() is not True:
#             return

#         print(f'Read {self.path}')
#         self._dac.BUF_READ.set(1, write=True)
#         print('Done BUF_READ = 1')
#         self._dac.MEM_ACCESS.set(1, write=True)
#         print('Done MEM_ACCESS = 1')

#         vals = self._txnChunker(0, None, self._base, self._stride, self._wordBitSize, txnType=rim.Read, numWords=4096)
#         vals = [self._base.fromBytes(vals[i:i+4]) for i in range(0, 4096*4, 4)]
#         print(vals)


#         self._dac.BUF_READ.set(0, write=True)
#         self._dac.MEM_ACCESS.set(0, write=True)

    def checkBlocks(self, recurse=True, variable=None):
        with self._txnLock:
            # Wait for all txns to complete
            self._waitTransaction(0)

            # Error check?
            self._clearError()

            # Convert the read verify data back to the native type
            # Can't do this until waitTransaction is done
            checkValues = odict()
            for offset, ba in self._verValues.items():
                checkValues[offset] = [self._base.fromBytes(ba[i:i+self._stride])
                                       for i in range(0, len(ba), self._stride)]

#            if len(checkValues) > 0:
#                print(checkValues)

            # Do verify if necessary
            if len(self._verValues) > 0:
                # Compare wrData with verData
                if checkValues != self._wrValues:
                    msg = 'Verify error \n'
                    msg += f'Expected: \n {self._wrValues} \n'
                    msg += f'Got: \n {checkValues}'
                    print(msg)
                    raise MemoryError(name=self.name, address=self.address, msg=msg, size=self._rawSize)


            # destroy the txn maps when done with verify
            self._verValues = odict()
            self._wrValues = odict()



#     def readBlocks(self, **kwargs):
#         if self.enable.get() is not True:
#             return

#         self._dac.BUF_READ.set(1, write=False, check=False)
#         self._dac.MEM_ACCESS.set(1, check=False)
#         super().readBlocks(**kwargs)
#         self._dac.BUF_READ.set(0, write=False, check=False)
#         self._dac.MEM_ACCESS.set(0)
