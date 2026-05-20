import pyrogue as pr


class AdcAccumulator(pr.Device):
    def __init__(self, maxRows=128, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.RemoteVariable(
            name='AdcBaselines',
            offset=0x0000,
            base=pr.Int,
            mode='RW',
            numValues=maxRows,
            valueBits=14,
            valueStride=32))
