#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Run the shared nonzero/mux/stop-zero test via VirtualClient, retaining VCS evidence.

This checks output registers. Observe the modeled DAC signals in VCS separately
before completing #86's combined register/model requirement.
"""
from _cosim_common import parser, passed, positive, restore, run


def check_stop_zero(sess, args, report, directory):
    # Lazy import so --help and pure validation do not require a Rogue environment.
    from verify_stop_and_zero import run_cycles
    args.skip_cols = ''
    with restore([sess.group.ColTuneEnable]):
        sess.group.ColTuneEnable.set([True] * sess.chans_per_board)
        run_cycles(sess, args)
    passed(report, 'nonzero -> confirmed mux run -> stopped/zero registers', cycles=args.cycles)
    report['limitations'] = ['Register verification only. Correlate VCS modeled DAC signals and retain the trace on #86.',
                             'No physical DAC-voltage measurement; DMM/scope acceptance remains open.']
    report['final_state'] = 'timing stopped, PID disabled, column outputs zeroed; per-row currents and column selection restored'


def main():
    p = parser(__doc__)
    p.add_argument('--cycles', type=int, default=5)
    p.add_argument('--force-uA', type=positive, default=50.0)
    p.add_argument('--tol-uA', type=positive, default=0.5)
    p.add_argument('--settle-sec', type=positive, default=5.0)
    p.add_argument('--num-pts', type=int, default=512)
    return run(p.parse_args(), check_stop_zero)


if __name__ == '__main__':
    raise SystemExit(main())
