
import pyrogue as pr
import warm_tdm_api

class SaTuneProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._saTuneWrap, **kwargs)

        # Low offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SA FB Tuning"))

        # High offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbHighOffset',
                                  value=1.0,
                                  mode='RW',
                                  description="Ending point offset for SA FB Tuning"))

        # Step size for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbNumSteps',
                                  value=10,
                                  mode='RW',
                                  description="Number of steps for SA FB Tuning"))

        # Low offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SA Bias Tuning"))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHighOffset',
                                  value=1.0,
                                  mode='RW',
                                  description="Ending point offset for SA Bias Tuning"))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasNumSteps',
                                  value=10,
                                  mode='RW',
                                  description="Number of steps for SA Bias Tuning"))

        # SA Tuning Results
        self.add(pr.LocalVariable(name='SaTuneOutput',
                                  value={},
                                  mode='RO',
                                  description="Results Data From SA Tuning"))

    def _saTuneWrap(self):
        ret = warm_tdm_api.saTune(group=self.parent,pctVar=self.Progress)
        self.SaTuneOutput.set(value=ret)

