#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""VirtualClient connection, evidence and cleanup for explicit cosim runs.

No Rogue import until connection, so validators can also run in ordinary CI.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
import shutil
import math
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('must be finite and positive')
    return value


def parser(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=9099)
    p.add_argument('--manifest', type=Path, required=True,
                   help='JSON identifying the running VCS firmware, fixture and toolchain')
    p.add_argument('--output', type=Path, required=True,
                   help='artifact directory accessible at the SAME path by server and client')
    p.add_argument('--timing-timeout', type=positive, default=120.0,
                   help='wall seconds allowed for simulated timing transitions')
    return p


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def validate_manifest(manifest):
    for field in ['firmware_commit', 'server_software_commit', 'surf_commit', 'ruckus_commit']:
        require(isinstance(manifest.get(field), str) and
                re.fullmatch(r'[0-9a-fA-F]{40}', manifest[field]) is not None,
                f'Manifest needs a full 40-character {field}')
    for field in ['fixture', 'toolchain']:
        require(isinstance(manifest.get(field), str) and bool(manifest[field].strip()),
                f'Manifest needs nonempty {field}')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def passed(report, name, **details):
    report['checks'].append(dict(name=name, result='PASS', **details))
    print('PASS:', name, flush=True)


def wait_running(tx, expected, timeout):
    end = time.monotonic() + timeout
    while bool(tx.Running.get()) != expected:
        if time.monotonic() >= end:
            raise TimeoutError(f'Running did not become {expected} within {timeout}s')
        time.sleep(0.1)


@contextmanager
def restore(variables):
    """Restore every saved variable, reporting cleanup failure without masking a test error."""
    saved = [(v, deepcopy(v.get())) for v in variables]
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        errors = []
        for var, value in reversed(saved):
            try:
                var.set(value)
            except BaseException as exc:
                errors.append(exc)
                print(f'RESTORE FAILED {var.path}: {exc}', file=sys.stderr, flush=True)
        if errors and not failed:
            raise RuntimeError('Variable restoration failed') from errors[0]


def stopped_session(sess):
    require(len(sess.cbs) == 1 and len(sess.rbs) == 1,
            'Tests require one column board and one row board')
    tx = sess.coordinator_cb.WarmTdmCore.Timing.TimingTx
    require(not tx.Running.get(), 'Stop timing before starting this test')
    require(not sess.root.DataWriter.IsOpen.get(), 'Close the writer before starting this test')
    for name in ['SaOffsetProcess', 'SaTuneProcess', 'Sq1TuneProcess',
                 'FasTuneProcess', 'TesBiasWaveformProcess']:
        require(not getattr(sess.group, name).Running.get(), f'{name} is already running')
    return tx


def run(args, check):
    """Run one test through an actual VirtualClient and always write a result file.

    The supplied manifest is provenance, not automatic detection of a VCS server.
    Run only against a dedicated simulation server; no flash/reload is issued.
    """
    args.output = args.output.expanduser().resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='cosim-', dir=args.output))
    report = dict(result='FAIL', checks=[], started_utc=datetime.now(timezone.utc).isoformat(),
                  arguments=vars(args).copy(), scope='software-visible checks; declared simulation setup in manifest; no physical acceptance')
    client = None
    started = time.monotonic()
    try:
        manifest = json.loads(args.manifest.read_text())
        validate_manifest(manifest)
        report['supplied_simulation_manifest'] = manifest
        source_dir = directory / 'scripts'
        source_dir.mkdir()
        script_paths = list(Path(__file__).parent.glob('verify_cosim_*.py')) + [Path(__file__), Path(__file__).with_name('verify_stop_and_zero.py'), Path(__file__).with_name('_hwtest_common.py')]
        report['script_sha256'] = {}
        for path in script_paths:
            shutil.copyfile(path, source_dir / path.name)
            report['script_sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        report['client_source'] = dict(commit=git('rev-parse', 'HEAD'),
            status=git('status', '--short'), submodules=git('submodule', 'status'))
        # Include a patch because the maintainer may test a working candidate.
        (directory / 'client.patch').write_text(git('diff', 'HEAD'))
        sys.path.insert(0, str(ROOT / 'software/scripts'))
        import _setupLibPaths  # noqa: F401
        import pyrogue.interfaces
        import rogue
        import warm_tdm_api.operations as ops
        report['rogue_version'] = rogue.Version.current()
        report['python_version'] = sys.version
        report['rogue_native'] = dict(path=rogue.__file__, sha256=hashlib.sha256(Path(rogue.__file__).read_bytes()).hexdigest())
        report['pyrogue_source'] = str(Path(pyrogue.__file__).resolve())
        client = pyrogue.interfaces.VirtualClient(addr=args.host, port=args.port)
        sess = ops.Session(client.root.Group, output=SimpleNamespace(sessiondir=str(directory)))
        report['boards'] = {}
        for name, board in sess.boards().items():
            av = board.WarmTdmCore.WarmTdmCommon2.AxiVersion
            report['boards'][name] = dict(build_stamp=av.BuildStamp.get(), git_hash=av.GitHash.get())
        stopped_session(sess)
        check(sess, args, report, directory)
        require(bool(report['checks']), 'No checks executed')
        report['result'] = 'PASS'
    except BaseException as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        print(report['error'], file=sys.stderr, flush=True)
    finally:
        if client is not None:
            try:
                client.stop()
            except BaseException as exc:
                report['result'] = 'FAIL'
                report['client_close_error'] = str(exc)
        report['wall_seconds'] = time.monotonic() - started
        (directory / 'result.json').write_text(json.dumps(report, indent=2, default=json_value)+'\n')
        print(f"{report['result']}: {directory / 'result.json'}", flush=True)
    return 0 if report['result'] == 'PASS' else 1
