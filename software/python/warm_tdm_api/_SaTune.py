import pyrogue as pr
import warm_tdm_api
import numpy as np
import matplotlib.pyplot as plt
import time

class SinglePlot(pr.LinkVariable):

    def __init__(self, **kwargs):
        super().__init__(
            linkedGet=self.linkedGet,
            **kwargs)

        self._fig = plt.Figure(tight_layout=True, figsize=(20,10))
        self._ax = self._fig.add_subplot()
        self._fig.suptitle(u'SA OUT (mV) vs. SA FB (\u03bcA)')

    def _plot_ax(self, ax, col, curves, shunt):
        ax.clear()
        ax.set_ylabel('SA Out (mV)')
        ax.set_xlabel(u'SA FB (\u03bcA)')
        
        for step, value in enumerate(curves['biasValues']):
            linewidth = 1.0
            if step == curves['bestIndex']:
                linewidth = 2.0
            peak = curves['peaks'][step] 
            label = f'{value:1.3f} - P-P: {peak:1.3f}'
            ax.plot(curves['xValues'], curves['curves'][step], label=label, linewidth=linewidth)

        A, w, p, c = curves['bestfit'] 
        fitfunc = lambda t: A * np.sin(w*t + p) + c
        r = np.linspace(min(curves['xValues']), max(curves['xValues']), 1000)
        fitline = np.array([fitfunc(t) for t in r])
        label = f'fitted - P-P: {A*2:0.03f} - ' + u'\u03A6o: ' + f'{(2.0*np.pi)/w:0.01f}'
        ax.plot(r, fitline, label=label, linestyle='dashed')
            
        ax.set_title(f'Channel {col} - FB Shunt = {shunt/1000} kOhms')
        ax.legend(title=u'SA BIAS (\u03bcA) - SA OUT P-P (mV)')
        

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.SaTuneOutput.value()
        
        if tune == {}:
            return self._fig

        col = index
        if col == -1:
            col = self.parent.PlotColumn.value()

        shunt = self.parent.parent.SA_FB_SHUNT_R.value()            

        self._plot_ax(self._ax, col, tune[col], shunt[col])

        return self._fig

class MultiPlot(SinglePlot):

    def __init__(self, **kwargs):
        pr.LinkVariable.__init__(
            self,
            linkedGet = self.linkedGet,
            **kwargs)
        
        self._fig = plt.Figure(tight_layout=True, figsize=(20, 20))
        self._ax = self._fig.subplots(4, 2, sharey=True)
        self._fig.suptitle('SA OUT (mV) vs. SA FB (\u03bcA)')

    def linkedGet(self):
        tune = self.parent.SaTuneOutput.value()
        shunt = self.parent.parent.SA_FB_SHUNT_R.value()        

        if tune == {}:
            return self._fig

        axes = self._ax.reshape(8)
        for col, ax in enumerate(axes):
            self._plot_ax(ax, col, tune[col], shunt[col])

        return self._fig


class SaTuneProcess(pr.Process):

    def __init__(self, *, config, maxBiasSteps=10, **kwargs):
        self._maxBiasSteps = maxBiasSteps
        
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
                                  units = 'uA',
                                  description='Starting point offset for SA FB Tuning. This value is an offset from the currently configured '
                                              'SaFb value. (well not in the current code, but it should be). '))

        # High offset for SA FB Tuning
        self.add(pr.LocalVariable(name='SaFbHighOffset',
                                  value=300.0,
                                  units='uA',
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
                                  value=20.0,
                                  mode='RW',
                                  units = 'uA',
                                  description='Starting point offset for SA Bias Tuning. This value is an offset from the currently configured '
                                              'SaBias value. (well not in the current code, but it should be). '))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHighOffset',
                                  value=60.0,
                                  mode='RW',
                                  units = 'uA',
                                  description='Ending point offset for SA Bias Tuning. This value is an offset from the currently configured '
                                              'SaBias value. (well not in the current code, but it should be). '))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasNumSteps',
                                  minimum=1,
                                  maximum=self._maxBiasSteps,
                                  value=5,
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

        self.add(SinglePlot(name='Plot',
                            mode='RO',
                            hidden=True,
                            dependencies = [self.SaTuneOutput, self.PlotColumn],
                            description = 'A matplotlib figure of a selected column'))

        self.add(MultiPlot(name='MultiPlot',
                           mode='RO',
                           hidden=True,
                           dependencies = [self.SaTuneOutput],
                           description = 'A matplotlib figure of all the curves'))
        

        self.add(pr.LocalCommand(name='SavePlotData',
                                 value='',
                                 function=self._saveData,
                                 description="Command to save the plot data as a numpy binary file (np.save). The arg is the filename to write the data to. "))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')


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

