import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np
import warm_tdm

class PidRowDebugger(pr.Device):
    def __init__(self, debugDev, row, **kwargs):
        super().__init__(**kwargs)

        self.debugDev = debugDev
        self.row = row
        self.parsedVars = ['AccumError', 'SumAccum', 'Diff', 'PidResult', 'Sq1FbPre', 'Sq1FbPost', 'FluxJumps']

        self.add(pr.LocalVariable(
            name = 'Visits',
            mode = 'RO',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'AccumError',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'SumAccum',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'Diff',
            mode = 'RO',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'PidResult',
            mode = 'RO',
            disp = '{:0.03f}',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'Sq1FbPre',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'Sq1FbPost',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            value = 0.0))

        self.add(pr.LocalVariable(
            name = 'FluxJumps',
            mode = 'RO',
            value = 0))

    def updateFromParser(self):
        with self.root.updateGroup():
            for varName in self.parsedVars:
                self.variables[varName].set(self.debugDev.variables[varName].get(read=False))
            self.Visits.set(self.Visits.get() + 1)
        


class PidDebugger(pr.DataReceiver):

    def __init__(self, numRows, col, frontEnd, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()

        self.col = col

        super().__init__(memBase=self.mem, **kwargs)

        self.add(pr.RemoteVariable(
            name = 'Column',
            mode = 'RO',
            offset = 0 * 8,
            base = pr.UInt,
            bitSize = 3))

        self.add(pr.RemoteVariable(
            name = 'RowIndex',
            mode = 'RO',
            offset = 0,
            disp = '{:d}',
            base = pr.UInt,
            bitOffset = 8,
            bitSize = 8))

        self.add(pr.RemoteVariable(
            name = 'RunTime',
            mode = 'RO',
            offset = 0,
            bitOffset = 16,
            bitSize = 48,
            disp = '{:d}',
            base = pr.UInt))

        self.add(pr.RemoteVariable(
            name = 'AccumError',
            mode = 'RO',
            offset = 2 * 8,
            base = warm_tdm.AdcDsp.ACCUM_BASE,
            bitSize = warm_tdm.AdcDsp.ACCUM_BASE.bitSize))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            mode = 'RO',
            offset = 4 * 8,
            base = warm_tdm.AdcDsp.ACCUM_BASE,
            bitSize = warm_tdm.AdcDsp.ACCUM_BASE.bitSize))


        self.add(pr.RemoteVariable(
            name = 'Diff',
            mode = 'RO',
            offset = 5 * 8,
            base = warm_tdm.AdcDsp.ACCUM_BASE,
            bitSize = warm_tdm.AdcDsp.ACCUM_BASE.bitSize))

        self.add(pr.RemoteVariable(
            name = 'PidResult',
            mode = 'RO',
            offset = 6 * 8,
            disp = '{:0.03f}',
            base = warm_tdm.AdcDsp.RESULT_BASE,
            bitSize = warm_tdm.AdcDsp.RESULT_BASE.bitSize))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPreRaw',
            mode = 'RO',
            offset = 3 * 8,
            base = pr.UInt,
            bitSize = 14))

        self.add(pr.LinkVariable(
            name = 'Sq1FbPre',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            dependencies = [self.Sq1FbPreRaw, self.Column],
            linkedGet = lambda: frontEnd.Channel[self.Column.value()].SQ1FbAmp.dacToOutCurrent(self.Sq1FbPreRaw.value())))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPostRaw',
            mode = 'RO',
            offset = 8 * 8,
            base = pr.UInt,
            bitSize = 14))

        self.add(pr.LinkVariable(
            name = 'Sq1FbPost',
            mode = 'RO',
            disp = '{:0.03f}',
            units = u'\u03bcA',
            dependencies = [self.Sq1FbPostRaw, self.Column],
            linkedGet = lambda: frontEnd.Channel[self.Column.value()].SQ1FbAmp.dacToOutCurrent(self.Sq1FbPostRaw.value())))

        self.add(pr.RemoteVariable(
            name = 'FluxJumps',
            mode = 'RO',
            offset = 7 * 8,
            base = pr.Int,
            bitSize = 8,
            bitOffset = 0))

        self.add(pr.ArrayDevice(
            name = 'RowPids',
            groups = ['NoConfig'],
            arrayClass = PidRowDebugger,
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

        #print(f'Got PID Debug frame for col {self.col}, row {raw[1]}, size {fl}')
        if fl != 72:
            return

        # Overwrite the MemEmulate data with new frame
        for i, byte in enumerate(raw):
            self.mem._data[i] = byte

        self.readBlocks()
        self.checkBlocks()

        row = self.RowIndex.get(read=False)
        self.RowPids.PID[row].updateFromParser()
