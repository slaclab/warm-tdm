# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

"""FAS control-flow tests with real tuning code and synthetic measured responses.

These exercise physical addressing, isolation, discovery, and failure cleanup;
they do not model Rogue transport, the RTL request queue, or cryogenic devices.
"""

import ast
import copy
from contextlib import nullcontext
import importlib.util
import io
import logging
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


API = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api'


def load_modules():
    # Curve classes have no SciPy dependency; the enclosing historical file
    # imports SciPy for unrelated helpers. Exercise the actual class bodies.
    tree = ast.parse((API / '_CurveClass.py').read_text())
    classes = ast.Module(body=[n for n in tree.body if isinstance(n, ast.ClassDef)],
                         type_ignores=[])
    namespace = {'np': np}
    exec(compile(classes, str(API / '_CurveClass.py'), 'exec'), namespace)
    api = ModuleType('warm_tdm_api')
    api.Curve = namespace['Curve']
    api.CurveData = namespace['CurveData']
    spec = importlib.util.spec_from_file_location(
        'warm_tdm_api.tuning', API / 'tuning/__init__.py')
    package = importlib.util.module_from_spec(spec)
    api.tuning = package
    with patch.dict(sys.modules, {
            'warm_tdm_api': api, 'warm_tdm_api.tuning': package}):
        spec.loader.exec_module(package)
    return package._common, package._fas, package._fas_two_level


common, flat, two = load_modules()


class Variable:
    def __init__(self, value, on_set=None):
        self.data = copy.deepcopy(value)
        self.on_set = on_set
        self.writes = []

    def get(self, read=True, index=-1):
        # Expose array caches to catch snapshots that alias subsequent writes.
        return self.data if index == -1 else self.data[index]

    def value(self):
        return self.data

    def set(self, value, index=-1, **kwargs):
        self.writes.append((copy.deepcopy(value), index))
        if index != -1:
            self.data[index] = value
        elif isinstance(self.data, np.ndarray):
            self.data[:] = value
        else:
            self.data = copy.deepcopy(value)
        if self.on_set:
            self.on_set(value, index)

    def setDisp(self, value):
        self.set({'MANUAL': 1, 'TIMING': 0}[value])


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, value):
        self.now += value


class Driver:
    def __init__(self, board, fixture):
        self.board = board
        self.fixture = fixture
        self.path = f'RowBoard[{board}].RowDacDriver'
        self.Mode = Variable(0)
        self.FasOn = SimpleNamespace(Current=Variable(
            np.full(32, 99.0), self.program))  # Deliberately unusable bootstrap.
        self.FasOff = SimpleNamespace(Current=Variable(np.zeros(32)))

    def program(self, value, index):
        key = (self.board, index)
        self.fixture.events.append(('program', key, value, self.Mode.get()))
        if self.Mode.get() == 1:
            self.fixture.outputs[key] = value
        self.fixture.on_program(key)

    def manual_set(self, *, address, current, check_mode=True):
        if self.Mode.get() != 1:
            raise RuntimeError('Driver is not in MANUAL')
        key = (self.board, address)
        self.fixture.outputs[key] = float(current)
        self.fixture.events.append(('drive', key, float(current)))
        self.fixture.on_drive(key, float(current))
        return dict(address=address, current=current)


