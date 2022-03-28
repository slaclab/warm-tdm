import pyrogue as pr
import warm_tdm_api
import numpy as np
import matplotlib.pyplot as plt
import time

class SaTuneProcess(pr.Process):

    def __init__(self, *, config, maxBiasSteps=10, **kwargs):
        self._maxBiasSteps=maxBiasSteps

        self._single_fig = plt.Figure(tight_layout=True, figsize=(20,10))
        self._single_ax = self._single_fig.add_subplot()
        self._single_fig.suptitle('SA FB (DAC V) vs. SA OUT (V@ADC)')                
        
        self._multi_fig = plt.Figure(tight_layout=True, figsize=(20, 20))
        self._multi_ax = self._multi_fig.subplots(4, 2, sharey=True)
        self._multi_fig.suptitle('SA FB (DAC V) vs. SA OUT (V@ADC)')        
        
        self._columns = len(config.columnMap)

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
                                  value=0,
                                  minimum=0,
                                  maximum=len(config.columnMap)-1,
                                  hidden=True,
                                  mode='RW',
                                  description="Controls which column is selected for the resulting plot and fitted value variables below"))


        self.add(pr.LinkVariable(name='FittedSaFb',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saFbGet,
                                 description="Fitted SaFB value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LinkVariable(name='FittedSaBias',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saBiasGet,
                                 description="Fitted SaBias value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LinkVariable(name='FittedSaOffset',
                                 mode='RO',
                                 hidden=True,
                                 dependencies=[self.PlotColumn,self.SaTuneOutput],
                                 linkedGet=self._saOffsetGet,
                                 description="Fitted SaOffset value for the column selected via the PlotColumn variable above. "))

#         self.add(pr.LinkVariable(name='PlotXData',
#                                  mode='RO',
#                                  hidden=True,
#                                  dependencies=[self.PlotColumn,self.SaTuneOutput],
#                                  linkedGet=self._plotXGet,
#                                  description="X-Axis data for the column selected via the PlotColumn variable above. "))

#         for i in range(self._maxBiasSteps):
#             self.add(pr.LinkVariable(name=f'PlotYData[{i}]',
#                                      mode='RO',
#                                      hidden=True,
#                                      dependencies=[self.PlotColumn,self.SaTuneOutput],
#                                      linkedGet=lambda i=i: self._plotYGet(i),
#                                      description="Y-Axis data for each SaBias value for the column selected via the PlotColumn variable above. "))

        self.add(pr.LinkVariable(name='Plot',
                                 mode='RO',
                                 hidden=True,
                                 dependencies = [self.SaTuneOutput, self.PlotColumn],
                                 linkedGet = self._singlePlot,
                                 description = 'A matplotlib figure of all the curves'))

        self.add(pr.LinkVariable(name='PlotMulti',
                                 mode='RO',
                                 hidden=True,
                                 dependencies = [self.SaTuneOutput],
                                 linkedGet = self._multiPlot,
                                 description = 'A matplotlib figure of all the curves'))
        

        @self.command(hidden=True)
        def AllPlots():
            for i in range(self._columns):
                self.PlotColumn.set(i)
                time.sleep(.5)
                self.Plot.get()
                time.sleep(.5)

        self.add(pr.LocalCommand(name='SavePlotData',
                                 value='',
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

    def _plotYGet(self, index):
        with self.root.updateGroup():
            col = index #self.PlotColumn.value()

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

    def _plot_ax(self, ax, col, curves):
        ax.clear()
        for step, value in enumerate(curves['biasValues']):
            linewidth = 1.0
            if step == curves['bestIndex']:
                linewidth = 2.0
            peak = curves['peaks'][step]
            label = f'{value:1.3f} - Peak: {peak:1.3f}'
            ax.plot(curves['xValues'], curves['curves'][step], label=label, linewidth=linewidth)

        ax.set_title(f'Channel {col}')
        ax.legend(title='SA BIAS')
        

    def _singlePlot(self, index=-1, read=False):
        print(f'_singlePlot(index={index}, read={read})')
#        if self._single_fig is not None:
#            plt.close(self._single_fig)
        tune = self.SaTuneOutput.value()
        
        if tune == {}:
            return self._single_fig

        col = index
        if col == -1:
            col = self.PlotColumn.value()

        self._plot_ax(self._single_ax, col, tune[col])

        return self._single_fig
            

    def _multiPlot(self):
        tune = self.SaTuneOutput.value()

        if tune == {}:
            return self._multi_fig

        axes = self._multi_ax.reshape(8)
        for col, ax in enumerate(axes):
            self._plot_ax(ax, col, tune[col])


        return self._multi_fig
