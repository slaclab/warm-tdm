#!/usr/bin/env python3
##############################################################################
## This file is part of 'warm-tdm'.
## It is subject to the license terms in the LICENSE.txt file found in the
## top-level directory of this distribution and at:
##    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part of 'warm-tdm', including this file,
## may be copied, modified, propagated, or distributed except according to
## the terms contained in the LICENSE.txt file.
##############################################################################
"""Hardware test for Issue #86 (FastDacDriver override-write race) — confirm the
committed ``stop_and_zero`` reorder actually zeros the fast DACs after a run.

Acceptance and results: https://github.com/slaclab/warm-tdm/issues/86

Software-observable half of the procedure: for N cycles, drive the column
force/bias DACs to a verified nonzero value at idle and during a PID-disabled
muxed run using nonzero per-row currents, call
``stop_and_zero``, and confirm the fast-DAC readbacks (``DacCurrentNow`` on the
SQ1Fb / SAFb / SQ1Bias drivers) return to ~0. A dropped override write shows up
as a channel that holds its previous value.

    python verify_stop_and_zero.py --host localhost --port 9099 --cycles 5

If a run shows ``readback moved: False`` (the force never lands), rerun with
``--diagnose`` to tell apart the two causes: the FastDacDriver override one-shot
race (force dropped during a run) vs. the PID servo driving the force away. It
sweeps idle/PID-off (A), running/PID-off (B), running/PID-on (C), then
stop_and_zero (D), and prints the conclusion. Use ``--skip-cols`` to leave known-
bad columns out (default: none):

    python verify_stop_and_zero.py --diagnose --skip-cols 3

NOTE: this checks the register READBACK only. The definitive analog confirmation
(a load board + DMM reading differential zero) stays a manual step on Issue #86.
Per-row current settings are restored afterward; timing is left stopped and PID
disabled. The normal test requires one column board and one row board. Run on real hardware: emulate does not clock the DAC FSM against live
timing, so it cannot exercise the race this test exists to catch.
"""
import argparse
import logging
import math

import numpy as np
import sys
import time

from _hwtest_common import add_conn_args, connect, Checklist, finish

log = logging.getLogger(__name__)

# The three fast-DAC drivers on each column board and their live readback var.
_DRIVERS = ['SQ1Fb', 'SAFb', 'SQ1Bias']


def _force_setters(sess):
    """Group-level force-current variables, one per driver kind."""
    return {
        'SQ1Fb':   sess.group.Sq1FbForceCurrent,
        'SAFb':    sess.group.SaFbForceCurrent,
        'SQ1Bias': sess.group.Sq1BiasForceCurrent,
    }


def _read_array(sess, field):
    """Complete finite readbacks, or an exception that prevents a PASS."""
    if not sess.cbs or sess.chans_per_board <= 0:
        raise RuntimeError("No expected fast-DAC channels")
    out = {}
    for idx, cb in sorted(sess.cbs.items()):
        for drv in _DRIVERS:
            dev = getattr(cb, drv)
            vals = []
            for ch in range(sess.chans_per_board):
                value = float(getattr(dev, field)[ch].get())
                if not math.isfinite(value):
                    raise ValueError(f"Non-finite {field}: board {idx}, {drv}, channel {ch}")
                vals.append(value)
            out[(idx, drv)] = vals
    return out


def _read_now(sess):
    """Read every current through its LinkVariable getter."""
    return _read_array(sess, 'DacCurrentNow')


def _moved_channels(readings, tol, skip_cols):
    """(board, driver, ch) whose |current| exceeds tol, skip_cols excluded."""
    return [(b, drv, ch)
            for (b, drv), vals in readings.items()
            for ch, v in enumerate(vals)
            if ch not in skip_cols and abs(v) > tol]


def _set_force(setters, ncol, val, skip_cols):
    """Set every force-current driver to val on all columns except skip_cols."""
    vec = [0.0 if c in skip_cols else float(val) for c in range(ncol)]
    for var in setters.values():
        var.set(vec)


def _set_pid(cb, ncol, on):
    """Enable/disable SQ1 PID on every column of a board."""
    for c in range(ncol):
        cb.DataPath.AdcDsp[c].PidEnable.set(bool(on))


