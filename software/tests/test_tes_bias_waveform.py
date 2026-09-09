# This file is part of the WarmTDM software package. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the WarmTDM software package may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.

"""Waveform control-flow tests with real NumPy, fake Rogue nodes and fake time.

These do not exercise Rogue's threads/transports or physical DAC outputs.
"""

import importlib.util
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np


class Variable:
    def __init__(self, *, name, value, enum=None, **kwargs):
        self.name = name
        self.value = value
        self.enum = enum

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Device:
    def __init__(self, *, name='device', **kwargs):
        self.name = name
        self.nodes = {}

    def add(self, node):
        self.nodes[node.name] = node
        node.parent = self
        if '[' in node.name:
            name, index = node.name.rstrip(']').split('[')
            if not hasattr(self, name):
                setattr(self, name, {})
            getattr(self, name)[int(index)] = node
        else:
            setattr(self, node.name, node)


class Process(Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._runEn = True
        self._log = Mock(spec=logging.Logger)


def load_waveform():
    path = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/_TesBiasWaveform.py'
    spec = importlib.util.spec_from_file_location('tes_waveform_under_test', path)
    module = importlib.util.module_from_spec(spec)
    fake_rogue = SimpleNamespace(Device=Device, Process=Process, LocalVariable=Variable)
    with patch.dict(sys.modules, {'pyrogue': fake_rogue}):
        spec.loader.exec_module(module)
    return module


waveform = load_waveform()


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []
        self.on_sleep = lambda: None

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        if len(self.sleeps) > 1000:
            raise AssertionError('Playback did not stop within the test budget')
        self.sleeps.append(seconds)
        self.now += seconds
        self.on_sleep()


class BiasVariable:
    def __init__(self, values):
        self.value = np.asarray(values, dtype=float)
        self.writes = []
        self.on_write = lambda: None

    def get(self):
        # Deliberately expose the cache to catch failure to copy the snapshot.
        return self.value

    def set(self, values):
        self.writes.append(np.asarray(values).copy())
        self.value[:] = values
        self.on_write()


class WaveformTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.time_patch = patch.object(waveform, 'time', self.clock)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.configure([3.0])

    def configure(self, original):
        self.process = waveform.TesBiasWaveformProcess(
            config=SimpleNamespace(numColumns=len(original)))
        self.bias = BiasVariable(original)
        self.group = SimpleNamespace(TesBias=self.bias)
        self.process.parent = self.group
        for gen in self.process.TesBiasWaveformGenerator.values() if original else []:
            gen.Mode.set(2)  # Legacy numeric mode 2 is Sine.
            gen.TESBiasLow.set(0.0)
            gen.TESBiasHigh.set(10.0)
        self.process.UpdateRate.set(0.1)

    def run_waveform(self):
        self.process._tesBiasWaveformWrap()

    def stop(self):
        self.process._runEn = False

    def assert_restored(self, original):
        np.testing.assert_array_equal(self.bias.value, original)
        np.testing.assert_array_equal(self.bias.writes[-1], original)

    def test_stop_during_long_interval_restores_without_another_sample(self):
        self.clock.on_sleep = self.stop
        self.run_waveform()
        self.assertEqual(self.clock.sleeps, [0.05])
        self.assertEqual(len(self.bias.writes), 2)
        np.testing.assert_array_equal(self.bias.writes[0], [5.0])
        self.assert_restored([3.0])

    def test_stopped_before_entry_does_not_write(self):
        self.stop()
        self.run_waveform()
        self.assertEqual(self.bias.writes, [])

    def test_partial_write_failure_restores_an_independent_snapshot(self):
        failure = OSError('partial hardware write')

        def fail_first_write():
            if len(self.bias.writes) == 1:
                raise failure

        self.bias.on_write = fail_first_write
        with self.assertRaises(OSError) as caught:
            self.run_waveform()
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(self.bias.writes), 2)
        self.assert_restored([3.0])

    def test_interrupt_during_wait_restores(self):
        def interrupt():
            raise KeyboardInterrupt()

        self.clock.on_sleep = interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_waveform()
        self.assert_restored([3.0])

    def test_restore_failure_on_stop_is_raised_and_logged(self):
        failure = OSError('restore failed')

        def stop_then_fail_restore():
            if len(self.bias.writes) == 1:
                self.stop()
            else:
                raise failure

        self.bias.on_write = stop_then_fail_restore
        with self.assertRaises(OSError) as caught:
            self.run_waveform()
        self.assertIs(caught.exception, failure)
        self.process._log.exception.assert_called_once()
        self.assertNotIn('Original TES biases restored.',
                         [call.args[0] for call in self.process._log.info.call_args_list])

    def test_restore_failure_preserves_original_playback_error(self):
        original_error = RuntimeError('playback failed')

        def always_fail():
            if len(self.bias.writes) == 1:
                raise original_error
            raise OSError('restore also failed')

        self.bias.on_write = always_fail
        with self.assertRaises(RuntimeError) as caught:
            self.run_waveform()
        self.assertIs(caught.exception, original_error)
        self.process._log.exception.assert_called_once()
        self.assertEqual(len(self.bias.writes), 2)

    def test_invalid_update_rates_never_write(self):
        for rate in [0.0, -1.0, float('nan'), float('inf'), -float('inf'), 1e-320]:
            with self.subTest(rate=rate):
                self.process.UpdateRate.set(rate)
                with self.assertRaises(ValueError):
                    self.run_waveform()
                self.assertEqual(self.bias.writes, [])

    def test_invalid_waveform_settings_never_write(self):
        cases = [('Mode', 123), ('Frequency', -1.0), ('Frequency', float('nan')),
                 ('Frequency', float('inf')), ('TESBiasLow', float('nan')),
                 ('TESBiasHigh', float('inf'))]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.configure([3.0])
                getattr(self.process.TesBiasWaveformGenerator[0], field).set(value)
                with self.assertRaises(ValueError):
                    self.run_waveform()
                self.assertEqual(self.bias.writes, [])

    def test_invalid_initial_biases_never_write(self):
        for values in [[float('nan')], [float('inf')], [1.0, 2.0], [[3.0]]]:
            with self.subTest(values=values):
                self.bias.value = np.asarray(values)
                with self.assertRaises(ValueError):
                    self.run_waveform()
                self.assertEqual(self.bias.writes, [])

    def test_all_none_is_a_noop(self):
        self.process.TesBiasWaveformGenerator[0].Mode.set(0)
        self.run_waveform()
        self.assertEqual(self.bias.writes, [])
        self.process._log.warning.assert_called_once()

    def test_zero_lines_is_a_noop(self):
        self.configure([])
        self.run_waveform()
        self.assertEqual(self.bias.writes, [])

    def test_generator_count_and_legacy_mode_numbers(self):
        self.configure([3.0] * 16)
        self.assertEqual(len(self.process.TesBiasWaveformGenerator), 16)
        gen = self.process.TesBiasWaveformGenerator[15]
        self.assertEqual(gen.Mode.enum, {0: 'None', 1: 'Square', 2: 'Sine'})
        self.assertIsInstance(gen.TESBiasLow.get(), float)
        self.assertIsInstance(gen.TESBiasHigh.get(), float)

    def test_mixed_modes_use_real_waveform_math_and_restore_every_line(self):
        self.configure([3.0, 4.0, 7.0])
        self.process.UpdateRate.set(4.0)
        generators = self.process.TesBiasWaveformGenerator
        generators[0].Mode.set(1)
        generators[1].TESBiasHigh.set(20.0)
        generators[2].Mode.set(0)

        def stop_after_three_samples():
            if len(self.bias.writes) == 3:
                self.stop()

        self.bias.on_write = stop_after_three_samples
        self.run_waveform()
        np.testing.assert_allclose(self.bias.writes[:3],
                                   [[0., 10., 7.], [0., 20., 7.], [10., 10., 7.]])
        self.assert_restored([3.0, 4.0, 7.0])

    def test_slow_writes_warn_once_and_still_restore(self):
        self.process.UpdateRate.set(100.0)

        def slow_write():
            self.clock.now += 0.03
            if len(self.bias.writes) == 3:
                self.stop()

        self.bias.on_write = slow_write
        self.run_waveform()
        self.process._log.warning.assert_called_once()
        self.assertIn('achievable host', self.process._log.warning.call_args.args[0])
        self.assert_restored([3.0])

    def test_restart_takes_a_new_snapshot(self):
        self.clock.on_sleep = self.stop
        self.run_waveform()
        self.bias.value[:] = [11.0]
        self.process._runEn = True
        self.run_waveform()
        self.assert_restored([11.0])

    def test_nonfinite_generated_sample_restores_prior_writes(self):
        self.process.UpdateRate.set(10.0)
        with patch.object(waveform, 'wfsin', side_effect=[5.0, float('nan')]):
            with self.assertRaisesRegex(ValueError, 'non-finite TES bias'):
                self.run_waveform()
        self.assertEqual(len(self.bias.writes), 2)
        self.assert_restored([3.0])


if __name__ == '__main__':
    unittest.main()
