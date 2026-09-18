##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
import time
import pyrogue as pr
import pyrogue.interfaces.simulation
import numpy as np
import warm_tdm


class PidRowDebuggerBase(pr.Device):
    """Common coherent sample on the existing integer/FP per-row diagnostics."""

    def __init__(self, debugDev, row, **kwargs):
        super().__init__(**kwargs)
        self.debugDev = debugDev
        self.row = row
        self._nextSampleAt = 0.0
        self._sampleConfig = None
        self.add(pr.LocalVariable(
            name='Sample', mode='RO', typeStr='Float64[np]',
            value=np.full(warm_tdm.SAMPLE_SIZE, np.nan),
            description='One PID visit: FPGA time (s), global column, row, signed DAC, '
                        'full feedback, net wraps, mean error, drops, format, wrap period, flags.',
            groups=['NoConfig', 'NoStream', 'NoState']))

    def updateSample(self, msg):
        # Use the decoded frame, never a series of independently updated scalar
        # variables. Cached DSP configuration avoids SRP I/O in the receive thread.
        dsp = self.debugDev._dsp
        if dsp is None:
            quantum, committed = float('nan'), False
        else:
            quantumVar = (dsp.FluxQuantumFpRaw if msg.header.formatType == warm_tdm.FormatType.PID_FLOAT
                          else dsp.FluxQuantumRaw)
            quantum = quantumVar.value()
            committed = bool(dsp.PidEnableRaw.value() and (dsp.RowEnableMask.value() >> self.row) & 1)
        config = (quantum if np.isfinite(quantum) else None, committed, msg.header.formatVersion)
        now = time.monotonic()
        if now < self._nextSampleAt and config == self._sampleConfig:
            return
        self.Sample.set(warm_tdm.pid_debug_sample(msg, quantum=quantum, committed=committed))
        self._nextSampleAt, self._sampleConfig = now + 0.1, config


class PidRowDebugger(PidRowDebuggerBase):
    def __init__(self, debugDev, row, **kwargs):
        super().__init__(debugDev=debugDev, row=row, **kwargs)
        self.parsedVars = ['AccumError', 'SumAccum', 'Diff', 'PidResult', 'Sq1FbPre', 'Sq1FbPost',
                           'Sq1FbFull', 'FluxJumps', 'NumSamples', 'ReadoutCount']

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
            name = 'Sq1FbFull',
            description = 'Post-wrap/clamp fractional feedback in signed DAC-code units (NaN for v1 frames).',
            mode = 'RO',
            disp = '{:0.09f}',
            value = float('nan')))

        self.add(pr.LocalVariable(
            name = 'FluxJumps',
            mode = 'RO',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'NumSamples',
            mode = 'RO',
            disp = '{:d}',
            value = 0))

        self.add(pr.LocalVariable(
            name = 'ReadoutCount',
            mode = 'RO',
            disp = '{:d}',
            value = 0))
        

    def updateFromParser(self, msg):
        with self.root.updateGroup():
            for varName in self.parsedVars:
                self.variables[varName].set(self.debugDev.variables[varName].get(read=False))
            self.Visits.set(self.Visits.get() + 1)
            self.updateSample(msg)
        


class PidDebugger(pr.DataReceiver):

    def __init__(self, numRows, col, frontEnd, dsp=None, **kwargs):
        self.mem = pyrogue.interfaces.simulation.MemEmulate()

        self.col = col
        self._dsp = dsp

        super().__init__(memBase=self.mem, **kwargs)

        self.add(pr.LocalVariable(
            name = 'Sq1FbFull',
            description = 'Post-wrap/clamp fractional feedback in signed DAC-code units (NaN for v1 frames).',
            mode = 'RO',
            disp = '{:0.09f}',
            value = float('nan')))

        self.add(pr.RemoteVariable(
            name = 'Column',
            mode = 'RO',
            offset = 0 * 8,
            base = pr.UInt,
            bitSize = 4))

        self.add(pr.RemoteVariable(
            name = 'LogicalRow',
            description = 'Logical row this PID-debug frame belongs to.',
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
            # Body word 1 (was word 2 pre-split; the baseline word 1 is gone).
            offset = 1 * 8,
            base = warm_tdm.AdcDsp.ACCUM_BASE,
            bitSize = warm_tdm.AdcDsp.ACCUM_BASE.bitSize))

        self.add(pr.RemoteVariable(
            name = 'SumAccum',
            mode = 'RO',
            offset = 3 * 8,
            base = warm_tdm.AdcDsp.ACCUM_BASE,
            bitSize = warm_tdm.AdcDsp.ACCUM_BASE.bitSize))


        self.add(pr.RemoteVariable(
            name = 'Diff',
            mode = 'RO',
            offset = 4 * 8,
            base = warm_tdm.AdcDsp.ACCUM_BASE,
            bitSize = warm_tdm.AdcDsp.ACCUM_BASE.bitSize))

        self.add(pr.RemoteVariable(
            name = 'PidResult',
            mode = 'RO',
            offset = 5 * 8,
            disp = '{:0.03f}',
            base = warm_tdm.AdcDsp.RESULT_BASE,
            bitSize = warm_tdm.AdcDsp.RESULT_BASE.bitSize))

        self.add(pr.RemoteVariable(
            name = 'Sq1FbPreRaw',
            mode = 'RO',
            offset = 2 * 8,
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
            offset = 7 * 8,
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
            offset = 6 * 8,
            base = pr.Int,
            bitSize = 32,
            bitOffset = 0))

        self.add(pr.RemoteVariable(
            name = 'DropCount',
            mode = 'RO',
            disp = '{:d}',
            base = pr.UInt,
            offset = 7*8,
            bitOffset = 32))

        self.add(pr.RemoteVariable(
            name = 'NumSamples',
            mode = 'RO',
            disp = '{:d}',
            base = pr.UInt,
            offset = 8 * 8))

        self.add(pr.RemoteVariable(
            name = 'ReadoutCount',
            mode = 'RO',
            disp = '{:d}',
            base = pr.UInt,
            bitOffset = 32,
            offset = 8 * 8))
        

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
        fl = frame.getPayload()
        raw = bytearray(fl)
        frame.read(raw, 0)

        #print(f'Got PID Debug frame for col {self.col}, row {raw[1]}, size {fl}')
        try:
            msg = warm_tdm.PidDebug.from_numpy(np.frombuffer(raw, dtype=np.uint8))
        except (ValueError, IndexError) as exc:
            print(f'Invalid PID debug frame: {exc}')
            return
        if msg.col != self.col or msg.row not in self.RowPids.PID:
            self._log.warning('Ignoring PID frame for column %s, row %s', msg.col, msg.row)
            return

        # Keep the existing diagnostic register offsets for both frame versions.
        # Decode the v2/v3 fractional word separately and remove it for this legacy
        # 72-byte MemEmulate map; never interpret an absent v1 value as zero.
        body = raw[warm_tdm.FRAME_HEADER_BYTES:]
        if 'sq1FbFull' in msg.fields:
            body = body[:48] + body[56:]
        # V1/v2 stored only eight count bits. Normalize the sign before the live
        # register view reads it (v3 carries a sign-extended int32).
        body[48:52] = msg.fields['numFluxJumps'].to_bytes(4, 'little', signed=True)
        for i, byte in enumerate(body):
            self.mem._data[i] = byte

        self.Sq1FbFull.set(msg.fields.get('sq1FbFull', float('nan')))
        self.readBlocks()
        self.checkBlocks()

        self.RowPids.PID[msg.row].updateFromParser(msg)
