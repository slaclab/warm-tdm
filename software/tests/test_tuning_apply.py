# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Legacy tuning handoff regressions; no Rogue runtime or hardware required.

Run with: python -m unittest discover -s software/tests -v
Only numpy is required. Acquisition and the offset servo are replaced so the
checks exercise application of already fitted operating points.
"""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


class Variable:
    def __init__(self, value, table=False):
        self.data = np.array(value, copy=True)
        self.table = table
        self.set = Mock(side_effect=self._set)

    def get(self, read=False, index=-1):
        if self.table and index == -1:
            raise AssertionError('The legacy whole-table getter assumes 32 rows')
        return self.data.copy() if index == -1 else self.data[index]

    def value(self):
        return self.get()

    def _set(self, value, index=-1):
        if index == -1:
            self.data = np.array(value, copy=True)
        else:
            self.data[index] = value


def fit(xOut=1.0, biasOut=2.0, yOut=3.0):
    return SimpleNamespace(xOut=xOut, biasOut=biasOut, yOut=yOut)


class TuningApplyTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/_Tuning.py'
        spec = importlib.util.spec_from_file_location('legacy_tuning_test', path)
        self.tuning = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
                'warm_tdm_api': SimpleNamespace(),
                'simple_pid': SimpleNamespace(PID=Mock(side_effect=AssertionError(
                    'This test should not run the offset servo')))}):
            spec.loader.exec_module(self.tuning)
        self.tuning.saOffset = Mock()

        self.group = SimpleNamespace(
            ColTuneEnable=Variable([True, False, True]),
            RowMap=Variable(list(range(40))),
            RowIndexOrderList=Variable([37, 2]),
            SaBiasCurrent=Variable([10.0, 20.0, 30.0]),
            SaFbForceCurrent=Variable([40.0, 50.0, 60.0]),
            ActivateRowIndex=Mock(), DeactivateRowIndex=Mock())
        self.initial = {}
        for i, name in enumerate(('Sq1BiasCurrent', 'Sq1FbCurrent', 'SaFbCurrent')):
            values = np.arange(120, dtype=float).reshape(3, 40) + 1000 * i
            setattr(self.group, name, Variable(values, table=True))
            self.initial[name] = values.copy()

        self.process = SimpleNamespace(
            _runEn=True, ServoDisable=Variable(False), TotalSteps=Variable(0),
            Sq1BiasNumSteps=Variable(1), Sq1FbNumSteps=Variable(2))
        self.saResults = [fit(), fit(None, None, None), fit(4.0, 5.0, 6.0)]
        self.sq1Results = [self.saResults,
                           [fit(7.0, 8.0, 9.0), fit(None, None, None),
                            fit(10.0, 11.0, 12.0)]]
        self.tuning.saBiasSweep = Mock(return_value=self.saResults)
        self.tuning.sq1BiasSweep = Mock(side_effect=self.sq1Results)

    def assert_tables_unapplied(self):
        for name, values in self.initial.items():
            variable = getattr(self.group, name)
            variable.set.assert_not_called()
            np.testing.assert_array_equal(variable.data, values)

    def assert_sa_unapplied(self):
        self.assert_tables_unapplied()
        self.group.SaBiasCurrent.set.assert_not_called()
        self.group.SaFbForceCurrent.set.assert_not_called()
        self.tuning.saOffset.assert_not_called()

    def test_sa_offset_observes_fitted_bias_and_force_feedback(self):
        def check_offset(**kwargs):
            np.testing.assert_array_equal(self.group.SaBiasCurrent.data, [2, 20, 5])
            np.testing.assert_array_equal(self.group.SaFbForceCurrent.data, [1, 50, 4])
            expected = self.initial['SaFbCurrent'].copy()
            expected[0, :] = 1
            expected[2, :] = 4
            np.testing.assert_array_equal(self.group.SaFbCurrent.data, expected)

        self.tuning.saOffset.side_effect = check_offset
        result = self.tuning.saTune(group=self.group, process=self.process)
        self.assertIs(result, self.saResults)
        self.tuning.saOffset.assert_called_once_with(group=self.group, process=self.process)
        self.group.Sq1BiasCurrent.set.assert_not_called()
        self.group.Sq1FbCurrent.set.assert_not_called()

    def test_sa_do_set_false_preserves_existing_application_behavior(self):
        self.tuning.saTune(group=self.group, process=self.process, doSet=False)
        self.assert_sa_unapplied()

    def test_sa_stop_during_sweep_does_not_apply_fits(self):
        def stopped_sweep(**kwargs):
            self.process._runEn = False
            return self.saResults
        self.tuning.saBiasSweep.side_effect = stopped_sweep
        self.tuning.saTune(group=self.group, process=self.process, doSet=True)
        self.assert_sa_unapplied()

    def test_sa_validates_all_enabled_fits_before_writing(self):
        for field in ('xOut', 'biasOut'):
            for bad in (None, float('nan'), float('inf')):
                with self.subTest(field=field, bad=bad):
                    self.saResults[2] = fit(4, 5, 6)
                    setattr(self.saResults[2], field, bad)
                    with self.assertRaisesRegex(RuntimeError, 'column 2'):
                        self.tuning.saTune(group=self.group, process=self.process)
                    self.assert_sa_unapplied()

    def test_sq1_applies_three_tables_to_actual_rows_and_enabled_columns(self):
        result = self.tuning.sq1Tune(self.group, self.process, doSet=True)
        self.assertEqual(result, self.sq1Results)
        for name, field in (('Sq1BiasCurrent', 'biasOut'),
                            ('Sq1FbCurrent', 'xOut'), ('SaFbCurrent', 'yOut')):
            expected = self.initial[name].copy()
            for row, results in zip((37, 2), self.sq1Results):
                for col in (0, 2):
                    expected[col, row] = getattr(results[col], field)
            np.testing.assert_array_equal(getattr(self.group, name).data, expected)
        self.assertEqual([call.args[0] for call in self.group.ActivateRowIndex.call_args_list],
                         [37, 2])
        self.assertEqual([call.args[0] for call in self.group.DeactivateRowIndex.call_args_list],
                         [37, 2])
        # SQ1 application must preserve the offset used to acquire its curves.
        self.tuning.saOffset.assert_called_once_with(group=self.group)

    def test_sq1_default_does_not_apply(self):
        self.tuning.sq1Tune(self.group, self.process)
        self.assert_tables_unapplied()

    def test_sq1_explicit_do_set_false_does_not_apply(self):
        self.tuning.sq1Tune(self.group, self.process, doSet=False)
        self.assert_tables_unapplied()

    def test_sq1_stop_during_first_row_does_not_apply_or_visit_next_row(self):
        def stopped_sweep(*args):
            self.process._runEn = False
            return self.sq1Results[0]
        self.tuning.sq1BiasSweep.side_effect = stopped_sweep
        result = self.tuning.sq1Tune(self.group, self.process, doSet=True)
        self.assertEqual(result, [self.sq1Results[0]])
        self.assert_tables_unapplied()
        self.group.ActivateRowIndex.assert_called_once_with(37)
        self.group.DeactivateRowIndex.assert_called_once_with(37)

    def test_sq1_stop_during_final_row_does_not_apply(self):
        results = iter(self.sq1Results)
        def stopped_sweep(*args):
            result = next(results)
            if result is self.sq1Results[-1]:
                self.process._runEn = False
            return result
        self.tuning.sq1BiasSweep.side_effect = stopped_sweep
        self.tuning.sq1Tune(self.group, self.process, doSet=True)
        self.assert_tables_unapplied()
        self.assertEqual(self.group.DeactivateRowIndex.call_count, 2)

    def test_sq1_exception_releases_row_without_applying(self):
        self.tuning.sq1BiasSweep.side_effect = RuntimeError('sweep failed')
        with self.assertRaisesRegex(RuntimeError, 'sweep failed'):
            self.tuning.sq1Tune(self.group, self.process, doSet=True)
        self.assert_tables_unapplied()
        self.group.DeactivateRowIndex.assert_called_once_with(37)

    def test_sq1_validates_every_row_before_writing_any_table(self):
        for field in ('xOut', 'biasOut', 'yOut'):
            for bad in (None, float('nan'), float('inf')):
                with self.subTest(field=field, bad=bad):
                    self.sq1Results[-1][2] = fit(10, 11, 12)
                    setattr(self.sq1Results[-1][2], field, bad)
                    self.tuning.sq1BiasSweep.side_effect = self.sq1Results
                    with self.assertRaisesRegex(RuntimeError, 'column 2, row 2'):
                        self.tuning.sq1Tune(self.group, self.process, doSet=True)
                    self.assert_tables_unapplied()

    def test_sq1_voltage_diagnostic_cannot_apply_as_feedback_current(self):
        self.process.ServoDisable.set(True)
        with self.assertRaisesRegex(RuntimeError, 'ServoDisable'):
            self.tuning.sq1Tune(self.group, self.process, doSet=True)
        self.assert_tables_unapplied()
        self.tuning.sq1BiasSweep.assert_not_called()
        self.tuning.saOffset.assert_not_called()
        self.group.ActivateRowIndex.assert_not_called()

    def test_sq1_voltage_diagnostic_still_runs_without_application(self):
        self.process.ServoDisable.set(True)
        self.tuning.sq1Tune(self.group, self.process)
        self.assertEqual(self.tuning.sq1BiasSweep.call_count, 2)
        self.assert_tables_unapplied()


if __name__ == '__main__':
    unittest.main()
