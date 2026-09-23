#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Bring up (and monitor) a closed-loop muxed SQ1-FB PID lock in the GroupTb cosim.

Encapsulates the exact process we use to chase a lock so it is repeatable across
sessions. Run against a live ``warmTdmServer --sim`` (see
software/cosim/README_cosim.md for the sim recipe). Read-only apart
from the tune-point / servo registers it deliberately sets; it always ``EndRun``s.

The process, in order (each step matters -- see docs/plans/tes-scaling/ and
cosim-tuning-settings.md):
  0. --seed-tune-points: Group.SetCosimTunePoints() for a fresh sim (RowMap +
     FAS-on=163 uA + SA/SQ1 seed; runs saOffset server-side).
  1. --seed-tune: write the COHERENT per-row operating point -- Sq1Bias, Sq1Fb
     AND SaFb, not just Sq1Fb. On the 23 uA sinusoid model the mid-slope lock is
     Sq1Bias=50 uA (NOT 100 -- 100 clips the SQ1-bias DAC to ~77 and will not
     lock), Sq1Fb~2 uA (steep flank at that bias), SaFb~9 uA. The per-row SaFb
     sets the SA operating point, so all three MUST be written before the SA
     null in step 3. Do NOT ClearPids (it wipes the seeded feedback -> the servo
     drops to the ungovernable V-Phi extremum).
  2. FluxQuantum = Phi0 (23 uA). The multi-flux-wrap RTL rejects the write unless
     PID is disabled + ControlBusy clear, so PidEnable(False) first.
  3. sa_offset() AFTER the operating-point tables are applied, so the offset
     references the SA operating point the muxed readout uses.
  4. setup_mux() -- sample_num~20 keeps the per-visit error small.
  5. set_pid() -- P is the stable single-integrator knob (sq1Fb += P*error). At
     the correct Sq1Bias=50 point the stable integer sign is NEGATIVE (P=-0.05
     normalized). P-only (I=0) locks cleanly; a nonzero I can wind the 19-bit
     flux count. (The sign is opposite the earlier clipped-77 result -- the
     operating point, not just the gain, determines it.)
  6. run_mux(), poll per-row AccumError.
  7. --tes-steps>0: ramp TesBias and read the FluxJumps register at each step --
     the end-to-end flux-jump demo. A locked servo tracks the TES-induced flux
     and wraps at +/-7862; FluxJumps climbs monotonically while Sq1FbFull stays
     bounded. Verified 2026-09-18: +4 uA/step drove FluxJumps 1 -> ~104 over an
     80 uA ramp. P does NOT gate this; the applied TES flux does.

Example (fresh sim, lock 4 rows then ramp TES through many flux jumps):
  python cosim_pid_lock.py --rows 4 --seed-tune-points --seed-tune \\
      --tes-steps 20 --tes-step-uA 4
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=9099)
    p.add_argument('--col', type=int, default=0, help='global column index to servo')
    p.add_argument('--rows', type=int, default=8, help='rows to monitor')
    # NEGATIVE P is the stable integer sign at the correct Sq1Bias=50 tune point
    # (see cosim-tuning-settings.md / docs/plans/tes-scaling). P-only (I=0)
    # converges cleanly; a nonzero I can wind the 19-bit flux count.
    p.add_argument('--p', type=float, default=-0.05, help='normalized P gain (stable knob; NEGATIVE at the 23uA/Sq1Bias=50 point)')
    p.add_argument('--i', type=float, default=0.0, help='normalized I gain (double integrator; leave 0)')
    p.add_argument('--d', type=float, default=0.0, help='normalized D gain')
    p.add_argument('--sample-num', type=int, default=20, help='samples per row window')
    p.add_argument('--num-pts', type=int, default=400, help='RowPeriodCycles')
    # Coherent SQ1 operating point on the 23 uA sinusoid-blend model (mid-slope).
    p.add_argument('--sq1fb', type=float, default=2.0,
                   help='SQ1 FB mid-slope operating point [uA] at Sq1Bias=50')
    p.add_argument('--sq1bias', type=float, default=50.0,
                   help='SQ1 bias [uA] (fitted; 100 clips the DAC and will not lock)')
    p.add_argument('--safb', type=float, default=9.0,
                   help='SA FB [uA] (SA-tune null; must be applied before sa_offset)')
    p.add_argument('--flux-quantum', type=float, default=23.0,
                   help='FluxQuantum = SQ1 flux period Phi0 [uA]')
    p.add_argument('--secs', type=float, default=10.0, help='monitor duration')
    p.add_argument('--seed-tune-points', action='store_true',
                   help='run Group.SetCosimTunePoints() first (fresh-sim fixture: RowMap+FAS+SA/SQ1 seed)')
    p.add_argument('--seed-tune', action='store_true',
                   help='write the coherent per-row operating point (Sq1Bias/Sq1Fb/SaFb) before the SA null')
    # TES flux-jump ramp: after locking, walk TesBias and read the FluxJumps
    # register (ground truth) at each step. This is the end-to-end flux-jump demo.
    p.add_argument('--tes-steps', type=int, default=0,
                   help='if >0, after locking ramp TesBias this many steps and report FluxJumps')
    p.add_argument('--tes-step-uA', type=float, default=4.0,
                   help='TesBias increment per step [uA] (keep < one Phi0 so the servo tracks continuously)')
    p.add_argument('--tes-settle', type=float, default=5.0,
                   help='seconds to settle after each TesBias step')
    p.add_argument("--run-dir", type=Path, help="Existing measurement run")
    return p


def mae(dsp, rows):
    return int(np.mean(np.abs(np.asarray(dsp.AccumError.get())[:rows])))


