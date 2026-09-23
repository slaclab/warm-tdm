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
"""Snapshot the PGP-ring link health from the coordinator's Pgp2bAxi monitor.

Purpose: characterize the *intermittent* row-board bring-up. The row board is
reached only over the PGP ring through the coordinator (ring / --simPgpRing
topology, and the real hardware ring). When the row board "can't be talked to",
the question is whether the coordinator's PGP link came up cleanly. This reads
the surf ``Pgp2bAxi[0]`` status block on the coordinator (ColumnBoard[0]):

  * link-ready flags   -- RxPhyReady / TxPhyReady / RxLocalLinkReady /
                          RxRemLinkReady / TxLinkReady. All should be 1 on a
                          healthy ring.
  * RxRemLinkReadyCount -- number of times the remote link (re)established.
                          On a stable link this is a small, STATIC number; a
                          value that grows across snapshots means the link is
                          flapping -- the signature of a marginal bring-up.
  * Rx/TxClkFreq        -- the recovered/transmit GT clock frequency monitors.
                          Off-nominal here points at a refclk/CPLL problem.
  * RxRemOverflow / RxRemPause -- backpressure/overflow indicators.

Use it two ways:
  1. One-shot on a *good* boot vs a *failed* boot, to compare.
  2. ``--watch N`` to poll every N seconds and flag any change in the
     link-ready flags or a rising RxRemLinkReadyCount (catches flapping).

It does NOT change RTL or reflash; it only enables the (default-disabled)
ComCore/PgpCore register subtree so the status registers are readable, then
reads them. Safe to run against a live warmTdmServer.

Examples:
  # one snapshot, pin to the firmware build stamp
  python pgp_link_health.py

  # poll every 5 s for flapping; Ctrl-C to stop and print a summary
  python pgp_link_health.py --watch 5

  # also snapshot the row board's own Pgp2bAxi (only readable once the ring is
  # already up -- i.e. when the board IS reachable)
  python pgp_link_health.py --include-row
"""
import argparse
import time

import _hwtest_common as hw


# Link-ready flags that must all read 1 on a healthy PGP link.
READY_FLAGS = [
    'RxPhyReady', 'TxPhyReady',
    'RxLocalLinkReady', 'RxRemLinkReady', 'TxLinkReady',
]

# Other status of interest (value printed as-is; interpretation in the docstring).
STATUS_VARS = [
    'RxRemLinkReadyCount',   # rising => flapping
    'RxClkFreq', 'TxClkFreq',
    'RxRemOverflow', 'RxRemPause',
    'RxLinkPolarity',
    'RxRemLinkData',         # the upstream node's advertised ring address
]


def _pgp_nodes(sess, include_row):
    """Yield (label, Pgp2bAxi node) for the coordinator and, optionally, rows.

    The ComCore/PgpCore subtree is created disabled (see _ComCore.py); enable it
    so the register reads actually go out on the wire. Reaching the ROW board's
    Pgp2bAxi requires the ring to already be up, so it is opt-in.
    """
    def find(board, label):
        try:
            com = board.WarmTdmCore.ComCore
            com.enable.set(True)
            com.PgpCore.enable.set(True)
            return (label, com.PgpCore.node('Pgp2bAxi[0]'))
        except Exception as exc:
            print(f'  (no Pgp2bAxi on {label}: {exc})')
            return None

    out = []
    for idx, cb in sess.cbs.items():
        tag = 'ColumnBoard[%d]%s' % (idx, ' (coordinator)' if idx == 0 else '')
        node = find(cb, tag)
        if node:
            out.append(node)
    if include_row:
        for idx, rb in sess.rbs.items():
            node = find(rb, f'RowBoard[{idx}]')
            if node:
                out.append(node)
    return out


def _snapshot(node):
    """Read the ready flags + status vars off one Pgp2bAxi node into a dict."""
    snap = {}
    for name in READY_FLAGS + STATUS_VARS:
        try:
            snap[name] = node.node(name).get()
        except Exception as exc:
            snap[name] = f'<err: {exc}>'
    return snap


def _print_snapshot(label, snap):
    ready = all(snap.get(f) in (1, True) for f in READY_FLAGS)
    print(f'  {label}: {"LINK UP" if ready else "LINK NOT READY"}')
    flags = '  '.join(f'{f}={snap.get(f)}' for f in READY_FLAGS)
    print(f'    {flags}')
    for name in STATUS_VARS:
        print(f'    {name} = {snap.get(name)}')
    return ready


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    hw.add_conn_args(p)
    p.add_argument('--watch', type=float, default=0.0, metavar='SEC',
                   help='poll every SEC seconds and flag changes (Ctrl-C to stop)')
    p.add_argument('--include-row', action='store_true',
                   help="also read each row board's Pgp2bAxi (needs the ring up)")
    args = p.parse_args()

    sess = hw.connect(args)
    nodes = _pgp_nodes(sess, args.include_row)
    if not nodes:
        print('No Pgp2bAxi nodes found; is the tree built?')
        return hw.finish(1)

    if args.watch <= 0:
        print('-' * 72)
        allok = True
        for label, node in nodes:
            allok &= _print_snapshot(label, _snapshot(node))
        print('-' * 72)
        return hw.finish(0 if allok else 1)

    # Watch mode: baseline, then report only deltas + rising re-link counts.
    print('-' * 72)
    baseline = {}
    for label, node in nodes:
        snap = _snapshot(node)
        baseline[label] = snap
        _print_snapshot(label, snap)
    print('-' * 72)
    print(f'Watching every {args.watch}s; Ctrl-C to stop.')
    try:
        while True:
            time.sleep(args.watch)
            for label, node in nodes:
                snap = _snapshot(node)
                prev = baseline[label]
                changed = {k: (prev.get(k), snap.get(k))
                           for k in READY_FLAGS + STATUS_VARS
                           if prev.get(k) != snap.get(k)}
                if changed:
                    stamp = time.strftime('%H:%M:%S')
                    print(f'[{stamp}] {label} CHANGED:')
                    for k, (old, new) in changed.items():
                        arrow = ' <-- link (re)established' \
                            if k == 'RxRemLinkReadyCount' else ''
                        print(f'    {k}: {old} -> {new}{arrow}')
                    baseline[label] = snap
    except KeyboardInterrupt:
        print('\nStopped.')
    return hw.finish(0)


if __name__ == '__main__':
    main()
