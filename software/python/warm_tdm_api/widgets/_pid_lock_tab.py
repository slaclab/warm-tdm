##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Client-local multi-channel PID plots using existing per-row sample publications."""
import time

import numpy as np
from pydm import data_plugins
from pydm.widgets.waveformplot import PyDMWaveformPlot, WaveformCurveItem
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QColor, QIcon, QPixmap
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QScrollArea, QMessageBox,
)
from warm_tdm import (
    TIME, COLUMN, ROW, DAC, FULL, JUMPS, ERROR, DROPS, FLAGS,
    FULL_UNAVAILABLE, NOT_COMMITTED, SAMPLE_SIZE,
)
from warm_tdm_api.widgets import (
    PidHistory, PidSampleSource, PidChannelPicker, MAX_PLOT_CHANNELS,
    channel_label, style_display, style_live_plot, TRACE_COLORS,
)

CHANNEL_COLORS = TRACE_COLORS + ('#ad4778', '#667322', '#485db0', '#875536')


class PidLockTab(QWidget):
    """``init_channel`` addresses a Group. Selection belongs only to this widget.

    Dynamic listeners deliberately bypass PyDM channel teardown, which stops the
    shared VirtualClient in some Rogue versions. This widget never stops it.
    """

    def __init__(self, parent=None, init_channel=None):
        super().__init__(parent)
        self.channel = init_channel
        self._source = None
        self._entries = {}
        self._plots = []
        self._curves = {}
        self._linked = False
        self._epoch = None
        self._built = False
        self._next_color = 0
        # Columns whose PID-debug stream this widget turned on (it was off when we
        # selected it). We disable exactly these on deselect/close, never a column
        # another client enabled. Enable is per column in hardware, not per row.
        self._enabled_columns = set()
        style_display(self)
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)
        QTimer.singleShot(0, self._connect_source)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        title = QLabel('PID lock monitor')
        title.setObjectName('plotHeading')
        heading.addWidget(title)
        heading.addStretch()
        self._age = QLabel('Connecting…')
        self._age.setObjectName('plotStatus')
        heading.addWidget(self._age)
        layout.addLayout(heading)

        options = QHBoxLayout()
        self._mode = QComboBox()
        self._mode.addItems(['DAC + flux jumps', 'Full feedback', 'Both'])
        options.addWidget(self._mode)
        self._layout_mode = QComboBox()
        self._layout_mode.addItems(['Overlay', 'Separate panels'])
        options.addWidget(self._layout_mode)
        options.addWidget(QLabel('History'))
        self._window = QSpinBox()
        self._window.setRange(5, 600)
        self._window.setValue(60)
        self._window.setSuffix(' s')
        options.addWidget(self._window)
        self._pause = QPushButton('Pause')
        self._pause.setCheckable(True)
        options.addWidget(self._pause)
        clear = QPushButton('Clear history')
        options.addWidget(clear)
        options.addStretch()
        layout.addLayout(options)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 8, 0)
        buttons = QHBoxLayout()
        self._add_button = QPushButton('Add channels…')
        self._add_button.setEnabled(False)
        buttons.addWidget(self._add_button)
        remove = QPushButton('Remove')
        buttons.addWidget(remove)
        clear_selection = QPushButton('Clear list')
        buttons.addWidget(clear_selection)
        side.addLayout(buttons)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(['Show', 'Channel', 'Status'])
        self._table.verticalHeader().hide()
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        side.addWidget(self._table, 1)
        self._selection_note = QLabel('Add channels to begin.')
        self._selection_note.setWordWrap(True)
        side.addWidget(self._selection_note)
        note = QLabel('Selecting a channel turns on its column’s PID-debug stream '
                      '(one shared hardware enable per column, all rows). This window '
                      'turns off the streams it enabled when you deselect them or close it.')
        note.setWordWrap(True)
        note.setObjectName('plotNote')
        side.addWidget(note)
        splitter.addWidget(sidebar)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        splitter.addWidget(self._scroll)
        splitter.setSizes([370, 800])
        splitter.setStretchFactor(1, 1)
        self._notice = QLabel()
        self._notice.setWordWrap(True)
        self._notice.hide()
        layout.addWidget(self._notice)
        self._detail = QLabel('')
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)
        footer = QLabel('Up to 10 samples/s per channel · Common hardware timebase · '
                        'Solid: DAC · Dashed: full feedback (Both mode) · Fast transients may be missed')
        footer.setObjectName('plotNote')
        footer.setWordWrap(True)
        layout.addWidget(footer)
        self._add_button.clicked.connect(self._pick_channels)
        remove.clicked.connect(self._remove_selected)
        clear_selection.clicked.connect(lambda: self.remove_channels(list(self._entries)))
        self._table.itemChanged.connect(self._visibility_changed)
        self._table.itemSelectionChanged.connect(self._show_detail)
        self._mode.currentIndexChanged.connect(self._rebuild_plots)
        self._layout_mode.currentIndexChanged.connect(self._rebuild_plots)
        self._window.valueChanged.connect(self._set_window)
        self._pause.toggled.connect(self._set_paused)
        clear.clicked.connect(self._clear)
        self._rebuild_plots()

    def _connect_source(self):
        try:
            self._source = PidSampleSource(self.channel)
            self.destroyed.connect(lambda _=None, source=self._source: source.close())
            if not self._source.topology:
                raise ValueError('No PID sample channels are available on this server.')
            self._linked, self._epoch, _ = self._source.drain()
            self._built = True
            self._add_button.setEnabled(True)
            # Start empty: selecting a channel enables its column's stream, so
            # auto-adding one would write a hardware enable just by opening the tab.
        except Exception as exc:
            self._show_error(f'Cannot connect to PID samples: {exc}')
            self._age.setText('Unavailable')

    def _pick_channels(self):
        dialog = PidChannelPicker(self._source.topology, self._entries, self)
        if dialog.exec() == dialog.Accepted:
            try:
                self.add_channels(dialog.pairs)
            except Exception as exc:
                QMessageBox.warning(self, 'Could not add channels', str(exc))

    def add_channels(self, pairs):
        pairs = sorted(set(pairs) - self._entries.keys())
        if len(pairs) + len(self._entries) > MAX_PLOT_CHANNELS:
            raise ValueError(f'Select at most {MAX_PLOT_CHANNELS} channels.')
        if any(c not in self._source.topology or r not in self._source.topology[c] for c, r in pairs):
            raise ValueError('Channel is not available on this server.')
        try:
            self._source.select(set(self._entries) | set(pairs))
        except Exception:
            self._source.select(self._entries)
            raise
        for key in pairs:
            self._entries[key] = dict(history=PidHistory(seconds=self._window.value()),
                                      color=CHANNEL_COLORS[self._next_color % len(CHANNEL_COLORS)],
                                      visible=True, received=None)
            self._next_color += 1
        self._sync_debug_enables()
        self._selection_changed()

    def remove_channels(self, pairs):
        for key in pairs:
            self._entries.pop(key, None)
        if self._source is not None:
            self._source.select(self._entries)
        self._sync_debug_enables()
        if not self._entries:
            self._next_color = 0
        self._selection_changed()

    def _sync_debug_enables(self):
        # Enable the PID-debug stream for every selected column and disable those
        # we enabled that are no longer selected. Enable is per column (all rows)
        # and shared across clients, so we only ever turn off columns we turned on
        # and never touch one another client enabled. No-op when read-only/unlinked.
        if self._source is None or not self._linked or data_plugins.is_read_only():
            return
        selected = {c for c, _ in self._entries}
        for column in sorted(selected - self._enabled_columns):
            try:
                if not self._source.debug_enabled(column):
                    self._source.set_debug(column, True)
                    self._enabled_columns.add(column)
            except Exception as exc:
                self._show_error(f'Could not enable debug stream for column {column}: {exc}')
        for column in sorted(self._enabled_columns - selected):
            try:
                self._source.set_debug(column, False)
            except Exception as exc:
                self._show_error(f'Could not disable debug stream for column {column}: {exc}')
            else:
                self._enabled_columns.discard(column)

    def _remove_selected(self):
        keys = [tuple(self._table.item(index.row(), 0).data(Qt.UserRole))
                for index in self._table.selectionModel().selectedRows()]
        self.remove_channels(keys)

    def _selection_changed(self):
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._entries))
        for row, (key, entry) in enumerate(self._entries.items()):
            show = QTableWidgetItem()
            show.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            show.setCheckState(Qt.Checked if entry['visible'] else Qt.Unchecked)
            show.setData(Qt.UserRole, key)
            label = QTableWidgetItem(channel_label(*key))
            label.setForeground(QColor(entry['color']))
            swatch = QPixmap(12, 12)
            swatch.fill(QColor(entry['color']))
            label.setIcon(QIcon(swatch))
            self._table.setItem(row, 0, show)
            self._table.setItem(row, 1, label)
            self._table.setItem(row, 2, QTableWidgetItem('Waiting'))
        self._table.blockSignals(False)
        self._rebuild_plots()
        if self._entries:
            self._table.selectRow(0)
        else:
            self._detail.clear()

    def _visibility_changed(self, item):
        if item.column() == 0:
            self._entries[tuple(item.data(Qt.UserRole))]['visible'] = item.checkState() == Qt.Checked
            self._rebuild_plots()

    def _rebuild_plots(self, *_):
        for plot in self._plots:
            plot.redraw_timer.stop()
        old = self._scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._plots = []
        self._curves = {}
        container = QWidget()
        container.setAutoFillBackground(True)
        container.setPalette(self.palette())
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        visible = [k for k, entry in self._entries.items() if entry['visible']]
        if not visible:
            empty = QLabel('Add channels to compare PID feedback, or show a channel from the list.')
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty)
        else:
            groups = [visible] if self._layout_mode.currentIndex() == 0 else [[key] for key in visible]
            for keys in groups:
                if self._layout_mode.currentIndex() == 1:
                    layout.addWidget(QLabel(channel_label(*keys[0])))
                mode = self._mode.currentIndex()
                fields = [DAC] if mode == 0 else [FULL] if mode == 1 else [DAC, FULL]
                specs = [('SQ1 feedback', 'Signed DAC codes', fields, 3),
                         ('Mean PID error', 'ADC counts / sample', [ERROR], 2)]
                if mode != 1:
                    specs.insert(1, ('Net flux wraps', 'Wrap count', [JUMPS], 1))
                for title, units, fields, stretch in specs:
                    plot = PyDMWaveformPlot()
                    plot.addAxis(plot_data_item=None, name='left', orientation='left', label=units)
                    plot.setAutoRangeX(False)
                    plot.set_needs_redraw()
                    plot.setMinimumHeight(125 if fields == [JUMPS] else 175)
                    # Channel colors are keyed by the persistent sidebar; large
                    # legends obscure the traces in overlay mode.
                    plot.showLegend = title == 'SQ1 feedback' and len(keys) == 1
                    for key in keys:
                        color = self._entries[key]['color']
                        for field in fields:
                            suffix = (' / full' if field == FULL else ' / DAC') if mode == 2 else ''
                            curve = WaveformCurveItem(name=channel_label(*key) + suffix,
                                color=color, lineWidth=2, antialias=True,
                                lineStyle=Qt.DashLine if field == FULL and mode == 2 else Qt.SolidLine)
                            plot.addCurve(curve, curve_color=color)
                            self._curves[key, field] = curve
                    style_live_plot(plot, title, units)
                    self._plots.append(plot)
                    layout.addWidget(plot, stretch)
        self._scroll.setWidget(container)
        count = len(visible)
        text = f'{count} visible / {len(self._entries)} selected (maximum {MAX_PLOT_CHANNELS}).'
        if count > 8:
            text += ' Crowded overlay: use separate panels or hide channels. Colors repeat after 8.'
        self._selection_note.setText(text)
        self._draw()

    def _draw(self):
        latest = [e['history'].last[TIME] for e in self._entries.values()
                  if e['visible'] and e['history'].last is not None]
        reference = max(latest) if latest else None
        for key, entry in self._entries.items():
            if not entry['visible']:
                continue
            data = entry['history'].arrays(reference=reference)
            for field in (DAC, FULL, JUMPS, ERROR):
                curve = self._curves.get((key, field))
                if curve is not None:
                    curve.setData(x=data[:, TIME], y=data[:, field], connect='finite')
        for plot in self._plots:
            plot.setXRange(-self._window.value(), 0, padding=0)
            plot.getAxis('left').linkedView().updateAutoRange()

    def _tick(self):
        if not self._built:
            return
        linked, epoch, pending = self._source.drain()
        if epoch != self._epoch:
            self._linked, self._epoch = linked, epoch
            self._clear()
            # A link transition can flip hardware enables underneath us (e.g. a
            # server restart). Forget what we thought we enabled so the re-sync
            # re-evaluates each selected column against actual hardware and only
            # re-claims columns it truly turns on.
            self._enabled_columns.clear()
            self._sync_debug_enables()
        changed = False
        for key, samples in pending.items():
            if key[0] == 'enable':
                continue
            pair = key[1:]
            if pair not in self._entries or self._pause.isChecked() or not linked:
                continue
            entry = self._entries[pair]
            for sample in samples:
                if (np.shape(sample) != (SAMPLE_SIZE,)
                        or tuple(sample[[COLUMN, ROW]]) != pair):
                    continue
                previous = entry['history'].last
                if previous is not None and sample[TIME] < previous[TIME]:
                    # Run restart invalidates the common time origin for every trace.
                    for other in self._entries.values():
                        other['history'].clear()
                        other['received'] = None
                if entry['history'].append(sample):
                    entry['received'] = time.monotonic()
                    changed = True
        if changed:
            self._draw()
        self._update_status()

    def _update_status(self):
        live = 0
        now = time.monotonic()
        for row, (key, entry) in enumerate(self._entries.items()):
            age = None if entry['received'] is None else now - entry['received']
            status = ('Disconnected' if not self._linked else 'Paused' if self._pause.isChecked()
                      else 'Waiting' if age is None else f'Stale {age:.0f}s' if age > 2 else 'Live')
            live += status == 'Live'
            item = self._table.item(row, 2)
            item.setText(status)
            sample = entry['history'].last
            detail = status
            if sample is not None:
                detail += f' · Net wraps: {sample[JUMPS]:g} · Debug drops: {sample[DROPS]:g}'
                if int(sample[FLAGS]) & NOT_COMMITTED:
                    detail += ' · PID/row disabled; feedback not applied'
                elif int(sample[FLAGS]) & FULL_UNAVAILABLE:
                    detail += ' · Full feedback unavailable'
            item.setToolTip(detail)
            if status == 'Live' and sample is not None:
                if int(sample[FLAGS]) & NOT_COMMITTED:
                    item.setText('PID/row off')
                elif int(sample[FLAGS]) & FULL_UNAVAILABLE:
                    item.setText('No full FB')
        if self._pause.isChecked():
            text, state = 'Paused', 'idle'
        elif not self._linked:
            text, state = 'Disconnected', 'stale'
        else:
            text = f'{live} / {len(self._entries)} channels live'
            state = 'live' if live and live == len(self._entries) else 'idle' if not self._entries else 'stale'
        self._show_detail()
        self._age.setText(text)
        if self._age.property('state') != state:
            self._age.setProperty('state', state)
            self._age.style().unpolish(self._age)
            self._age.style().polish(self._age)

    def _show_error(self, message):
        self._notice.setText(message)
        self._notice.setVisible(bool(message))

    def _show_detail(self):
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            label = self._table.item(row, 1)
            status = self._table.item(row, 2)
            if label is not None and status is not None:
                self._detail.setText(label.text() + ' · ' + (status.toolTip() or status.text()))

    def _clear(self):
        if self._source is not None:
            self._source.discard()
        for entry in self._entries.values():
            entry['history'].clear()
            entry['received'] = None
        self._draw()
        self._update_status()

    def _set_window(self, seconds):
        for entry in self._entries.values():
            entry['history'].seconds = seconds
            entry['history'].trim()
        self._draw()

    def _set_paused(self, paused):
        self._pause.setText('Resume' if paused else 'Pause')
        if not paused:
            self._clear()
        self._update_status()

    def closeEvent(self, event):
        self._timer.stop()
        if self._source is not None:
            # Turn off only the streams this window enabled, then detach listeners.
            self._disable_our_streams()
            self._source.close()
        super().closeEvent(event)

    def _disable_our_streams(self):
        if self._source is None or not self._linked or data_plugins.is_read_only():
            return
        for column in sorted(self._enabled_columns):
            try:
                self._source.set_debug(column, False)
            except Exception:
                pass
        self._enabled_columns.clear()
