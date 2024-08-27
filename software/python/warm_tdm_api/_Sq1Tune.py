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
        self._fig.suptitle(u'SA FB (\u03bcA) vs. SQ1 FB (\u03bcA)')

    def _plot_ax(self, ax, col, row, tune):
        if row >= len(tune):
            curves = None
        elif col >= len(tune[row]):
            curves = None
        else:
            curves = tune[row][col]

        warm_tdm_api.plotCurveDataDict(
            ax=ax,
            curveDataDict=curves,
            ax_title=f'Row {row} Column {col}',
            xlabel=u'SQ1 FB (\u03bcA)',
            ylabel=u'SA FB (\u03bcA)',
            legend_title='SQ1 Bias Curves')

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.Sq1TuneOutput.value()

        if tune == {} or tune == []:
            return self._fig


        if index == -1:
            col = self.parent.PlotColumn.value()
            row = self.parent.PlotRow.value()
        else:
            col, row = index

        print(f'Sq1TunePlot - {row=}, {col=}')

 #       shunts = [self.parent.Loading.Column[x].SQ1_FB_SHUNT_R.value() for x in range(8)]

        self._plot_ax(self._ax, col, row, tune)

        return self._fig

class MultiPlot(SinglePlot):

    def __init__(self, **kwargs):
        pr.LinkVariable.__init__(
            self,
            linkedGet = self.linkedGet,
            **kwargs)

        self._fig = plt.Figure(tight_layout=True, figsize=(20, 20))
        self._ax = self._fig.subplots(4, 2, sharey=True)
        self._fig.suptitle(u'SA FB (\u03bcA) vs. SQ1 FB (\u03bcA)')

    def linkedGet(self, index=-1):
        tune = self.parent.Sq1TuneOutput.value()
#        shunt = self.parent.parent.SQ1_FB_SHUNT_R.value()

        if tune == {} or tune == []:
            return self._fig

        if index == -1:
            row = self.parent.PlotRow.value()
        else:
            row = index

        axes = self._ax.reshape(8)
        for col, ax in enumerate(axes):
            self._plot_ax(ax, col, row, tune)

        return self._fig

