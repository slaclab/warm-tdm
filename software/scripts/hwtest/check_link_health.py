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

Polls the HOST-side rogue RSSI client counters (UdpRssiPack: hwg.SrpRssi /
hwg.DataRssi), snapshots them, waits, and reports whether the link stayed up.
This doubles as the ``check_link_health`` helper the issue asks for: run it once
on a quiet link for a baseline, and again while you perturb the fiber (Part 2 of
the wiki page) to confirm the counters register the fault.

    python check_link_health.py --host localhost --port 9099 --seconds 30

Deliberately uses the host-side client counters, NOT the FPGA-side RSSI cores:
the FPGA counters are read over SRP (which rides the link under test), so they
are unreadable *during* a drop and reset on reconnect. The host-side counters
(`rssiOpen`, `rssiDownCount`, ...) live in the local rogue process and stay
readable through a fiber loss — the whole point of a link-health check.

By default a healthy link => PASS (rssiOpen True, no rssiDownCount growth). Use
--expect-faults when deliberately perturbing the link, where a rssiDownCount
increment is the PASS condition.
"""
import argparse
import sys
import time

from _hwtest_common import add_conn_args, connect, Checklist, finish

# We poll the HOST-side rogue RSSI client (UdpRssiPack: hwg.SrpRssi / hwg.DataRssi),
# NOT the FPGA-side RSSI cores under ComCore.EthCore.
#
# WHY (learned on the bench, Issue #50): the FPGA-side counters are reached over
# SRP, which rides the very link under test. When the fiber drops, those reads
# time out — you cannot observe the fault while it is happening — and the FPGA
# RSSI core RESETS its counters on reconnect (deltas go negative). The host-side
# UdpRssiPack counters live in the local rogue process, need no fiber transaction,
# stay readable during a drop, and monotonically record it:
#   - rssiOpen        (RO) : client-side link-up flag; goes False during a drop.
#   - rssiDownCount   (RO) : increments each time the link goes down — the clean
#                            fault signal.
#   - rssiDropCount   (RO) : client-side dropped segments (informational).
#   - rssiRetranCount (RO) : client-side retransmits (informational).
_ERROR_COUNTERS = ['rssiDownCount', 'rssiDropCount', 'rssiRetranCount']
_STATUS_VARS = ['rssiOpen', 'curMaxSegment', 'curMaxBuffers']


def _rssi_cores(sess):
    """Yield (label, device) for the host-side RSSI clients (UdpRssiPack).

    These are added at HardwareGroup level as ``SrpRssi`` (register path) and
    ``DataRssi`` (streaming path) in ``_HardwareGroup.py``.
    """
    hwg = sess.hwg
    for name in ('SrpRssi', 'DataRssi'):
        dev = getattr(hwg, name, None)
        if dev is not None:
            yield name, dev


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


def _is_open(dev):
    """Host-side link-up flag (rssiOpen); None if unavailable."""
    v = getattr(dev, 'rssiOpen', None)
    if v is None:
        return None
    try:
        return bool(v.get())
    except Exception:
        return None


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
        chk.item(False, 'Found a host-side RSSI client (SrpRssi/DataRssi)',
                 'none present')
        return finish(chk.report())

    # Baseline read. These are host-side (local) counters — no fiber transaction,
    # so no enable/ReadDevice-over-SRP needed; just read the current values.
    print('\nReading host-side RSSI baseline...')
    baseline = {}
    for label, dev in cores:
        status = _read_status(dev)
        baseline[label] = _read_counters(dev)
        print(f'  {label}: status={status} counters={baseline[label]}')

    # "Is the link up?" — host-side rssiOpen flag.
    any_open = any(_is_open(dev) for _, dev in cores if _is_open(dev) is not None)
    chk.item(any_open, 'At least one RSSI client reports rssiOpen=True')

    # Poll window. Nothing to fetch over the fiber — the host client updates its
    # own counters; we just sample them (and stay responsive during a real drop).
    print(f'\nPolling for {args.seconds:.0f}s '
          f'({"expecting faults" if args.expect_faults else "expecting a quiet link"})...')
    deadline = time.time() + args.seconds
    while time.time() < deadline:
        time.sleep(args.interval)

    # Final read + deltas.
    print('\nFinal counters and deltas:')
    down_total = 0     # the unambiguous fault signal (rssiDownCount growth)
    drop_retx_total = 0
    per_core_down = {}
    for label, dev in cores:
        final = _read_counters(dev)
        delta = {k: final.get(k, 0) - baseline[label].get(k, 0) for k in final}
        downs = max(0, delta.get('rssiDownCount', 0))
        drop_retx = max(0, delta.get('rssiDropCount', 0)) + max(0, delta.get('rssiRetranCount', 0))
        down_total += downs
        drop_retx_total += drop_retx
        per_core_down[label] = downs
        print(f'  {label}: final={final} delta={delta}')

    # Link-up state now (readable even if it just dropped — host-side flag).
    open_now = any(_is_open(dev) for _, dev in cores if _is_open(dev) is not None)

    print(f'\n  rssiDownCount growth (fault signal): {down_total}')
    print(f'  Drop+Retransmit growth (informational): {drop_retx_total}')

    if args.expect_faults:
        chk.item(down_total > 0,
                 'Induced fault registered (rssiDownCount grew)',
                 f'downCount growth={down_total}, open_now={open_now}')
    else:
        chk.item(open_now, 'Link reports rssiOpen after the poll window')
        chk.item(down_total == 0,
                 'No link-down events over the poll window (link stable)',
                 f'downCount growth={down_total}')
        if drop_retx_total:
            hot = ', '.join(f'{k} (+{v})' for k, v in per_core_down.items() if v)
            print(f'  note: {drop_retx_total} drop/retx segments '
                  f'(informational). link-down by core: {hot or "none"}')

    return finish(chk.report())


if __name__ == '__main__':
    sys.exit(main())
