#-----------------------------------------------------------------------------
# This file is part of the 'warm-tdm' project. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'warm-tdm' project, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np
import warm_tdm


class PidRowDebuggerFp(pr.Device):
    def __init__(self, debugDev, row, **kwargs):
        super().__init__(**kwargs)

        self.debugDev = debugDev
        self.row = row
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

    def updateFromParser(self):
        with self.root.updateGroup():
            for varName in self.parsedVars:
                self.variables[varName].set(self.debugDev.variables[varName].get(read=False))
            self.Visits.set(self.Visits.get() + 1)


class PidDebuggerFp(pr.DataReceiver):

    def __init__(self, numRows, col, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()

        self.col = col

        super().__init__(memBase=self.mem, **kwargs)

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

    def process(self, frame):
        channel = frame.getChannel()
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)

        if fl != warm_tdm.PID_DEBUG_FP_FRAME_BYTES:
            print(f'Got PID FP debug frame with wrong size {fl}')
            return

        # Strip the 16-byte self-describing header; the register map addresses the
        # 40-byte body, so copy only the body into the MemEmulate backing store.
        body = raw[warm_tdm.FRAME_HEADER_BYTES:]
        for i, byte in enumerate(body):
            self.mem._data[i] = byte

        self.readBlocks()
        self.checkBlocks()

        row = self.RowIndex.get(read=False)
        self.RowPids.PID[row].updateFromParser()
