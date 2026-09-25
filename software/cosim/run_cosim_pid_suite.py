#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Turnkey PID cosim suite: build + run verify_cosim_pid.py for BOTH controllers.

The integer (AdcDsp) and float (AdcDspFp) datapaths are selected by a compile-time
generic and share the GroupTb build dir + TCP ports, so they cannot run at once.
This driver does, sequentially for each requested path:

    rm -rf firmware/build/GroupTb
    USE_FLOAT_PID=<0|1> VARIATION_SEED=0 make vcs        (Vivado 2025.1 export)
    source setup_env.sh && ./sim_vcs_mx.sh               (VCS compile -> simv)
    ./simv -licqueue                                     (free-run, TCP bridges)
    warmTdmServer.py --sim [--floatPid] ...              (Rogue server on :9099)
    <readiness gate: bridge ports + a real SRP read>
    verify_cosim_pid.py --path <path> ...                (the harness, subprocess)
    <teardown: kill server, then simv>

then aggregates a combined suite_result.json. Verify mode = AND of both paths.

Env overrides: WTJ_VIVADO_ENV, WTJ_VCS_ENV, WTJ_CONDA_SH, WTJ_CONDA_ENV.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUPTB = ROOT / 'firmware/simulations/GroupTb'
BEHAV = ROOT / 'firmware/build/GroupTb/GroupTb_project.sim/sim_1/behav'
HARNESS = ROOT / 'software/cosim/verify_cosim_pid.py'

VIVADO_ENV = os.environ.get('WTJ_VIVADO_ENV',
                            '/sdf/group/faders/tools/xilinx/2025.1/Vivado/2025.1/settings64.sh')
VCS_ENV = os.environ.get('WTJ_VCS_ENV',
                         '/sdf/group/faders/tools/synopsys/vcs/X-2025.06/settings.sh')
CONDA_SH = os.environ.get('WTJ_CONDA_SH',
                          str(Path.home() / 'group/miniforge3/etc/profile.d/conda.sh'))
CONDA_ENV = os.environ.get('WTJ_CONDA_ENV', 'warm-tdm-r615')

BRIDGE_PORTS = [10000, 11000, 20000, 21000]
ROGUE_PORT = 9099


def _bash(script):
    """A login-ish bash -c wrapper in its own session (so we can kill the group)."""
    return subprocess.Popen(['bash', '-c', script], cwd=str(ROOT),
                            start_new_session=True)


