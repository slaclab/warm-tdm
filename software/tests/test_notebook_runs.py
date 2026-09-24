# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Run persistence, offline creation, portable templates and failed-check evidence."""
import ast
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runs = load('runs_test', 'software/python/warm_tdm_run/__init__.py')
output = load('output_test', 'software/python/warm_tdm_api/operations/session/_output.py')
config = load('config_test', 'software/python/warm_tdm_api/operations/session/_config.py')
checker = load('check_test', 'software/scripts/check_notebooks.py')


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.template = self.base / 'template.ipynb'
        self.template.write_text(json.dumps(dict(nbformat=4, metadata={}, cells=[
            dict(cell_type='code', source=['print(1)'], metadata={}, execution_count=4,
                 outputs=[dict(output_type='stream', name='stdout', text=['1'])])
        ])))
        self.module_patch = patch.dict(sys.modules, {'warm_tdm_run': runs})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)

    def create(self):
        return runs.create_run(self.template, self.base, 'gain sweep', purpose='Compare gains')

    def test_create_is_unique_output_free_and_preserves_original(self):
        before = self.template.read_bytes()
        first, second = self.create(), self.create()
        self.assertNotEqual(first, second)
        self.assertEqual(self.template.read_bytes(), before)
        self.assertEqual((first/'provenance/template.ipynb').read_bytes(), before)
        cell = json.loads((first/'template.ipynb').read_text())['cells'][0]
        self.assertEqual(cell['outputs'], [])
        self.assertIsNone(cell['execution_count'])
        self.assertEqual(json.loads((first/'run.json').read_text())['purpose'], 'Compare gains')

    def test_reconnect_and_relocation_do_not_create_nested_sessions(self):
        root = self.create()
        (root/'data/saved.dat').write_bytes(b'evidence')
        original = sorted(p.relative_to(root) for p in root.rglob('*'))
        for _ in range(2):
            out = output.OutputDir.existing_run(root)
            self.assertEqual(Path(out.sessiondir), root/'data')
            self.assertEqual(Path(out.configdir), root/'config')
        self.assertEqual(sorted(p.relative_to(root) for p in root.rglob('*')), original)
        moved = (self.base/'moved').resolve()
        shutil.move(root, moved)
        self.assertEqual(runs.find_run(moved/'data'), moved)
        self.assertEqual(Path(output.OutputDir.existing_run(moved).sessiondir), moved/'data')
        self.assertEqual((moved/'data/saved.dat').read_bytes(), b'evidence')

    def test_missing_invalid_or_unwritable_directory_never_falls_back(self):
        with self.assertRaises(FileNotFoundError):
            output.OutputDir.existing_run(self.base/'absent')
        with self.assertRaises(FileNotFoundError):
            runs.create_run(self.template, self.base/'absent', 'test')
        root = self.create()
        with patch.object(runs.os, 'access', return_value=False):
            with self.assertRaises(PermissionError):
                output.OutputDir.existing_run(root)
        (root/'data').rmdir()
        with self.assertRaises(NotADirectoryError):
            output.OutputDir.existing_run(root)
        self.assertFalse((root/'data').exists())
        self.assertFalse((self.base/'absent').exists())

    def test_creation_refuses_tracked_tree_and_cleans_partial_run(self):
        with self.assertRaises(ValueError):
            runs.create_run(self.template, self.base, 'bad', repo=self.base)
        before = set(self.base.rglob('run.json'))
        with patch.object(runs, 'source_snapshot', side_effect=OSError('snapshot failed')):
            with self.assertRaises(OSError):
                runs.create_run(self.template, self.base, 'broken', repo=self.base/'elsewhere')
        self.assertEqual(set(self.base.rglob('run.json')), before)
        self.assertEqual(list(self.base.glob('*/*broken*')), [])

    def test_config_is_saved_in_run_config_and_not_overwritten(self):
        root = self.create()
        session = config.ConfigMixin()
        session.output = output.OutputDir.existing_run(root)
        session._require_output = lambda: session.output.sessiondir
        session.root = SimpleNamespace(SaveConfig=Mock(), SaveState=Mock())
        a, b, c = session.save_config(), session.save_config(), session.save_state()
        self.assertEqual({Path(x).parent for x in [a,b,c]}, {root/'config'})
        self.assertNotEqual(a,b)

    def test_connection_records_do_not_infer_server_revision(self):
        root = self.create()
        version = SimpleNamespace(BuildStamp=SimpleNamespace(get=lambda:'image-a'),
                                  GitHash=SimpleNamespace(get=lambda:123))
        board = SimpleNamespace(WarmTdmCore=SimpleNamespace(WarmTdmCommon=SimpleNamespace(AxiVersion=version)))
        session = SimpleNamespace(boards=lambda:{'Column 0':board})
        with patch.object(runs, 'source_snapshot', return_value={'revision':'client-only'}):
            one = runs.record_connection(session,root,'host',9099)
            two = runs.record_connection(session,root,'host',9099,server_revision='declared')
        self.assertNotEqual(one,two)
        record = json.loads(one.read_text())
        self.assertIsNone(record['server_software_revision'])
        self.assertEqual(record['boards']['Column 0']['BuildStamp'], 'image-a')
        self.assertIn('error', record['boards']['Column 0']['DeviceDna'])
        self.assertEqual(json.loads(two.read_text())['server_revision_source'], 'operator')

    def session_functions(self):
        # Exercise the actual connection functions without importing the device tree.
        path = ROOT/'software/python/warm_tdm_api/operations/session/__init__.py'
        tree = ast.parse(path.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {'_output_for','connect','use'}]
        env = dict(OutputDir=output.OutputDir, Session=Mock(side_effect=lambda group,output:SimpleNamespace(group=group,output=output)),
                   set_default_session=lambda x:x)
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'),env)
        return env

    def test_installed_client_does_not_borrow_a_checkout_revision(self):
        root = self.create()
        installed = self.base/'env/lib/python/site-packages/warm_tdm_run/__init__.py'
        with patch.object(runs, '__file__', str(installed)), \
             patch.object(runs, 'source_snapshot') as snapshot:
            record_path = runs.record_connection(SimpleNamespace(boards=lambda:{}), root, 'host', 9099)
            snapshot.assert_not_called()
            self.assertIsNone(json.loads(record_path.read_text())['source']['revision'])
            with self.assertRaises(RuntimeError):
                runs.run_cosim('verify_cosim_controls', root, [])

    def test_connect_validates_before_client_and_reuses_same_run(self):
        env = self.session_functions()
        interface = ModuleType('pyrogue.interfaces')
        client = SimpleNamespace(root=SimpleNamespace(Group=object()),stop=Mock())
        interface.VirtualClient = Mock(return_value=client)
        rogue = ModuleType('pyrogue'); rogue.interfaces = interface
        with patch.dict(sys.modules,{'pyrogue':rogue,'pyrogue.interfaces':interface}):
            with self.assertRaises(FileNotFoundError):
                env['connect'](run_dir=self.base/'missing')
            interface.VirtualClient.assert_not_called()
            root = self.create()
            one, two = env['connect'](run_dir=root), env['use'](client,run_dir=root)
            self.assertEqual(one.output.sessiondir,two.output.sessiondir)
            with self.assertRaises(ValueError):
                env['connect'](run_dir=root,path=self.base)
            env['Session'].side_effect = RuntimeError('tree mismatch')
            with self.assertRaises(RuntimeError):
                env['connect'](run_dir=root)
            client.stop.assert_called_once()

    def test_template_bootstrap_works_outside_checkout(self):
        root = self.create()
        source = ROOT/'software/notebooks/hardware/operations_template.ipynb'
        nb = json.loads(source.read_text())
        setup = next(''.join(c['source']) for c in nb['cells'] if c['cell_type']=='code'
                     and 'runs.find_run()' in ''.join(c['source']))
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(root)
        env = {}
        with patch.dict(os.environ,{'WARM_TDM_PATH':str(ROOT)}), patch.object(sys,'path',sys.path.copy()):
            exec(compile(setup,'bootstrap','exec'),env)
        self.assertEqual(env['RUN_DIR'],root)

    def test_templates_are_structurally_valid_and_output_free(self):
        self.assertEqual(checker.main([]), 0)

    def test_template_checker_rejects_saved_results_and_malformed_cells(self):
        clean = dict(nbformat=4, nbformat_minor=5, metadata={}, cells=[
            dict(cell_type='code', id='setup', metadata={}, source='%matplotlib inline',
                 outputs=[], execution_count=None)])
        checker.validate(clean)  # Notebook magics are valid cell contents.
        for field, value in [('outputs', [{'output_type': 'stream', 'text': 'result'}]),
                             ('execution_count', 1), ('source', [17]),
                             ('metadata', None), ('cell_type', 'invalid'), ('id', '')]:
            with self.subTest(field=field):
                notebook = deepcopy(clean)
                notebook['cells'][0][field] = value
                with self.assertRaises(ValueError):
                    checker.validate(notebook)
        for field in ['outputs', 'execution_count']:
            notebook = deepcopy(clean)
            del notebook['cells'][0][field]
            with self.assertRaises(ValueError):
                checker.validate(notebook)
        duplicate = deepcopy(clean)
        duplicate['cells'] *= 2
        with self.assertRaises(ValueError):
            checker.validate(duplicate)

    def test_template_checker_ignores_checkpoints_and_does_not_rewrite_files(self):
        template = ROOT/'software/notebooks/hardware/operations_template.ipynb'
        content = template.read_bytes()
        (self.base/'template.ipynb').write_bytes(content)
        checkpoints = self.base/'.ipynb_checkpoints'
        checkpoints.mkdir()
        (checkpoints/'template-checkpoint.ipynb').write_text('not json')
        with patch.object(checker, 'ROOT', self.base):
            self.assertEqual(checker.main([]), 0)
        self.assertEqual((self.base/'template.ipynb').read_bytes(), content)

    def test_failed_cosim_invocation_keeps_log_and_separate_directory(self):
        root = self.create()
        fake = self.base/'checkout'
        scripts = fake/'software/cosim'; scripts.mkdir(parents=True)
        (scripts/'verify_cosim_controls.py').write_text(
            'def main(argv):\n    print("failed measurement retained")\n    return 1\n')
        with patch.object(runs,'__file__',str(fake/'software/python/warm_tdm_run/__init__.py')), \
             patch.object(runs,'source_snapshot',return_value={}):
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    runs.run_cosim('verify_cosim_controls',root,[])
        logs=list((root/'data').glob('*/console.txt'))
        self.assertEqual(len(logs),2)
        self.assertTrue(all('failed measurement retained' in p.read_text() for p in logs))


if __name__ == '__main__':
    unittest.main()
