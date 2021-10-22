import pyrogue as pr
import warm_tdm_api
import numpy as np

class SaTuneProcess(pr.Process):

    def __init__(self, *, config, maxBiasSteps=10, **kwargs):
        self._maxBiasSteps=maxBiasSteps

        # Init master class
        pr.Process.__init__(self, function=self._saTuneWrap, **kwargs)

        self.add(pr.LocalVariable(name='TestString',
                                  value='',
                                  mode='RW',
                                  description=""))

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
                                  minimum=1,
                                  maximum=10000,
                                  value=1000,
                                  mode='RW',
                                  description="Number of steps for SA FB Tuning"))

        # Wait time between FB set and output sampling
        self.add(pr.LocalVariable(name='SaFbSampleDelay',
                                  value=.001,
                                  mode='RW',
                                  description="Wait time between FB set and SA Out sampling in seconds"))


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
                                  minimum=1,
                                  maximum=self._maxBiasSteps,
                                  value=10,
                                  mode='RW',
                                  description="Number of steps for SA Bias Tuning"))

        # Set values after finish
        self.add(pr.LocalVariable(name='SetAfterFinish',
                                  value=False,
                                  mode='RW',
                                  description="Set the values after finish"))

        # Select Channel
        self.add(pr.LocalVariable(name='PlotColumn',
                                  value=0,
                                  minimum=0,
                                  maximum=len(config.columnMap)-1,
                                  hidden=True,
                                  mode='RW',
                                  description="Channel Number To Plot"))

        # SA Tuning Results
        self.add(pr.LocalVariable(name='SaTuneOutput',
                                  hidden=True,
                                  value={},
                                  mode='RO',
                                  description="Results Data From SA Tuning"))

        self.add(pr.LinkVariable(name='FittedSaFb',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saFbGet,
                                 description=""))

        self.add(pr.LinkVariable(name='FittedSaBias',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saBiasGet,
                                 description=""))

        self.add(pr.LinkVariable(name='FittedSaOffset',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saOffsetGet,
                                 description=""))

        self.add(pr.LinkVariable(name='PlotXData',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._plotXGet,
                                 description=""))

        for i in range(self._maxBiasSteps):
            self.add(pr.LinkVariable(name=f'PlotYData[{i}]',
                                     mode='RO',
                                     hidden=True,
                                     dependencies=[self.PlotColumn,self.SaTuneOutput],
                                     linkedGet=lambda i=i: self._plotYGet(i),
                                     description=""))

        self.add(pr.LocalCommand(name='SavePlotData',
                                 value='',
                                 function=self._saveData,
                                 description=""))

    def _plotXGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()

            if col >= len(self.SaTuneOutput.value()):
                return np.array([0.0])
            else:
                return self.SaTuneOutput.value()[col]['xValues']

    def _plotYGet(self,i):
        with self.root.updateGroup():
            col = self.PlotColumn.value()

            if col >= len(self.SaTuneOutput.value()) or i >= len(self.SaTuneOutput.value()[col]['curves']):
                return np.array([0.0])
            else:
                return self.SaTuneOutput.value()[col]['curves'][i]

    def _saFbGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()
            if col >= len(self.SaTuneOutput.value()):
                return 0.0
            else:
                return self.SaTuneOutput.value()[col]['fbOut']

    def _saBiasGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()
            if col >= len(self.SaTuneOutput.value()):
                return 0.0
            else:
                return self.SaTuneOutput.value()[col]['biasOut']

    def _saOffsetGet(self):
        with self.root.updateGroup():
            col = self.PlotColumn.value()
            if col >= len(self.SaTuneOutput.value()):
                return 0.0
            else:
                return self.SaTuneOutput.value()[col]['offsetOut']

    def _saTuneWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.saTune(group=self.parent,process=self,doSet=self.SetAfterFinish.value())
            self.SaTuneOutput.set(value=[r.asDict() for r in ret])

    def _saveData(self,arg):
        print(f"Save data called with {arg}")
        if arg != '':
            np.save(arg,self.SaTuneOutput.value())
