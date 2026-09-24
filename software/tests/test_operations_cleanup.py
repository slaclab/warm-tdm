# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Failure-path regressions using the actual operations mixins and fake I/O."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acquisition = load('acquisition', 'software/python/warm_tdm_api/operations/session/_acquisition.py')
tuning = load('tuning', 'software/python/warm_tdm_api/operations/session/_tuning.py')
forcedac = load('forcedac', 'software/python/warm_tdm_api/operations/session/_forcedac.py')
session_package = SimpleNamespace(COORDINATOR_COL_BOARD=0)
operations_package = SimpleNamespace(session=session_package)
with patch.dict(sys.modules, {
        'warm_tdm_api': SimpleNamespace(operations=operations_package),
        'warm_tdm_api.operations': operations_package,
        'warm_tdm_api.operations.session': session_package}):
    setup = load('setup_test._setup', 'software/python/warm_tdm_api/operations/session/_setup.py')
with patch.dict(sys.modules, {'_hwtest_common': SimpleNamespace(
        add_conn_args=Mock(), connect=Mock(), Checklist=Mock(), finish=Mock())}):
    hwtest = load('stop_zero_hwtest', 'software/hwtest/verify_stop_and_zero.py')


def var(value):
    return SimpleNamespace(get=Mock(return_value=value), set=Mock())


