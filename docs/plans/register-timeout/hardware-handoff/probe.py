#!/usr/bin/env python3
"""Timestamped virtual-client probes. Only scratch-write writes hardware."""
import argparse
import json
import sys
import time
import traceback


def emit(event, **fields):
    print(json.dumps(dict(event=event, epoch=time.time(), monotonic=time.monotonic(),
                          **fields), default=str), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=9099)
    p.add_argument('--root', default='GroupRoot')
    p.add_argument('--case', required=True, choices=[
        'baseline', 'version-only', 'scratch-first', 'axi-batched', 'axi-sequential',
        'safb-batched', 'safb-sequential', 'column-batched', 'column-sequential',
        'row-stock', 'readall-stock', 'readall-sequential', 'scratch-write', 'identity'])
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--pause', type=float, default=2.0)
    p.add_argument('--seconds', type=int, default=60)
    args = p.parse_args()
    if args.repeat < 1 or args.seconds < 1 or args.pause < 0:
        p.error('repeat and seconds must be positive; pause must be nonnegative')
    import pyrogue.interfaces
    client = pyrogue.interfaces.VirtualClient(addr=args.host, port=args.port)
    base = args.root + '.Group.HardwareGroup'
    col = base + '.ColumnBoard[0]'
    row = base + '.RowBoard[0]'
    version = '.WarmTdmCore.WarmTdmCommon.AxiVersion'
    av = col + version
    rpc = client._remoteAttr

    def op(path, method, *a, **kw):
        start = time.monotonic()
        emit('operation_start', path=path, method=method, args=a, kwargs=kw)
        try:
            value = rpc(path, method, *a, **kw)
        except Exception:
            emit('operation_error', path=path, method=method,
                 elapsed=time.monotonic()-start, traceback=traceback.format_exc())
            raise
        emit('operation_done', path=path, method=method,
             elapsed=time.monotonic()-start, result=value)
        return value

    def get(path):
        value = op(path, 'get', read=True)
        if value is None:
            raise RuntimeError(f'No value returned for required register {path}')
        return value

    def block(path, wait):
        return op(path, 'readAndWaitBlocks', recurse=True, waitEach=wait)

    def snapshot(label):
        values = {}
        for core in ('SrpRssi', 'DataRssi'):
            entry = {}
            for name in ('rssiOpen', 'curMaxSegment', 'curMaxBuffers',
                         'curCumAckTout', 'curRetranTout', 'curNullTout',
                         'curMaxRetran', 'curMaxCumAck',
                         'rssiDownCount', 'rssiDropCount', 'rssiRetranCount',
                         'locBusy', 'locBusyCnt', 'remBusy', 'remBusyCnt'):
                try:
                    # These are host-side RSSI variables, not FPGA register accesses.
                    entry[name] = rpc(base + '.' + core + '.' + name, 'get')
                except Exception as exc:
                    entry[name] = {'unavailable': str(exc)}
            values[core] = entry
        emit('counters', label=label, values=values)

    def flags():
        values = {}
        for path in (args.root, args.root+'.Group', base, col,
                     col+'.WarmTdmCore', col+'.WarmTdmCore.WarmTdmCommon',
                     av, col+'.SAFb', row):
            values[path] = rpc(path, 'forceWaitEach')
        emit('forceWaitEach', values=values)
        if any(value is None for value in values.values()):
            raise RuntimeError('Required device/serialization metadata is missing; verify the tree paths.')
        if args.case == 'column-batched' and values[col]:
            raise RuntimeError('Column forces serialization: restart server with --column-mode batched.')
        target = av if args.case == 'axi-batched' else col+'.SAFb'
        if args.case in ('axi-batched', 'safb-batched') and values[target]:
            raise RuntimeError('Target forces serialization; this would not be a batched test.')

    def run_case():
        if args.case == 'baseline':
            for second in range(args.seconds):
                time.sleep(1)
                snapshot(f'idle_{second+1}')
        elif args.case == 'version-only':
            get(av+'.FpgaVersion')
        elif args.case == 'scratch-first':
            get(av+'.ScratchPad')
            get(av+'.FpgaVersion')
        elif args.case.startswith('axi-'):
            block(av, args.case.endswith('sequential'))
        elif args.case.startswith('safb-'):
            block(col+'.SAFb', args.case.endswith('sequential'))
        elif args.case.startswith('column-'):
            block(col, args.case.endswith('sequential'))
        elif args.case == 'row-stock':
            block(row, False)  # Board's own forceWaitEach still wins.
        elif args.case == 'readall-stock':
            op(args.root+'.ReadAll', '__call__')
        elif args.case == 'readall-sequential':
            block(args.root, True)
        elif args.case == 'identity':
            for board in (col, row):
                for name in ('FpgaVersion', 'GitHash', 'BuildStamp', 'DeviceDna'):
                    get(board+version+'.'+name)
        elif args.case == 'scratch-write':
            path = av+'.ScratchPad'
            original = int(get(path))  # If this fails, no write is attempted.
            emit('scratch_original', path=path, value=original)
            try:
                for value in (0xA5A55A5A, 0x5A5AA5A5):
                    # set may itself trigger Rogue's automatic verification read.
                    op(path, 'set', value, write=True)
                    actual = int(get(path))
                    if actual != value:
                        raise RuntimeError(f'ScratchPad expected {value:#x}, got {actual:#x}')
            finally:
                emit('scratch_restore_start', path=path, value=original)
                op(path, 'set', original, write=True)
                restored = int(get(path))
                if restored != original:
                    raise RuntimeError('ScratchPad restoration readback mismatch')
                emit('scratch_restored', path=path, value=restored)

    failed = False
    try:
        emit('connected', arguments=vars(args))
        # Metadata and host counters only: no implicit hardware identity/warmup reads.
        flags()
        for iteration in range(1, args.repeat+1):
            snapshot(f'before_{iteration}')
            emit('case_start', case=args.case, iteration=iteration)
            start = time.monotonic()
            try:
                run_case()
            except Exception:
                failed = True
                emit('case_error', case=args.case, iteration=iteration,
                     elapsed=time.monotonic()-start, traceback=traceback.format_exc())
            else:
                emit('case_done', case=args.case, iteration=iteration,
                     elapsed=time.monotonic()-start)
            snapshot(f'after_{iteration}')
            if failed:
                break  # Preserve the first failure; no automatic retry or recovery.
            if iteration < args.repeat:
                time.sleep(args.pause)
    finally:
        client.stop()
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
