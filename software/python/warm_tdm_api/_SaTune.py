
import pyrogue as pr
import warm_tdm_api
import numpy as np

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

        # Select Channel
        self.add(pr.LocalVariable(name='PlotColumn',
                                  value=0,
                                 hidden=True,
                                  mode='RW',
                                  description="Channel Number To Plot"))

        # SA Tuning Results
        self.add(pr.LocalVariable(name='SaTuneOutput',
                                  hidden=True,
                                  value=[],
                                  mode='RO',
                                  description="Results Data From SA Tuning"))

        self.add(pr.LinkVariable(name='SaFb',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saFbGet,
                                 description=""))

        self.add(pr.LinkVariable(name='SaBias',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saBiasGet,
                                 description=""))

        self.add(pr.LinkVariable(name='PlotXData',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._plotXGet,
                                 description=""))

        for i in range(10):
            self.add(pr.LinkVariable(name=f'PlotYData[{i}]',
                                     mode='RO',
                                     hidden=True,
                                     dependencies=[self.PlotColumn,self.SaTuneOutput],
                                     linkedGet=lambda i=i: self._plotYGet(i),
                                     description=""))

    def _plotXGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()

            if col >= len(self.SaTuneOutput.value()):
                return np.array([0.0])
            else:
                return np.array(self.SaTuneOutput.value()[col].xValues_)

    def _plotYGet(self,i):
        with self.root.updateGroup():
            col = self.PlotColumn.value()

            if col >= len(self.SaTuneOutput.value()):
                return np.array([0.0])
            elif i >= len(self.SaTuneOutput.value()[col].curveList_):
                return np.array([0.0] * len(self.SaTuneOutput.value()[col].xValues_))
            else:
                return np.array(self.SaTuneOutput.value()[col].curveList_[i].points_)

    def _saFbGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()
            if col >= len(self.SaTuneOutput.value()):
                return 0.0
            else:
                return self.SaTuneOutput.value()[col].fbOut

    def _saBiasGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()
            if col >= len(self.SaTuneOutput.value()):
                return 0.0
            else:
                return self.SaTuneOutput.value()[col].biasOut

    def _saTuneWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.saTune(group=self.parent,process=self)
            self.SaTuneOutput.set(value=ret)

