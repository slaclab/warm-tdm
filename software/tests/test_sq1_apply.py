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


def curveResult(xOut=1.0, biasOut=2.0, yOut=3.0, phinot=23.0):
    """A mock CurveData: fitted lock point + a best-curve flux period (phinot).

    ``update()`` is a no-op here (the real one recomputes ``bestCurve``); the
    mock just carries a ``bestCurve`` with a ``phinot`` for the FluxQuantum path.
    """
    bestCurve = SimpleNamespace(phinot=phinot) if phinot is not None else None
    return SimpleNamespace(xOut=xOut, biasOut=biasOut, yOut=yOut,
                           bestCurve=bestCurve, update=Mock())


def adcDspMock():
    """One column's AdcDsp node exposing the setters the FluxQuantum apply uses."""
    return SimpleNamespace(PidEnable=SimpleNamespace(set=Mock()),
                           FluxQuantum=SimpleNamespace(set=Mock()))


class Sq1ApplyTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/tuning/_sq1.py'
        spec = importlib.util.spec_from_file_location('sq1_test._sq1', path)
        self.module = importlib.util.module_from_spec(spec)
        common = SimpleNamespace(
            _pause_point=lambda process, publish=None: process.running,
            saOffset=Mock(), saFbServo=Mock())
        with patch.dict(sys.modules, {
                'warm_tdm_api': SimpleNamespace(tuning=common),
                'warm_tdm_api.tuning': common}):
            spec.loader.exec_module(self.module)
        # Two columns, only column 0 enabled. Each column maps to one AdcDsp node
        # (col_iter yields (board, chan) for every column in order); the
        # FluxQuantum apply writes AdcDsp[chan] under ColumnBoard[board].
        self.adcDsp = [adcDspMock(), adcDspMock()]
        columnBoard = [SimpleNamespace(DataPath=SimpleNamespace(AdcDsp=self.adcDsp))]
        self.group = SimpleNamespace(
            RowReadoutOrder=var([1]), colEnableBools=np.array([True, False]),
            SaFbForceCurrent=var(np.zeros(2)),
            Sq1FbCurrent=var(np.full((2, 3), 10.0)),
            Sq1BiasCurrent=var(np.full((2, 3), 20.0)),
            SaFbCurrent=var(np.full((2, 3), 30.0)),
            col_iter=lambda: iter([(0, 0), (0, 1)]),
            HardwareGroup=SimpleNamespace(ColumnBoard=columnBoard),
            ManualRowOn=Mock(), ManualRowOff=Mock())
        self.process = SimpleNamespace(running=True, _log=Mock(), _publishResults=Mock())
        for name in ('Sq1BiasNumSteps', 'Sq1FbNumSteps', 'TotalSteps',
                     'ServoKp', 'ServoKi', 'ServoKd', 'ServoPrecision',
                     'ServoMaxLoops', 'ServoDisable'):
            setattr(self.process, name, var(1))
        self.results = [curveResult(xOut=1.0, biasOut=2.0, yOut=3.0, phinot=23.0),
                        curveResult(xOut=None, biasOut=None, yOut=None, phinot=None)]
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
                    self.results[0] = curveResult(xOut=1.0, biasOut=2.0, yOut=3.0)
                    setattr(self.results[0], field, bad)
                    with self.assertRaisesRegex(RuntimeError, 'no fitted operating point'):
                        self.module.sq1Tune(self.group, self.process, doSet=True)
                    self.assert_unapplied()
                    # The lock-point validation raises before any FluxQuantum write.
                    self.adcDsp[0].FluxQuantum.set.assert_not_called()

    def test_complete_fit_programs_flux_quantum_from_best_curve_phinot(self):
        self.module.sq1Tune(self.group, self.process, doSet=True)
        # Enabled column 0: PID disabled first, then FluxQuantum = best-curve phinot.
        self.adcDsp[0].PidEnable.set.assert_called_once_with(False)
        self.adcDsp[0].FluxQuantum.set.assert_called_once_with(23.0)
        # Disabled column 1 is untouched.
        self.adcDsp[1].FluxQuantum.set.assert_not_called()
        self.adcDsp[1].PidEnable.set.assert_not_called()

    def test_do_set_false_leaves_flux_quantum_unchanged(self):
        self.module.sq1Tune(self.group, self.process, doSet=False)
        for dsp in self.adcDsp:
            dsp.FluxQuantum.set.assert_not_called()

    def test_stop_before_completion_leaves_flux_quantum_unchanged(self):
        def stopped_sweep(**kwargs):
            self.process.running = False
            return self.results
        self.module.sq1BiasSweep.side_effect = stopped_sweep
        self.module.sq1Tune(self.group, self.process, doSet=True)
        for dsp in self.adcDsp:
            dsp.FluxQuantum.set.assert_not_called()

    def test_missing_phinot_skips_flux_quantum_but_keeps_lock_point(self):
        for bad in (None, float('nan'), float('inf'), 0.0, -1.0):
            with self.subTest(phinot=bad):
                self.adcDsp[0].FluxQuantum.set.reset_mock()
                for name in ('Sq1FbCurrent', 'Sq1BiasCurrent', 'SaFbCurrent'):
                    getattr(self.group, name).set.reset_mock()
                self.results[0] = curveResult(phinot=bad)
                # The lock point still applies; only the FluxQuantum write is skipped.
                self.module.sq1Tune(self.group, self.process, doSet=True)
                self.group.Sq1FbCurrent.set.assert_called_once()
                self.adcDsp[0].FluxQuantum.set.assert_not_called()

    def test_no_best_curve_skips_flux_quantum(self):
        self.results[0] = curveResult(phinot=None)  # bestCurve is None
        self.module.sq1Tune(self.group, self.process, doSet=True)
        self.group.Sq1FbCurrent.set.assert_called_once()
        self.adcDsp[0].FluxQuantum.set.assert_not_called()


if __name__ == '__main__':
    unittest.main()
