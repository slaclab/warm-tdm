import pyrogue
import warm_tdm_api

rowMap = [(0,0)] * 20
colMap = [(0,0)] * 20

class GroupRoot(pyrogue.Root):
    def __init__( self, **kwargs):

        super().__init__(**kwargs)

        self.add(warm_tdm_api.Group(rowMap=rowMap,colMap=colMap,emulate=True))

