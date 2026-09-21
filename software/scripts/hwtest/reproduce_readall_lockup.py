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
"""Reproduce (or clear) the row-board ReadAll lockup against a live cosim/HW.

Bench symptom: a full ReadAll fails at the row board, then wedges column-board
SRP access too. Root cause on hardware was an undersized PGP ring RX VC FIFO
(FIFO_ADDR_WIDTH_G): a burst of slow SPI-backed row register reads backs up the
receive path and stalls the shared SRP stream. Bench fix = enlarge the RX VC
FIFO (8 -> 10). This script is the A/B probe:

  * Build a GroupTb ring cosim with FIFO_ADDR_WIDTH_G=8 (regressed) -> expect the
    row ReadAll to stall / time out and a subsequent column read to also hang.
  * Rebuild with FIFO_ADDR_WIDTH_G=10 (fix) -> expect both to complete.

Sequence:
  1. Read the row board's AxiVersion (proves basic ring SRP works -- this is the
     fast path that succeeds even when ReadAll wedges).
  2. ReadAll the WHOLE row board device subtree (sweeps the slow SPI DAC regs).
  3. Read the coordinator's AxiVersion AFTER the row ReadAll (proves the shared
     SRP stream is still alive -- this is what wedges on the bench).

Each step runs under a watchdog: pyrogue reads block, so a real lockup would hang
forever. The watchdog thread reports which step stalled and by how long. On a
healthy tree every step returns well under the timeout.

Run against a live warmTdmServer (cosim in ring mode, or hardware):
  # cosim ring mode:
  python warmTdmServer.py --sim --simPgpRing --columnBoards 1 --rowBoards 1 \
      --rowAddrBits 5 --maxRows 32
  python reproduce_readall_lockup.py --step-timeout 120

Cosim is slow (seconds/transaction over the ring); use a generous --step-timeout.
"""
import argparse
import threading
import time

import _hwtest_common as hw


def _timed(label, fn, timeout):
    """Run fn() in a watchdog thread; return (ok, elapsed, result_or_exc).

    pyrogue reads block indefinitely on a wedged SRP stream, so we run the read
    in a daemon thread and time it out. A timed-out thread is left dangling (the
    process will be killed by finish()) -- acceptable for a one-shot diagnostic.
    """
    box = {}
    def run():
        t0 = time.time()
        try:
            box['result'] = fn()
        except Exception as exc:            # noqa: BLE001 -- report any failure
            box['exc'] = exc
        finally:
            box['elapsed'] = time.time() - t0

    th = threading.Thread(target=run, daemon=True)
    print(f'  [..] {label} ...', flush=True)
    t0 = time.time()
    th.start()
    th.join(timeout)
    if th.is_alive():
        print(f'  [STALL] {label}: no response after {timeout:.0f}s '
              f'(SRP stream appears wedged)', flush=True)
        return (False, timeout, None)
    elapsed = box.get('elapsed', time.time() - t0)
    if 'exc' in box:
        print(f'  [FAIL] {label}: {box["exc"]!r} after {elapsed:.2f}s', flush=True)
        return (False, elapsed, box['exc'])
    print(f'  [OK] {label} in {elapsed:.2f}s', flush=True)
    return (True, elapsed, box.get('result'))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    hw.add_conn_args(p)
    p.add_argument('--step-timeout', type=float, default=120.0, metavar='SEC',
                   help='per-step watchdog timeout in seconds (default 120)')
    p.add_argument('--row', type=int, default=0, help='row board index (default 0)')
    p.add_argument('--col', type=int, default=0,
                   help='coordinator column board index (default 0)')
    args = p.parse_args()

    sess = hw.connect(args)
    hwg = sess.hwg
    row = hwg.RowBoard[args.row]
    col = hwg.ColumnBoard[args.col]
    rowAxi = row.WarmTdmCore.WarmTdmCommon.AxiVersion
    colAxi = col.WarmTdmCore.WarmTdmCommon.AxiVersion

    chk = hw.Checklist('Row ReadAll lockup reproduction')

    # 1. Fast path: row AxiVersion (works even when ReadAll wedges).
    ok, _, _ = _timed('Row AxiVersion.GitHash (fast ring SRP)',
                      lambda: rowAxi.GitHash.get(), args.step_timeout)
    chk.item(ok, 'Row AxiVersion readable before ReadAll')

    # 2. The trigger: sweep the whole row tree (hits the slow SPI DAC regs).
    #    ReadDevice(arg) -> readAndWaitBlocks(recurse=arg); MUST pass True or it
    #    only reads the board's top-level blocks (returns instantly, reads
    #    nothing). True recurses into WarmTdmCore + the SPI DACs and blocks.
    ok_readall, _, _ = _timed('Row board ReadAll (full subtree sweep)',
                              lambda: row.ReadDevice(True), args.step_timeout)
    chk.item(ok_readall, 'Row board ReadAll completed')

    # 3. The tell: is the shared SRP stream still alive afterward?
    ok_col, _, _ = _timed('Coordinator AxiVersion.GitHash AFTER row ReadAll',
                          lambda: colAxi.GitHash.get(), args.step_timeout)
    chk.item(ok_col, 'Column SRP still responsive after row ReadAll',
             '' if ok_col else 'column wedged -> lockup reproduced')

    if not ok_readall or not ok_col:
        chk.note('LOCKUP REPRODUCED: this matches the bench failure. Expected '
                 'with the regressed RX VC FIFO (FIFO_ADDR_WIDTH_G=8).')
    else:
        chk.note('No lockup: the tree survived a full row ReadAll. Expected with '
                 'the fixed RX VC FIFO (FIFO_ADDR_WIDTH_G=10).')

    return hw.finish(chk.report())


if __name__ == '__main__':
    main()
