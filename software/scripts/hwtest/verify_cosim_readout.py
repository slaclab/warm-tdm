#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Check VCS readout/PID/config, exact masking and acquisition cleanup via VirtualClient."""
import _thread
from pathlib import Path
import threading

import numpy as np

from _cosim_common import parser, passed, positive, require, restore, run, wait_running


def require_samples(data, expected):
    actual = {(int(col), int(row)) for col, rows in data.items()
              for row, values in rows.items() if len(values)}
    require(actual == expected, f'Channel mismatch: missing={expected-actual}, unexpected={actual-expected}')
    for col, row in expected:
        values = np.asarray(data[col][row])
        require(values.size > 0 and np.all(np.isfinite(values)), f'Invalid samples c{col}r{row}')


def inspect_file(path, expected, pid_expected, live_fs, live_scales):
    import pyrogue.utilities.fileio
    import warm_tdm
    from warm_tdm_api.operations import StreamData
    from warm_tdm_api.operations.unit_conversions import derive_fs, derive_sq1fb_to_pA
    counts = dict(readout=0, pid=0, config=0)
    # The normal reader skips malformed PID frames; this acceptance test must not.
    with pyrogue.utilities.fileio.FileReader(files=[path]) as reader:
        for header, payload in reader.records():
            if header.channel == 9:
                require(len(payload) >= 40 and len(payload) % 8 == 0, 'Malformed readout frame')
                counts['readout'] += 1
            elif header.channel in range(8):
                require(len(payload) == warm_tdm.PID_DEBUG_FRAME_BYTES, 'Malformed PID-debug frame')
                counts['pid'] += 1
            elif header.channel == 255:
                counts['config'] += 1
    require(all(counts.values()), f'Missing frame types: {counts}')
    stream = StreamData(path)
    require_samples(stream.data, expected)
    pid_pairs = {(int(c), int(r)) for c, rows in stream.pid.items() for r, fields in rows.items()
                 if fields and all(len(v) for v in fields.values())}
    require(pid_pairs == pid_expected, f'PID channel mismatch: {pid_pairs} vs {pid_expected}')
    for c, r in pid_pairs:
        require(all(np.all(np.isfinite(v)) for v in stream.pid[c][r].values()), 'Non-finite PID fields')
    require(bool(stream.config), 'No decodable embedded configuration')
    for col in live_scales:
        fs = derive_fs(stream.config, col)
        scale = derive_sq1fb_to_pA(stream.config, col)
        require(fs is not None and np.isfinite(fs) and fs > 0, 'Missing/invalid file sample rate')
        require(scale is not None and np.isfinite(scale) and scale != 0, 'Missing/invalid file calibration')
        np.testing.assert_allclose(fs, live_fs, rtol=1e-5)
        np.testing.assert_allclose(scale, live_scales[col], rtol=1e-5)
    return counts


