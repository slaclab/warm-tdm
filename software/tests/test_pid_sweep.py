# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Sweep real logical rows and restore the selected column on interruptions."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np

spec=importlib.util.spec_from_file_location('sweep_test',Path(__file__).resolve().parents[1]/'python/warm_tdm_api/operations/pid_sweep.py')
sweep=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


class SweepTests(unittest.TestCase):
    def fixture(self):
        # Inactive rows read zero; the live rows are 10 and 13.
        error=np.zeros(16); error[[10,13]]=[20,-40]
        variable=lambda v:SimpleNamespace(get=Mock(return_value=v))
        dsp=SimpleNamespace(AccumError=variable(error),FluxJumps=variable(np.zeros(16)),
                            PidEnable=variable(True),RowEnableMask=variable((1<<16)-1))
        gain=SimpleNamespace(get=Mock(return_value=-0.2),set=Mock())
        board=SimpleNamespace(DataPath=SimpleNamespace(AdcDsp={0:dsp}),
              WarmTdmCore=SimpleNamespace(Timing=SimpleNamespace(TimingTx=SimpleNamespace(Running=variable(True)))))
        session=SimpleNamespace(group=SimpleNamespace(RowReadoutOrder=variable([10,13]),PidP_Gain=gain),
            col_enable_bools=lambda:[True],col_to_board_chan=lambda c:(0,0),cbs={0:board},
            coordinator_cb=board,set_pid=Mock())
        return session,dsp,gain

    def test_noncontiguous_rows_and_opposite_flux_changes(self):
        session,dsp,gain=self.fixture()
        counts=np.zeros(16);counts[[10,13]]=[1,-1]
        dsp.FluxJumps.get.side_effect=[np.zeros(16),np.zeros(16),counts,counts,counts]
        with patch.object(sweep.time,'sleep'):
            result=sweep.sweep_pid_p(session,0,[-0.01],seconds=3)
        self.assertEqual(result[0]['rows'],[10,13])
        self.assertEqual(result[0]['floor'],30)
        self.assertEqual(result[0]['max_flux_excursion'],1)
        session.set_pid.assert_called_once_with(p=-0.01,cols=[0])
        gain.set.assert_called_once_with(value=-0.2,index=0)

    def test_interrupt_restores_gain_and_retains_completed_candidates(self):
        session,dsp,gain=self.fixture()
        results=[]
        with patch.object(sweep.time,'sleep',side_effect=[None,None,None,KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                sweep.sweep_pid_p(session,0,[-0.01,-0.02],seconds=3,results=results)
        self.assertEqual(len(results),1)
        gain.set.assert_called_once_with(value=-0.2,index=0)

    def test_invalid_mask_or_measurement_rejected_before_gain_write(self):
        session,dsp,gain=self.fixture()
        dsp.RowEnableMask.get.return_value=1
        with self.assertRaises(ValueError):
            sweep.sweep_pid_p(session,0,[-0.01],seconds=3)
        session.set_pid.assert_not_called()
        dsp.RowEnableMask.get.return_value=(1<<16)-1
        dsp.AccumError.get.return_value=np.full(16,float('nan'))
        with self.assertRaises(ValueError):
            sweep.sweep_pid_p(session,0,[-0.01],seconds=3)
        session.set_pid.assert_not_called()


if __name__=='__main__':
    unittest.main()
