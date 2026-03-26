import pyrogue as pr
import time
import warm_tdm_api

class RunEmulate(pr.RunControl):
    """Special base class to control runs. """

    def __init__(self, *, hidden=True, states=None, cmd=None, **kwargs):
        super().__init__(hidden=hidden, rates={1 : '1 Hz', 100 : '100Hz', 400 : '400Hz'}, **kwargs)

    def _run(self):

        self.runCount.set(0)

        while (self.runState.valueDisp() == 'Running'):
            time.sleep(1.0 / self.runRate.value())
            ts = int(time.time() * 10000)

            for kn,n in self.root.getNodes(typ=warm_tdm_api.TdmGroupEmulate).items():
                n._request(ts)

            with self.runCount.lock:
                self.runCount.set(self.runCount.value() + 1,write=False)
