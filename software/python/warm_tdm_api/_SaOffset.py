
import pyrogue as pr
import warm_tdm_api


class SaOffsetProcess(pr.Process):

    def __init__(self, **kwargs):

        # Init master class
        pr.Process.__init__(self, function=self._saOffsetWrap, **kwargs)


        self.add(pr.LocalVariable(
            name='Kp',
            value=-.75,
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
                group=self.parent,
                kp=self.Kp.get(),
                ki=self.Ki.get(),
                kd=self.Kd.get(),
                precision=self.Precision.get(),
                timeout=self.Timeout.get())

            self.SaOffsetOutput.set(ret)

