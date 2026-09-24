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
from pydm import PyDMApplication, data_plugins
from pydm.utilities import connection

ROOT = Path(__file__).resolve().parents[2]
load_package_exports('warm_tdm', ROOT / 'firmware/python/warm_tdm',
                     {'_PidLockMonitor', '_PidDebugger', '_PidDebuggerFp', '_PidDebugFilter', '_DataFormats'})
load_package_exports('warm_tdm_api.widgets', ROOT / 'software/python/warm_tdm_api/widgets',
                     {'_plot_style', '_pid_history', '_pid_selection', '_pid_source', '_pid_channel_picker', '_pid_lock_tab'})
import warm_tdm
from warm_tdm import PidLockMonitor, PidDebugger, PidDebuggerFp, PidDebugFilter, DAC, FULL
from warm_tdm_api.widgets import PidLockTab, PidChannelPicker
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialogButtonBox


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
    faulthandler.dump_traceback_later(60)
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
    widget = other = None
    try:
        print('Starting synthetic Rogue root', flush=True)
        root.start()
        print('Connecting PyDM', flush=True)
        widget = PidLockTab(init_channel=f'rogue://127.0.0.1:{server.port()}/GroupRoot.Group')
        widget.resize(1150, 820)
        widget.show()
        connection.establish_widget_connections(widget)
        pump(app, 1)
        assert widget._built and widget._source is not None
        # The tab opens empty and writes no hardware enable until a channel is added.
        assert not widget._entries and widget._enabled_columns == set()
        assert all(not dsp.PidDebugEnable.value() for dsp in dsps.values())
        picker = PidChannelPicker(widget._source.topology, widget._entries, widget)
        picker.columns.setText('0, 3, 8')
        picker.rows.setText('10-15')
        assert len(picker.pairs) == 18 and '3 columns × 6 rows = 18' in picker.preview.text()
        picker.show()
        pump(app)
        if os.getenv('PID_MONITOR_SCREENSHOT'):
            path = Path(os.environ['PID_MONITOR_SCREENSHOT'])
            assert picker.grab().save(str(path.with_stem(path.stem + '-picker')))
        picker.rows.setText('0-999999999999')
        assert not picker.buttons.button(QDialogButtonBox.Ok).isEnabled()
        picker.close()
        # The picker excludes channels already selected in the window.
        widget.add_channels([(0, 0)])
        picker = PidChannelPicker(widget._source.topology, widget._entries, widget)
        picker.columns.setText('0')
        picker.rows.setText('0')
        assert not picker.pairs  # Already selected.
        picker.close()
        widget.remove_channels(list(widget._entries))
        widget.add_channels([(0, 10), (0, 11), (8, 10)])
        other = PidLockTab(init_channel=widget.channel)
        other.resize(1150, 820)
        other.show()
        pump(app, 1)
        other.remove_channels(list(other._entries))
        other.add_channels([(0, 11)])
        assert widget._source.client is other._source.client
        assert set(other._entries) == {(0, 11)}
        assert monitor.ColumnSelect.value() == 0 and monitor.RowSelect.value() == 0
        # Selecting channels auto-enables each selected column's stream (widget
        # has columns 0 and 8 selected); the enabling window tracks what it turned on.
        assert dsps[0].PidDebugEnable.value() and dsps[8].PidDebugEnable.value()
        assert widget._enabled_columns == {0, 8}
        # 'other' selected column 0 after 'widget' already enabled it, so 'other'
        # does not claim it and will not disable it out from under 'widget'.
        assert other._enabled_columns == set()

        def send_fixed(i, row):
            full = 3800 + i * 140 + (row - 10) * 200
            count = max(0, (full - 2500) // 2000)
            wrapped = full - count * 2000
            header = struct.pack('<4BIQ', 1, 3, 0, 0, 0, int((1 + i * 0.15) * 1e9))
            words = [row << 8, int(200 * np.exp(-i / 5)), 8191, 0, 0, 0,
                     wrapped << 23, count, 8191, 16]
            sources[0].send(header + struct.pack('<10Q', *words))
            return full, wrapped

        def send_fp(i):
            fp = (struct.pack('<4BIQ', 2, 1, 0, 1, 0, int((1 + i * .15) * 1e9)) +
                  struct.pack('<QfffffiHBBI', 10 << 8, 48, 987, 1, 2,
                              1800.25 + i * 30, 1, (-200 + i * 30) & 0x3fff, 16, 0, 0))
            sources[1].send(fp)

        for i in range(25):
            full, wrapped = send_fixed(i, 10)
            send_fixed(i, 11)
            send_fp(i)
            pump(app)
        for entry in widget._entries.values():
            assert len(entry['history'].samples) > 10
        history = widget._entries[0, 10]['history']
        assert history.last[FULL] == full and history.last[DAC] == wrapped
        assert debuggers[0].RowPids.PID[10].Visits.value() == 25
        assert widget._entries[8, 10]['history'].last[FULL] == 1800.25 + 24 * 30
        assert other._entries[0, 11]['history'].last is not None
        widget._mode.setCurrentIndex(2)
        widget._window.setValue(5)
        pump(app)
        assert len(widget._curves) == 12
        if os.getenv('PID_MONITOR_SCREENSHOT'):
            assert widget.grab().save(os.environ['PID_MONITOR_SCREENSHOT'])
        # Hide/reveal affects only presentation, retaining subscriptions/history.
        kept = len(widget._entries[0, 10]['history'].samples)
        widget._table.item(0, 0).setCheckState(Qt.Unchecked)
        assert ((0, 10), DAC) not in widget._curves
        assert len(widget._entries[0, 10]['history'].samples) == kept
        widget._table.item(0, 0).setCheckState(Qt.Checked)
        assert ((0, 10), DAC) in widget._curves
        widget._layout_mode.setCurrentIndex(1)
        pump(app)
        assert len(widget._plots) == 9
        if os.getenv('PID_MONITOR_SCREENSHOT'):
            path = Path(os.environ['PID_MONITOR_SCREENSHOT'])
            assert widget.grab().save(str(path.with_stem(path.stem + '-panels')))
        widget._layout_mode.setCurrentIndex(0)
        widget._mode.setCurrentIndex(1)
        assert len(widget._plots) == 2 and len(widget._curves) == 6
        assert ((0, 10), DAC) not in widget._curves

        # Pause freezes history; resume starts clean without replaying queued data.
        widget._pause.click()
        assert widget._age.text() == 'Paused'
        send_fixed(25, 10)
        pump(app)
        assert history.last[FULL] == full
        widget._pause.click()
        assert not history.samples
        send_fixed(26, 10)
        pump(app)
        assert history.last is not None

        # A removed/re-added selection has a fresh history, not cached telemetry.
        widget._table.selectRow(list(widget._entries).index((0, 11)))
        widget._remove_selected()
        assert dsps[0].PidDebugEnable.value() and dsps[8].PidDebugEnable.value()
        send_fixed(26, 11)
        pump(app)
        assert other._entries[0, 11]['history'].last is not None
        widget.add_channels([(0, 11)])
        assert widget._entries[0, 11]['history'].last is None
        send_fixed(27, 11)
        pump(app)
        assert widget._entries[0, 11]['history'].last is not None

        # Closing a window must not stop the shared client or the other window.
        other.close()
        assert not other._source._listeners
        send_fixed(28, 10)
        pump(app)
        assert widget._entries[0, 10]['history'].last[FULL] == 3800 + 28 * 140
        assert widget._source.client.linked
        # Exercise the same callback used by actual link transitions.
        widget._source._link_changed(False)
        pump(app)
        assert widget._age.text() == 'Disconnected'
        assert not any(e['history'].samples for e in widget._entries.values())
        # A link drop forgets our enable ownership (we cannot safely toggle while
        # unlinked); the re-sync on reconnect re-evaluates against live hardware.
        assert widget._enabled_columns == set()
        widget._source._link_changed(True)
        pump(app)
        send_fixed(29, 10)
        pump(app)
        assert widget._entries[0, 10]['history'].last is not None
        # Columns 0 and 8 were still enabled in hardware across the blip, so the
        # re-sync leaves them on without re-claiming them.
        assert dsps[0].PidDebugEnable.value() and dsps[8].PidDebugEnable.value()
        print('PASS: multi-row/board streams, independent windows, layouts, enables, pause, remove/re-add and teardown')
    finally:
        if other is not None:
            other.close()
            other.deleteLater()
        if widget is not None:
            widget.close()
            widget.deleteLater()
            pump(app)
            if widget._source is not None:
                widget._source.client.stop()
        root.stop()
        faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':
    main()
