
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
                                  value=1.0,
                                  mode='RW',
                                  description="Ending point offset for Fas Flux Tuning"))

        # Step size for Fas Flux Tuning
        self.add(pr.LocalVariable(name='FasFluxNumSteps',
                                  value=10,
                                  mode='RW',
                                  description="Number of steps for Fas Flux Tuning"))

        # FAS Tuning Results
        self.add(pr.LocalVariable(name='FasTuneOutput',
                                  hidden=True,
                                  value={},
                                  mode='RO',
                                  description="Results Data From FAS Tuning"))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

    def _fasTuneWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.fasTune(group=self.parent, process=self)
            self.FasTuneOutput.set(value=ret)
