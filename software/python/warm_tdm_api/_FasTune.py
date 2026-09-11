import matplotlib.pyplot as plt
import numpy as np
import pyrogue as pr

import warm_tdm_api


class RowFasSweepPlot(pr.LinkVariable):

    def __init__(self, **kwargs):
        super().__init__(linkedGet=self.linkedGet, **kwargs)
        self._fig = plt.Figure(tight_layout=True, figsize=(20, 20))
        self._ax = self._fig.add_subplot()

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.FasTuneOutput.value()
        result_index = self.parent.PlotRow.value() if index == -1 else index

        self._ax.clear()
        self._ax.set_xlabel('FAS current (uA)')
        self._ax.set_ylabel('SA feedback servo (uA)')
        self._ax.grid(True)

        if result_index < 0 or result_index >= len(tune):
            self._ax.set_title(
                'SA Feedback Required to Null SA Output vs FAS Current\n'
                'Selected Row')
            self._ax.text(.5, .5, 'Not tuned', ha='center', va='center',
                          transform=self._ax.transAxes)
            return self._fig

        result = tune[result_index]
        logical_row = result['logicalRow']
        self._ax.set_title(
            'SA Feedback Required to Null SA Output vs FAS Current\n'
            f'Logical Row {logical_row}; '
            f'Row Board {result["board"]}, Address {result["address"]}')

        x_values = result['xValues']
        curves = result['curves']
        # Plot every column that produced data. Disabled columns -- and, on a
        # stopped/paused sweep, not-yet-swept columns -- have empty curves and
        # are skipped, so partial results stay plottable.
        tuned_columns = [col for col, curve in enumerate(curves)
                         if len(curve) > 0]
        if not tuned_columns:
            self._ax.text(.5, .5, 'No tuning data', ha='center', va='center',
                          transform=self._ax.transAxes)
            return self._fig

        for col in tuned_columns:
            curve = curves[col]
            # A curve may be shorter than x_values if the sweep was stopped
            # mid-acquisition; plot against as many x points as were collected.
            x = x_values[:len(curve)]
            line, = self._ax.plot(x, curve, label=f'Column {col}')
            # Mark this column's sampled response minimum.
            min_idx = int(np.argmin(curve))
            self._ax.plot(x[min_idx], curve[min_idx], '*',
                          color=line.get_color())

        # One physical FAS-on current is selected across the tuned columns
        # (median of per-column minima) and shared by every column on this line.
        fas_on = result['fasOn']
        if fas_on is not None:
            self._ax.axvline(
                fas_on, linestyle='--',
                label=f'Selected FAS-on {fas_on:.3f} uA')
        self._ax.legend()
        return self._fig


class FasTunePlot(pr.LinkVariable):

    def __init__(self, **kwargs):
        super().__init__(linkedGet=self.linkedGet, **kwargs)
        self._fig = plt.Figure(tight_layout=True, figsize=(20, 20))
        self._ax = self._fig.add_subplot()

    def linkedGet(self, index=-1, read=False):
        tune = self.parent.FasTuneOutput.value()
        self._ax.clear()
        self._ax.set_title('Selected FAS-On Current vs Logical Row')
        self._ax.set_xlabel('Logical row')
        self._ax.set_ylabel('Selected FAS-on current (uA)')
        self._ax.grid(True)

        if not tune:
            self._ax.text(.5, .5, 'Not tuned', ha='center', va='center',
                          transform=self._ax.transAxes)
            return self._fig

        rows = [result['logicalRow'] for result in tune]
        currents = [
            np.nan if result['fasOn'] is None else result['fasOn']
            for result in tune
        ]
        self._ax.plot(rows, currents, marker='o')
        return self._fig


class FasTuneProcess(warm_tdm_api.PausableProcess):

    def __init__(self, *, config, **kwargs):
        super().__init__(
            function=self._fasTuneWrap,
            description=(
                'Sweep each enabled FAS line, select its on-current, and '
                'optionally program the fitted values.'),
            **kwargs)

        self.add(pr.LocalVariable(
            name='FasFluxLowOffset',
            value=0.0,
            mode='RW',
            units='uA',
            description='First FAS current in the sweep.'))
        self.add(pr.LocalVariable(
            name='FasFluxHighOffset',
            value=310.0,
            mode='RW',
            units='uA',
            description='Last FAS current in the sweep.'))
        self.add(pr.LocalVariable(
            name='FasFluxNumSteps',
            value=21,
            minimum=2,
            mode='RW',
            description='Number of FAS sweep points.'))
        self.add(pr.LocalVariable(
            name='FasMinimumTolerance',
            value=0.1,
            minimum=0.0,
            mode='RW',
            units='uA',
            description='SA-feedback tolerance above the sampled minimum '
                        'used to identify a contiguous flat-bottom region. '
                        'FasOn is selected at the region midpoint.'))
        self.add(pr.LocalVariable(
            name='FasFluxSampleDelay',
            value=0.001,
            mode='RW',
            units='s',
            description='Wall-clock delay after each ManualSet write.'))
        self.add(pr.LocalVariable(
            name='Sq1BiasCurrent',
            value=40.0,
            mode='RW',
            units='uA',
            description='Temporary SQ1 bias applied to enabled columns while '
                        'measuring the FAS response. The original force-current '
                        'values are restored when the process exits.'))
        self.add(pr.LocalVariable(
            name='SetAfterFinish',
            value=False,
            mode='RW',
            description='Program the fitted FasOn currents after a successful '
                        'sweep. When false, only publish the tuning results.'))

        # saFbServo() reads these parameters from its calling Process.
        self.add(pr.LocalVariable(
            name='ServoKp',
            value=0.8,
            mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoKi',
            value=0.0,
            mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoKd',
            value=0.0,
            mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoPrecision',
            value=0.01,
            mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoMaxLoops',
            value=500,
            minimum=1,
            mode='RW'))
        self.add(pr.LocalVariable(
            name='FasTuneOutput',
            hidden=True,
            value=[],
            mode='RO',
            description='FAS sweep results in active row order.'))
        self.add(pr.LocalVariable(
            name='PlotRow',
            value=0,
            minimum=0,
            maximum=max(config.maxRows-1, 0),
            mode='RW',
            description='Index into the active-row sweep results. The sweep '
                        'plot shows every tuned column for the selected row.'))

        self.add(RowFasSweepPlot(
            name='SweepPlot',
            hidden=True,
            mode='RO',
            dependencies=[self.PlotRow, self.FasTuneOutput]))
        self.add(FasTunePlot(
            name='TunePlot',
            hidden=True,
            mode='RO',
            dependencies=[self.FasTuneOutput]))

    def _fasTuneWrap(self):
        # Detailed acquisition/programming trace is emitted at DEBUG; raise this
        # node's log level to DEBUG to see it when diagnosing a run.
        self._log.debug('Entering FAS tune update group')
        with self.root.updateGroup(0.25):
            curves = warm_tdm_api.fasTune(
                group=self.parent,
                process=self,
                doSet=self.SetAfterFinish.value())
            self._log.debug('Serializing %d FAS sweep result(s)', len(curves))
            output = self._publishResults(curves)
        self._log.debug('Published %d FAS sweep result(s)', len(output))
        self._log.debug('FAS tune process callback finished')

    def _publishResults(self, curves):
        output = []
        for curve in curves:
            result = curve.asDict()
            result.update({
                'logicalRow': curve.logicalRow,
                'board': curve.board,
                'address': curve.address,
                'fasOn': curve.fasOn,
            })
            output.append(result)
        self.FasTuneOutput.set(output)
        return output
