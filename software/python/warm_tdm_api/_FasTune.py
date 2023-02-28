
import pyrogue as pr
import warm_tdm_api
import numpy as np
import matplotlib.pyplot as plt

class RowFasSweepPlot(pr.LinkVariable):

    def __init__(self, **kwargs):
        super().__init__(linkedGet=self.linkedGet, **kwargs)

        self._fig = plt.Figure(tight_layout=True, figsize=(20,20))
        self._ax = self._fig.add_subplot()
        self._fig.suptitle('FAS Flux Row')

    def _plot_ax(self, ax, row, curves):
        ax.clear()
        ax.set_ylabel('SA FB Servo')
        ax.set_xlabel(u'FAS Flux (\u03bcA)')

        numColumns = len(curves['biasValues'])

        # Plot the curve for each column
        for col in range(numColumns):
            minX = curves['lowIndexes'][col]
            minY = curves['lowPoints'][col]
            label = f'{col}: {minimum}'
            ax.plot(curves['xValues'], curves['curves'][col], '-', minX, minY, '*', label=label)

        # Plot a vertial line at the median FasFluxOn of all the curves
        median = np.median(curves['lowIndexes'])
        label = f'Median: {median}'
        ax.axvline(median, label=label)

        ax.set_title(f'Row {row} FAS Sweep')
        ax.legend(title='Column: Minimum FAS')

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.FasTuneOutput.value()

        if tune == []:
            return self._fig

        row = index
        if row == -1:
            row = self.parent.PlotRow.value()

        self._plot_ax(self._ax, row, tune[row])

        return self._fig


class FasTunePlot(pr.LinkVariable):

    def __init__(self, **kwargs):
        super().__init__(linkedGet=self.linkedGet, **kwargs)

        self._fig = plt.Figure(tight_layout=True, figsize=(20,20))
        self._ax = self._fig.add_subplot()
        self._fig.suptitle('FAS Flux Tune')

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.FasTuneOutput.value()

        if tune == []:
            return self._fig

        ax.plot([np.median(row['lowIndexes']) for row in tune])

        return self._fig


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

        # Set values after finish
        self.add(pr.LocalVariable(name='SetAfterFinish',
                                  value=False,
                                  mode='RW',
                                  description="This variable controls if the FAS set points found at the end of the process is set back. "
                                              "Otherwise the previous values of FasFluxOn, FasFluxOff and SaFb for each row will be restored."))

        # FAS Tuning Results
        self.add(pr.LocalVariable(name='FasTuneOutput',
                                  hidden=True,
                                  value=[],
                                  mode='RO',
                                  description="Results Data From FAS Tuning"))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

        self.add(pr.LocalVariable(
            name = 'PlotRow',
            value = 0))

        self.add(RowFasSweepPlot(
            name = 'SweepPlot',
            hidden = True,
            dependencies = [self.PlotRow, self.FasTuneOutput]))

        self.add(FasTunePlot(
            name = 'TunePlot',
            hidden = True,
            dependencies = [self.FasTuneOutput]))

    def _fasTuneWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.fasTune(group=self.parent, process=self)
            self.FasTuneOutput.set(value=[r.asDict() for r in ret])
