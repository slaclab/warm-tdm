
import pyrogue as pr
import warm_tdm_api

class Sq1TuneProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._sq1TuneWrap, **kwargs)

        # Low offset for SQ1 FB Tuning
        self.add(pr.LocalVariable(name='Sq1FbLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SQ1 FB Tuning"))

        # High offset for SQ1 FB Tuning
        self.add(pr.LocalVariable(name='Sq1FbHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SQ1 FB Tuning"))

        # Step size for SQ1 FB Tuning
        self.add(pr.LocalVariable(name='Sq1FbNumSteps',
                                  value=0.0,
                                  mode='RW',
                                  description="Number of steps for SQ1 FB Tuning"))

        # Low offset for SQ1 Bias Tuning
        self.add(pr.LocalVariable(name='Sq1BiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SQ1 Bias Tuning"))

        # High offset for SQ1 Bias Tuning
        self.add(pr.LocalVariable(name='Sq1BiasHighOffset',
                                  value=0.0,
                                  mode='RW',
                                  description="Ending point offset for SQ1 Bias Tuning"))

        # Step size for SQ1 Bias Tuning
        self.add(pr.LocalVariable(name='Sq1BiasNumSteps',
                                  value=0.0,
                                  mode='RW',
                                  description="Number of steps for SQ1 Bias Tuning"))

        # SQ1 Tuning Results
        self.add(pr.LocalVariable(name='Sq1TuneOutput',
                                  value={},
                                  hidden=True,
                                  mode='RO',
                                  description="Results Data From SQ1 Tuning"))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

    def _sq1TuneWrap(self):
        #ret = warm_tdm_api.saTune(self.parent,row=0,pctVar=self.Progress)
        #self.SaTuneOutput.set(value=ret)
        pass