def board(tx):
    return SimpleNamespace(WarmTdmCore=SimpleNamespace(Timing=SimpleNamespace(TimingTx=tx)))


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tx = SimpleNamespace(Running=var(False), StartRun=Mock(), EndRun=Mock())
        self.writer = SimpleNamespace(IsOpen=var(False), AutoName=Mock(),
            DataFile=var('data.dat'), Open=Mock(), Close=Mock())
        self.session = acquisition.AcquisitionMixin()
        self.session.coordinator_cb = board(self.tx)
        self.session.root = SimpleNamespace(DataWriter=self.writer)
        self.session._require_output = Mock(return_value='/tmp')
        self.sleep = patch.object(acquisition.time, 'sleep').start()
        self.addCleanup(patch.stopall)

    def test_preserves_initial_run_ownership(self):
        for running in [False, True]:
            with self.subTest(running=running):
                self.tx.Running.get.return_value = running
                self.tx.StartRun.reset_mock()
                self.tx.EndRun.reset_mock()
                self.session.take_data(0)
                self.assertEqual(self.tx.StartRun.call_count, int(not running))
                self.assertEqual(self.tx.EndRun.call_count, int(not running))
        self.assertEqual(self.writer.Close.call_count, 2)

    def test_startup_interrupt_stops_without_opening_file(self):
        self.sleep.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.session.take_data(1)
        self.tx.EndRun.assert_called_once()
        self.writer.Open.assert_not_called()

    def test_partial_start_failure_still_stops(self):
        self.tx.StartRun.side_effect = OSError('partial start')
        with self.assertRaisesRegex(OSError, 'partial start'):
            self.session.take_data(1)
        self.tx.EndRun.assert_called_once()

    def test_file_setup_failure_stops_owned_run(self):
        for action in [self.writer.AutoName, self.writer.DataFile.set,
                       self.session._require_output]:
            with self.subTest(action=action):
                action.side_effect = OSError('file setup')
                self.tx.EndRun.reset_mock()
                with self.assertRaisesRegex(OSError, 'file setup'):
                    self.session.take_data(1)
                self.tx.EndRun.assert_called_once()
                self.writer.Open.assert_not_called()
                action.side_effect = None

    def test_partial_open_failure_attempts_close_and_stop(self):
        self.writer.Open.side_effect = OSError('partial open')
        with self.assertRaisesRegex(OSError, 'partial open'):
            self.session.take_data(1)
        self.writer.Close.assert_called_once()
        self.tx.EndRun.assert_called_once()

    def test_close_failure_does_not_skip_timing_stop(self):
        self.writer.Close.side_effect = OSError('close')
        with self.assertRaisesRegex(OSError, 'close'):
            self.session.take_data(0)
        self.tx.EndRun.assert_called_once()

    def test_preserves_interrupt_when_both_cleanups_fail(self):
        self.sleep.side_effect = [None, KeyboardInterrupt()]
        self.writer.Close.side_effect = OSError('close')
        self.tx.EndRun.side_effect = OSError('stop')
        with self.assertLogs(acquisition.log, 'ERROR') as logs:
            with self.assertRaises(KeyboardInterrupt):
                self.session.take_data(1)
        self.assertEqual(len(logs.records), 2)
        self.writer.Close.assert_called_once()
        self.tx.EndRun.assert_called_once()

    def test_stop_failure_after_successful_close_is_reported(self):
        self.tx.EndRun.side_effect = OSError('stop')
        with self.assertRaisesRegex(OSError, 'stop'):
            self.session.take_data(0)
        self.writer.Close.assert_called_once()

    def test_existing_run_is_not_stopped_on_error(self):
        self.tx.Running.get.return_value = True
        self.writer.Open.side_effect = OSError('open')
        with self.assertRaises(OSError):
            self.session.take_data(1)
        self.tx.EndRun.assert_not_called()
        self.writer.Close.assert_called_once()

    def test_existing_writer_and_invalid_duration_rejected_before_start(self):
        self.writer.IsOpen.get.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'already open'):
            self.session.take_data(1)
        for value in [-1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                self.session.take_data(value)
        self.tx.StartRun.assert_not_called()
        self.writer.Close.assert_not_called()

    def test_run_directory_captures_have_distinct_names_without_autoname(self):
        self.session.output = SimpleNamespace(run_dir='/tmp/run')
        self.session._require_output.return_value = '/tmp/run/data'
        self.session.take_data(0)
        self.session.take_data(0)
        names = [call.args[0] for call in self.writer.DataFile.set.call_args_list]
        self.assertEqual(len(set(names)), 2)
        self.assertTrue(all(Path(name).parent == Path('/tmp/run/data') for name in names))
        self.writer.AutoName.assert_not_called()


class TuningTests(unittest.TestCase):
    def setUp(self):
        self.proc = SimpleNamespace(Start=Mock(), Stop=Mock(), Running=var(False),
                                   Message=var('Done'), SaTuneOutput=var('result'), Setting=var(0))
        self.session = tuning.TuningMixin()
        self.session.group = SimpleNamespace(SaTuneProcess=self.proc)
        self.now = 0.0
        def sleep(seconds):
            self.now += seconds
        self.sleep = patch.object(tuning.time, 'sleep', side_effect=sleep).start()
        patch.object(tuning.time, 'monotonic', side_effect=lambda: self.now).start()
        self.addCleanup(patch.stopall)
        self.proc.Start.side_effect = lambda: setattr(self.proc.Running.get, 'return_value', True)

    def test_timeout_stops_and_bounds_poll_interval(self):
        with self.assertRaises(TimeoutError):
            self.session.run_process('SaTuneProcess', timeout_sec=0.2, poll_sec=1)
        self.proc.Stop.assert_called_once()
        self.assertEqual(self.now, 0.2)

    def test_stop_error_does_not_mask_timeout_or_interrupt(self):
        for interrupt in [False, True]:
            with self.subTest(interrupt=interrupt):
                self.proc.Running.get.return_value = False
                self.proc.Stop.side_effect = OSError('stop failed')
                if interrupt:
                    self.sleep.side_effect = KeyboardInterrupt
                with self.assertRaises(KeyboardInterrupt if interrupt else TimeoutError):
                    self.session.run_process('SaTuneProcess', timeout_sec=0.1)

    def test_partial_start_error_attempts_stop(self):
        self.proc.Start.side_effect = OSError('start failed')
        with self.assertRaisesRegex(OSError, 'start failed'):
            self.session.run_process('SaTuneProcess')
        self.proc.Stop.assert_called_once()

    def test_existing_process_is_not_reconfigured_or_stopped(self):
        self.proc.Running.get.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'already running'):
            self.session.run_process('SaTuneProcess', Setting=5)
        self.proc.Setting.set.assert_not_called()
        self.proc.Start.assert_not_called()
        self.proc.Stop.assert_not_called()

    def test_nonblocking_leaves_process_running(self):
        self.assertIsNone(self.session.run_process('SaTuneProcess', block=False))
        self.proc.Stop.assert_not_called()
        self.assertTrue(self.proc.Running.get())

    def test_normal_completion_returns_output(self):
        self.proc.Start.side_effect = None
        self.assertEqual(self.session.run_process('SaTuneProcess'), 'result')
        self.proc.Stop.assert_not_called()

    def test_process_error_is_not_returned_as_success(self):
        self.proc.Start.side_effect = None
        self.proc.Message.get.return_value = 'Stopped after error!'
        with self.assertRaisesRegex(RuntimeError, 'Stopped after error'):
            self.session.run_process('SaTuneProcess')
        self.proc.SaTuneOutput.get.assert_not_called()

    def test_invalid_wait_parameters_do_not_start(self):
        for kwargs in [{'poll_sec': 0}, {'poll_sec': float('nan')},
                       {'timeout_sec': -1}, {'timeout_sec': float('inf')}]:
            with self.assertRaises(ValueError):
                self.session.run_process('SaTuneProcess', **kwargs)
        self.proc.Start.assert_not_called()


