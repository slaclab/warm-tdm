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

Wiki: HW-Verify-Issue-86-FastDac-Override-Race

Software-observable half of the procedure: for N cycles, drive the column
force/bias DACs to a clearly nonzero value during a live muxed run, call
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
(a load board + DMM reading differential zero) stays a manual step on the wiki
page — a readback of 0 is necessary but the load-board measurement is what closes
Issue #32. Run on real hardware: emulate does not clock the DAC FSM against live
timing, so it cannot exercise the race this test exists to catch.
"""
import argparse
import sys
import time

from _hwtest_common import add_conn_args, connect, Checklist, finish

# The three fast-DAC drivers on each column board and their live readback var.
_DRIVERS = ['SQ1Fb', 'SAFb', 'SQ1Bias']


def _force_setters(sess):
    """Group-level force-current variables, one per driver kind."""
    return {
        'SQ1Fb':   sess.group.Sq1FbForceCurrent,
        'SAFb':    sess.group.SaFbForceCurrent,
        'SQ1Bias': sess.group.Sq1BiasForceCurrent,
    }


def _read_now(sess, nchan=8):
    """Read DacCurrentNow (uA) for every driver on every column board.

    ``DacCurrentNow`` is an indexed array of LinkVariables
    (``DacCurrentNow[0..7]``), not a single vectored variable, so read each
    channel node individually.

    Returns {(board_idx, driver): [per-channel currents]}.
    """
    out = {}
    for idx, cb in sorted(sess.cbs.items()):
        for drv in _DRIVERS:
            dev = getattr(cb, drv, None)
            if dev is None or not hasattr(dev, 'DacCurrentNow'):
                continue
            arr = dev.DacCurrentNow
            vals = []
            for ch in range(nchan):
                try:
                    vals.append(float(arr[ch].get()))
                except Exception:
                    break
            if vals:
                out[(idx, drv)] = vals
    return out


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


def _read_cmd(sess, nchan=8):
    """Commanded override current (OverrideCurrent, uA) per driver/board.

    This is what ``ForceCurrent`` writes -- the OverrideRaw register, read back
    through OverrideCurrent. Comparing it to DacCurrentNow (the actual DAC
    output) shows whether the write reached the register but never the DAC.
    """
    out = {}
    for idx, cb in sorted(sess.cbs.items()):
        for drv in _DRIVERS:
            dev = getattr(cb, drv, None)
            if dev is None or not hasattr(dev, 'OverrideCurrent'):
                continue
            oc = dev.OverrideCurrent
            vals = []
            for ch in range(nchan):
                try:
                    vals.append(float(oc[ch].get()))
                except Exception:
                    break
            if vals:
                out[(idx, drv)] = vals
    return out


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
    import warm_tdm_api.operations as ops

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
    ops.setup_mux(num_pts=args.num_pts, enable_pid=False)
    tx.StartRun()
    _set_force(setters, ncol, f, skip)
    time.sleep(args.settle_sec)
    b_moved, _ = report('B')

    print('\n[C] running, PID on  -> what the PASS/FAIL test does')
    ops.setup_mux(num_pts=args.num_pts, enable_pid=True)
    _set_force(setters, ncol, f, skip)
    time.sleep(args.settle_sec)
    c_moved, _ = report('C')

    print('\n[D] stop_and_zero  -> back to ~0?')
    ops.stop_and_zero()
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
    args = p.parse_args()

    import warm_tdm_api.operations as ops

    sess = connect(args)

    if args.diagnose:
        return diagnose(sess, args)

    chk = Checklist('Issue #86 stop_and_zero fast-DAC zeroing')

    setters = _force_setters(sess)
    ncol = len(sess.group.ColTuneEnable.get())

    if not _read_now(sess):
        chk.item(False, 'Fast-DAC readback (DacCurrentNow) available', 'none found')
        return finish(chk.report())

    all_cycles_ok = True
    for cyc in range(1, args.cycles + 1):
        print(f'\n--- cycle {cyc}/{args.cycles} ---')

        # 1. Start a muxed run so the DAC FSM is actively cycling.
        ops.setup_mux(num_pts=args.num_pts, enable_pid=True)

        # 2. Drive all three force currents clearly nonzero.
        for name, var in setters.items():
            var.set([args.force_uA] * ncol)
        after_set = _read_now(sess)
        moved = any(abs(v) > args.tol_uA for vals in after_set.values() for v in vals)
        print(f'  set force = {args.force_uA} uA; readback moved: {moved}')

        # 3. The fix under test: stop MUX, wait for idle, then zero.
        ops.stop_and_zero()

        # 4. Confirm every fast-DAC channel came back to ~0.
        after_zero = _read_now(sess)
        residual = {}
        for key, vals in after_zero.items():
            bad = [i for i, v in enumerate(vals) if abs(v) > args.tol_uA]
            if bad:
                residual[key] = {i: vals[i] for i in bad}
        ok = not residual
        all_cycles_ok = all_cycles_ok and ok
        if ok:
            print(f'  cycle {cyc}: all fast-DAC channels within +/-{args.tol_uA} uA of 0')
        else:
            print(f'  cycle {cyc}: RESIDUAL nonzero channels (dropped writes?): {residual}')

    chk.item(all_cycles_ok,
             f'stop_and_zero zeroed all fast DACs across {args.cycles} cycles',
             'all within tolerance' if all_cycles_ok else 'see residuals above')
    chk.note('MANUAL: confirm differential zero on a load board with a DMM '
             '(readback==0 is necessary, not sufficient — see wiki Part 2).')

    return finish(chk.report())


if __name__ == '__main__':
    sys.exit(main())
