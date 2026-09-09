#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""False-pass and cleanup regressions for the VirtualClient cosim test scripts."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts/hwtest'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load('_cosim_common')
with patch.dict(sys.modules, {'_cosim_common': common}):
    readout = load('verify_cosim_readout')
    tuning = load('verify_cosim_tuning')
    controls = load('verify_cosim_controls')


class CosimChecks(unittest.TestCase):
    def test_readout_rejects_empty_partial_extra_and_nonfinite_channels(self):
        for data in [{}, {0: {0: [1]}}, {0: {0: [1], 1: [2], 2: [3]}},
                     {0: {0: [1], 1: [np.nan]}}]:
            with self.subTest(data=data), self.assertRaises(AssertionError):
                readout.require_samples(data, {(0, 0), (0, 1)})
        readout.require_samples({0: {0: [1], 1: [2]}}, {(0, 0), (0, 1)})

    def curve(self):
        return dict(xValues=[0, 1, 2, 3, 4], biasValues=[1],
                    curves=[[0, 1, 2, 1, 0]], xOut=1, yOut=1, biasOut=1, bestIndex=0)

    def test_tuning_rejects_flat_incomplete_nonfinite_or_unselected_curves(self):
        tuning.require_curve(self.curve(), 5, 1, 0.1)
        for update in [dict(curves=[[1]*5]), dict(curves=[[1]*4]),
                       dict(curves=[[0, 1, np.nan, 1, 0]]), dict(xOut=None), dict(bestIndex=2)]:
            with self.subTest(update=update), self.assertRaises(AssertionError):
                tuning.require_curve(dict(self.curve(), **update), 5, 1, 0.1)

    def test_restoration_attempts_all_variables_and_preserves_primary_error(self):
        a = SimpleNamespace(path='a', get=Mock(return_value=1), set=Mock())
        b = SimpleNamespace(path='b', get=Mock(return_value=2), set=Mock(side_effect=OSError('restore')))
        with self.assertRaisesRegex(ValueError, 'test failed'):
            with common.restore([a, b]):
                raise ValueError('test failed')
        a.set.assert_called_once_with(1)
        b.set.assert_called_once_with(2)
        with self.assertRaisesRegex(RuntimeError, 'restoration failed'):
            with common.restore([a, b]):
                pass

    def test_manifest_requires_exact_revisions_and_fixture(self):
        good = dict(firmware_commit='a'*40, server_software_commit='b'*40,
                    surf_commit='c'*40, ruckus_commit='d'*40, fixture='GroupTb', toolchain='VCS')
        common.validate_manifest(good)
        for key, value in [('firmware_commit', 'HEAD'), ('fixture', ''), ('server_software_commit', None)]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                common.validate_manifest(dict(good, **{key: value}))

    def test_timing_timeout_is_failure(self):
        tx = SimpleNamespace(Running=SimpleNamespace(get=lambda: True))
        with patch.object(common.time, 'monotonic', side_effect=[0., 2.]), self.assertRaises(TimeoutError):
            common.wait_running(tx, False, 1.)

    def test_broadcast_verdict_checks_every_board_and_restores_leaves(self):
        def leaf(value):
            node = SimpleNamespace(path='leaf', value=value)
            node.get = lambda: node.value
            node.set = lambda value: setattr(node, 'value', value)
            return node
        leds = [leaf(1), leaf(0)]
        txs = [SimpleNamespace(**{n: leaf(0) for n in ['PwrSyncA', 'PwrSyncB', 'PwrSyncC', 'PwrSyncEn']}) for _ in leds]
        cables = [leaf(100.), leaf(200.)]
        boards = [SimpleNamespace(WarmTdmCore=SimpleNamespace(Timing=SimpleNamespace(TimingTx=tx),
            WarmTdmCommon2=SimpleNamespace(WarmTdmConfig=SimpleNamespace(LedEn=led)))) for led, tx in zip(leds, txs)]
        def ps(value):
            for tx in txs:
                for n in ['PwrSyncA', 'PwrSyncB', 'PwrSyncC']:
                    getattr(tx, n).set(2 if value else 0)
                tx.PwrSyncEn.set(value)
        group = SimpleNamespace(LedEnable=SimpleNamespace(set=lambda v: [n.set(v) for n in leds]),
            CableResistance=SimpleNamespace(set=lambda v: [n.set(v) for n in cables]),
            PowerSupplySynchronized=SimpleNamespace(set=ps))
        sess = SimpleNamespace(boards=lambda: dict(enumerate(boards)), group=group,
                               hwg=SimpleNamespace(find=lambda **kw: cables))
        args = SimpleNamespace(broadcasts_only=True)
        controls.check_controls(sess, args, {'checks': []}, None)
        self.assertEqual([v.get() for v in leds], [1, 0])
        self.assertEqual([v.get() for v in cables], [100., 200.])
        group.LedEnable.set = lambda v: leds[0].set(v)
        with self.assertRaisesRegex(AssertionError, 'LED register fanout'):
            controls.check_controls(sess, args, {'checks': []}, None)
        self.assertEqual([v.get() for v in leds], [1, 0])


if __name__ == '__main__':
    unittest.main()