def _bash_wait(script, log_path, timeout):
    """Run a bash script to completion, teeing to log_path. Returns exit code."""
    with open(log_path, 'wb') as log:
        proc = subprocess.Popen(['bash', '-c', script], cwd=str(ROOT),
                                stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill(proc)
            return 124


def _kill(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def _port_open(port, host='localhost'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def _wait_ports(ports, timeout, want_open=True):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if all(_port_open(p) == want_open for p in ports):
            return True
        time.sleep(1.0)
    return False


def _preflight():
    busy = [p for p in BRIDGE_PORTS + [ROGUE_PORT] if _port_open(p)]
    if busy:
        raise SystemExit(f'Refusing to start: ports already bound {busy}. '
                         'Tear down any running cosim first (int/float cannot coexist).')


def make_manifest(path_kind, out):
    def git(*a):
        return subprocess.check_output(['git', '-C', str(ROOT), *a], text=True).strip()
    manifest = dict(
        firmware_commit=git('rev-parse', 'HEAD'),
        server_software_commit=git('rev-parse', 'HEAD'),
        surf_commit=git('rev-parse', 'HEAD:firmware/submodules/surf'),
        ruckus_commit=git('rev-parse', 'HEAD:firmware/submodules/ruckus'),
        fixture=f'GroupTb WAFER, 1 col + 1 row board, 32 rows, VARIATION_SEED=0, '
                f'USE_FLOAT_PID={"1" if path_kind == "float" else "0"} ({path_kind} AdcDsp)',
        toolchain='Vivado 2025.1; VCS X-2025.06')
    out.write_text(json.dumps(manifest, indent=2))
    return out


def build(path_kind, logdir, timeout):
    use_float = '1' if path_kind == 'float' else '0'
    env = f'source {VIVADO_ENV} && source {VCS_ENV}'
    rc = _bash_wait(
        f'{env} && rm -rf {ROOT}/firmware/build/GroupTb && cd {GROUPTB} && '
        f'USE_FLOAT_PID={use_float} VARIATION_SEED=0 make vcs',
        logdir / f'{path_kind}_make_vcs.log', timeout)
    if rc != 0:
        return rc
    return _bash_wait(
        f'{env} && cd {BEHAV} && source setup_env.sh && ./sim_vcs_mx.sh',
        logdir / f'{path_kind}_sim_vcs_mx.log', timeout)


def launch_simv(logdir, path_kind):
    log = open(logdir / f'{path_kind}_simv.log', 'wb')
    return subprocess.Popen(
        ['bash', '-c', f'source {VIVADO_ENV} && source {VCS_ENV} && cd {BEHAV} && '
                       f'source setup_env.sh && exec ./simv -licqueue'],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def launch_server(logdir, path_kind):
    float_flag = '--floatPid ' if path_kind == 'float' else ''
    log = open(logdir / f'{path_kind}_server.log', 'wb')
    return subprocess.Popen(
        ['bash', '-c', f'source {CONDA_SH} && conda activate {CONDA_ENV} && '
                       f'cd {ROOT}/software/scripts && exec python warmTdmServer.py --sim '
                       f'{float_flag}--columnBoards 1 --rowBoards 1 --rowAddrBits 5 --maxRows 32'],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


_SRP_PROBE = """\
import sys
sys.path.insert(0, 'software/scripts')
import _setupLibPaths  # noqa: F401
import pyrogue.interfaces
c = pyrogue.interfaces.VirtualClient(addr='localhost', port=9099)
try:
    cb = c.root.Group.HardwareGroup.ColumnBoard[0]
    # A real SRP read through the simv bridge confirms alignment, not just a
    # server socket. SampleCount is a cheap always-present coordinator register.
    v = cb.WarmTdmCore.Timing.TimingTx.SampleCount.get()
    print('SRP_OK', v)
finally:
    c.stop()
"""


def srp_ready(logdir, path_kind, timeout):
    """Poll a real SRP read until the Rogue<->simv bridge is aligned (simv can take
    ~90 s to boot after the server socket opens), or give up after timeout."""
    probe_py = logdir / 'srp_probe.py'
    probe_py.write_text(_SRP_PROBE)
    end = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < end:
        attempt += 1
        rc = _bash_wait(
            f'source {CONDA_SH} && conda activate {CONDA_ENV} && cd {ROOT} && '
            f'python {probe_py}',
            logdir / f'{path_kind}_srp_probe.log', min(120, timeout))
        if rc == 0:
            return True
        time.sleep(5)
    return False


def run_harness(path_kind, manifest, outdir, logdir, args):
    cmd = (f'source {CONDA_SH} && conda activate {CONDA_ENV} && cd {ROOT} && '
           f'python {HARNESS} --path {path_kind} --mode {args.mode} '
           f'--behaviors {args.behaviors} --rows {args.rows} --col {args.col} '
           f'--acq {args.acq} --settle {args.settle} --prime {args.prime} '
           f'--manifest {manifest} --output {outdir}')
    if args.profile:
        cmd += f' --profile {args.profile}'
    if args.seed_tune_points:
        cmd += ' --seed-tune-points'
    return _bash_wait(cmd, logdir / f'{path_kind}_harness.log', args.harness_timeout)


def latest_result(outdir):
    results = sorted(Path(outdir).glob('cosim-*/result.json'),
                     key=lambda p: p.stat().st_mtime)
    if not results:
        return None
    return json.loads(results[-1].read_text())


def run_one(path_kind, args):
    outdir = Path(args.output).expanduser().resolve() / path_kind
    outdir.mkdir(parents=True, exist_ok=True)
    logdir = outdir / 'suite_logs'
    logdir.mkdir(exist_ok=True)
    entry = dict(path=path_kind, build='skipped', readiness='n/a', harness_rc=None,
                 result='FAIL')
    simv = server = None
    try:
        _preflight()
        if args.build:
            rc = build(path_kind, logdir, args.build_timeout)
            entry['build'] = 'ok' if rc == 0 else f'failed(rc={rc})'
            if rc != 0:
                return entry
        simv = launch_simv(logdir, path_kind)
        if not _wait_ports(BRIDGE_PORTS, args.readiness_timeout):
            entry['readiness'] = 'bridge_ports_timeout'
            return entry
        server = launch_server(logdir, path_kind)
        if not _wait_ports([ROGUE_PORT], args.readiness_timeout):
            entry['readiness'] = 'rogue_port_timeout'
            return entry
        if not srp_ready(logdir, path_kind, args.readiness_timeout):
            entry['readiness'] = 'srp_probe_failed'
            return entry
        entry['readiness'] = 'ok'
        manifest = make_manifest(path_kind, outdir / 'manifest.json')
        entry['harness_rc'] = run_harness(path_kind, manifest, outdir, logdir, args)
        report = latest_result(outdir)
        entry['result_json'] = str(outdir)
        if report is not None:
            entry['result'] = report.get('result', 'FAIL')
            entry['checks'] = [dict(name=c['name'],
                                    threshold_met=c.get('threshold_met'),
                                    mean_residual=c.get('mean_residual'),
                                    peak_abs_error=c.get('peak_abs_error'),
                                    max_flux_jump=c.get('max_flux_jump'))
                               for c in report.get('checks', [])]
        return entry
    finally:
        if not args.keep_up:
            _kill(server)
            time.sleep(2)
            _kill(simv)
        else:
            entry['left_running'] = True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--paths', default='integer,float',
                   help='comma list: integer,float (order = run order)')
    p.add_argument('--mode', choices=['verify', 'measure'], default='verify')
    p.add_argument('--behaviors', default='steady,step')
    p.add_argument('--rows', type=int, default=8)
    p.add_argument('--col', type=int, default=0)
    p.add_argument('--acq', type=float, default=20.0)
    p.add_argument('--settle', type=float, default=5.0)
    p.add_argument('--prime', type=float, default=5.0)
    p.add_argument('--profile', type=Path,
                   default=ROOT / 'software/cosim/cosim_pid.example.json')
    p.add_argument('--seed-tune-points', action='store_true', default=True,
                   help='seed the fixture on each fresh sim (default on)')
    p.add_argument('--no-seed-tune-points', dest='seed_tune_points', action='store_false')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--build', dest='build', action='store_true', default=True)
    p.add_argument('--no-build', dest='build', action='store_false',
                   help='reuse a sim already up (single path only)')
    p.add_argument('--keep-up', action='store_true', help='leave the last sim running')
    p.add_argument('--build-timeout', type=float, default=1800.0)
    p.add_argument('--readiness-timeout', type=float, default=600.0)
    p.add_argument('--harness-timeout', type=float, default=1800.0)
    args = p.parse_args(argv)

    paths = [x.strip() for x in args.paths.split(',') if x.strip()]
    outroot = Path(args.output).expanduser().resolve()
    outroot.mkdir(parents=True, exist_ok=True)
    suite = dict(result='PASS', mode=args.mode, behaviors=args.behaviors,
                 started_utc=datetime.now(timezone.utc).isoformat(), paths={})
    started = time.monotonic()
    for path_kind in paths:
        print(f'\n===== {path_kind} PID cosim =====', flush=True)
        entry = run_one(path_kind, args)
        suite['paths'][path_kind] = entry
        print(f'{path_kind}: build={entry["build"]} readiness={entry["readiness"]} '
              f'result={entry["result"]}', flush=True)
        if args.mode == 'verify' and entry['result'] != 'PASS':
            suite['result'] = 'FAIL'
    suite['wall_seconds'] = time.monotonic() - started
    (outroot / 'suite_result.json').write_text(json.dumps(suite, indent=2, default=str) + '\n')
    print(f'\nSUITE {suite["result"]}: {outroot / "suite_result.json"}', flush=True)
    return 0 if suite['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
