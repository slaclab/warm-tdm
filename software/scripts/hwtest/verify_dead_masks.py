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
"""Hardware test for Issue #60 (dead-list masking drops the wrong channels).

Wiki: HW-Verify-Issue-60-Dead-List-Masking

Fully software-verifiable: take a baseline stream file with no masks, apply a
known dead set, take a second file, and assert that the channels that disappear
are *exactly* the ones masked — nothing extra dropped, nothing masked-but-still-
present. A mismatch prints the requested vs. actually-dropped sets so the
mapping bug can be pinned.

    python verify_dead_masks.py --host localhost --port 9099 \
        --cols c4r3,c4r19,c5r58 --acq 10

Run against a configuration that actually produces per-(col,row) data on the
channels you intend to mask (choose the enabled set / row map on the server or
with --setup-mux). Emulate will not produce real analog data, so use real
hardware for a meaningful verdict.
"""
import argparse
import sys

from _hwtest_common import add_conn_args, connect, Checklist

from warm_tdm_api.operations import make_dead_masks, expand_channels


def present_channels(stream_data):
    """Set of 'c<col>r<row>' strings that carry data in a StreamData."""
    return set(expand_channels('c*r*', stream_data.data))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    add_conn_args(p)
    p.add_argument('--cols', type=str, default='c4r3,c4r19,c5r58,c6r0,c6r58',
                   help="comma-separated dead channels to mask, e.g. 'c4r3,c5r58' "
                        "(default: the Issue #60 set)")
    p.add_argument('--acq', type=float, default=10.0,
                   help='acquisition time per file, seconds (default: 10)')
    p.add_argument('--ncol', type=int, default=8, help='columns for mask sizing')
    p.add_argument('--nrow', type=int, default=256, help='rows for mask sizing')
    p.add_argument('--setup-mux', action='store_true',
                   help='call setup_mux before acquiring (else assume the run is '
                        'already configured on the server)')
    args = p.parse_args()

    import warm_tdm_api.operations as ops

    dead = [c.strip() for c in args.cols.split(',') if c.strip()]
    dead_set = set(dead)

    sess = connect(args)
    chk = Checklist('Issue #60 dead-list masking')

    if args.setup_mux:
        ops.setup_mux(enable_pid=True)

    # --- baseline (no masks) ------------------------------------------------
    print('\nAcquiring BASELINE (no masks)...')
    baseline_path = ops.take_data(acq_time_sec=args.acq)
    baseline = ops.StreamData(baseline_path)
    base_chans = present_channels(baseline)
    print(f'  baseline file: {baseline_path}')
    print(f'  baseline channels ({len(base_chans)}): {sorted(base_chans)}')

    chk.item(len(base_chans) > 0,
             'Baseline file contains channel data',
             f'{len(base_chans)} channels')

    # The masked set must actually be present in the baseline, or "it dropped"
    # is meaningless. Warn on any requested channel absent from the baseline.
    not_in_base = dead_set - base_chans
    chk.item(not not_in_base,
             'All requested dead channels are present in the baseline',
             'missing from baseline: ' + (', '.join(sorted(not_in_base)) or 'none'))

    # --- apply masks --------------------------------------------------------
    masks = make_dead_masks(dead, ncol=args.ncol, nrow=args.nrow)
    print(f'\nApplying dead masks for {dead}...')
    sess.apply_dead_masks(masks)

    # --- masked acquisition -------------------------------------------------
    print('\nAcquiring MASKED...')
    masked_path = ops.take_data(acq_time_sec=args.acq)
    masked = ops.StreamData(masked_path)
    masked_chans = present_channels(masked)
    print(f'  masked file: {masked_path}')
    print(f'  masked channels ({len(masked_chans)}): {sorted(masked_chans)}')

    # --- the verdict --------------------------------------------------------
    dropped = base_chans - masked_chans          # disappeared after masking
    still_present = dead_set & masked_chans       # masked but still there (bug)
    extra_dropped = dropped - dead_set            # dropped but not masked (bug)

    print('\nComparison:')
    print(f'  requested dead : {sorted(dead_set)}')
    print(f'  actually dropped: {sorted(dropped)}')

    chk.item(not still_present,
             'No masked channel remained in the stream',
             'still present: ' + (', '.join(sorted(still_present)) or 'none'))
    chk.item(not extra_dropped,
             'No unmasked channel was dropped',
             'unexpectedly dropped: ' + (', '.join(sorted(extra_dropped)) or 'none'))
    chk.item(dropped == (dead_set & base_chans),
             'Dropped set equals the requested dead set (restricted to baseline)',
             'exact match' if dropped == (dead_set & base_chans) else 'MISMATCH')

    if extra_dropped or still_present:
        print('\n  Mapping hint: the (requested -> dropped) discrepancy above is '
              'what pins the bit-order / index bug. Re-run with a single --cols '
              'entry to isolate the offset (see the wiki page, Part 3).')

    return chk.report()


if __name__ == '__main__':
    sys.exit(main())
