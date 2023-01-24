import pyrogue as pr
import numpy as np

import matplotlib.pyplot as plt

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
            value=-.1,
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
            value=0.001,
            mode='RW',
            description="Convergance precision"))


        self.add(pr.LocalVariable(
            name='MaxLoops',
            value=100,
#            units = 'Seconds',
            mode='RW',
            description="Max number of loops for PID convergance"))


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
                group=self.parent,
                process=self)

            self.SaOffsetOutput.set(ret)

class SaOffsetSweepProcess(pr.Process):

    def __init__(self, config, **kwargs):

        description = """Process which performs an SaBias sweep and plots the SaOffset value required to zero out the SaOut value at each step.
        The SaOffset PID parameters are taken from the SaOffsetProcess Device."""

        # Init master class
        pr.Process.__init__(self, description=description, function=self._saOffsetSweep, **kwargs)

        self.columns = len(config.columnMap)

        self._fig = plt.Figure(tight_layout=True, figsize=(20,10))
        self._ax = self._fig.add_subplot()        

        # Low offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasLow',
                                  value=1.0,
                                  mode='RW',
                                  description="Starting point offset for SA Bias Sweep"))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHigh',
                                  value=100.0,
                                  mode='RW',
                                  description="Ending point offset for SA Bias Sweep"))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasNumSteps',
                                  minimum=1,
                                  value=100,
                                  mode='RW',
                                  description="Number of steps for SA Bias Sweep"))

        self.add(pr.LocalVariable(name='SaFbPoints',
                                  value = [0.0, 0.15],
                                  mode = 'RW'))

        self.add(pr.LocalVariable(name='PlotXData',
                                  description='X axis data',
                                  mode='RO',
                                  hidden=True,
                                  value = np.zeros(10)))

        self.add(pr.LocalVariable(name=f'PlotYData',
                                  description=f'Y axis data',
                                  mode='RO',
                                  hidden=True,
                                  value = np.zeros([10, 2, self.columns])))

        self.add(pr.LocalVariable(name='PlotChannel',
                                  value = 0,
                                  minimum = 0,
                                  maximum = self.columns,
                                  mode = 'RW'))

        self.add(pr.LinkVariable(name='Plot',
                                 mode='RO',
                                 hidden=True,
                                 linkedGet = self._plot,
                                 dependencies = [self.PlotYData, self.PlotChannel]))

        self.ReadDevice.addToGroup('NoDoc')
        self.WriteDevice.addToGroup('NoDoc')

    def _saOffsetSweep(self):
        with self.root.updateGroup(.25):
            group = self.parent

            startBias = group.SaBiasCurrent.get()
            startOffset = group.SaOffset.get()            

            low = self.SaBiasLow.get()
            high = self.SaBiasHigh.get()
            biasSteps = self.SaBiasNumSteps.get()
            colCount = len(group.ColumnMap.get())

            biasRange = np.linspace(low, high, biasSteps, endpoint=True)

            fbPoints = self.SaFbPoints.get()

            curves = np.zeros((biasSteps, len(fbPoints), colCount))

            saBias = np.full(colCount, low)
            mask = np.array([1.0 if en else 0 for en in group.ColTuneEnable.value()])

            totalSteps = len(fbPoints) * biasRange.size
            self.TotalSteps.set(totalSteps)

            for i, bias in enumerate(biasRange):
                saBias = mask * bias
                group.SaBiasCurrent.set(saBias)
                try:
                    warm_tdm_api.saOffset(group=group)
                except:
                    print('saOffset timed out')
                
                for j, fb in enumerate(fbPoints):
                    saFb = mask * fb
                    group.SaFbForceCurrent.set(saFb)

                    
                    curves[i, j] = group.SaOut.get() #group.SaOffset.get()
                    #curves[i, j] = group.SaOffset.get()                    

                    self.Advance() #Progress.set((i*biasSteps + j) / totalSteps)
                    if self._runEn is False:
                        self.Message.set('Stopped by user')
                        return

            self.PlotXData.set(biasRange)
            self.PlotYData.set(curves)

            # Set bias and offset back to where they were before the sweep
            group.SaBiasCurrent.set(startBias)
            group.SaOffset.set(startOffset)

    def _plot(self):

        xdata = self.PlotXData.value()
        ydata = self.PlotYData.value()
        chan = self.PlotChannel.value()

        self._ax.clear()
        self._ax.set_xlabel(u'SA Bias Current (\u03bcA)')
        self._ax.set_ylabel('SA Out Voltage (mV)')
        self._ax.set_title(f'SA Bias Sweep - Channel {chan}')

        for i, fb in enumerate(self.SaFbPoints.value()):
            self._ax.plot(xdata, ydata[:,i,chan], label=f'{fb}')

        self._ax.legend(title=u'SA FB (\u03bcA)')
        return self._fig
