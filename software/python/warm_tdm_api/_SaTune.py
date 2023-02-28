import pyrogue as pr
import warm_tdm_api
import numpy as np

class SaTuneProcess(pr.Process):

    def __init__(self, *, config, maxBiasSteps=10, **kwargs):
        self._maxBiasSteps=maxBiasSteps

        # Init master class
        pr.Process.__init__(self, function=self._saTuneWrap,
                            description='Process which performs an SA tuning step.'
                                        'This tuning process sweeps the SaFb value and determines the SaOffset value required zero out the SaOut '
                                        'value. This sweep is repeated for a series of SaBias values. Once the sweep is completed the process will '
                                        'determine the SaBias value which results in the largest peak to peak amplitude in the SaFb vs SaOffset curve. '
                                        'For the select SaBias curce the process will then select the point on the curve with the highest slope.'
                                        'The resulting curves are available as a dictionary of numpy arrays.',
                            **kwargs)

        # Low offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description='Starting point offset for SA FB Tuning. This value is an offset from the currently configured '
                                              'SaFb value. (well not in the current code, but it should be). '))

        # High offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbHighOffset',
                                  value=1.0,
                                  mode='RW',
                                  description='Ending point offset for SA FB Tuning. This value is an offset from the currently configured '
                                              'SaFb value. (well not in the current code, but it should be). '))

        # Step size for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbNumSteps',
                                  minimum=1,
                                  maximum=10000,
                                  value=1000,
                                  mode='RW',
                                  description='Number of steps between the SaFbLowOffset and SaFbHighOffset, inclusively.'))

        # Wait time between FB set and output sampling
        self.add(pr.LocalVariable(name='SaFbSampleDelay',
                                  value=.001,
                                  groups='NoDoc',
                                  mode='RW',
                                  description="Wait time between FB set and SA Out sampling in seconds"))


        # Low offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasLowOffset',
                                  value=0.0,
                                  mode='RW',
                                  description='Starting point offset for SA Bias Tuning. This value is an offset from the currently configured '
                                              'SaBias value. (well not in the current code, but it should be). '))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHighOffset',
                                  value=1.0,
                                  mode='RW',
                                  description='Ending point offset for SA Bias Tuning. This value is an offset from the currently configured '
                                              'SaBias value. (well not in the current code, but it should be). '))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasNumSteps',
                                  minimum=1,
                                  maximum=self._maxBiasSteps,
                                  value=10,
                                  mode='RW',
                                  description='Number of steps between the SaBiasLowOffset and SaBiasHighOffset, inclusively.'))

        # Set values after finish
        self.add(pr.LocalVariable(name='SetAfterFinish',
                                  value=False,
                                  mode='RW',
                                  description="This variale controls if the tuning point found at the end of the process is set back. "
                                              "Otherwise the previous values of SaFb and SaBias will be restored."))

        # SA Tuning Results
        self.add(pr.LocalVariable(name='SaTuneOutput',
                                  hidden=True,
                                  value={},
                                  mode='RO',
                                  description="Results Data From SA Tuning. "
                                              "This is a list of dictionaries, with one dictionary for each column in the system (ColumBoards * 8). "
                                              "Each dctionary contains the following fields: . "
                                              "xValues: x-axis values (SaFb) for each curve. "
                                              "biasValues: array of SaBias values, one for each SaBias step. "
                                              "curves: SaOffset vs SaFb curves, one for each SaBias value. "
                                              "biasOut: Selected SaBias value after fitting. "
                                              "fbOut: Selected SaFb value after fitting. "
                                              "offsetOut: Selected SaOffset out value after fitting. "))

        # Select Channel
        self.add(pr.LocalVariable(name='PlotColumn',
                                  groups='NoDoc',
                                  value=0,
                                  minimum=0,
                                  maximum=len(config.columnMap)-1,
                                  hidden=True,
                                  mode='RW',
                                  description="Controls which column is selected for the resulting plot and fitted value variables below"))


        self.add(pr.LinkVariable(name='FittedSaFb',
                                 groups='NoDoc',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saFbGet,
                                 description="Fitted SaFB value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LinkVariable(name='FittedSaBias',
                                 groups='NoDoc',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saBiasGet,
                                 description="Fitted SaBias value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LinkVariable(name='FittedSaOffset',
                                 mode='RO',
                                 groups='NoDoc',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saOffsetGet,
                                 description="Fitted SaOffset value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LinkVariable(name='PlotXData',
                                 mode='RO',
                                 groups='NoDoc',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._plotXGet,
                                 description="X-Axis data for the column selected via the PlotColumn variable above. "))

        for i in range(self._maxBiasSteps):
            self.add(pr.LinkVariable(name=f'PlotYData[{i}]',
                                     mode='RO',
                                     hidden=True,
                                     groups='NoDoc',
                                     dependencies=[self.PlotColumn,self.SaTuneOutput],
                                     linkedGet=lambda i=i: self._plotYGet(i),
                                     description="Y-Axis data for each SaBias value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LocalCommand(name='SavePlotData',
                                 value='',
                                 groups='NoDoc',
                                 function=self._saveData,
                                 description="Command to save the plot data as a numpy binary file (np.save). The arg is the filename to write the data to. "))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

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