def _read_cmd(sess):
    return _read_array(sess, 'OverrideCurrent')


def _cmd_landed(cmd, tol, skip_cols):
    """True if any (non-skipped) commanded override exceeds tol."""
    return bool(_moved_channels(cmd, tol, skip_cols))


def diagnose(sess, args):
    """Explain 'force never lands': override register vs. DAC output, per state.

    ``ForceCurrent`` writes the *override* path (OverrideCurrent -> OverrideRaw).
    In the RTL an override only reaches the DAC when its one-cycle overrideWrValid
    pulse coincides with the driver FSM sitting in IDLE_S -- and the FSM leaves
    IDLE on every row strobe. So we test:
      A  TRUE idle (Mode=0, stopped), PID off -> does the override apply at rest?
      B  running (free-run MUX), PID off      -> is it dropped by the run (race)?
      C  running, PID on                      -> what the PASS/FAIL test does.
      D  stop_and_zero                        -> does the fix return output to ~0?
    Each block prints commanded->actual so a write that lands in the register but
    not on the DAC is obvious.
    """
    chk = Checklist('Issue #86 force-write race diagnosis')
    setters = _force_setters(sess)
    ncol = len(sess.group.ColTuneEnable.get())
    skip = {int(c) for c in args.skip_cols.split(',') if c.strip() != ''}
    cb = sess.coordinator_cb
    tx = cb.WarmTdmCore.Timing.TimingTx
    tol, f = args.tol_uA, args.force_uA
    orig_mode = tx.Mode.get()

    if skip:
        print(f'Skipping columns {sorted(skip)} (left at 0 / ignored).')

    def report(label):
        actual = _read_now(sess)
        cmd = _read_cmd(sess)
        for key in sorted(actual):
            _, drv = key
            av = actual[key]
            cv = cmd.get(key, [0.0] * len(av))
            cells = ['--' if ch in skip else f'{cv[ch]:.0f}->{av[ch]:.1f}'
                     for ch in range(len(av))]
            print(f'    {drv:8s} cmd->now: {cells}')
        moved = _moved_channels(actual, tol, skip)
        print(f'  [{label}] channels whose DAC OUTPUT moved (>{tol} uA): {len(moved)}')
        return moved, cmd

    print('\n[A] TRUE idle (Mode=0, run stopped), PID off  -> does the override apply at rest?')
    _set_pid(cb, ncol, False)
    tx.Mode.set(0)                       # software-stepped: FSM can rest in IDLE
    if tx.Running.get():
        tx.EndRun()
    time.sleep(args.settle_sec)
    _set_force(setters, ncol, f, skip)
    time.sleep(args.settle_sec)
    a_moved, a_cmd = report('A')
    _set_force(setters, ncol, 0.0, skip)

    print('\n[B] running (free-run MUX), PID off  -> dropped by the run (one-shot race)?')
    sess.setup_mux(num_pts=args.num_pts, enable_pid=False)
    tx.StartRun()
    _set_force(setters, ncol, f, skip)
    time.sleep(args.settle_sec)
    b_moved, _ = report('B')

    print('\n[C] running, PID on  -> what the PASS/FAIL test does')
    sess.setup_mux(num_pts=args.num_pts, enable_pid=True)
    _set_force(setters, ncol, f, skip)
    time.sleep(args.settle_sec)
    c_moved, _ = report('C')

    print('\n[D] stop_and_zero  -> back to ~0?')
    sess.stop_and_zero()
    d_moved, _ = report('D')

    # Leave the rig quiet: PID off, forces 0, run stopped, original mode restored.
    _set_pid(cb, ncol, False)
    _set_force(setters, ncol, 0.0, skip)
    if tx.Running.get():
        tx.EndRun()
    tx.Mode.set(orig_mode)

    print('\nConclusion:')
    if a_moved:
        chk.item(True, 'Override reaches the DAC output at true idle (A)',
                 f'{len(a_moved)} channels moved')
        if not b_moved:
            chk.note('DIAGNOSIS: override one-shot RACE — the override applies at true idle '
                     '(A) but is DROPPED once timing free-runs (B): overrideWrValid misses '
                     'the FSM IDLE window. Matches docs/design/fastdac-override-race.md.')
        elif b_moved and not c_moved:
            chk.note('DIAGNOSIS: PID servo masks it — override lands during a run (B) but PID '
                     'drives the output away (C). The "readback moved: False" was PID.')
        else:
            chk.note(f'INCONCLUSIVE: output moved A={len(a_moved)} B={len(b_moved)} '
                     f'C={len(c_moved)} — inspect cmd->now above.')
    elif _cmd_landed(a_cmd, tol, skip):
        chk.item(False, 'Override reaches the DAC output at true idle (A)',
                 'the OverrideCurrent register holds the commanded value but DacCurrentNow '
                 'stayed 0 even with timing stopped — the write never reaches the DAC. '
                 'Points at the override apply path (overrideWrValid one-shot), not PID. '
                 'See docs/design/fastdac-override-race.md.')
    else:
        chk.item(False, 'Override register accepts the commanded current (A)',
                 'commanded OverrideCurrent did not read back — a set/units/path issue '
                 'upstream of the DAC, before the override race even applies.')
    chk.item(not d_moved, 'stop_and_zero returned all fast DACs to ~0 (D)',
             'all ~0' if not d_moved else f'{len(d_moved)} residual channels')
    chk.note('MANUAL: confirm differential zero on the load board with a DMM.')
    return finish(chk.report())


