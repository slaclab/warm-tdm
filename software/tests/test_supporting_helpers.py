# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Exercise existing command closures and PromLoader with fake hardware only."""
import argparse
import ast
from contextlib import nullcontext
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def closure(path, name, env):
    tree = ast.parse((ROOT / path).read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, str(path), 'exec'), env)
    return env[name]


class BatchHelpersTests(unittest.TestCase):
    def test_all_fast_dacs_stages_all_channels_before_flushing_each_driver(self):
        for variant in ['ColumnModule', 'ColumnFpgaBoard', 'ColumnAwaXeFpgaBoard']:
            with self.subTest(variant=variant):
                events = []
                dev = SimpleNamespace(root=SimpleNamespace(updateGroup=lambda: nullcontext()))
                for name in ['SAFb', 'SQ1Fb', 'SQ1Bias']:
                    leaves = {i: SimpleNamespace(set=Mock(side_effect=lambda *, value, write, n=name, c=i:
                        events.append(('stage', n, c, value, write)))) for i in range(8)}
                    setattr(dev, name, SimpleNamespace(OverrideRaw=leaves,
                        writeAndVerifyBlocks=Mock(side_effect=lambda n=name: events.append(('flush', n)))))
                fn = closure(f'firmware/python/warm_tdm/_{variant}.py', 'AllFastDacs', {'self': dev})
                fn(1234)
                self.assertEqual(len(events), 27)
                self.assertTrue(all(e[0]=='stage' and e[3:]==(1234, False) for e in events[:24]))
                self.assertEqual(events[24:], [('flush', 'SAFb'), ('flush', 'SQ1Fb'), ('flush', 'SQ1Bias')])

    def test_fir_taps_respects_cache_only_and_batched_write(self):
        for write in [False, True]:
            with self.subTest(write=write):
                events = []
                taps = np.array([0.1, 0.8, 0.1])
                filters = {i: SimpleNamespace(Taps=SimpleNamespace(set=Mock(
                    side_effect=lambda value, write, c=i: events.append(('stage', c, value.copy(), write)))),
                    writeAndVerifyBlocks=Mock(side_effect=lambda c=i: events.append(('flush', c)))) for i in range(8)}
                dev = SimpleNamespace(root=SimpleNamespace(updateGroup=lambda: nullcontext()), FirFilter=filters)
                firwin = Mock(return_value=taps)
                fn = closure('firmware/python/warm_tdm/_DataPath.py', 'setFirTaps',
                    {'self': dev, 'numberTaps': 3, 'scipy': SimpleNamespace(signal=SimpleNamespace(firwin=firwin))})
                fn(1e6, write)
                firwin.assert_called_once_with(3, 1e6, fs=125e6, window='hamming')
                self.assertEqual(len(events), 16 if write else 8)
                for event in events[:8]:
                    self.assertEqual(event[0], 'stage')
                    np.testing.assert_array_equal(event[2], taps)
                    self.assertIs(event[3], False)
                self.assertEqual(events[8:], [('flush', i) for i in range(8)] if write else [])


class PromLoaderTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.avs = [SimpleNamespace(path=f'Board[{i}].AxiVersion', readBlocks=Mock(), waitBlocks=Mock(),
            printStatus=Mock(), FpgaReload=Mock(side_effect=lambda c=i: self.events.append(('reload', c))))
            for i in range(2)]
        self.proms = [SimpleNamespace(path=f'Board[{i}].Prom', enable=SimpleNamespace(set=Mock()),
            parent=SimpleNamespace(AxiVersion=self.avs[i]),
            LoadMcsFile=Mock(side_effect=lambda image, c=i: self.events.append(('load', c, image))))
            for i in range(2)]
        self.root = MagicMock()
        self.root.__enter__.return_value = self.root
        self.root.Group.HardwareGroup.ColumnBoard = {0: SimpleNamespace(WarmTdmCore=
            SimpleNamespace(WarmTdmCommon2=SimpleNamespace(AxiVersion=self.avs[0])))}
        self.root.find.side_effect = lambda name: self.avs if name=='AxiVersion' else self.proms
        self.factory = Mock(return_value=self.root)
        self.api = SimpleNamespace(WarmTdmArgparse=argparse.ArgumentParser, arg_dict=lambda a: {}, GroupRoot=self.factory)

    def invoke(self, args, responses):
        with patch.dict(sys.modules, {'warm_tdm_api': self.api, 'warm_tdm': SimpleNamespace(),
                                      'pyrogue': SimpleNamespace(addLibraryPath=Mock()), 'rogue': SimpleNamespace()}), \
             patch.object(sys, 'argv', ['PromLoader'] + args), \
             patch('builtins.input', side_effect=responses):
            try:
                runpy.run_path(str(ROOT/'software/scripts/PromLoader'))
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise

    def test_program_reload_targets_only_selected_prom_sibling(self):
        self.invoke(['--path','/tmp/candidate.mcs','--reload'], ['1','y'])
        self.assertEqual(self.events, [('load',1,'/tmp/candidate.mcs'),('reload',1)])

    def test_reload_only_never_programs(self):
        self.invoke(['--reload-only'], ['1','y'])
        self.assertEqual(self.events, [('reload',1)])

    def test_reload_all_keeps_coordinator_connection_until_last(self):
        self.invoke(['--reload-only'], ['all','y'])
        self.assertEqual(self.events, [('reload',1),('reload',0)])

    def test_local_package_flag_is_explicitly_supported(self):
        self.invoke(['--local', '--reload-only'], ['0', 'y'])
        self.assertEqual(self.events, [('reload', 0)])

    def test_program_failure_never_reloads(self):
        self.proms[0].LoadMcsFile.side_effect = OSError('flash failed')
        with self.assertRaises(OSError):
            self.invoke(['--path','/tmp/candidate.mcs','--reload'], ['0','y'])
        self.assertEqual(self.events, [])

    def test_negative_index_cannot_silently_select_last_board(self):
        with self.assertRaises(ValueError):
            self.invoke(['--reload-only'], ['-1','y'])
        self.assertEqual(self.events, [])

    def test_unknown_and_conflicting_flags_rejected_before_connection(self):
        for args in [['--reloadd'], ['--reload','--reload-only']]:
            with self.assertRaises(SystemExit):
                self.invoke(args, [])
        self.factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
