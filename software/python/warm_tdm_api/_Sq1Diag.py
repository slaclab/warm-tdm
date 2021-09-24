
import pyrogue as pr
import warm_tdm_api

class Sq1DiagProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._sq1DiagWrap, **kwargs)

        # SQ1 Diagnostic Results
        self.add(pr.LocalVariable(name='Sq1DiagOutput',
                                  hidden=True,
                                  value={},
                                  mode='RO',
                                  description="Results Data From SQ1 Diagnostic"))

    def _sq1DiagWrap(self):
        #ret = warm_tdm_api.saTune(self.parent,row=0,pctVar=self.Progress)
        #self.SaTuneOutput.set(value=ret)
        pass