def main(argv=None):
    args = build_parser().parse_args(argv)
    sys.path.insert(0, str(ROOT / 'software/python'))
    import warm_tdm_run as runs
    run_dir = runs.validate_run(args.run_dir) if args.run_dir else None
    sys.path.insert(0, str(ROOT / 'software/scripts'))
    import _setupLibPaths  # noqa: F401
    import pyrogue.interfaces
    import warm_tdm_api.operations as ops

    client = pyrogue.interfaces.VirtualClient(addr=args.host, port=args.port)
    tx = None
    try:
        sess = ops.Session(client.root.Group,
                           output=ops.OutputDir.existing_run(run_dir) if run_dir else None)
        if not 0 < args.rows <= int(sess.group.MaxRows.get()):
            raise ValueError('rows must fit the configured logical row count')
        if not 0 <= args.col < int(sess.group.NumColumns.get()):
            raise ValueError('col is outside this Group')
        board, channel = sess.col_to_board_chan(args.col)
        cb = sess.cbs[board]
        tx = sess.coordinator_cb.WarmTdmCore.Timing.TimingTx
        dsp = cb.DataPath.AdcDsp[channel]
        if bool(tx.Running.get()):
            tx.EndRun()
            time.sleep(0.4)

        # 0) fresh-sim fixture: RowMap + FAS-on + SA/SQ1 seed (runs saOffset).
        if run_dir:
            runs.record_connection(sess, run_dir, args.host, args.port)
        if args.seed_tune_points:
            sess.group.SetCosimTunePoints()
            print("Ran SetCosimTunePoints()")

        # Read out exactly the rows under test. A fresh sim defaults
        # RowReadoutOrder to [0], so without this only row 0 is ever visited and
        # rows 1..N-1 read as stale/zero (not servoed).
        sess.group.RowReadoutOrder.set(list(range(args.rows)))

        # 1) COHERENT per-row operating point. Write Sq1Bias AND Sq1Fb AND SaFb,
        # not just Sq1Fb -- the per-row SaFb sets the SA operating point, so all
        # three must be in the readout tables BEFORE the SA null below, or the
        # servo will not lock. (Do NOT ClearPids: that wipes the seeded feedback
        # and drops the servo to the ungovernable V-Phi extremum.)
        if args.seed_tune:
            for r in range(args.rows):
                sess.group.Sq1BiasCurrent.set(index=(args.col, r), value=args.sq1bias)
                sess.group.Sq1FbCurrent.set(index=(args.col, r), value=args.sq1fb)
                sess.group.SaFbCurrent.set(index=(args.col, r), value=args.safb)
            print(f"Seeded per-row Sq1Bias={args.sq1bias} Sq1Fb={args.sq1fb} "
                  f"SaFb={args.safb} uA on col {args.col} rows 0..{args.rows-1}")

        # 2) FluxQuantum = Phi0 (setup responsibility -- RTL default is 0/disabled).
        # The multi-flux-wrap RTL rejects a FluxQuantum change unless PID is
        # disabled and ControlBusy is clear (the reciprocal/shift/count registers
        # must be quiescent), so disable PID first.
        dsp.PidEnable.set(False)
        dsp.FluxQuantum.set(args.flux_quantum)
        print(f"FluxQuantum = {float(dsp.FluxQuantum.get()):.3f} uA")

        # 3) null the SA AFTER the operating-point tables are applied, so the
        # offset references the SA operating point the muxed readout will use.
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

        if run_dir:
            report_path = run_dir / 'data' / f'pid-lock-{time.time_ns()}.json'
            report_path.write_text(json.dumps(dict(trajectory=traj, final=final, arguments=vars(args)),
                                               indent=2, default=str) + '\n')
            print(f'Lock trajectory: {report_path}')

        # TES flux-jump ramp: walk TesBias and read the FluxJumps register
        # (ground truth) at each step. A locked servo tracks the TES-induced
        # flux and wraps at +/-7862; FluxJumps should climb monotonically while
        # Sq1FbFull stays bounded (does NOT rail). P does not gate this -- it is
        # driven by how much TES flux is applied. Keep --tes-step-uA below one
        # Phi0 so the loop tracks continuously rather than jumping fringes.
        if args.tes_steps > 0:
            fjv = np.asarray(dsp.FluxJumps.get())
            fbv = np.asarray(dsp.Sq1FbFull.get())
            base = float(np.asarray(sess.group.TesBias.get())[args.col])
            start = [int(fjv.flat[r]) for r in range(args.rows)]
            print(f"\nTES flux-jump ramp from TesBias={base:.1f} uA, "
                  f"{args.tes_steps} x {args.tes_step_uA} uA:")
            print(f"  {'dTesBias':>9} {'FluxJumps(net)':>28} {'Sq1FbFull[0]':>13}")
            try:
                for k in range(1, args.tes_steps + 1):
                    sess.group.TesBias.set(index=args.col, value=base + k * args.tes_step_uA)
                    time.sleep(args.tes_settle)
                    fjv = np.asarray(dsp.FluxJumps.get())
                    fbv = np.asarray(dsp.Sq1FbFull.get())
                    net = [int(fjv.flat[r]) - start[r] for r in range(args.rows)]
                    print(f"  {k*args.tes_step_uA:8.1f}u {str(net):>28} "
                          f"{float(fbv.flat[0]):13.1f}")
            finally:
                sess.group.TesBias.set(index=args.col, value=base)
    finally:
        try:
            if tx is not None and bool(tx.Running.get()):
                tx.EndRun()
        finally:
            client.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