class ForceTests(unittest.TestCase):
    def setUp(self):
        self.session = forcedac.ForceDacMixin()
        self.session.chans_per_board = 2
        self.session.cbs = {}
        self.session.group = SimpleNamespace()
        for i in range(2):
            cb = SimpleNamespace()
            for setter, dev_name in self.session._FAST_DAC_FORCE.values():
                setattr(cb, dev_name, SimpleNamespace(
                    DacCurrentNow={ch: var(0.0) for ch in range(2)}))
                # Per-board (unmasked) force setter -- the write path stop_and_zero
                # and set_force use so disabled columns are still driven/zeroed.
                setattr(cb, setter, var([0.0] * 2))
            cb.SaBiasOffset = SimpleNamespace(
                BiasCurrent={ch: var(25.0) for ch in range(2)},
                OffsetVoltage={ch: var(0.5) for ch in range(2)})
            cb.TesBias = SimpleNamespace(BiasCurrent={ch: var(30.0) for ch in range(2)})
            self.session.cbs[i] = cb
        for setter, _ in self.session._FAST_DAC_FORCE.values():
            # Group-level setter is still read for the column count (get); the
            # ColEnableMask gating on its set() is exactly what the fix bypasses.
            setattr(self.session.group, setter, var([0.0] * 4))
        self.tx = SimpleNamespace(Running=var(False), EndRun=Mock(), Mode=var(0))
        self.session.coordinator_cb = board(self.tx)
        for name in ['SaBiasCurrent', 'SaOffset', 'TesBias']:
            setattr(self.session.group, name, var([0.0] * 4))
        patch.object(forcedac.time, 'sleep').start()
        self.addCleanup(patch.stopall)

    def test_complete_finite_readbacks_succeed(self):
        self.assertEqual(self.session.set_force('Sq1Fb', 0, tries=1), (True, {}))
        for cb in self.session.cbs.values():
            for current in cb.SQ1Fb.DacCurrentNow.values():
                current.get.assert_called_once()

    def test_failed_and_partial_reads_never_succeed_and_other_channels_still_read(self):
        for cb in self.session.cbs.values():
            cb.SQ1Fb.DacCurrentNow[0].get.side_effect = OSError('read failed')
        ok, residual = self.session.set_force('Sq1Fb', 0, tries=2)
        self.assertFalse(ok)
        self.assertEqual(set(residual), {(0, 0), (1, 0)})
        self.assertTrue(all(np.isnan(v) for v in residual.values()))
        self.session.cbs[1].SQ1Fb.DacCurrentNow[1].get.assert_called()

    def test_all_failed_reads_and_missing_channels_fail(self):
        for cb in self.session.cbs.values():
            del cb.SQ1Fb.DacCurrentNow
        ok, residual = self.session.set_force('Sq1Fb', 0, tries=1)
        self.assertFalse(ok)
        self.assertEqual(len(residual), 4)

    def test_nan_and_infinite_currents_fail(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            self.session.cbs[1].SQ1Fb.DacCurrentNow[1].get.return_value = value
            ok, residual = self.session.set_force('Sq1Fb', 0, tries=1)
            self.assertFalse(ok)
            self.assertIn((1, 1), residual)

    def test_incomplete_reader_result_fails(self):
        self.session._read_dac_now = Mock(return_value={})
        ok, residual = self.session.set_force('Sq1Fb', 0, tries=1)
        self.assertFalse(ok)
        self.assertEqual(len(residual), 4)

    def test_retry_can_recover_missing_read(self):
        self.session.cbs[0].SQ1Fb.DacCurrentNow[0].get.side_effect = [OSError('transient'), 0]
        self.assertEqual(self.session.set_force('Sq1Fb', 0, tries=2), (True, {}))

    def test_invalid_target_shape_values_and_topology_rejected_before_write(self):
        setter_mock = self.session.cbs[0].Sq1FbForceCurrent.set
        for target in [[0], [0, 0, 0, float('nan')], float('inf'), [[0] * 4]]:
            with self.assertRaises(ValueError):
                self.session.set_force('Sq1Fb', target)
        self.session.cbs = {}
        with self.assertRaises(ValueError):
            self.session.set_force('Sq1Fb', 0)
        setter_mock.assert_not_called()

    def test_stop_zero_reports_failure_and_attempts_remaining_outputs(self):
        for cb in self.session.cbs.values():
            cb.Sq1FbForceCurrent.set.side_effect = OSError('fast write')
        self.session.cbs[0].SaBiasOffset.BiasCurrent[0].set.side_effect = OSError('slow write')
        self.assertFalse(self.session.stop_and_zero())
        for cb in self.session.cbs.values():
            cb.SaFbForceCurrent.set.assert_called()
            cb.Sq1BiasForceCurrent.set.assert_called()
        self.session.cbs[0].SaBiasOffset.BiasCurrent[1].set.assert_called_once_with(0.0)
        for cb in self.session.cbs.values():
            cb.SaBiasOffset.OffsetVoltage[0].set.assert_called_once_with(0.0)
            cb.TesBias.BiasCurrent[1].set.assert_called_once_with(0.0)

    def test_force_write_uses_unmasked_per_board_setter(self):
        # Issue #86 regression: the force write must go through the unmasked
        # per-board setter, never the ColEnableMask-gated Group setter, so
        # disabled columns are still driven/zeroed by stop_and_zero.
        self.session.set_force('SaFb', 0, tries=1)
        for cb in self.session.cbs.values():
            cb.SaFbForceCurrent.set.assert_called()
        self.session.group.SaFbForceCurrent.set.assert_not_called()

    def test_stop_zero_does_not_claim_stopped_if_timing_stays_running(self):
        self.tx.Running.get.return_value = True
        self.assertFalse(self.session.stop_and_zero(settle_sec=0))
        self.tx.EndRun.assert_called_once()
        self.session.cbs[1].TesBias.BiasCurrent[1].set.assert_called_once_with(0.0)

    def test_stop_zero_success(self):
        self.assertTrue(self.session.stop_and_zero())

    def test_stop_zero_reaches_slow_outputs_even_when_all_columns_disabled(self):
        self.session.group.ColEnableMask = var(0)
        # The Group setters intentionally discard writes to disabled columns.
        # Assert the underlying outputs, rather than calls to those setters.
        outputs = []
        for cb in self.session.cbs.values():
            for bank in [cb.SaBiasOffset.BiasCurrent,
                         cb.SaBiasOffset.OffsetVoltage, cb.TesBias.BiasCurrent]:
                for leaf in bank.values():
                    leaf.set.side_effect = lambda value, leaf=leaf: setattr(leaf.get, 'return_value', value)
                    outputs.append(leaf)
        self.assertTrue(self.session.stop_and_zero())
        self.assertTrue(all(leaf.get() == 0 for leaf in outputs))
        for name in ['SaBiasCurrent', 'SaOffset', 'TesBias']:
            getattr(self.session.group, name).set.assert_not_called()


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.session = setup.SetupMixin()
        self.session.group = SimpleNamespace(
            RowEnableMasks=var([10 + col for col in range(16)]),
            PidP_Gain=var([1.0] * 16), PidI_Gain=var([2.0] * 16),
            PidD_Gain=var([0.0] * 16))
        self.session.col_to_board_chan = lambda col: divmod(col, 8)
        self.enabled = [col in (1, 9) for col in range(16)]
        self.session.col_enable_bools = lambda: self.enabled
        self.session.cbs = {}
        self.tx = SimpleNamespace(**{name: var(0) for name in (
            'Mode', 'RowPeriodCycles', 'SampleStartTime', 'SampleEndTime')})
        for idx in range(2):
            cb = board(self.tx)
            cb.DataPath = SimpleNamespace(AdcDsp={ch: SimpleNamespace(
                ClearPids=Mock(), PidEnable=var(True), PidDebugEnable=var(True),
                RowEnableMask=var(255)) for ch in range(8)})
            self.session.cbs[idx] = cb
        self.session.coordinator_cb = self.session.cbs[0]
        self.session.rbs = {0: object()}
        self.session.rdds = {0: SimpleNamespace(Mode=var(1))}

    def test_mux_sets_pid_debug_and_masks_on_each_board(self):
        self.session.setup_mux(enable_pid_debug=True)
        for col in range(16):
            idx, ch = divmod(col, 8)
            dsp = self.session.cbs[idx].DataPath.AdcDsp[ch]
            dsp.ClearPids.assert_called_once()
            dsp.PidEnable.set.assert_called_once_with(self.enabled[col])
            dsp.PidDebugEnable.set.assert_called_once_with(self.enabled[col])
            if self.enabled[col]:
                dsp.RowEnableMask.set.assert_called_once_with(10 + col)
            else:
                dsp.RowEnableMask.set.assert_not_called()

    def test_mux_can_disable_all_pid_and_debug_outputs(self):
        self.session.setup_mux(enable_pid=False, enable_pid_debug=False)
        for cb in self.session.cbs.values():
            for dsp in cb.DataPath.AdcDsp.values():
                dsp.PidEnable.set.assert_called_once_with(False)
                dsp.PidDebugEnable.set.assert_called_once_with(False)

    def test_set_pid_uses_global_gain_index_and_board_local_debug_index(self):
        self.session.set_pid(p=3, i=4, debug=True)
        for gain, value in [('PidP_Gain', 3.0), ('PidI_Gain', 4.0)]:
            self.assertEqual(getattr(self.session.group, gain).set.call_count, 2)
            for col in (1, 9):
                getattr(self.session.group, gain).set.assert_any_call(value=value, index=col)
        for idx in range(2):
            self.session.cbs[idx].DataPath.AdcDsp[1].PidDebugEnable.set.assert_called_once_with(True)
            self.session.cbs[idx].DataPath.AdcDsp[0].PidDebugEnable.set.assert_not_called()


class DeadMaskTests(unittest.TestCase):
    def setUp(self):
        self.session = setup.SetupMixin()
        self.session.group = SimpleNamespace(RowEnableMasks=var([255] * 24))
        self.session.col_to_board_chan = lambda col: divmod(col, 8)
        self.mask = var(255)
        self.session.cbs = {2: SimpleNamespace(DataPath=SimpleNamespace(
            AdcDsp={3: SimpleNamespace(RowEnableMask=self.mask)}))}

    def test_apply_writes_global_column_hardware_before_updating_cache(self):
        events = []
        self.mask.set.side_effect = lambda value: events.append(('hardware', value))
        self.session.group.RowEnableMasks.set.side_effect = lambda **kw: events.append(('cache', kw))
        self.session.apply_dead_masks({19: 5})
        self.assertEqual(events, [('hardware', 5), ('cache', {'value': 5, 'index': 19})])

    def test_failed_write_does_not_report_mask_applied_in_cache(self):
        self.mask.set.side_effect = OSError('write failed')
        with self.assertRaisesRegex(OSError, 'write failed'):
            self.session.apply_dead_masks({19: 5})
        self.session.group.RowEnableMasks.set.assert_not_called()

    def test_absent_board_is_skipped_without_cache_update(self):
        with self.assertLogs(setup.log, 'WARNING'):
            self.session.apply_dead_masks({0: 5})
        self.mask.set.assert_not_called()
        self.session.group.RowEnableMasks.set.assert_not_called()


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.running = False
        self.current = 0.0
        self.tx = SimpleNamespace(Running=SimpleNamespace(get=lambda: self.running))
        self.tx.StartRun = Mock(side_effect=self.start)
        cb = board(self.tx)
        cb.DataPath = SimpleNamespace(AdcDsp={0: SimpleNamespace(PidEnable=var(False))})
        for drv in hwtest._DRIVERS:
            setattr(cb, drv, SimpleNamespace(
                DacCurrentNow={0: SimpleNamespace(get=Mock(side_effect=lambda: self.current))}))
        self.group = SimpleNamespace(NumColumns=var(1))
        for name in ['Sq1FbCurrent', 'SaFbCurrent', 'Sq1BiasCurrent']:
            setattr(self.group, name, var(np.array([[7.0, 8.0]])))
        self.sess = SimpleNamespace(cbs={0: cb}, rbs={0: object()}, chans_per_board=1,
            coordinator_cb=cb, group=self.group, setup_mux=Mock(),
            stop_and_zero=Mock(side_effect=self.zero), set_force=Mock(side_effect=self.force))
        self.args = SimpleNamespace(cycles=2, tol_uA=0.5, force_uA=50., settle_sec=0.,
                                    num_pts=512, skip_cols='')
        patch.object(hwtest.time, 'sleep').start()
        self.addCleanup(patch.stopall)

    def start(self):
        self.events.append('start')
        self.running = True

    def zero(self, **kwargs):
        self.events.append('zero')
        self.running = False
        self.current = 0.0
        return True

    def force(self, *args, **kwargs):
        self.events.append('nonzero')
        self.current = 50.0
        return True, {}

    def test_success_requires_real_start_every_cycle_and_restores_row_settings(self):
        self.assertTrue(hwtest.run_cycles(self.sess, self.args))
        self.assertEqual(self.tx.StartRun.call_count, 2)
        self.assertEqual(self.events[:6], ['zero', 'nonzero', 'nonzero', 'nonzero', 'start', 'zero'])
        for name in ['Sq1FbCurrent', 'SaFbCurrent', 'Sq1BiasCurrent']:
            np.testing.assert_array_equal(getattr(self.group, name).set.call_args.args[0], [[7., 8.]])
        self.assertFalse(self.running)

    def test_zero_only_baseline_fails_without_starting_run(self):
        self.sess.set_force.side_effect = lambda *a, **k: (True, {})
        with self.assertRaisesRegex(RuntimeError, 'Nonzero baseline'):
            hwtest.run_cycles(self.sess, self.args)
        self.tx.StartRun.assert_not_called()
        self.assertFalse(self.running)

    def test_failed_or_nonfinite_reads_never_pass(self):
        leaf = self.sess.coordinator_cb.SQ1Fb.DacCurrentNow[0]
        leaf.get.side_effect = OSError('read')
        with self.assertRaises(OSError):
            hwtest.run_cycles(self.sess, self.args)
        leaf.get.side_effect = lambda: self.current
        self.current = float('nan')
        with self.assertRaises(ValueError):
            hwtest.run_cycles(self.sess, self.args)
        self.tx.StartRun.assert_not_called()

    def test_failure_to_start_mux_fails_and_cleans_up(self):
        self.tx.StartRun.side_effect = None
        with patch.object(hwtest, '_wait_running', side_effect=TimeoutError('running')):
            with self.assertRaises(TimeoutError):
                hwtest.run_cycles(self.sess, self.args)
        self.assertFalse(self.running)
        self.assertEqual(self.current, 0.0)

    def test_zeroing_failure_is_not_a_pass(self):
        count = 0
        def zero(**kwargs):
            nonlocal count
            count += 1
            self.zero()
            return count != 2
        self.sess.stop_and_zero.side_effect = zero
        with self.assertRaisesRegex(RuntimeError, 'incomplete cleanup'):
            hwtest.run_cycles(self.sess, self.args)
        self.assertGreaterEqual(count, 3)

    def test_post_zero_read_failure_or_nan_never_passes(self):
        for value in [OSError('post-zero read'), float('nan')]:
            with self.subTest(value=value):
                leaf = self.sess.coordinator_cb.SQ1Fb.DacCurrentNow[0]
                leaf.get = Mock(side_effect=[0.0, 50.0, 50.0, value])
                with self.assertRaises((OSError, ValueError)):
                    hwtest.run_cycles(self.sess, self.args)
                self.assertFalse(self.running)

    def test_running_zero_baseline_fails_even_after_idle_nonzero(self):
        def start():
            self.start()
            self.current = 0.0
        self.tx.StartRun.side_effect = start
        with self.assertRaisesRegex(RuntimeError, 'Nonzero baseline'):
            hwtest.run_cycles(self.sess, self.args)
        self.assertFalse(self.running)

    def test_nonzero_baseline_requires_every_channel(self):
        with self.assertRaisesRegex(RuntimeError, 'Nonzero baseline'):
            hwtest._require_nonzero({(0, 'SQ1Fb'): [50.0, 0.0]}, 0.5)

    def test_cosim_timing_timeout_reaches_start_stop_waits_and_cleanup(self):
        self.args.timing_timeout = 120.0
        with patch.object(hwtest, '_wait_running') as wait:
            hwtest.run_cycles(self.sess, self.args)
        self.assertTrue(all(c.kwargs['timeout'] == 120.0 for c in wait.call_args_list))
        self.assertTrue(all(c.kwargs['settle_sec'] == 120.0
                            for c in self.sess.stop_and_zero.call_args_list))

    def test_invalid_cycles_rejected_without_writes(self):
        self.args.cycles = 0
        with self.assertRaises(ValueError):
            hwtest.run_cycles(self.sess, self.args)
        self.sess.stop_and_zero.assert_not_called()


if __name__ == '__main__':
    unittest.main()
