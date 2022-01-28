import pyrogue as pr
import warm_tdm_api
import numpy as np
import time

class SaStripChartProcess(pr.Process):

    def __init__(self, **kwargs):
        super().__init__(function=self._process, **kwargs)

        self.add(pr.LocalVariable(
            name = 'Channel',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'SampleRate',
            value = .1))

        self.add(pr.LocalVariable(
            name = 'RunTime',
            value = 100.0))

        self.add(pr.LocalVariable(
            name = 'SampleDataY',
            mode = 'RO',
            value = np.zeros(1, np.float64)))

        self.add(pr.LocalVariable(
            name = 'SampleDataX',
            mode = 'RO',
            value = np.zeros(1, np.float64))) 
       

    def _process(self):
        saOutVar = self.parent.SaOut
        channel = self.Channel.get()
        sleep = self.SampleRate.get()
        run_time = self.RunTime.get()
        samples = []
        times = []
        start_time = time.time()
        stop_time = start_time() + run_time
        while time.time() < stop_time:
            times.append(time.time()-start_time)
            samples.append(saOutVar.get(index=channel, read=True))
            self.Progress.set(times[-1]/run_time)
            time.sleep(sleep)

        self.Progress.set(1.0)

        self.SampleDataY.set(np.array(samples))
        self.SampleDataX.set(np.array(times))
    
