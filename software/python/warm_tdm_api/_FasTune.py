
import pyrogue as pr
import warm_tdm_api

class FasTuneProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._fasTuneWrap, **kwargs)

        # Low offset for Fas FLux Tuning
        self.add(pr.LocalVariable(name='FasFluxLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for Fas Flux Tuning"))

        # High offset for Fas Flux Tuning
        self.add(pr.LocalVariable(name='FasFluxHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for Fas Flux Tuning"))

        # Step size for Fas Flux Tuning
        self.add(pr.LocalVariable(name='FasFluxStepSize',
                                  value=0.0,
                                  mode='RW',
                                  description="Step size for Fas Flux Tuning"))

        # FAS Tuning Results
        self.add(pr.LocalVariable(name='FasTuneOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From FAS Tuning"))

    def _fasTuneWrap(self):
        #ret = warm_tdm_api.saTune(self.parent,row=0,pctVar=self.Progress)
        #self.SaTuneOutput.set(value=ret)
        pass


