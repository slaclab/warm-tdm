##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Explicit real Rogue/ZMQ/PyDM/Qt smoke with synthetic hardware (no board I/O).

Run with a Rogue/PyDM environment and QT_QPA_PLATFORM=offscreen if headless.
Loads monitor exports from package initializers without unrelated board drivers.
Set PID_MONITOR_SCREENSHOT to save a rendered GUI example.
"""
import os
import faulthandler
from pathlib import Path
import struct
import time
from types import SimpleNamespace

import numpy as np
import pyrogue as pr
import pyrogue.interfaces
import rogue.interfaces.stream
from pid_monitor_imports import load_package_exports

# Use the installed Rogue plugin with the installed Qt binding.
os.environ['PYDM_DATA_PLUGINS_PATH'] = str(Path(pr.__file__).parent / 'pydm/data_plugins')
from pydm import PyDMApplication
from pydm.utilities import connection

ROOT = Path(__file__).resolve().parents[2]
load_package_exports('warm_tdm', ROOT / 'firmware/python/warm_tdm',
                     {'_PidLockMonitor', '_PidDebugger', '_PidDebuggerFp', '_PidDebugFilter', '_DataFormats'})
load_package_exports('warm_tdm_api.widgets', ROOT / 'software/python/warm_tdm_api/widgets',
                     {'_pid_history', '_pid_lock_tab'})
import warm_tdm
from warm_tdm import PidLockMonitor, PidDebugger, PidDebuggerFp, PidDebugFilter, DAC, FULL
from warm_tdm_api.widgets import PidLockTab


class Source(rogue.interfaces.stream.Master):
    def send(self, raw):
        frame = self._reqFrame(len(raw), True)
        with frame.lock():
            frame.write(bytearray(raw), 0)
        self._sendFrame(frame)


def pump(app, seconds=0.15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def main():
    faulthandler.dump_traceback_later(30)
    app = PyDMApplication(use_main_window=False, command_line_args=[])
    root = pr.Root(name='GroupRoot', pollEn=False)
    group = pr.Device(name='Group')
    hardware = pr.Device(name='HardwareGroup')
    group.add(hardware)
    root.add(group)
    dsps = {}
    debuggers = {}
    sources = {board: Source() for board in range(2)}
    # Register-format fixtures avoid loading unrelated ADC/filter hardware drivers.
    warm_tdm.AdcDsp = SimpleNamespace(ACCUM_BASE=pr.Fixed(18, 0), RESULT_BASE=pr.Fixed(48, 23))
    front_end = SimpleNamespace(Channel={
        col: SimpleNamespace(SQ1FbAmp=SimpleNamespace(dacToOutCurrent=float)) for col in range(8)})
    for board in range(2):
        cb = pr.Device(name=f'ColumnBoard[{board}]')
        dp = pr.Device(name='DataPath')
        cb.add(dp)
        hardware.add(cb)
        for column in range(8):
            dsp = pr.Device(name=f'AdcDsp[{column}]')
            for name, value in [('FluxQuantumRaw' if board == 0 else 'FluxQuantumFpRaw', 2000),
                                ('PidEnableRaw', True), ('RowEnableMask', 0xffff),
                                ('PidDebugEnable', False)]:
                dsp.add(pr.LocalVariable(name=name, value=value))
            dp.add(dsp)
            dsps[board * 8 + column] = dsp
            debug_class = PidDebugger if board == 0 else PidDebuggerFp
            debug_args = dict(frontEnd=front_end) if board == 0 else {}
            debugger = debug_class(name=f'PidDebug[{board * 8 + column}]',
                                   numRows=16, col=column, dsp=dsp, **debug_args)
            hardware.add(debugger)
            debuggers[board * 8 + column] = debugger
            sources[board] >> PidDebugFilter(column=column) >> debugger
    monitor = PidLockMonitor(name='PidLockMonitor', debuggers=debuggers, rows=16)
    hardware.add(monitor)
    assert not isinstance(monitor, pr.DataReceiver)
    server = pyrogue.interfaces.ZmqServer(root=root, addr='127.0.0.1', port=0)
    root.addInterface(server)
    widget = None
    try:
        print('Starting synthetic Rogue root', flush=True)
        root.start()
        print('Connecting PyDM', flush=True)
        widget = PidLockTab(init_channel=f'rogue://127.0.0.1:{server.port()}/GroupRoot.Group')
        widget.resize(1150, 820)
        widget.show()
        connection.establish_widget_connections(widget)
        pump(app, 1)
        assert widget._built and hasattr(widget, '_curves')
        assert all(not dsp.PidDebugEnable.value() for dsp in dsps.values())

        # GUI-side channel writes must reach the selected column's enable only.
        widget._debug_enable.click()
        pump(app)
        assert dsps[0].PidDebugEnable.value()
        assert not dsps[8].PidDebugEnable.value()
        monitor.RowSelect.set(10)
        pump(app)
        assert widget._row == 10

        for i in range(25):
            full = 3800 + i * 140
            count = max(0, (full - 2500) // 2000)
            wrapped = full - count * 2000
            header = struct.pack('<4BIQ', 1, 3, 0, 0, 0, int((1 + i * 0.15) * 1e9))
            words = [10 << 8, int(200 * np.exp(-i / 5)), 8191, 0, 0, 0,
                     wrapped << 23, count, 8191, 16]
            sources[0].send(header + struct.pack('<10Q', *words))
            pump(app)
        assert len(widget._history.samples) > 10
        assert widget._history.last[FULL] == full
        assert widget._history.last[DAC] == wrapped
        assert debuggers[0].RowPids.PID[10].Visits.value() == 25
        assert debuggers[0].RowPids.PID[10].NumSamples.value() == 16
        np.testing.assert_array_equal(monitor.Sample.value(), debuggers[0].RowPids.PID[10].Sample.value())
        widget._mode.setCurrentIndex(2)
        widget._window.setValue(5)
        pump(app)
        assert widget._curves[FULL].isVisible() and widget._curves[DAC].isVisible()
        if os.getenv('PID_MONITOR_SCREENSHOT'):
            assert widget.grab().save(os.environ['PID_MONITOR_SCREENSHOT'])

        widget._pause.click()
        assert widget._age.text() == 'Paused'
        widget._pause.click()
        assert not widget._history.samples
        monitor.ColumnSelect.set(8)
        pump(app)
        assert widget._column == 8
        assert not widget._history.samples
        assert widget._debug_enable.channel.endswith('.PidLockMonitor.PidDebugEnable')
        assert not monitor.PidDebugEnable.get(read=False)
        assert dsps[0].PidDebugEnable.value()  # Selection does not change hardware.
        widget._debug_enable.click()
        pump(app)
        assert dsps[8].PidDebugEnable.value()
        fp = (struct.pack('<4BIQ', 2, 1, 0, 1, 0, 20_000_000_000) +
              struct.pack('<QfffffiHBBI', 10 << 8, 48, 987, 1, 2,
                          1800.25, 1, (-200) & 0x3fff, 16, 0, 0))
        sources[1].send(fp)
        deadline = time.monotonic() + 3
        while widget._history.last is None and time.monotonic() < deadline:
            pump(app)
        assert widget._history.last is not None, (monitor.Status.value(), monitor.Sample.value())
        assert widget._history.last[FULL] == 1800.25
        assert widget._history.last[DAC] == -200
        assert debuggers[8].RowPids.PID[10].Sq1FbNewFp.value() == 1800.25
        assert debuggers[8].RowPids.PID[10].Visits.value() == 1
        widget._mode.setCurrentIndex(1)
        assert not widget._curves[DAC].isVisible()
        assert not widget._flux.isVisible()
        print('PASS: live Rogue stream -> ZMQ -> PyDM plots, enable, selection, pause and FP switch')
    finally:
        if widget is not None:
            connection.close_widget_connections(widget)
            widget.close()
            widget.deleteLater()
            pump(app)
        root.stop()
        faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':
    main()
