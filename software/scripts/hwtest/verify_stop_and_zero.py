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

NOTE: this checks the register READBACK only. The definitive analog confirmation
(a load board + DMM reading differential zero) stays a manual step on the wiki
page — a readback of 0 is necessary but the load-board measurement is what closes
Issue #32. Run on real hardware: emulate does not clock the DAC FSM against live
timing, so it cannot exercise the race this test exists to catch.
"""
import argparse
import sys

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
    args = p.parse_args()

    import warm_tdm_api.operations as ops

    sess = connect(args)
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
