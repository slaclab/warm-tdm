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
"""Fiber/link health check for Issue #50 (how to check health of the fiber link).

Wiki: HW-Verify-Issue-50-Fiber-Link-Health

Enables the RSSI cores under each ColumnBoard's ComCore.EthCore, snapshots the
link counters, polls for a while, and reports whether the error/reconnect
counters stayed flat. This doubles as the ``check_link_health`` helper the issue
asks for: run it once on a quiet link for a baseline, and again while you perturb
the fiber (Part 2 of the wiki page) to confirm the counters register the fault.

    python check_link_health.py --host localhost --port 9099 --seconds 30

By default a healthy link => PASS (no growth in Drop/Retransmit/Reconnect over
the poll window). Use --expect-faults when you are deliberately perturbing the
link and want the *presence* of counter growth to be the PASS condition.
"""
import argparse
import sys
import time

from _hwtest_common import add_conn_args, connect, Checklist

# RSSI counters we treat as link-health signals (surf RssiCore). We read what is
# present and skip any a given firmware build doesn't expose.
_ERROR_COUNTERS = ['DropCnt', 'RetransmitCnt', 'ReconnectCnt']
_STATUS_VARS = ['OpenConn', 'ConnState', 'RxFrameRate', 'TxFrameRate']


def _rssi_cores(sess):
    """Yield (label, rssi_device) for every RSSI core across all column boards."""
    for idx, cb in sorted(sess.cbs.items()):
        eth = cb.WarmTdmCore.ComCore.EthCore
        for name in ('SRP_RSSI', 'Data_RSSI'):
            dev = getattr(eth, name, None)
            if dev is not None:
                yield f'ColumnBoard[{idx}].{name}', dev


def _read_counters(dev):
    """Read the available error counters from an RSSI device as {name: int}."""
    out = {}
    for c in _ERROR_COUNTERS:
        var = getattr(dev, c, None)
        if var is not None:
            try:
                out[c] = int(var.get())
            except Exception:
                pass
    return out


def _read_status(dev):
    out = {}
    for s in _STATUS_VARS:
        var = getattr(dev, s, None)
        if var is not None:
            try:
                out[s] = var.get()
            except Exception:
                pass
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    add_conn_args(p)
    p.add_argument('--seconds', type=float, default=30.0,
                   help='poll window in seconds (default: 30)')
    p.add_argument('--interval', type=float, default=1.0,
                   help='poll interval in seconds (default: 1)')
    p.add_argument('--expect-faults', action='store_true',
                   help='invert the verdict: PASS when counters GROW (use while '
                        'deliberately perturbing the fiber, wiki Part 2)')
    args = p.parse_args()

    sess = connect(args)
    chk = Checklist('Issue #50 fiber link health')

    cores = list(_rssi_cores(sess))
    if not cores:
        chk.item(False, 'Found at least one RSSI core', 'none present')
        return chk.report()

    # Enable + baseline read.
    print('\nEnabling RSSI cores and reading baseline...')
    baseline = {}
    for label, dev in cores:
        try:
            dev.enable.set(True)
            dev.ReadDevice()
        except Exception as exc:
            print(f'  {label}: could not enable/read ({exc})')
        status = _read_status(dev)
        baseline[label] = _read_counters(dev)
        print(f'  {label}: status={status} counters={baseline[label]}')

    any_open = False
    for label, dev in cores:
        oc = getattr(dev, 'OpenConn', None)
        if oc is not None:
            try:
                any_open = any_open or bool(oc.get())
            except Exception:
                pass
    chk.item(any_open, 'At least one RSSI connection is open (OpenConn)')

    # Poll window.
    print(f'\nPolling for {args.seconds:.0f}s '
          f'({"expecting faults" if args.expect_faults else "expecting a quiet link"})...')
    deadline = time.time() + args.seconds
    while time.time() < deadline:
        for label, dev in cores:
            try:
                dev.ReadDevice()
            except Exception:
                pass
        time.sleep(args.interval)

    # Final read + deltas.
    print('\nFinal counters and deltas:')
    grew_total = 0
    per_core_grew = {}
    for label, dev in cores:
        final = _read_counters(dev)
        delta = {k: final.get(k, 0) - baseline[label].get(k, 0) for k in final}
        grew = sum(v for v in delta.values() if v > 0)
        per_core_grew[label] = grew
        grew_total += grew
        print(f'  {label}: final={final} delta={delta}')

    if args.expect_faults:
        chk.item(grew_total > 0,
                 'Error/reconnect counters grew under the induced fault',
                 f'total counter growth = {grew_total}')
    else:
        chk.item(grew_total == 0,
                 'No error/reconnect counter growth over the poll window '
                 '(link healthy)',
                 f'total counter growth = {grew_total}')
        if grew_total:
            hot = ', '.join(f'{k} (+{v})' for k, v in per_core_grew.items() if v)
            print(f'  cores with growth: {hot}')

    return chk.report()


if __name__ == '__main__':
    sys.exit(main())
