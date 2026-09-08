# This file is part of the WarmTDM software package. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the WarmTDM software package may be copied, modified, propagated,
# or distributed except according to the terms contained in LICENSE.txt.

"""Explicit runtime smoke test: real Rogue threads/ZMQ, simulated bias values.

Run from a Rogue-enabled environment:
    python software/tests/rogue_tes_bias_waveform_smoke.py

No board connection is created. This is separate from the fake-node CI suite.
"""

import importlib.util
import logging
import pathlib
import sys
import time
from types import SimpleNamespace
import unittest

import numpy as np
import pyrogue as pr
import pyrogue.interfaces as interfaces
import rogue

source = pathlib.Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/_TesBiasWaveform.py'
spec = importlib.util.spec_from_file_location('tes_waveform_runtime', source)
waveform = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = waveform
spec.loader.exec_module(waveform)

class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []
    def emit(self, record):
        self.messages.append(self.format(record))

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.bias = np.arange(16, dtype=float) + 3.0
        self.writes = []
        self.fail_writes = set()
        self.root = pr.Root(name='Smoke', pollEn=False)
        self.group = pr.Device(name='Group')
        self.group.add(pr.LinkVariable(name='TesBias', mode='RW',
            linkedGet=lambda: self.bias.copy(), linkedSet=self.write_bias))
        self.proc = waveform.TesBiasWaveformProcess(name='TesBiasWaveformProcess',
            config=SimpleNamespace(numColumns=16))
        self.group.add(self.proc)
        self.root.add(self.group)
        self.server = interfaces.ZmqServer(root=self.root, addr='127.0.0.1', port=0)
        self.root.addInterface(self.server)
        self.addCleanup(self.root.stop)
        self.root.start()
        self.client = interfaces.VirtualClient(addr='127.0.0.1', port=self.server.port())
        self.addCleanup(self.client.stop)
        self.remote = self.client.root.Group.TesBiasWaveformProcess
        self.logs = LogCapture()
        self.proc._log.addHandler(self.logs)
        self.addCleanup(self.proc._log.removeHandler, self.logs)
        self.remote.UpdateRate.set(0.1)
        gen = self.remote.TesBiasWaveformGenerator[0]
        gen.Mode.setDisp('Sine')
        gen.Frequency.set(1.0)
        gen.TESBiasLow.set(0.25)
        gen.TESBiasHigh.set(10.25)

    def write_bias(self, value):
        value = np.asarray(value).copy()
        self.writes.append(value)
        if len(self.writes) in self.fail_writes:
            self.bias[0] = value[0]  # Simulate a partially completed hardware write.
            raise OSError('injected write failure %d' % len(self.writes))
        self.bias[:] = value

    def wait_for(self, condition):
        deadline = time.monotonic() + 3.0
        while not condition():
            if time.monotonic() > deadline:
                self.fail('Runtime condition timed out; Message=%s' % self.proc.Message.get())
            time.sleep(0.005)

    def start_and_finish(self):
        self.remote.Start()
        self.wait_for(lambda: self.proc._thread is not None)
        self.proc._thread.join(3.0)
        self.assertFalse(self.proc._thread.is_alive())
        self.assertFalse(self.remote.Running.get())

    def test_start_stop_restart_and_slow_rate(self):
        for shift in [0.0, 100.0]:
            self.bias[:] = np.arange(16, dtype=float) + 3.0 + shift
            original = self.bias.copy()
            before = len(self.writes)
            self.remote.Start()
            self.wait_for(lambda: len(self.writes) > before and self.remote.Running.get())
            np.testing.assert_array_equal(self.bias[1:], original[1:])
            start = time.monotonic()
            self.remote.Stop()
            elapsed = time.monotonic() - start
            print('Stop round trip: %.6f seconds' % elapsed, flush=True)
            self.assertLess(elapsed, 0.5)  # Generous host budget vs 10-second sample interval.
            self.assertFalse(self.remote.Running.get())
            self.assertEqual(self.remote.Message.get(), 'Done')
            self.assertEqual(len(self.writes), before + 2)
            np.testing.assert_array_equal(self.bias, original)

    def test_partial_write_failure_restores_and_reports_error(self):
        original = self.bias.copy()
        self.fail_writes = {1}
        self.start_and_finish()
        self.assertIn('error', self.remote.Message.get().lower())
        self.assertEqual(len(self.writes), 2)
        np.testing.assert_array_equal(self.bias, original)
        self.assertTrue(any('injected write failure 1' in x for x in self.logs.messages))

    def test_restore_failure_reports_error_on_stop(self):
        self.fail_writes = {2}
        self.remote.Start()
        self.wait_for(lambda: len(self.writes) == 1)
        self.remote.Stop()
        self.assertFalse(self.remote.Running.get())
        self.assertIn('error', self.remote.Message.get().lower())
        self.assertTrue(any('Failed to restore original TES biases' in x for x in self.logs.messages))
        self.assertFalse(any('Original TES biases restored.' in x for x in self.logs.messages))

    def test_client_discovery_and_saved_config_migration(self):
        self.assertEqual(len(self.remote.TesBiasWaveformGenerator), 16)
        self.assertFalse(hasattr(self.remote, 'SoftwareClock'))
        self.assertFalse(hasattr(self.remote, 'tesBiasWaveformGenerator'))
        legacy = 'Smoke:\n  Group:\n    TesBiasWaveformProcess:\n      SoftwareClock: 25.0\n      tesBiasWaveformGenerator[15]:\n        Mode: 1\n        TESBiasLow: 0.125\n        TESBiasHigh: 1.875\n'
        migrated = legacy.replace('SoftwareClock:', 'UpdateRate:').replace(
            'tesBiasWaveformGenerator[', 'TesBiasWaveformGenerator[')
        self.root.setYaml(migrated, writeEach=True, modes=['RW'])
        gen = self.remote.TesBiasWaveformGenerator[15]
        self.assertEqual(self.remote.UpdateRate.get(), 25.0)
        self.assertEqual(gen.Mode.get(), 1)
        self.assertEqual(gen.Mode.getDisp(), 'Square')
        self.assertEqual(gen.TESBiasLow.get(), 0.125)
        self.assertEqual(gen.TESBiasHigh.get(), 1.875)
        gen.Mode.set(2)
        self.assertEqual(gen.Mode.getDisp(), 'Sine')
        saved = self.root.getYaml(modes=['RW'])
        self.assertIn('TesBiasWaveformGenerator[15]', saved)
        self.assertNotIn('SoftwareClock', saved)
        gen.Mode.set(0)
        self.root.setYaml(saved, writeEach=True, modes=['RW'])
        self.assertEqual(gen.Mode.getDisp(), 'Sine')
        self.assertEqual(gen.TESBiasLow.get(), 0.125)

    def test_invalid_rate_and_all_none_do_not_write(self):
        self.remote.UpdateRate.set(0.0)
        self.start_and_finish()
        self.assertEqual(self.writes, [])
        self.assertIn('error', self.remote.Message.get().lower())
        self.remote.TesBiasWaveformGenerator[0].Mode.setDisp('None')
        self.start_and_finish()
        self.assertEqual(self.writes, [])
        self.assertEqual(self.remote.Message.get(), 'Done')

if __name__ == '__main__':
    print('Python:', sys.version, 'Rogue:', rogue.Version.current(), 'NumPy:', np.__version__)
    unittest.main(verbosity=2)
