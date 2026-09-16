#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Bring up (and monitor) a closed-loop muxed SQ1-FB PID lock in the GroupTb cosim.

Encapsulates the exact process we use to chase a lock so it is repeatable across
sessions. Run against a live ``warmTdmServer --sim`` (see
docs/plans/pid-cosim-verification/PROGRESS.md for the sim recipe). Read-only apart
from the tune-point / servo registers it deliberately sets; it always ``EndRun``s.

The process, in order (each step matters -- see PROGRESS.md "night" section):
  1. Seed the operating point at MID-SLOPE. The SQ1 flux-lock must sit on the
     steep, roughly-linear zero-crossing of the sinusoid V-Phi (~7 uA = ~Phi0/4 of
     the 10 uA SQ1 period), NOT near the extremum (~0.85 Phi0). Off mid-slope the
     loop will not lock at any gain.
  2. Set FluxQuantum = Phi0 (the SQ1 flux period). The RTL flux-jump wrap
     (AdcDsp.vhd) needs it; it defaults to 0 (disabled) -- setup must set it.
  3. sa_offset() -- null SaOutAdc (WaveformCapture.AdcAverage) just before the
     run. This zeroes the raw ADC stream the AdcAccumulator sums; there is no
     per-row baseline written (AdcBaselines stays 0 by design). NOTE the Session
     method is ``sa_offset``; ``saOffset`` silently no-ops.
  4. setup_mux() -- fewer samples/row (sample_num~20) shrinks the per-visit error
     and keeps the integrator from railing.
  5. set_pid() -- P is the STABLE knob here: the RTL adds pidResult to sq1Fb every
     visit (sq1Fb += P*error), so "P" is a single integrator that nulls the error.
     I-only is a DOUBLE integrator (sumAccum += error AND sq1Fb += I*sumAccum) and
     oscillates at any gain/sign -- do not lock with I alone. On the descending
     slope the stable P sign is POSITIVE.
  6. run_mux(), then poll per-row AccumError.

Known state (2026-09-15): at mid-slope, FluxQuantum=Phi0, sample_num=20, P=+0.05,
most rows lock to ~+/-1000 counts (~ADC quant floor); a few high rows (5-7) still
swing (row 6 is an outlier even with PID off) -- under investigation.
"""
import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=9099)
    p.add_argument('--col', type=int, default=0, help='global column index to servo')
    p.add_argument('--rows', type=int, default=8, help='rows to monitor')
    p.add_argument('--p', type=float, default=0.05, help='normalized P gain (stable knob)')
    p.add_argument('--i', type=float, default=0.0, help='normalized I gain (double integrator; leave 0)')
    p.add_argument('--d', type=float, default=0.0, help='normalized D gain')
    p.add_argument('--sample-num', type=int, default=20, help='samples per row window')
    p.add_argument('--num-pts', type=int, default=400, help='RowPeriodCycles')
    p.add_argument('--sq1fb', type=float, default=7.0,
                   help='mid-slope SQ1 FB operating point [uA] (~Phi0/4)')
    p.add_argument('--flux-quantum', type=float, default=10.0,
                   help='FluxQuantum = SQ1 flux period Phi0 [uA]')
    p.add_argument('--secs', type=float, default=6.0, help='monitor duration')
    p.add_argument('--seed-tune', action='store_true',
                   help='also (re)seed Sq1FbCurrent to --sq1fb for every monitored row')
    return p


def mae(dsp, rows):
    return int(np.mean(np.abs(np.asarray(dsp.AccumError.get())[:rows])))


def main(argv=None):
    args = build_parser().parse_args(argv)
    sys.path.insert(0, str(ROOT / 'software/scripts'))
    import _setupLibPaths  # noqa: F401
    import pyrogue.interfaces
    import warm_tdm_api.operations as ops

    client = pyrogue.interfaces.VirtualClient(addr=args.host, port=args.port)
    sess = ops.Session(client.root.Group,
                       output=SimpleNamespace(sessiondir='/tmp/cosim_pid_lock'))
    cb = sess.coordinator_cb
    tx = cb.WarmTdmCore.Timing.TimingTx
    dsp = cb.DataPath.AdcDsp[args.col]
    try:
        if bool(tx.Running.get()):
            tx.EndRun()
            time.sleep(0.4)

        # 1) mid-slope operating point
        if args.seed_tune:
            for r in range(args.rows):
                sess.group.Sq1FbCurrent.set(index=(args.col, r), value=args.sq1fb)
            print(f"Seeded Sq1FbCurrent = {args.sq1fb} uA on col {args.col} rows 0..{args.rows-1}")

        # 2) FluxQuantum = Phi0 (setup responsibility -- RTL default is 0/disabled)
        dsp.FluxQuantum.set(args.flux_quantum)
        print(f"FluxQuantum = {float(dsp.FluxQuantum.get()):.3f} uA")

        # 3) null the SA just before the run
        sess.sa_offset()
        print(f"SaOutAdc after null = {float(np.asarray(sess.group.SaOutAdc.get())[args.col]):+.4f} V")

        # 4) mux config, 5) gains, 6) run
        sess.setup_mux(num_pts=args.num_pts, sample_num=args.sample_num,
                       enable_pid=True, enable_pid_debug=True)
        sess.set_pid(p=args.p, i=args.i, d=args.d, cols=[args.col])
        print(f"SampleCount = {int(tx.SampleCount.get())}  "
              f"gains P={args.p} I={args.i} D={args.d}")
        sess.run_mux()

        traj = []
        for _ in range(int(args.secs)):
            time.sleep(1.0)
            traj.append(mae(dsp, args.rows))
        final = [int(x) for x in np.asarray(dsp.AccumError.get())[:args.rows]]
        print(f"mean|AccumError| per second: {traj}")
        print(f"final per-row AccumError:    {final}")
        print(f"FluxJumps: {[int(x) for x in np.asarray(dsp.FluxJumps.get())[:args.rows]]}")
    finally:
        try:
            if bool(tx.Running.get()):
                tx.EndRun()
        finally:
            client.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
