
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
        ax.grid(True)

        if curves is None or len(curves['biasValues']) == 0:
            ax.set_title(f'Row {row} FAS Sweep')
            ax.text(.5, .5, 'Not Tuned', ha='center', va='center', fontsize=28)
            return

        numColumns = len(curves['biasValues'])
        low_points = np.asarray(curves['lowPoints'])
        low_fluxes = low_points[:, 0]

        # Plot the curve for each column
        for col in range(numColumns):
            min_x, min_y = low_points[col]
            label = f'{col}: {min_x:0.3f}'
            ax.plot(curves['xValues'], curves['curves'][col], '-', label=label)
            ax.plot(min_x, min_y, '*')

        # Plot a vertical line at the median FAS flux minimum across all columns.
        median = np.median(low_fluxes)
        label = f'Median: {median:0.3f}'
        ax.axvline(median, label=label)

        ax.set_title(f'Row {row} FAS Sweep')
        ax.legend(title='Column: Minimum FAS')

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.FasTuneOutput.value()
        self._ax.clear()

        if tune == []:
            self._ax.set_title('FAS Flux Row')
            self._ax.text(.5, .5, 'Not Tuned', ha='center', va='center', fontsize=28)
            return self._fig

        row = index
        if row == -1:
            row = self.parent.PlotRow.value()

        if row >= len(tune):
            self._ax.set_title(f'Row {row} FAS Sweep')
            self._ax.text(.5, .5, 'Not Tuned', ha='center', va='center', fontsize=28)
            return self._fig

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

        self._ax.clear()
        self._ax.set_title('FAS Flux Tune')
        self._ax.set_xlabel('Row')
        self._ax.set_ylabel(u'Median FAS Flux Minimum (\u03bcA)')
        self._ax.grid(True)

        if tune == []:
            self._ax.text(.5, .5, 'Not Tuned', ha='center', va='center', fontsize=28)
            return self._fig

        medians = []
        for row_curves in tune:
            low_points = np.asarray(row_curves['lowPoints'])
            if len(low_points) == 0:
                medians.append(np.nan)
            else:
                medians.append(np.median(low_points[:, 0]))

        rows = np.arange(len(medians))
        self._ax.plot(rows, medians, marker='o')

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

        # FAS Tuning Results
        self.add(pr.LocalVariable(name='FasTuneOutput',
                                  hidden=True,
                                  value=[],
                                  mode='RO',
                                  description="Results Data From FAS Tuning"))

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
