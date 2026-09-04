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
        column = self.parent.PlotColumn.value()

        self._ax.clear()
        self._ax.set_xlabel('FAS current (uA)')
        self._ax.set_ylabel('SA feedback servo (uA)')
        self._ax.grid(True)

        if result_index < 0 or result_index >= len(tune):
            self._ax.set_title(
                'SA Feedback Required to Null SA Output vs FAS Current\n'
                f'Selected Row, Column {column}')
            self._ax.text(.5, .5, 'Not tuned', ha='center', va='center',
                          transform=self._ax.transAxes)
            return self._fig

        result = tune[result_index]
        logical_row = result['logicalRow']
        self._ax.set_title(
            'SA Feedback Required to Null SA Output vs FAS Current\n'
            f'Logical Row {logical_row}, Column {column}; '
            f'Row Board {result["board"]}, Address {result["address"]}')
        x_values = result['xValues']
        curves = result['curves']
        if column < 0 or column >= len(curves):
            self._ax.text(
                .5, .5, f'Column {column} is unavailable',
                ha='center', va='center', transform=self._ax.transAxes)
            return self._fig

        curve = curves[column]
        if len(curve) == 0:
            self._ax.text(
                .5, .5, f'No tuning data for Column {column}',
                ha='center', va='center', transform=self._ax.transAxes)
            return self._fig

        self._ax.plot(
            x_values[:len(curve)], curve, label=f'Column {column}')

        if result['fasOn'] is not None:
            self._ax.axvline(
                result['fasOn'], linestyle='--',
                label=f'Selected FAS-on {result["fasOn"]:.3f} uA')
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


class FasTuneProcess(pr.Process):

    def __init__(self, *, config, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name='FasFluxLowOffset', value=0.0, mode='RW', units='uA',
            description='First FAS current in the sweep.'))
        self.add(pr.LocalVariable(
            name='FasFluxHighOffset', value=310.0, mode='RW', units='uA',
            description='Last FAS current in the sweep.'))
        self.add(pr.LocalVariable(
            name='FasFluxNumSteps', value=21, minimum=2, mode='RW',
            description='Number of FAS sweep points.'))
        self.add(pr.LocalVariable(
            name='FasMinimumTolerance', value=0.1, minimum=0.0,
            mode='RW', units='uA',
            description='SA-feedback tolerance above the sampled minimum '
                        'used to identify a contiguous flat-bottom region. '
                        'FasOn is selected at the region midpoint.'))
        self.add(pr.LocalVariable(
            name='FasFluxSampleDelay', value=0.001, mode='RW', units='s',
            description='Wall-clock delay after each ManualSet write.'))
        self.add(pr.LocalVariable(
            name='FasFluxSampleReads', value=3, minimum=0, mode='RW',
            description='Number of averaged-ADC reads discarded after each '
                        'ManualSet write. These transactions advance cosim '
                        'before the SA feedback servo tests convergence.'))
        self.add(pr.LocalVariable(
            name='Sq1BiasCurrent', value=40.0, mode='RW', units='uA',
            description='Temporary SQ1 bias applied to enabled columns while '
                        'measuring the FAS response. The original force-current '
                        'values are restored when the process exits.'))
        self.add(pr.LocalVariable(
            name='SetAfterFinish', value=False, mode='RW',
            description='Program the fitted FasOn currents after a successful '
                        'sweep. When false, only publish the tuning results.'))

        # saFbServo() reads these parameters from its calling Process.
        self.add(pr.LocalVariable(
            name='ServoKp', value=0.8, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoKi', value=0.0, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoKd', value=0.0, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoPrecision', value=0.01, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoMaxLoops', value=500, minimum=1, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoSampleReads', value=3, minimum=0, mode='RW',
            description='Number of averaged-ADC reads discarded after each SA '
                        'feedback write so the new value can propagate in '
                        'cosim.'))

        self.add(pr.LocalVariable(
            name='FasTuneOutput', hidden=True, value=[], mode='RO',
            description='FAS sweep results in active row order.'))
        self.add(pr.LocalVariable(
            name='PlotRow', value=0, minimum=0,
            maximum=max(config.maxRows-1, 0), mode='RW',
            description='Index into the active-row sweep results.'))
        self.add(pr.LocalVariable(
            name='PlotColumn', value=0, minimum=0,
            maximum=max(config.numColumns-1, 0), mode='RW',
            description='Column displayed in the selected-row FAS sweep '
                        'response plot.'))

        self.add(RowFasSweepPlot(
            name='SweepPlot', hidden=True, mode='RO',
            dependencies=[
                self.PlotRow, self.PlotColumn, self.FasTuneOutput]))
        self.add(FasTunePlot(
            name='TunePlot', hidden=True, mode='RO',
            dependencies=[self.FasTuneOutput]))

    def _process(self):
        """Run without reporting a user-stopped tune as successfully done."""
        # Enable the detailed acquisition/programming trace for every FAS run.
        # Do this after attachment so the full-path PyRogue logger is active.
        self.setLogLevel('DEBUG', includeRogue=False)
        self._log.debug('FAS tune process starting with debug logging enabled')
        self.Message.setDisp('Running')
        self.setStep(0)
        self.setProgress(0.0)

        self._fasTuneWrap()

        if self._runEn:
            self._log.debug('FAS tune process completed normally')
            self.Message.setDisp('Done')
            self.setProgress(1.0)
        else:
            self._log.debug(
                'FAS tune process stopped at step %s of %s',
                self.Step.value(), self.TotalSteps.value())
            self.Message.setDisp('Stopped')

    def _fasTuneWrap(self):
        self._log.debug('Entering FAS tune update group')
        with self.root.updateGroup(0.25):
            curves = warm_tdm_api.fasTune(
                group=self.parent,
                process=self,
                doSet=self.SetAfterFinish.value())
            self._log.debug('Serializing %d FAS sweep result(s)', len(curves))
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
        self._log.debug('Published %d FAS sweep result(s)', len(output))