class Fixture:
    def __init__(self, row_map=None, active=(10, 11, 12, 13)):
        if row_map is None:
            row_map = [dict(rsBoard=0, rsAddr=rs, csBoard=0, csAddr=cs)
                       for cs in range(10, 18) for rs in range(10)]
        self.events = []
        self.outputs = {}
        self.on_drive = lambda key, current: None
        self.on_program = lambda key: None
        self.on_measure = lambda: None
        self.centers = {}
        self.samples = []
        self.process = SimpleNamespace(_log=Mock(spec=logging.Logger), _runEn=True)
        for name, value in dict(
                DiscoveryNumSteps=9,
                FasFluxLowOffset=0., FasFluxHighOffset=8., FasFluxNumSteps=9,
                CsFluxLowOffset=0., CsFluxHighOffset=8., CsFluxNumSteps=9,
                FasFluxSampleDelay=.001, FasMinimumTolerance=.05,
                FasMinimumResponse=.1, FasIsolationTolerance=.1, Sq1BiasCurrent=40.,
                ServoKp=.8, ServoKi=0., ServoKd=0., ServoPrecision=.01, ServoMaxLoops=2,
                FasDiscoveryOutput=[], FasValidationOutput=[], FasTuneOutput=[],
                Message='', TotalSteps=0).items():
            setattr(self.process, name, Variable(value))
        self.process._publishResults = self.publish_curves
        self.process.pausePoint = self.pause_point
        self.steps = 0
        self.clock = Clock()
        self.process._incrementSteps = self.increment
        boards = {mapping[field] for mapping in row_map
                  for field in ('rsBoard', 'csBoard') if field in mapping}
        self.drivers = {b: Driver(b, self) for b in boards}
        tx = SimpleNamespace(Running=Variable(False))
        self.group = SimpleNamespace(
            RowMap=Variable(row_map), RowReadoutOrder=Variable(list(active)),
            NumColumns=Variable(2), colEnableBools=np.array([True, False]),
            SaFbForceCurrent=Variable(np.array([11., 12.])),
            Sq1BiasForceCurrent=Variable(np.array([13., 14.])),
            Sq1FbForceCurrent=Variable(np.array([15., 16.])),
            SaFbCurrent=Variable(np.array([np.arange(len(row_map))+20.,
                                          np.arange(len(row_map))+30.])),
            SaOutAdc=Variable(np.zeros(2)),
            HardwareGroup=SimpleNamespace(
                ColumnBoard={0: SimpleNamespace(WarmTdmCore=SimpleNamespace(
                    Timing=SimpleNamespace(TimingTx=tx)))},
                RowBoard={b: SimpleNamespace(RowDacDriver=d) for b, d in self.drivers.items()}))
        self.tx = tx
        for mapping in row_map:
            for prefix in ('rs', 'cs'):
                if prefix+'Addr' in mapping:
                    # Start with inactive mapped outputs on to test isolation.
                    self.outputs[(mapping[prefix+'Board'], mapping[prefix+'Addr'])] = 3.
        self.initial_forces = {name: getattr(self.group, name).get().copy()
                               for name in ('SaFbForceCurrent', 'Sq1BiasForceCurrent',
                                            'Sq1FbForceCurrent')}

    def pause_point(self, publish=None):
        if publish:
            publish()
        return self.process._runEn

    def publish_curves(self, curves):
        self.process.FasTuneOutput.set([
            dict(c.asDict(), logicalRow=c.logicalRow, board=c.board, address=c.address,
                 fasOn=c.fasOn, select=getattr(c, 'select', 'RS'),
                 companionCurrent=getattr(c, 'companionCurrent', None))
            for c in curves])

    def increment(self, count):
        self.steps += count

    def stop(self):
        self.process._runEn = False

    def response(self, *, group, process, publish=None, require_convergence=False):
        row = int(re.search(r'row (\d+)', process.Message.get()).group(1))
        mapping = group.RowMap.get()[row]
        rs_key = mapping['rsBoard'], mapping['rsAddr']
        cs_key = (mapping['csBoard'], mapping['csAddr']) if 'csAddr' in mapping else None
        if cs_key is not None:
            for key, value in self.outputs.items():
                if key not in (rs_key, cs_key):
                    assert value == 0., f'Unselected physical line {key} is on'
        rs_center, cs_center = self.centers.get(row, (2. + row % 3, 4.))
        gate = lambda current, center: max(0., 1. - ((current-center)/1.5)**2)
        response = -10. * gate(self.outputs[rs_key], rs_center)
        if cs_key is not None:
            response *= gate(self.outputs[cs_key], cs_center)
        self.samples.append((row, dict(self.outputs)))
        values = np.array([response, np.nan])
        # Behave like the servo by changing the force shadow, but never the
        # disabled column. This exercises independent restoration snapshots.
        forced = group.SaFbForceCurrent.get().copy()
        forced[0] = response
        group.SaFbForceCurrent.set(forced)
        self.on_measure()
        return values

    def run(self, do_set=False):
        with patch.object(two, 'time', self.clock), patch.object(flat, 'time', self.clock), \
             patch.object(flat.tuning, 'saFbServo', self.response):
            return flat.fasTune(group=self.group, process=self.process, doSet=do_set)


