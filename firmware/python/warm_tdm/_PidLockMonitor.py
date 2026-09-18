##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
import numpy as np
import pyrogue as pr

import warm_tdm


class PidLockMonitor(pr.Device):
    """Stable GUI channels selecting the existing per-row PID-debug samples.

    The existing receivers own frame decoding and sample publication. This
    adapter forwards their complete snapshots, never independently read scalar
    values. Selection is shared by clients and leaves hardware enables unchanged.
    """

    def __init__(self, *, debuggers, rows, **kwargs):
        super().__init__(**kwargs)
        self._selection = (min(debuggers), 0)
        dsps = {col: debugger._dsp for col, debugger in debuggers.items()}
        self.add(pr.LocalVariable(name='ColumnSelect', value=min(debuggers), minimum=min(debuggers),
                                  maximum=max(dsps), groups=['NoConfig']))
        self.add(pr.LocalVariable(name='RowSelect', value=0, minimum=0,
                                  maximum=rows - 1, groups=['NoConfig']))
        self.add(pr.LinkVariable(
            name='PidDebugEnable', mode='RW', base=pr.Bool, groups=['NoConfig'],
            description='Debug-stream enable for the selected column; selection does not change enables.',
            dependencies=[self.ColumnSelect] + [dsp.PidDebugEnable for dsp in dsps.values()],
            linkedGet=lambda read: dsps[self.ColumnSelect.value()].PidDebugEnable.get(read=read),
            linkedSet=lambda value, write: dsps[self.ColumnSelect.value()].PidDebugEnable.set(bool(value), write=write)))
        self.add(pr.LocalVariable(name='Sample', value=np.full(warm_tdm.SAMPLE_SIZE, np.nan),
                                  typeStr='Float64[np]', mode='RO',
                                  groups=['NoConfig', 'NoStream', 'NoState']))
        self.add(pr.LocalVariable(name='Status', value='Waiting for PID-debug frames',
                                  mode='RO', groups=['NoConfig']))
        self.ColumnSelect.addListener(self._selectionChanged)
        self.RowSelect.addListener(self._selectionChanged)
        for debugger in debuggers.values():
            for row in debugger.RowPids.PID.values():
                row.Sample.addListener(self._sampleChanged)

    def _selectionChanged(self, path, value):
        selection = (self.ColumnSelect.value(), self.RowSelect.value())
        if selection != self._selection:
            self._selection = selection
            self.Sample.set(np.full(warm_tdm.SAMPLE_SIZE, np.nan))
            self.Status.set('Waiting for PID-debug frames')

    def _sampleChanged(self, path, value):
        # A queued callback may run after selection changed. Match the identity
        # embedded in the snapshot against the current selection before forwarding.
        self._selectionChanged(None, None)
        sample = value.value
        if (sample[warm_tdm.COLUMN], sample[warm_tdm.ROW]) != self._selection:
            return
        self.Sample.set(sample)
        self.Status.set('Receiving FP PID' if sample[warm_tdm.FORMAT] == warm_tdm.FormatType.PID_FLOAT
                        else 'Receiving integer PID')
