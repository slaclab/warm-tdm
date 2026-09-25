# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Offline notebook/run management. Standard library only; no hardware imports."""
import getpass
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone


def _json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def _git(root, *args):
    try:
        return subprocess.check_output(
            ['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return None


def environment():
    packages = {}
    for name in ['rogue', 'numpy', 'scipy', 'matplotlib', 'jupyterlab', 'ipykernel']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return dict(python=platform.python_version(), platform=platform.platform(), packages=packages)


def _checkout():
    root = Path(__file__).resolve().parents[3]
    # An installed copy must not borrow the revision of an enclosing checkout.
    if Path(__file__).resolve() != root / 'software/python/warm_tdm_run/__init__.py':
        return None
    return root


def source_snapshot(root, destination):
    """Capture identity and local source changes; notebook contents are saved separately."""
    root = Path(root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    revision = _git(root, 'rev-parse', 'HEAD')
    status = _git(root, 'status', '--short', '--untracked-files=normal')
    patch = _git(root, 'diff', '--binary', 'HEAD', '--', '.', ':(glob,exclude)**/*.ipynb')
    if patch:
        (destination / 'source.patch').write_text(patch)
    # New source modules do not appear in git diff. Preserve them as well.
    untracked = _git(root, 'ls-files', '--others', '--exclude-standard', '--',
                     'software', 'firmware/python') or ''
    saved = []
    for name in untracked.splitlines():
        path = root / name
        if path.suffix in {'.py', '.json', '.yml', '.yaml'} and path.is_file():
            target = destination / 'untracked' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            saved.append(name)
    return dict(checkout=str(root), revision=revision.strip() if revision else None,
                status=status, saved_untracked_sources=saved,
                submodules=_git(root, 'submodule', 'status'))


def validate_run(directory):
    """Resolve an existing run; never create a directory or fall back elsewhere."""
    root = Path(directory).expanduser().resolve(strict=True)
    manifest = json.loads((root / 'run.json').read_text())
    if manifest.get('format') != 'warm-tdm-run-v1':
        raise ValueError('Not a Warm-TDM run directory: ' + str(root))
    for path in [root] + [root / n for n in ['data', 'config', 'figures', 'provenance']]:
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        if not os.access(path, os.W_OK | os.X_OK):
            raise PermissionError('Run directory is not writable: ' + str(path))
    return root


def find_run(start=None):
    """Find the run containing the notebook kernel's working directory."""
    start = Path(start or Path.cwd()).resolve()
    for path in [start, *start.parents]:
        if (path / 'run.json').is_file():
            return validate_run(path)
    raise FileNotFoundError('Open a copied notebook in its run directory, or set RUN_DIR explicitly.')


def create_run(template, base, name, purpose='', operator=None, repo=None):
    """Copy an output-free notebook into a new, exclusive measurement directory."""
    template = Path(template).resolve(strict=True)
    notebook = json.loads(template.read_text())
    if notebook.get('nbformat') != 4:
        raise ValueError('Expected a version 4 notebook')
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
    notebook.get('metadata', {}).pop('jupytext', None)
    slug = re.sub(r'[^a-zA-Z0-9_-]+', '-', name).strip('-')
    if not slug:
        raise ValueError('Provide a descriptive run name')
    base = Path(base).expanduser().resolve(strict=True)
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    if repo:
        checkout = Path(repo).resolve()
        if checkout == base or checkout in base.parents:
            local_runs = checkout / 'runs'
            if base != local_runs and local_runs not in base.parents:
                raise ValueError('Use external experiment storage or the checkout\'s ignored runs/ directory')
    now = datetime.now(timezone.utc)
    day = base / now.strftime('%Y-%m-%d')
    day.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=now.strftime('%H%M%S') + '_' + slug + '_', dir=day))
    try:
        for name in ['data', 'config', 'figures', 'provenance']:
            (root / name).mkdir()
        _json(root / template.name, notebook)
        shutil.copyfile(template, root / 'provenance' / 'template.ipynb')
        if repo and template.parent.name == 'cosim':
            for profile in (Path(repo) / 'software/cosim').glob('*.example.json'):
                shutil.copyfile(profile, root / 'config' / profile.name)
        source = source_snapshot(repo, root / 'provenance' / 'creation') if repo else None
        _json(root / 'run.json', dict(
            format='warm-tdm-run-v1', created_utc=now.isoformat(), purpose=purpose,
            operator=operator or getpass.getuser(), notebook=template.name,
            template=dict(path=str(template), sha256=hashlib.sha256(template.read_bytes()).hexdigest()),
            source=source, environment=environment(), server_software_revision=None))
        (root / 'README.md').write_text(
            '# Measurement record\n\n' + purpose + '\n\n'
            '## Outcome\n\nRecord observations, failed/interrupted attempts and data filenames here '
            'or in the executed notebook. Keep original data; use new notebooks for later analysis.\n')
    except BaseException:
        shutil.rmtree(root)
        raise
    return root


def record_connection(session, run_dir, host, port, server_revision=None):
    """Save read-only board identity and client provenance for this connection.

    A supplied server revision is operator-declared, never inferred from the client.
    Individual failed identity reads are retained as errors, not omitted.
    """
    root = validate_run(run_dir)
    dest = Path(tempfile.mkdtemp(prefix='connection-', dir=root / 'provenance'))
    boards = {}
    for name, board in session.boards().items():
        values = {}
        try:
            version = board.WarmTdmCore.WarmTdmCommon.AxiVersion
            for field in ['BuildStamp', 'GitHash', 'DeviceDna', 'ImageName']:
                try:
                    values[field] = getattr(version, field).get()
                except Exception as exc:
                    values[field] = dict(error=str(exc))
        except Exception as exc:
            values['error'] = str(exc)
        boards[name] = values
    checkout = _checkout()
    record = dict(connected_utc=datetime.now(timezone.utc).isoformat(), host=host, port=port,
                  server_software_revision=server_revision, server_revision_source='operator' if server_revision else 'unknown',
                  boards=boards, environment=environment(),
                  source=source_snapshot(checkout, dest) if checkout else
                  dict(revision=None, module=__file__, note='Installed client; checkout identity unavailable'))
    _json(dest / 'connection.json', record)
    return dest / 'connection.json'


def run_cosim(name, run_dir, arguments):
    """Call the maintained batch implementation, retaining its console and results.

    Each invocation owns a fresh directory, including when a notebook cell is
    rerun. Verification scripts own connection, cleanup, and acceptance criteria.
    """
    import contextlib
    import importlib.util
    import sys
    import traceback
    allowed = {'verify_cosim_controls', 'verify_cosim_readout', 'verify_cosim_stop_zero',
               'verify_cosim_pid', 'verify_cosim_tuning', 'cosim_pid_lock'}
    if name not in allowed:
        raise ValueError('Unknown cosim check: ' + name)
    root = validate_run(run_dir)
    checkout = _checkout()
    if checkout is None:
        raise RuntimeError('Cosim notebook checks require the source checkout; set WARM_TDM_PATH in the kernel environment')
    scripts = checkout / 'software/cosim'
    destination = Path(tempfile.mkdtemp(prefix=name + '-', dir=root / 'data'))
    argv = list(arguments) + (['--run-dir', str(root)] if name == 'cosim_pid_lock'
                              else ['--output', str(destination)])
    _json(destination / 'invocation.json', dict(script=name, arguments=argv,
          environment=environment(), source=source_snapshot(checkout, destination / 'source')))

    class Tee:
        def __init__(self, console, logfile):
            self.console, self.logfile = console, logfile
        def write(self, value):
            self.logfile.write(value)
            return self.console.write(value)
        def flush(self):
            self.logfile.flush()
            self.console.flush()

    sys.path.insert(0, str(scripts))
    try:
        with (destination / 'console.txt').open('w') as log:
            with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
                try:
                    spec = importlib.util.spec_from_file_location(name, scripts / (name + '.py'))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    status = module.main(argv)
                except BaseException:
                    traceback.print_exc()
                    raise
        if status:
            raise RuntimeError(f'{name} failed; inspect {destination}')
    finally:
        if str(scripts) in sys.path:
            sys.path.remove(str(scripts))
        print(f'Invocation records: {destination}')
    return destination
