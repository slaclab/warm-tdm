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
            self._ax.set_title('FAS sweep')
            self._ax.text(.5, .5, 'Not tuned', ha='center', va='center',
                          transform=self._ax.transAxes)
            return self._fig

        result = tune[result_index]
        logical_row = result['logicalRow']
        self._ax.set_title(
            f'Logical row {logical_row}: row board {result["board"]}, '
            f'address {result["address"]}')
        x_values = result['xValues']
        for column, curve in enumerate(result['curves']):
            if len(curve) != 0:
                self._ax.plot(
                    x_values[:len(curve)], curve, label=f'Column {column}')

        if result['fasOn'] is not None:
            self._ax.axvline(
                result['fasOn'], linestyle='--',
                label=f'FasOn {result["fasOn"]:.3f} uA')
        if any(len(curve) != 0 for curve in result['curves']):
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
        self._ax.set_title('FAS tune')
        self._ax.set_xlabel('Logical row')
        self._ax.set_ylabel('FasOn current (uA)')
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name='FasFluxLowOffset', value=0.0, mode='RW', units='uA',
            description='First FAS current in the sweep.'))
        self.add(pr.LocalVariable(
            name='FasFluxHighOffset', value=1.0, mode='RW', units='uA',
            description='Last FAS current in the sweep.'))
        self.add(pr.LocalVariable(
            name='FasFluxNumSteps', value=10, minimum=2, mode='RW',
            description='Number of FAS sweep points.'))
        self.add(pr.LocalVariable(
            name='FasFluxSampleDelay', value=0.001, mode='RW', units='s',
            description='Delay after each ManualSet write.'))

        # saFbServo() reads these parameters from its calling Process.
        self.add(pr.LocalVariable(
            name='ServoKp', value=-0.8, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoKi', value=0.0, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoKd', value=0.0, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoPrecision', value=0.01, mode='RW'))
        self.add(pr.LocalVariable(
            name='ServoMaxLoops', value=500, minimum=1, mode='RW'))

        self.add(pr.LocalVariable(
            name='FasTuneOutput', hidden=True, value=[], mode='RO',
            description='FAS sweep results in active row order.'))
        self.add(pr.LocalVariable(
            name='PlotRow', value=0, minimum=0, mode='RW',
            description='Index into the active-row sweep results.'))

        self.add(RowFasSweepPlot(
            name='SweepPlot', hidden=True, mode='RO',
            dependencies=[self.PlotRow, self.FasTuneOutput]))
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
            curves = warm_tdm_api.fasTune(group=self.parent, process=self)
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
