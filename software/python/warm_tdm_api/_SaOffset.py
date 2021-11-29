import pyrogue as pr
import warm_tdm_api
import numpy as np

class SaOffsetProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._saOffsetWrap, **kwargs)


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
            value=0.0002,
            mode='RW',
            description="Convergance precision"))


        self.add(pr.LocalVariable(
            name='Timeout',
            value=5.0,
            units = 'Seconds',
            mode='RW',
            description="Timeout for PID convergance"))


        # FAS Tuning Results
        self.add(pr.LocalVariable(
            name='SaOffsetOutput',
            hidden=True,
            value={},
            mode='RO',
            description="Results Data From SA Offset"))

    def _saOffsetWrap(self):
        with self.root.updateGroup(0.25):
            ret = warm_tdm_api.saOffset(
                group=self.parent)

            self.SaOffsetOutput.set(ret)

class SaOffsetSweepProcess(pr.Process):

    def __init__(self, config, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._saOffsetSweep, **kwargs)

        # Low offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasLow',
                                  value=0.0,
                                  mode='RW',
                                  description="Starting point offset for SA Bias Tuning"))

        # High offset for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasHigh',
                                  value=2.4999,
                                  mode='RW',
                                  description="Ending point offset for SA Bias Tuning"))

        # Step size for SA Bias Tuning
        self.add(pr.LocalVariable(name='SaBiasNumSteps',
                                  minimum=1,
                                  value=100,
                                  mode='RW',
                                  description="Number of steps for SA Bias Tuning"))

        self.add(pr.LocalVariable(name='PlotXData',
                                 mode='RO',
                                 hidden=True,
                                 value = np.zeros(10)))

        for i in range(len(config.columnMap)):
            self.add(pr.LocalVariable(name=f'PlotYData[{i}]',
                                     mode='RO',
                                     hidden=True,
                                     value = np.zeros(10)))

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
            mask = np.array([1.0 if en else 0 for en in group._config.columnEnable])

            for i, b in enumerate(biasRange):
                saBias = mask * b

                print(f'Setting saBias - {saBias}')

                group.SaBias.set(saBias)

                try:
                    warm_tdm_api.saOffset(group=group)
                except:
                    print('saOffset timed out')

                offset = group.SaOffset.get()

                print(f'Got saOffset - {offset}')

                curves[i] = offset

                self.Progress.set(i/steps)

            self.PlotXData.set(biasRange)
            for i in range(colCount):
                self.PlotYData[i].set(curves[:, i])