class FasTwoLevelTests(unittest.TestCase):
    def assert_restored(self, fixture):
        for name, original in fixture.initial_forces.items():
            np.testing.assert_array_equal(getattr(fixture.group, name).get(), original)
        for driver in fixture.drivers.values():
            self.assertEqual(driver.Mode.get(), 0)
            self.assertFalse(driver.FasOff.Current.writes)
        self.assertTrue(all(value == 0. for value in fixture.outputs.values()))

    def test_unknown_shared_cs_discovers_subset_without_changing_map(self):
        f = Fixture()
        original_map = copy.deepcopy(f.group.RowMap.get())
        curves = f.run(do_set=True)
        self.assertEqual([(c.logicalRow, c.select) for c in curves],
                         [(r, axis) for r in (10, 11, 12, 13) for axis in ('RS', 'CS')])
        self.assertEqual(f.group.RowMap.get(), original_map)
        self.assertFalse(f.group.RowMap.writes)
        self.assertFalse(f.group.RowReadoutOrder.writes)
        programs = [event for event in f.events if event[0] == 'program']
        self.assertEqual({event[1] for event in programs}, {(0, n) for n in (0, 1, 2, 3, 11)})
        self.assertEqual(len(programs), 5)  # Shared CS is programmed once.
        self.assertTrue(all(event[3] == 0 for event in programs))
        self.assertEqual(f.steps, 4 * (81 + 9 + 9 + 4))
        self.assertEqual(f.steps, f.process.TotalSteps.get())
        for grid in f.process.FasDiscoveryOutput.get():
            self.assertEqual(grid['csOn'], 4.)
            self.assertTrue(np.isnan(grid['responses'][1]).all())
        self.assertTrue(all(record['passed'] for record in f.process.FasValidationOutput.get()))
        self.assertTrue(all(len(c.curveList[1].points) == 0 for c in curves))
        self.assert_restored(f)

    def test_diagnostic_run_never_programs_candidates(self):
        f = Fixture(active=(10,))
        self.assertEqual(len(f.run()), 2)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_shared_rs_across_chips_and_multiple_columns_with_different_offsets(self):
        f = Fixture([dict(rsBoard=0, rsAddr=3, csBoard=1, csAddr=cs) for cs in (7, 8)],
                    active=(0, 1))
        f.centers = {0: (2., 4.), 1: (2., 6.)}
        f.group.colEnableBools[:] = True
        original_response = f.response

        def both_columns(**kwargs):
            values = original_response(**kwargs)
            return np.array([values[0], 100. + 2.*values[0]])

        f.response = both_columns
        curves = f.run(do_set=True)
        self.assertEqual(len(curves), 4)
        programs = [event for event in f.events if event[0] == 'program']
        self.assertEqual({event[1] for event in programs}, {(0, 3), (1, 7), (1, 8)})
        self.assertEqual(len(programs), 3)
        for curve in curves:
            self.assertEqual(len(curve.curveList[1].points), 9)
        self.assert_restored(f)

    def test_final_off_state_leakage_fails_without_programming(self):
        f = Fixture(active=(10,))
        original_response = f.response

        def leaking_response(**kwargs):
            values = original_response(**kwargs)
            if ('verification' in f.process.Message.get() and
                    f.outputs[(0, 0)] != 0. and f.outputs[(0, 11)] == 0.):
                values[0] += 1.
            return values

        f.response = leaking_response
        with self.assertRaisesRegex(RuntimeError, 'off-state isolation'):
            f.run(do_set=True)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_discover_and_refine_with_companion_on_another_board(self):
        f = Fixture([dict(rsBoard=0, rsAddr=3, csBoard=1, csAddr=7)], active=(0,))
        curves = f.run(do_set=True)
        self.assertEqual([c.select for c in curves], ['RS', 'CS'])
        self.assertEqual(f.steps, 103)
        self.assertEqual(len(f.process.FasDiscoveryOutput.get()), 1)
        self.assertEqual(sum(len(d.FasOn.Current.writes) for d in f.drivers.values()), 2)
        self.assert_restored(f)

    def test_same_process_redetects_topology_from_row_map_on_every_run(self):
        f = Fixture([dict(rsBoard=0, rsAddr=0)], active=(0,))
        self.assertFalse(hasattr(f.process, 'TwoLevelMode'))
        for two_level in (False, True, False):
            with self.subTest(two_level=two_level):
                mapping = dict(rsBoard=0, rsAddr=0)
                if two_level:
                    mapping.update(csBoard=0, csAddr=11)
                f.group.RowMap.set([mapping])
                f.steps = 0
                curves = f.run()
                self.assertEqual(len(curves), 2 if two_level else 1)
                self.assertEqual(f.steps, 103 if two_level else 9)

    def test_flat_maps_retain_one_level_behavior(self):
        f = Fixture([dict(rsBoard=0, rsAddr=i) for i in range(4)], active=(1,))
        curves = f.run()
        self.assertEqual(len(curves), 1)
        self.assertEqual((curves[0].logicalRow, curves[0].address, curves[0].fasOn), (1, 1, 3.))
        self.assertEqual(f.steps, 9)
        self.assertEqual(f.process.FasDiscoveryOutput.get(), [])

    def test_stop_retains_partial_grid_and_does_not_program(self):
        f = Fixture(active=(10,))
        f.on_measure = lambda: f.stop() if len(f.samples) == 7 else None
        self.assertEqual(f.run(do_set=True), [])
        grid = f.process.FasDiscoveryOutput.get()[0]
        self.assertEqual(np.isfinite(grid['responses']).sum(), 6)
        self.assertIsNone(grid['rsOn'])
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_stop_during_refinement_publishes_partial_curve(self):
        f = Fixture(active=(10,))
        discovery_points = f.process.DiscoveryNumSteps.get()**2
        f.on_measure = lambda: f.stop() if len(f.samples) == discovery_points + 3 else None
        curves = f.run(do_set=True)
        self.assertEqual(len(curves[0].curveList[0].points), 2)
        self.assertIsNone(curves[0].fasOn)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_stop_interrupts_long_settling_and_still_turns_off_every_line(self):
        f = Fixture(active=(10,))
        f.process.FasFluxSampleDelay.data = 10.
        stopped_at = []

        def stop_at_first_on(key, current):
            if current != 0. and not stopped_at:
                stopped_at.append(f.clock.now)
                f.stop()

        f.on_drive = stop_at_first_on
        f.run(do_set=True)
        self.assertLess(f.clock.now - stopped_at[0], 2.)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_stop_during_programming_rolls_back_all_touched_entries(self):
        f = Fixture(active=(10,))
        f.on_program = lambda key: f.stop()
        f.run(do_set=True)
        np.testing.assert_array_equal(f.drivers[0].FasOn.Current.get(), np.full(32, 99.))
        self.assertEqual(f.process.Message.get(), 'Stopped by user; FasOn unchanged')
        self.assert_restored(f)

    def test_partial_program_failure_rolls_back_even_failing_write(self):
        f = Fixture(active=(10,))
        calls = []

        def fail_second(key):
            calls.append(key)
            if len(calls) == 2:
                raise OSError('partial table write')

        f.on_program = fail_second
        with self.assertRaisesRegex(OSError, 'partial table write'):
            f.run(do_set=True)
        np.testing.assert_array_equal(f.drivers[0].FasOn.Current.get(), np.full(32, 99.))
        self.assert_restored(f)

    def test_unobservable_axis_fails_without_programming(self):
        f = Fixture(active=(10,))
        f.centers[10] = (3., 50.)  # CS on region is outside the search bounds.
        with self.assertRaisesRegex(RuntimeError, 'no resolved response'):
            f.run(do_set=True)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assertEqual(len(f.process.FasDiscoveryOutput.get()), 1)
        self.assert_restored(f)

    def test_incompatible_shared_currents_fail_measured_validation(self):
        f = Fixture(active=(10, 11))
        f.centers = {10: (3., 2.), 11: (4., 6.)}
        with self.assertRaisesRegex(RuntimeError, 'insufficient on-state response'):
            f.run(do_set=True)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assertFalse(f.process.FasValidationOutput.get()[0]['passed'])
        self.assert_restored(f)

    def test_bad_map_and_invalid_settings_fail_before_actuation(self):
        cases = [('mapping', {'csAddr': 32}), ('mapping', {'csBoard': 2}),
                 ('mapping', {'csAddr': 0}), ('FasFluxSampleDelay', 0.),
                 ('FasMinimumResponse', float('nan')),
                 ('FasFluxNumSteps', 2), ('CsFluxHighOffset', 0.)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                f = Fixture(active=(10,))
                if field == 'mapping':
                    f.group.RowMap.data[10].update(value)
                else:
                    getattr(f.process, field).data = value
                with self.assertRaises((RuntimeError, ValueError)):
                    f.run(do_set=True)
                self.assertFalse(f.events)
                self.assertTrue(all(not d.Mode.writes for d in f.drivers.values()))

    def test_measurement_failure_restores_companion_and_forces(self):
        f = Fixture(active=(10,))
        f.on_measure = Mock(side_effect=RuntimeError('servo timeout'))
        with self.assertRaisesRegex(RuntimeError, 'servo timeout'):
            f.run(do_set=True)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_stop_racing_final_mode_restore_rolls_back_without_write_through(self):
        f = Fixture(active=(10,))
        driver = f.drivers[0]
        driver.Mode.data = 1

        def stop_on_restore(value, index):
            if value == 1 and driver.FasOn.Current.writes:
                f.stop()

        driver.Mode.on_set = stop_on_restore
        f.run(do_set=True)
        np.testing.assert_array_equal(driver.FasOn.Current.get(), np.full(32, 99.))
        self.assertTrue(all(event[3] == 0 for event in f.events if event[0] == 'program'))
        self.assertEqual(driver.Mode.get(), 1)
        self.assertTrue(all(value == 0. for value in f.outputs.values()))

    def test_mode_restore_failure_also_rolls_back_programming(self):
        f = Fixture(active=(10,))
        driver = f.drivers[0]
        failed = []

        def fail_restore_once(value, index):
            if driver.FasOn.Current.writes and not failed:
                failed.append(True)
                raise OSError('mode restore failed')

        driver.Mode.on_set = fail_restore_once
        with self.assertRaisesRegex(OSError, 'mode restore failed'):
            f.run(do_set=True)
        np.testing.assert_array_equal(driver.FasOn.Current.get(), np.full(32, 99.))
        self.assert_restored(f)

    def test_cleanup_failure_attempts_remaining_forces_and_never_programs(self):
        f = Fixture(active=(10,))
        writes = []

        def fail_restore(value, index):
            writes.append(value)
            if np.array_equal(value, f.initial_forces['SaFbForceCurrent']):
                raise OSError('SA feedback restore failed')

        f.group.SaFbForceCurrent.on_set = fail_restore
        with self.assertRaisesRegex(OSError, 'SA feedback restore failed'):
            f.run(do_set=True)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        for name in ('Sq1BiasForceCurrent', 'Sq1FbForceCurrent'):
            np.testing.assert_array_equal(getattr(f.group, name).get(), f.initial_forces[name])
        self.assertEqual(f.drivers[0].Mode.get(), 0)

    def test_partial_manual_write_failure_preserves_error_and_cleans_all_lines(self):
        f = Fixture(active=(10,))
        calls = []

        def fail_once(key, current):
            calls.append(key)
            if len(calls) == 22:
                raise OSError('manual write failed')

        f.on_drive = fail_once
        with self.assertRaisesRegex(OSError, 'manual write failed'):
            f.run(do_set=True)
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_already_stopped_process_and_running_timing_do_not_write(self):
        for timing_running in (False, True):
            with self.subTest(timing_running=timing_running):
                f = Fixture(active=(10,))
                if timing_running:
                    f.tx.Running.data = True
                    with self.assertRaisesRegex(RuntimeError, 'timing to be stopped'):
                        f.run(do_set=True)
                else:
                    f.stop()
                    f.run(do_set=True)
                self.assertFalse(f.events)
                self.assertTrue(all(not getattr(f.group, name).writes for name in f.initial_forces))

    def test_stop_during_four_state_verification_does_not_program(self):
        f = Fixture(active=(10,))
        f.on_measure = lambda: f.stop() if len(f.samples) == 101 else None
        f.run(do_set=True)
        record = f.process.FasValidationOutput.get()[0]
        self.assertEqual(len(record['responses']), 1)
        self.assertFalse(record['passed'])
        self.assertFalse(f.drivers[0].FasOn.Current.writes)
        self.assert_restored(f)

    def test_strict_servo_rejects_timeout_and_default_retains_diagnostic_behavior(self):
        f = Fixture(active=(10,))
        f.group.SaOutAdc.data[:] = 1.
        common.saFbServo(group=f.group, process=f.process)
        with self.assertRaisesRegex(RuntimeError, 'did not converge'):
            common.saFbServo(group=f.group, process=f.process, require_convergence=True)

    def test_strict_servo_rejects_nonfinite_adc_without_feedback_write(self):
        f = Fixture(active=(10,))
        f.group.SaOutAdc.data[0] = np.nan
        with self.assertRaisesRegex(RuntimeError, 'Non-finite ADC'):
            common.saFbServo(group=f.group, process=f.process, require_convergence=True)
        self.assertFalse(f.group.SaFbForceCurrent.writes)

    def test_discovery_does_not_average_distinct_periodic_minima(self):
        responses = np.full((1, 7, 7), 10.)
        responses[0, 1:3, 1:3] = 0.
        responses[0, 4:6, 4:6] = 0.
        rs, cs = two._grid_seed(responses, np.arange(7), np.arange(7), .1, .1)
        self.assertEqual(responses[0, int(cs), int(rs)], 0.)


@unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'Matplotlib is not installed')
class FasPlotTests(unittest.TestCase):
    def setUp(self):
        # Load Matplotlib before the temporary module registry patch; removing
        # its imports afterward would create duplicate Artist class identities.
        import matplotlib.pyplot  # noqa: F401

        class NodeVariable(Variable):
            def __init__(self, name, value=None, **kwargs):
                super().__init__(value)
                self.name = name

        class Device:
            def __init__(self, **kwargs):
                self._log = Mock(spec=logging.Logger)
                self.root = SimpleNamespace(updateGroup=lambda *args: nullcontext())

            def add(self, node):
                node.parent = self
                setattr(self, node.name, node)

        spec = importlib.util.spec_from_file_location('_fas_process_test', API / '_FasTune.py')
        self.module = importlib.util.module_from_spec(spec)
        api = SimpleNamespace(PausableProcess=Device)
        with patch.dict(sys.modules, {
                'pyrogue': SimpleNamespace(LocalVariable=NodeVariable, LinkVariable=NodeVariable),
                'warm_tdm_api': api}):
            spec.loader.exec_module(self.module)
        self.process = self.module.FasTuneProcess(config=SimpleNamespace(maxRows=80))

    def test_real_plotting_and_result_serialization_for_complete_partial_and_empty_data(self):
        f = Fixture(active=(10,))
        curves = f.run()
        result = self.process._publishResults(curves)
        self.assertEqual(result[0]['companionAddress'], 11)
        self.assertEqual(result[1]['select'], 'CS')
        self.assertFalse(hasattr(self.process, 'TwoLevelMode'))
        self.process.FasDiscoveryOutput.set(f.process.FasDiscoveryOutput.get())
        for node in (self.process.SweepPlot, self.process.TunePlot,
                     self.process.DiscoveryPlot):
            with io.BytesIO() as output:
                node.linkedGet().savefig(output, format='png')
                self.assertGreater(output.tell(), 1000)
        grid = f.process.FasDiscoveryOutput.get()[0]
        grid['responses'][:, 1:, :] = np.nan
        grid['rsOn'] = grid['csOn'] = None
        self.process.FasDiscoveryOutput.set([grid])
        with io.BytesIO() as output:
            self.process.DiscoveryPlot.linkedGet().savefig(output, format='png')
            self.assertGreater(output.tell(), 1000)
        self.process.FasDiscoveryOutput.set([])
        self.assertIn('No discovery data', self.process.DiscoveryPlot.linkedGet().axes[0].texts[0].get_text())

    def test_process_clears_previous_diagnostics_when_next_run_fails_preflight(self):
        self.process.parent = SimpleNamespace()
        self.module.warm_tdm_api.fasTune = Mock(side_effect=ValueError('preflight failed'))
        for variable in (self.process.FasTuneOutput, self.process.FasDiscoveryOutput,
                         self.process.FasValidationOutput):
            variable.set([{'old': True}])
        with self.assertRaisesRegex(ValueError, 'preflight failed'):
            self.process._fasTuneWrap()
        self.assertEqual(self.process.FasTuneOutput.get(), [])
        self.assertEqual(self.process.FasDiscoveryOutput.get(), [])
        self.assertEqual(self.process.FasValidationOutput.get(), [])


if __name__ == '__main__':
    unittest.main()
