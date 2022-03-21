import pyrogue as pr
import numpy as np

import matplotlib.pyplot as plt
import mpld3

import warm_tdm_api



class SaOffsetProcess(pr.Process):
    """ Use a PID loop to determine the SaOffset values that null out the SaBias contribution to the input chain. """

    def __init__(self, **kwargs):

        description = """Process which attempts to find an SaOffset value which results in the SaOut value being zero.
        A PID controller is used with configurable parameters, including a precision value to determine how close to zero the loop must come.
        A timeout value will terminate the process if it fails to converge witing a set period of time."""



        # Init master class
        pr.Process.__init__(
            self,
            description=description,
            function=self._saOffsetWrap,
            **kwargs)


        self.add(pr.LocalVariable(
            name='Kp',
            value=-.25,
            mode='RW',
            description="Proportional PID coefficient"))

        self.add(pr.LocalVariable(
            name='Ki',
            value=0.0,
            mode='RW',
            description="Integral PID coefficient"))

        self.add(pr.LocalVariable(
            name='Kd',
            value=0.0,
            mode='RW',
            description="Differential PID coefficient"))

        self.add(pr.LocalVariable(
            name='Precision',
            value=0.02,
            mode='RW',
            description="Convergance precision"))


        self.add(pr.LocalVariable(
            name='Timeout',
            value=100.0,
            units = 'Seconds',
            mode='RW',
            description="Timeout for PID convergance"))


        # FAS Tuning Results
        self.add(pr.LocalVariable(
            name='SaOffsetOutput',
            hidden=True,
            value=[],
            mode='RO',
            description="Results Data From SA Offset. This is an array of values, one for each column. The length is ColumnCount * 8'"))


        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

    def _saOffsetWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.saOffset(
                group=self.parent)

            self.SaOffsetOutput.set(ret)

class SaOffsetSweepProcess(pr.Process):

    def __init__(self, config, **kwargs):

        description = """Process which performs an SaBias sweep and plots the SaOffset value required to zero out the SaOut value at each step.
        The SaOffset PID parameters are taken from the SaOffsetProcess Device."""

        # Init master class
        pr.Process.__init__(self, description=description, function=self._saOffsetSweep, **kwargs)

        self.columns = len(config.columnMap)

        self._fig = None        

        # Low offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasLow',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SA Bias Sweep"))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHigh',
                                  value=2.4999,
                                  mode='RW',
                                  description="Ending point offset for SA Bias Sweep"))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasNumSteps',
                                  minimum=1,
                                  value=100,
                                  mode='RW',
                                  description="Number of steps for SA Bias Sweep"))

        self.add(pr.LocalVariable(name='PlotXData',
                                 description="X axis data for the SaOffset vs SaBias curve",
                                 mode='RO',
                                 hidden=True,
                                 value = np.zeros(10)))

        for i in range(self.columns):
            self.add(pr.LocalVariable(name=f'PlotYData[{i}]',
                                     description=f"Y axis data for the SaOffset vs SaBias curve, for column {i}.",
                                     mode='RO',
                                     hidden=True,
                                     value = np.zeros(10)))

        self.add(pr.LinkVariable(name='Plot',
                                 mode='RO',
                                 hidden=True,
                                 linkedGet = self._plot,
                                 dependencies = [self.PlotYData[i] for i in range(self.columns)]))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

    def _saOffsetSweep(self):
        with self.root.updateGroup(.25):
            group = self.parent

            low = self.SaBiasLow.get()
            high = self.SaBiasHigh.get()
            steps = self.SaBiasNumSteps.get()
            colCount = len(group.ColumnMap.get())

            biasRange = np.linspace(low, high, steps, endpoint=True)

            curves = np.zeros((steps, colCount))

            saBias = np.full(colCount, low)
            mask = np.array([1.0 if en else 0 for en in group.ColTuneEnable.value()])

            for i, b in enumerate(biasRange):
                saBias = mask * b

                #print(f'Setting saBias - {saBias}')

                group.SaBias.set(saBias)

                try:
                    warm_tdm_api.saOffset(group=group)
                except:
                    print('saOffset timed out')

                offset = group.SaOffset.get()

                #print(f'Got saOffset - {offset}')

                curves[i] = offset

                self.Progress.set(i/steps)
                if self._runEn is False:
                    self.Message.set('Stopped by user')
                    return

            self.PlotXData.set(biasRange)
            for i in range(colCount):
                self.PlotYData[i].set(curves[:, i])

    def _plot(self, read):
        
        if self._fig is not None:
            plt.close(self._fig)

        self._fig = plt.Figure()
        ax = self._fig.add_subplot()

        ax.set_xlabel('Bias Voltage')
        ax.set_ylabel('Offset Voltage')
        ax.set_title('Offset Sweep')

        for i in range(self.columns):
            ax.plot(self.PlotXData.get(), self.PlotYData[i].get(read=read), label=f'Ch {i}')

        ax.legend()
        return self._fig
