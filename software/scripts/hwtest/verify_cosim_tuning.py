#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Exercise reduced SA/SQ1 tuning through VirtualClient on a configured sensor fixture.

Requires an explicit profile; a modeled operating point is not physical SQUID acceptance.
"""
import json
from pathlib import Path
import time

import numpy as np

from _cosim_common import json_value, parser, passed, positive, require, restore, run


def require_curve(curve, points, biases, minimum_span):
    x = np.asarray(curve['xValues'], dtype=float)
    y = np.asarray(curve['curves'], dtype=float)
    bias = np.asarray(curve['biasValues'], dtype=float)
    require(x.shape == (points,) and y.shape == (biases, points) and bias.shape == (biases,),
            f'Incomplete sweep: x={x.shape}, curves={y.shape}, biases={bias.shape}')
    require(np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and np.all(np.isfinite(bias)),
            'Non-finite sweep data')
    require(np.any(np.ptp(y, axis=1) > minimum_span), 'Sweep lacks required modeled response')
    require(all(curve.get(k) is not None and np.isfinite(float(curve[k]))
                for k in ['xOut', 'yOut', 'biasOut']), 'Missing/non-finite operating point')
    index = curve.get('bestIndex')
    require(isinstance(index, (int, np.integer)) and 0 <= index < biases, 'Invalid best-curve selection')


def check_tuning(sess, args, report, directory):
    profile = json.loads(args.profile.read_text())
    report['tuning_profile'] = profile
    cols, rows = profile['columns'], profile['rows']
    require(bool(cols) and len(set(cols)) == len(cols) and
            all(isinstance(c, int) and 0 <= c < sess.chans_per_board for c in cols), 'Invalid columns')
    require(bool(rows) and len(set(rows)) == len(rows) and
            all(isinstance(r, int) and 0 <= r < int(sess.group.MaxRows.get()) for r in rows), 'Invalid rows')
    require(len(cols) <= 2 and len(rows) <= 2, 'Use at most two columns and rows for reduced sweeps')
    specs = [('SaOffsetProcess', profile['sa_offset']), ('SaTuneProcess', profile['sa_tune']),
             ('Sq1TuneProcess', profile['sq1_tune'])]
    for params, prefix in [(profile['sa_tune'], 'Sa'), (profile['sq1_tune'], 'Sq1')]:
        require(5 <= params[prefix+'FbNumSteps'] <= 64 and 1 <= params[prefix+'BiasNumSteps'] <= 4,
                'Profile must explicitly bound feedback (5..64) and bias (1..4) steps')
    require(profile['sq1_tune'].get('ServoDisable', False) is False,
            'ServoDisable must be false for the closed-loop SQ1 check')
    spans = profile['minimum_curve_span']
    require(all(np.isfinite(spans[k]) and spans[k] > 0 for k in ['sa', 'sq1']), 'Positive curve spans required')
    variables = [sess.group.ColTuneEnable, sess.group.RowIndexOrderList]
    for name, params in specs:
        proc = getattr(sess.group, name)
        variables.extend(getattr(proc, key) for key in params)
    output = {}
    report['limitations'] = ['Model response only; real SQUID gain/noise/stability remain on #68',
                             'Cooperative Stop/transport cleanup may exceed the execution timeout']
    with restore(variables):
        sess.group.ColTuneEnable.set([c in cols for c in range(sess.chans_per_board)])
        sess.group.RowIndexOrderList.set(rows)
        failed = False
        try:
            if args.cancel_only:
                for attempt in range(2):
                    try:
                        sess.run_process('Sq1TuneProcess', timeout_sec=0.0,
                                         **profile['sq1_tune'])
                    except TimeoutError:
                        pass
                    else:
                        raise AssertionError('Process completed before timeout; cancellation was not tested')
                    require(not sess.group.Sq1TuneProcess.Running.get(), 'Process still running after Stop')
                    passed(report, f'timeout/Stop and restart attempt {attempt + 1}')
                return
            for name, params in specs:
                started = time.monotonic()
                result = sess.run_process(name, timeout_sec=args.process_timeout,
                                          poll_sec=0.5, **params)
                output[name] = result
                (directory / 'tuning-results.json').write_text(json.dumps(output, indent=2, default=json_value))
                if name == 'SaOffsetProcess':
                    values = np.asarray(result)
                    require(values.shape == (sess.chans_per_board,) and np.all(np.isfinite(values[cols])),
                            'Invalid SA offset result')
                    residual = np.asarray(sess.group.SaOutAdc.get())[cols]
                    precision = float(sess.group.SaOffsetProcess.Precision.get())
                    require(np.all(np.isfinite(residual)) and np.all(np.abs(residual) < precision),
                            'SA offset did not null modeled ADC output')
                elif name == 'SaTuneProcess':
                    require(len(result) == sess.chans_per_board, 'Missing SA column results')
                    for c in cols:
                        require_curve(result[c], params['SaFbNumSteps'], params['SaBiasNumSteps'], spans['sa'])
                else:
                    require(len(result) == len(rows), 'Missing SQ1 row results')
                    for row_result in result:  # Stored in requested row-list order, not physical row index.
                        require(len(row_result) == sess.chans_per_board, 'Missing SQ1 column results')
                        for c in cols:
                            require_curve(row_result[c], params['Sq1FbNumSteps'], params['Sq1BiasNumSteps'], spans['sq1'])
                passed(report, name + ' modeled result', wall_seconds=time.monotonic()-started)
        except BaseException:
            failed = True
            raise
        finally:
            # Try each cleanup even if another remote call fails.
            errors = []
            for name, _ in specs:
                try:
                    proc = getattr(sess.group, name)
                    if proc.Running.get():
                        proc.Stop()
                except BaseException as exc:
                    errors.append(str(exc))
            for row in rows:
                try:
                    sess.group.DeactivateRowIndex(row)
                except BaseException as exc:
                    errors.append(str(exc))
            try:
                sess.group.ColTuneEnable.set([True] * sess.chans_per_board)
                require(sess.stop_and_zero(settle_sec=args.timing_timeout), 'Final stop/zero failed')
            except BaseException as exc:
                errors.append(str(exc))
            report['cleanup_errors'] = errors
            if errors and not failed:
                raise RuntimeError('Tuning cleanup incomplete: ' + '; '.join(errors))
            report['final_state'] = 'rows deactivated, timing stopped, column outputs zeroed; settings restored on exit' if not errors else 'cleanup incomplete'
    report['final_state'] = 'rows deactivated, timing stopped, column outputs zeroed; process settings/selection restored'
    report['limitations'] = ['Model convergence only; physical SQUID gain, noise and stability remain on #68',
                             'Timeout requests cooperative Stop; VCS/transport cleanup may exceed wall timeout']


def main():
    p = parser(__doc__)
    p.add_argument('--profile', type=Path, required=True, help='fixture-specific reduced tuning parameters and thresholds')
    p.add_argument('--cancel-only', action='store_true', help='test timeout/Stop twice instead of convergence')
    p.add_argument('--process-timeout', type=positive, default=600.0)
    return run(p.parse_args(), check_tuning)


if __name__ == '__main__':
    raise SystemExit(main())
