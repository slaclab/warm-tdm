import pyrogue as pr

import warm_tdm

class ColumnVesperFpgaBoard(warm_tdm.ColumnFpgaBoard):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(warm_tdm.VesperBoreasConfig(
            saBiasDac = self.SaBiasDac,
            saOffsetDac = self.SaOffsetDac,
            tesBiasDac = self.TesBiasDac,
            saFbDac = self.SAFb,
            sq1BiasDac = self.SQ1Bias,
            sq1FbDac = self.SQ1Fb,
            auxDac = self.AuxDac
        ))
