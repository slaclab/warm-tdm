#-----------------------------------------------------------------------------
# This file is part of the 'warm-tdm' project. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'warm-tdm' project, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import queue
import threading
import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np
import warm_tdm


class PidRowDebuggerFp(warm_tdm.PidRowDebuggerBase):
    def __init__(self, debugDev, row, **kwargs):
        super().__init__(debugDev=debugDev, row=row, **kwargs)
        self.parsedVars = ['AccumErrorFp', 'Sq1FbFullFp', 'SumAccumFp', 'NewSumAccum', 'Sq1FbNewFp', 'NumFluxJumps', 'Sq1FbInt', 'AccumSamples']

        self.add(pr.LocalVariable(
            name = 'Visits',
            mode = 'RO',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'AccumErrorFp',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'Sq1FbFullFp',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'SumAccumFp',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'NewSumAccum',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'Sq1FbNewFp',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'NumFluxJumps',
            mode = 'RO',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'Sq1FbInt',
            mode = 'RO',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'AccumSamples',
            mode = 'RO',
            value = 0))

    def updateFromParser(self, msg):
        with self.root.updateGroup():
            for varName in self.parsedVars:
                self.variables[varName].set(self.debugDev.variables[varName].get(read=False))
            self.Visits.set(self.Visits.get() + 1)
            self.updateSample(msg)


class PidDebuggerFp(pr.DataReceiver):

    def __init__(self, numRows, col, dsp=None, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()

        self.col = col
        self._dsp = dsp

        # Frames are handed off to a worker thread so the Rogue receive thread
        # never blocks on decode/SRP/variable-notify work. A muxed run can emit
        # thousands of PID-debug frames/s; the bounded queue sheds surplus rather
        # than stalling the stream (and, in turn, unrelated variable updates).
        self._queue = queue.Queue(maxsize=256)
        self._worker = None

        super().__init__(memBase=self.mem, **kwargs)

        self.add(pr.LocalVariable(
            name = 'SwDropCount',
            description = 'PID-debug frames dropped in software because the worker '
                          'queue was full (distinct from the FPGA DropCount carried '
                          'in each frame).',
            mode = 'RO',
            disp = '{:d}',
            value = 0,
            groups = ['NoConfig', 'NoStream', 'NoState']))

        # Word 0: Column[3:0], pad[7:4], RowIndex[15:8], RunTime[63:16]
        self.add(pr.RemoteVariable(
            name = 'Column',
            mode = 'RO',
            offset = 0x00,
            base = pr.UInt,
            bitSize = 4,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'RowIndex',
            mode = 'RO',
            offset = 0x00,
            disp = '{:d}',
            base = pr.UInt,
            bitOffset = 8,
            bitSize = 8))

        self.add(pr.RemoteVariable(
            name = 'RunTime',
            mode = 'RO',
            offset = 0x00,
            bitOffset = 16,
            bitSize = 48,
            disp = '{:d}',
            base = pr.UInt))

        # Word 1: AccumErrorFp[31:0] (float32), Sq1FbFullFp[63:32] (float32)
        self.add(pr.RemoteVariable(
            name = 'AccumErrorFp',
            mode = 'RO',
            offset = 0x08,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbFullFp',
            mode = 'RO',
            offset = 0x08,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 32))

        # Word 2: SumAccumFp[31:0] (float32), NewSumAccum[63:32] (float32)
        self.add(pr.RemoteVariable(
            name = 'SumAccumFp',
            mode = 'RO',
            offset = 0x10,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'NewSumAccum',
            mode = 'RO',
            offset = 0x10,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 32))

        # Word 3: Sq1FbNewFp[31:0] (float32), NumFluxJumps[63:32] (int32)
        self.add(pr.RemoteVariable(
            name = 'Sq1FbNewFp',
            mode = 'RO',
            offset = 0x18,
            base = pr.Float,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'NumFluxJumps',
            mode = 'RO',
            offset = 0x18,
            base = pr.Int,
            bitSize = 32,
            bitOffset = 32))

        # Word 4: Sq1FbInt[13:0] (uint14), pad[15:14], AccumSamples[23:16] (uint8),
        #          pad[31:24], DropCount[63:32] (uint32)
        self.add(pr.RemoteVariable(
            name = 'Sq1FbInt',
            mode = 'RO',
            offset = 0x20,
            base = pr.UInt,
            bitSize = 14,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'AccumSamples',
            mode = 'RO',
            offset = 0x20,
            disp = '{:d}',
            base = pr.UInt,
            bitSize = 8,
            bitOffset = 16))

        self.add(pr.RemoteVariable(
            name = 'DropCount',
            mode = 'RO',
            offset = 0x20,
            disp = '{:d}',
            base = pr.UInt,
            bitSize = 32,
            bitOffset = 32))

        self.add(pr.ArrayDevice(
            name = 'RowPids',
            groups = ['NoConfig'],
            arrayClass = PidRowDebuggerFp,
            number = numRows,
            arrayArgs = [{
                'name': f'PID[{row}]',
                'row' : row,
                'debugDev': self} for row in range(numRows)]))

    def _start(self):
        super()._start()
        if self._worker is None:
            self._worker = threading.Thread(target=self._drain, name=f'PidDebugFp[{self.col}]',
                                            daemon=True)
            self._worker.start()

    def _stop(self):
        # Base _stop clears RxEnable so no further frames enqueue; then drain the
        # worker with a sentinel and join it.
        super()._stop()
        worker, self._worker = self._worker, None
        if worker is not None:
            self._queue.put(None)
            worker.join(timeout=2.0)

    def process(self, frame):
        # Runs on the Rogue receive thread with the frame lock held: copy the
        # bytes and hand off. All decode/SRP/variable work happens in _drain.
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)
        try:
            self._queue.put_nowait(raw)
        except queue.Full:
            self.SwDropCount.set(self.SwDropCount.value() + 1)

    def _drain(self):
        while True:
            raw = self._queue.get()
            if raw is None:
                return
            try:
                self._handleRaw(raw)
            except Exception as exc:  # never let one bad frame kill the worker
                self._log.error('FP PID debug worker error: %s', exc)

    def _handleRaw(self, raw):
        try:
            msg = warm_tdm.PidDebugFp.from_numpy(np.frombuffer(raw, dtype=np.uint8))
        except (ValueError, IndexError) as exc:
            self._log.warning('Invalid FP PID debug frame: %s', exc)
            return
        if msg.col != self.col or msg.row not in self.RowPids.PID:
            self._log.warning('Ignoring FP PID frame for column %s, row %s', msg.col, msg.row)
            return

        # Drop frames still inside the row's ~10 Hz display interval before any
        # further work: at muxed-run rates (thousands of visits/s/row) the block
        # read, checkBlocks and per-visit variable updates below would otherwise
        # flood Rogue's variable-notify pipeline and stall unrelated updates.
        if self.RowPids.PID[msg.row].throttled(msg):
            return

        # Strip the 16-byte self-describing header; the register map addresses the
        # 40-byte body, so copy only the body into the MemEmulate backing store.
        body = raw[warm_tdm.FRAME_HEADER_BYTES:]
        for i, byte in enumerate(body):
            self.mem._data[i] = byte

        self.readBlocks()
        self.checkBlocks()

        self.RowPids.PID[msg.row].updateFromParser(msg)
