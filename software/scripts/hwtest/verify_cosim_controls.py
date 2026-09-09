#!/usr/bin/env python3
# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Check Group broadcast leaves and DAC/FIR register writes through VirtualClient."""
import numpy as np

from _cosim_common import parser, passed, require, restore, run


def check_controls(sess, args, report, directory):
    boards = list(sess.boards().values())
    leds = [b.WarmTdmCore.WarmTdmCommon2.WarmTdmConfig.LedEn for b in boards]
    timing = [b.WarmTdmCore.Timing.TimingTx for b in boards]
    ps = [getattr(tx, name) for tx in timing
          for name in ['PwrSyncA', 'PwrSyncB', 'PwrSyncC', 'PwrSyncEn']]
    cables = sess.hwg.find(name='CableR$')
    require(bool(cables), 'No amplifier cable-resistance leaves found')
    with restore(leds + ps + cables):
        for state in [False, True]:
            sess.group.LedEnable.set(state)
            require(all(int(v.get()) == int(state) for v in leds), 'LED register fanout mismatch')
            sess.group.PowerSupplySynchronized.set(state)
            for tx in timing:
                require(all(int(getattr(tx, n).get()) == (2 if state else 0)
                            for n in ['PwrSyncA', 'PwrSyncB', 'PwrSyncC']), 'Power-sync fanout mismatch')
                require(bool(tx.PwrSyncEn.get()) == state, 'Power-sync enable mismatch')
        for resistance in [120.0, 250.0]:
            sess.group.CableResistance.set(resistance)
            require(all(float(v.get()) == resistance for v in cables), 'Cable resistance fanout mismatch')
    passed(report, 'Group broadcast leaf writes and restoration', boards=len(boards),
           cable_leaves=len(cables), limitation='LED light and supply phase require hardware measurements')

    if args.broadcasts_only:
        report['not_run'] = ['DAC override/zeroing and FIR registers']
        return

    cb = sess.coordinator_cb
    with restore([sess.group.ColTuneEnable]):
        sess.group.ColTuneEnable.set([True] * sess.chans_per_board)
        try:
            for code in [8192, 9000]:
                cb.AllFastDacs(code)
                for name in ['SQ1Fb', 'SAFb', 'SQ1Bias']:
                    dev = getattr(cb, name)
                    actual = [int(dev.OverrideRaw[ch].get()) for ch in range(sess.chans_per_board)]
                    require(actual == [code] * sess.chans_per_board, f'{name} override RAM mismatch')
            passed(report, 'AllFastDacs writes all override registers',
                   limitation='Raw command does not guarantee every output latched the override; #86 owns output verification')
        finally:
            require(sess.stop_and_zero(settle_sec=args.timing_timeout), 'Final DAC zeroing failed')
    report['final_state'] = 'timing stopped, column DACs zeroed; broadcast settings restored'

    if not args.fir:
        report['not_run'] = ['FIR registers: select --fir only for a fixture with GEN_ADC_FILTER_G=true']
        return
    dev = cb.DataPath.AdcFilters
    from scipy.signal import firwin
    enabled = dev.enable.get()
    old_cutoff = dev.FilterCuttoffFreq.get()
    try:
        dev.enable.set(True)
        taps = [dev.FirFilter[ch].Taps for ch in range(sess.chans_per_board)]
        with restore(taps):
            original = [np.asarray(v.get()).copy() for v in taps]
            for cutoff in [1e6, 5e6]:
                expected = firwin(len(original[0]), cutoff, fs=125e6, window='hamming')
                dev.FilterCuttoffFreq.set(cutoff, write=False)
                for v, previous in zip(taps, original):
                    np.testing.assert_allclose(v.get(read=False), expected, rtol=0, atol=5e-7)
                    np.testing.assert_allclose(v.get(), previous, rtol=0, atol=5e-7)
                dev.FilterCuttoffFreq.set(cutoff)
                for v in taps:
                    np.testing.assert_allclose(v.get(), expected, rtol=0, atol=5e-7)
                original = [np.asarray(v.get()).copy() for v in taps]
    finally:
        # Restore the informational cutoff cache before restoring enable state.
        # Tap registers have already been restored by restore(taps).
        dev.FilterCuttoffFreq.set(old_cutoff, write=False)
        dev.enable.set(enabled)
    passed(report, 'FIR cache-only and committed coefficients on all eight channels',
           limitation='Coefficient transactions only; no analog filter response measurement')


def main():
    p = parser(__doc__)
    p.add_argument('--broadcasts-only', action='store_true', help='only test the Group broadcast controls')
    p.add_argument('--fir', action='store_true', help='also test the compiled-in ADC FIR register bank')
    args = p.parse_args()
    if args.fir and args.broadcasts_only:
        p.error('--fir and --broadcasts-only are mutually exclusive')
    return run(args, check_controls)


if __name__ == '__main__':
    raise SystemExit(main())
