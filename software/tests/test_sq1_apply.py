# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""SQ1 fitted-table application without hardware or the Rogue runtime."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


def var(value):
    return SimpleNamespace(get=Mock(return_value=value), set=Mock())


class Sq1ApplyTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/tuning/_sq1.py'
        spec = importlib.util.spec_from_file_location('sq1_test._sq1', path)
        self.module = importlib.util.module_from_spec(spec)
        common = SimpleNamespace(
            _pause_point=lambda process, publish=None: process.running,
            saOffset=Mock(), saFbServo=Mock())
        with patch.dict(sys.modules, {
                'warm_tdm_api': SimpleNamespace(), 'sq1_test._common': common}):
            spec.loader.exec_module(self.module)
        self.group = SimpleNamespace(
            RowReadoutOrder=var([1]), colEnableBools=np.array([True, False]),
            SaFbForceCurrent=var(np.zeros(2)),
            Sq1FbCurrent=var(np.full((2, 3), 10.0)),
            Sq1BiasCurrent=var(np.full((2, 3), 20.0)),
            SaFbCurrent=var(np.full((2, 3), 30.0)),
            ManualRowOn=Mock(), ManualRowOff=Mock())
        self.process = SimpleNamespace(running=True, _log=Mock(), _publishResults=Mock())
        for name in ('Sq1BiasNumSteps', 'Sq1FbNumSteps', 'TotalSteps',
                     'ServoKp', 'ServoKi', 'ServoKd', 'ServoPrecision',
                     'ServoMaxLoops', 'ServoDisable'):
            setattr(self.process, name, var(1))
        self.results = [SimpleNamespace(xOut=1.0, biasOut=2.0, yOut=3.0),
                        SimpleNamespace(xOut=None, biasOut=None, yOut=None)]
        self.module.sq1BiasSweep = Mock(return_value=self.results)

    def assert_unapplied(self):
        for name in ('Sq1FbCurrent', 'Sq1BiasCurrent', 'SaFbCurrent'):
            getattr(self.group, name).set.assert_not_called()

    def test_complete_fit_preserves_untuned_rows_and_disabled_columns(self):
        self.module.sq1Tune(self.group, self.process, doSet=True)
        for name, initial, fitted in [('Sq1FbCurrent', 10, 1),
                                     ('Sq1BiasCurrent', 20, 2),
                                     ('SaFbCurrent', 30, 3)]:
            expected = np.full((2, 3), float(initial))
            expected[0, 1] = fitted
            variable = getattr(self.group, name)
            variable.set.assert_called_once()
            np.testing.assert_array_equal(variable.set.call_args.args[0], expected)
        self.group.ManualRowOff.assert_called_once_with(1)

    def test_stop_during_final_sweep_never_applies_partial_fits(self):
        def stopped_sweep(**kwargs):
            self.process.running = False
            return self.results
        self.module.sq1BiasSweep.side_effect = stopped_sweep
        self.assertEqual(self.module.sq1Tune(self.group, self.process, doSet=True),
                         [self.results])
        self.assert_unapplied()
        self.group.ManualRowOff.assert_called_once_with(1)

    def test_do_set_false_leaves_tables_unchanged(self):
        self.module.sq1Tune(self.group, self.process, doSet=False)
        self.assert_unapplied()

    def test_missing_or_nonfinite_fit_fails_before_any_table_write(self):
        for field in ('xOut', 'biasOut', 'yOut'):
            for bad in (None, float('nan'), float('inf')):
                with self.subTest(field=field, value=bad):
                    for name in ('Sq1FbCurrent', 'Sq1BiasCurrent', 'SaFbCurrent'):
                        getattr(self.group, name).set.reset_mock()
                    self.results[0] = SimpleNamespace(xOut=1.0, biasOut=2.0, yOut=3.0)
                    setattr(self.results[0], field, bad)
                    with self.assertRaisesRegex(RuntimeError, 'no fitted operating point'):
                        self.module.sq1Tune(self.group, self.process, doSet=True)
                    self.assert_unapplied()


if __name__ == '__main__':
    unittest.main()