def _wait_running(tx, expected, timeout=2.0):
    deadline = time.monotonic() + timeout
    while bool(tx.Running.get()) != expected:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timing Running did not become {expected}")
        time.sleep(0.01)


def _require_nonzero(readings, tol):
    bad = [(board, driver, ch) for (board, driver), values in readings.items()
           for ch, value in enumerate(values) if abs(value) <= tol]
    if not readings or bad:
        raise RuntimeError(f"Nonzero baseline not established on every output: {bad}")


def run_cycles(sess, args):
    """Test nonzero idle -> nonzero mux -> stop/zero; restore per-row settings.

    Uses one column + one row board, matching the supported setup_mux path.
    PID is disabled so its servo cannot erase the nonzero test stimulus.
    """
    timing_timeout = getattr(args, 'timing_timeout', 2.0)
    if not math.isfinite(timing_timeout) or timing_timeout <= 0:
        raise ValueError('timing-timeout must be finite and positive')
    if args.cycles < 1:
        raise ValueError("cycles must be positive")
    if not math.isfinite(args.tol_uA) or args.tol_uA < 0:
        raise ValueError("tol-uA must be finite and nonnegative")
    if not math.isfinite(args.force_uA) or abs(args.force_uA) <= args.tol_uA:
        raise ValueError("force-uA must be finite and exceed the zero tolerance")
    if not math.isfinite(args.settle_sec) or args.settle_sec < 0:
        raise ValueError("settle-sec must be finite and nonnegative")
    if args.num_pts <= 350:
        raise ValueError("num-pts must exceed the 350-cycle setup sample window")
    if len(sess.cbs) != 1 or len(sess.rbs) != 1:
        raise ValueError("This test requires one column board and one row board")
    if args.skip_cols:
        raise ValueError("skip-cols applies only to --diagnose; acceptance tests every output")

    tx = sess.coordinator_cb.WarmTdmCore.Timing.TimingTx
    _read_now(sess)  # Fail on absent/incomplete/non-finite readbacks before writing.
    names = ['Sq1FbCurrent', 'SaFbCurrent', 'Sq1BiasCurrent']
    saved = {name: np.asarray(getattr(sess.group, name).get()).copy() for name in names}
    ncol = len(sess.group.ColTuneEnable.get())
    for name, values in saved.items():
        if values.ndim != 2 or values.shape[0] != ncol or values.shape[1] == 0:
            raise ValueError(f"Unexpected per-row current shape for {name}: {values.shape}")
        if not np.all(np.isfinite(values)):
            raise ValueError(f"Non-finite original per-row currents: {name}")
    failed = False
    try:
        for cyc in range(1, args.cycles + 1):
            if not sess.stop_and_zero(settle_sec=timing_timeout):
                raise RuntimeError("Could not establish the initial stopped/zero state")
            sess.setup_mux(num_pts=args.num_pts, enable_pid=False)
            # Disable every PID explicitly, including tune-disabled columns.
            _set_pid(sess.coordinator_cb, sess.chans_per_board, False)
            for name, values in saved.items():
                getattr(sess.group, name).set(np.full(values.shape, args.force_uA))
            for kind in ['Sq1Fb', 'SaFb', 'Sq1Bias']:
                ok, residual = sess.set_force(kind, args.force_uA,
                    tol_uA=args.tol_uA, settle_sec=args.settle_sec)
                if not ok:
                    raise RuntimeError(f"{kind} nonzero force did not verify: {residual}")
            _require_nonzero(_read_now(sess), args.tol_uA)
            tx.StartRun()
            _wait_running(tx, True, timeout=timing_timeout)
            time.sleep(args.settle_sec)
            _require_nonzero(_read_now(sess), args.tol_uA)
            if not sess.stop_and_zero(settle_sec=timing_timeout):
                raise RuntimeError("stop_and_zero reported incomplete cleanup")
            _wait_running(tx, False, timeout=timing_timeout)
            readings = _read_now(sess)
            residual = _moved_channels(readings, args.tol_uA, set())
            if residual:
                raise RuntimeError(f"Nonzero outputs after stop/zero: {residual}")
            print(f'  cycle {cyc}: complete nonzero -> running -> zero readback PASS')
    except BaseException:
        failed = True
        raise
    finally:
        errors = []
        try:
            if not sess.stop_and_zero(settle_sec=timing_timeout):
                raise RuntimeError("Final stop/zero cleanup did not verify")
        except BaseException as exc:
            errors.append(exc)
            log.exception("Final stop/zero cleanup failed")
        for name, values in saved.items():
            try:
                getattr(sess.group, name).set(values)
            except BaseException as exc:
                errors.append(exc)
                log.exception("Failed restoring per-row settings for %s", name)
        if errors and not failed:
            raise errors[0]
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    add_conn_args(p)
    p.add_argument('--cycles', type=int, default=5,
                   help='number of set-nonzero -> run -> stop_and_zero cycles '
                        '(default: 5)')
    p.add_argument('--force-uA', type=float, default=50.0,
                   help='nonzero force current to set before each stop (default: 50)')
    p.add_argument('--tol-uA', type=float, default=0.5,
                   help='|current| below this reads as zero (default: 0.5)')
    p.add_argument('--num-pts', type=int, default=512, help='setup_mux num_pts')
    p.add_argument('--diagnose', action='store_true',
                   help='run the A/B/C/D matrix to tell the override race apart '
                        'from the PID servo (instead of the pass/fail cycles)')
    p.add_argument('--skip-cols', type=str, default='',
                   help="comma-separated columns to leave at 0 / ignore, e.g. '3'")
    p.add_argument('--settle-sec', type=float, default=0.5,
                   help='pause after setting force before readback (default: 0.5)')
    p.add_argument('--timing-timeout', type=float, default=2.0,
                   help='wall seconds for run/stop transitions; increase for VCS')
    args = p.parse_args()

    sess = connect(args)
    chk = Checklist('Issue #86 stop_and_zero fast-DAC zeroing')
    try:
        if args.diagnose:
            if len(sess.cbs) != 1 or len(sess.rbs) != 1:
                raise ValueError("Diagnosis requires one column board and one row board")
            # finish() hard-exits, so diagnosis must clean up before returning.
            return diagnose(sess, args)
        run_cycles(sess, args)
    except (Exception, KeyboardInterrupt) as exc:
        if args.diagnose:
            try:
                sess.stop_and_zero()
            except Exception:
                log.exception("Diagnostic cleanup failed")
        chk.item(False, 'Complete nonzero -> running -> stopped/zero sequence', str(exc))
    else:
        chk.item(True, f'Complete sequence across {args.cycles} cycles')
    chk.note('MANUAL: confirm physical outputs with a load-board DMM/scope; '
             'record evidence on Issue #86.')
    return finish(chk.report())


if __name__ == '__main__':
    sys.exit(main())