class Sq1TuneProcess(pr.Process):

    def __init__(self, *, config, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._sq1TuneWrap, **kwargs)

        # Low offset for SQ1 FB Tuning
        self.add(pr.LocalVariable(
            name='Sq1FbLowOffset',
            value=-77.0,
            mode='RW',
            units=u'\u03bcA',
            description="Starting point offset for SQ1 FB Tuning"))

        # High offset for SQ1 FB Tuning
        self.add(pr.LocalVariable(
            name='Sq1FbHighOffset',
            value=77.0,
            mode='RW',
            units=u'\u03bcA',
            description="Ending point offset for SQ1 FB Tuning"))

        # Step size for SQ1 FB Tuning
        self.add(pr.LocalVariable(
            name='Sq1FbNumSteps',
            value=300,
            mode='RW',
            description="Number of steps for SQ1 FB Tuning"))

        # Low offset for SQ1 Bias Tuning
        self.add(pr.LocalVariable(
            name='Sq1BiasLowOffset',
            value=0.0,
            mode='RW',
            units=u'\u03bcA',
            description="Starting point offset for SQ1 Bias Tuning"))

        # High offset for SQ1 Bias Tuning
        self.add(pr.LocalVariable(
            name='Sq1BiasHighOffset',
            value=75.0,
            mode='RW',
            units=u'\u03bcA',
            description="Ending point offset for SQ1 Bias Tuning"))

        # Step size for SQ1 Bias Tuning
        self.add(pr.LocalVariable(
            name='Sq1BiasNumSteps',
            value=10,
            mode='RW',
            description="Number of steps for SQ1 Bias Tuning"))

        self.add(pr.LocalVariable(
            name='ServoKp',
            value=-0.8,
            mode='RW',
            description="Proportional PID coefficient"))

        self.add(pr.LocalVariable(
            name='ServoKi',
            value=0.0,
            mode='RW',
            description="Integral PID coefficient"))

        self.add(pr.LocalVariable(
            name='ServoKd',
            value=0.0,
            mode='RW',
            description="Differential PID coefficient"))

        self.add(pr.LocalVariable(
            name='ServoPrecision',
            value=0.01,
            mode='RW',
            description="Convergance precision"))


        self.add(pr.LocalVariable(
            name='ServoMaxLoops',
            value=500,
            mode='RW',
            description="Max number of loops for PID convergance"))

        self.add(pr.LocalVariable(
            name='ServoDisable',
            value=False,
            mode='RW',
            description="Disable the servo and grab SaOutAdc directly"))


        # SQ1 Tuning Results
        self.add(pr.LocalVariable(
            name='Sq1TuneOutput',
            value={},
            hidden=True,
            mode='RO',
            description="Results Data From SQ1 Tuning"))

        self.add(pr.LocalVariable(
            name='PlotColumn',
            value=0,
            minimum=0,
            maximum=len(config.columnMap)-1,
            mode='RW',
            description="Controls which column is selected for the resulting plot and fitted value variables below"))

        self.add(pr.LocalVariable(
            name='PlotRow',
            value=0,
            minimum=0,
            maximum=len(config.rowMap)-1,
            mode='RW',
            description="Controls which row is selected for the resulting plot and fitted value variables below"))


        self.add(pr.LinkVariable(
            name='FittedSq1Fb',
            mode='RO',
            dependencies=[self.PlotColumn, self.PlotRow, self.Sq1TuneOutput],
            linkedGet=self._sq1FbGet,
            description="Fitted Sq1FB value for the column and row selected"))

        self.add(pr.LinkVariable(
            name='FittedSq1Bias',
            mode='RO',
            dependencies=[self.PlotColumn, self.PlotRow, self.Sq1TuneOutput],
            linkedGet=self._sq1BiasGet,
            description="Fitted Sq1Bias value for the column and row selected"))

        self.add(pr.LinkVariable(
            name='FittedSaFb',
            mode='RO',
            dependencies=[self.PlotColumn, self.PlotRow, self.Sq1TuneOutput],
            linkedGet=self._saFbGet,
            description="Fitted SaFb value for the column and row selected"))

        self.add(SinglePlot(
            name='Plot',
            mode='RO',
            hidden=True,
            dependencies = [self.Sq1TuneOutput, self.PlotColumn, self.PlotRow],
            description = 'A matplotlib figure of a selected column and row'))

        self.add(MultiPlot(
            name='MultiPlot',
            mode='RO',
            hidden=True,
            dependencies = [self.Sq1TuneOutput, self.PlotRow],
            description = 'A matplotlib figure of all the curves for a row'))

        self.add(pr.LocalCommand(
            name='SavePlotData',
            value='',
            function=self._saveData,
            description="Command to save the plot data as a numpy binary file (np.save). The arg is the filename to write the data to. "))


    def _getHelper(self, field):
        with self.root.updateGroup():
            col = self.PlotColumn.value()
            row = self.PlotRow.value()
            tune = self.Sq1TuneOutput.value()
            if row >= len(tune):
                return 0.0
            if col > len(tune[row]):
                return 0.0
            else:
                return tune[row][col][field]

    def _sq1FbGet(self):
        return self._getHelper('xOut')

    def _sq1BiasGet(self):
        return self._getHelper('biasOut')

    def _saFbGet(self):
        return self._getHelper('yOut')

    def _sq1TuneWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.sq1Tune(group=self.parent, process=self)
        self.Sq1TuneOutput.set(value = [[col.asDict() for col in row] for row in ret])
        print('SQ1Tune Output')
        print(self.Sq1TuneOutput.value())

    def _saveData(self,arg):
        print(f"Sq1Tune - Save data called with {arg=}")
        filename = arg
        if arg is None or arg == '':
            timestr = time.strftime("%Y%m%d-%H%M%S")
            filename = f'SQ1Tune_{timestr}.npy'

        np.save(filename, self.Sq1TuneOutput.value())
