import pyrogue as pr

class Ad5679R(pr.Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        NOP_CMD        = 0b0000
        WR_INP_CMD     = 0b0001
        DAC_UPDATE_CMD = 0b0010
        WR_DAC_CMD     = 0b0011
        PWR_DOWN_CMD   = 0b0100
        LDAC_MASK_CMD  = 0b0101
        SOFT_RST_CMD   = 0b0110
        INT_REF_CMD    = 0b0111
        DCEN_CMD       = 0b1000
        RDBACK_CMD     = 0b1001
        WR_ALL_INP_CMD = 0b1010
        WR_ALL_DAC_CMD = 0b1011

        for i in range(16):
            self.add(pr.RemoteVariable(
                name = f'Inp[{i}]',
                mode = 'RW',
                offset = WR_INP_CMD << 6 | i << 2,
                bitSize = 16,
                bitOffset = 0,
                base = pr.UInt))

            self.add(pr.RemoteVariable(
                name = f'Dac[{i}]',
                mode = 'RW',
                offset = DAC_UPDATE_CMD << 6 | i <<2,
                bitSize = 16,
                bitOffset = 0,
                base = pr.UInt))

        
