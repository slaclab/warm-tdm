
import pyrogue as pr
import warm_tdm_api

class TesRampProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._tesRampWrap, **kwargs)

        self.add(pr.LocalVariable(name='TesBiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for TES Bias Ramping"))

        # High offset for SQ1 Bias Ramping
        self.add(pr.LocalVariable(name='TesBiasHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SQ1 Bias Ramping"))

        # Step size for SQ1 Bias Ramping
        self.add(pr.LocalVariable(name='TesBiasStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for SQ1 Bias Ramping"))

        # TES Diagnostic Results
        self.add(pr.LocalVariable(name='TesDiagOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From Tes Diagnostic"))

    def _tesRampWrap(self):
        #ret = warm_tdm_api.saTune(self.parent,row=0,pctVar=self.Progress)
        #self.SaTuneOutput.set(value=ret)
        pass