def check_readout(sess, args, report, directory):
    cb = sess.coordinator_cb
    tx = cb.WarmTdmCore.Timing.TimingTx
    require(2 <= args.rows <= int(sess.group.MaxRows.get()), 'rows must be 2..Group.MaxRows')
    require(args.num_pts > 350, 'num-pts must exceed sample window (350)')
    dsp = [cb.DataPath.AdcDsp[ch] for ch in range(sess.chans_per_board)]
    variables = [sess.group.ColTuneEnable, sess.group.RowIndexOrderList,
                 tx.Mode, tx.RowPeriodCycles, tx.SampleStartTime, tx.SampleEndTime]
    variables += [rdd.Mode for rdd in sess.rdds.values()]
    variables += [getattr(d, name) for d in dsp for name in
                  ['PidEnable', 'PidDebugEnable', 'RowEnableMask', 'P_Coef', 'I_Coef', 'D_Coef']]
    with restore(variables):
        try:
            sess.group.ColTuneEnable.set([True] * sess.chans_per_board)
            sess.group.RowIndexOrderList.set(list(range(args.rows)))
            sess.setup_mux(num_pts=args.num_pts, enable_pid=True, enable_pid_debug=True)
            for d in dsp:
                for name in ['P_Coef', 'I_Coef', 'D_Coef']:
                    getattr(d, name).set(0.0)
                d.ClearPids()
                d.RowEnableMask.set((1 << 256) - 1)
            expected = {(c, r) for c in range(sess.chans_per_board) for r in range(args.rows)}
            live_fs = float(tx.DaqReadoutRate.get())
            scales = {c: float(cb.AnalogFrontEnd.Channel[c].SQ1FbAmp.CurrentPerLsb.get()) * 1e6
                      for c in range(sess.chans_per_board)}

            def capture(label, channels):
                path = sess.take_data(args.acq, start_delay_sec=args.start_delay)
                wait_running(tx, False, args.timing_timeout)
                require(not sess.root.DataWriter.IsOpen.get(), 'Writer left open')
                # RowEnableMask gates readout samples; PID debug still describes every row visit.
                counts = inspect_file(path, channels, expected, live_fs, scales)
                passed(report, label, file=path, frames=counts, channels=sorted(channels))
                return path

            capture('baseline readout, PID-debug and config-derived units', expected)
            masked = {(0, 0), (1, args.rows - 1)}
            for col, row in masked:
                dsp[col].RowEnableMask.set(((1 << 256) - 1) ^ (1 << row))
                require(int(dsp[col].RowEnableMask.get()) == (((1 << 256) - 1) ^ (1 << row)),
                        'Mask register mismatch')
            capture('exact dead-mask effect', expected - masked)
            for d in dsp:
                d.RowEnableMask.set((1 << 256) - 1)
            capture('unmasked repeated acquisition', expected)

            tx.StartRun()
            wait_running(tx, True, args.timing_timeout)
            sess.take_data(args.acq, start_delay_sec=args.start_delay)
            require(bool(tx.Running.get()), 'take_data stopped a pre-existing run')
            require(not sess.root.DataWriter.IsOpen.get(), 'Writer left open on pre-existing run')
            tx.EndRun()
            wait_running(tx, False, args.timing_timeout)
            passed(report, 'acquisition preserves pre-existing run ownership')

            timer = threading.Timer(args.interrupt_after, _thread.interrupt_main)
            timer.start()
            try:
                try:
                    sess.take_data(args.acq, start_delay_sec=args.interrupt_after + args.start_delay)
                except KeyboardInterrupt:
                    pass
                else:
                    raise AssertionError('Injected interruption was not observed')
            finally:
                timer.cancel()
                timer.join()
            wait_running(tx, False, args.timing_timeout)
            require(not sess.root.DataWriter.IsOpen.get(), 'Writer left open after interruption')
            passed(report, 'startup interruption cleanup through VirtualClient')
            capture('acquisition restarts after interruption', expected)

            if args.raw:
                path = sess.take_raw(0, timeout_sec=args.raw_timeout, check_delay_sec=1.0)
                # The capture writer saves its own dict as a pickled NumPy object.
                # Load only this newly generated, trusted simulation artifact.
                raw = np.load(path, allow_pickle=True).item()
                values = np.asarray(raw[0]['ADC Counts'][0])
                require(values.size > 0 and np.issubdtype(values.dtype, np.number)
                        and np.all(np.isfinite(values)), 'Empty/non-finite raw waveform')
                passed(report, 'raw ADC capture and decode', file=path, shape=values.shape,
                       limitation='Finite modeled samples; not calibrated physical gain/noise')
            else:
                report['not_run'] = ['Raw capture (select --raw; full capture can be slow in VCS)']
        finally:
            tx.EndRun()
            wait_running(tx, False, args.timing_timeout)
    report['final_state'] = 'timing stopped; row list, timing settings, PID controls and masks restored'


def main():
    p = parser(__doc__)
    p.add_argument('--rows', type=int, default=2)
    p.add_argument('--num-pts', type=int, default=512)
    p.add_argument('--acq', type=positive, default=30.0, help='wall seconds per capture; increase for slow VCS')
    p.add_argument('--start-delay', type=positive, default=5.0)
    p.add_argument('--interrupt-after', type=positive, default=1.0)
    p.add_argument('--raw', action='store_true')
    p.add_argument('--raw-timeout', type=positive, default=600.0)
    return run(p.parse_args(), check_readout)


if __name__ == '__main__':
    raise SystemExit(main())
