##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
import time

from pydm.widgets import PyDMCheckbox, PyDMLabel, PyDMSpinbox
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.frame import PyDMFrame
from pydm.widgets.waveformplot import PyDMWaveformPlot, WaveformCurveItem
from pyrogue.pydm.data_plugins.rogue_plugin import nodeFromAddress
from qtpy.QtCore import QTimer, Slot
from qtpy.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton,
)
import numpy as np

from warm_tdm import (
    TIME, COLUMN, ROW, DAC, FULL, JUMPS, ERROR, DROPS, FLAGS,
    FULL_UNAVAILABLE, NOT_COMMITTED, SAMPLE_SIZE,
)
from warm_tdm_api.widgets import PidHistory, style_display, style_live_plot, TRACE_COLORS


class PidLockTab(PyDMFrame):
    """Live PID-debug view. ``init_channel`` addresses a Group."""

    def __init__(self, parent=None, init_channel=None):
        self._built = False
        self._monitor_channels = []
        self._history = PidHistory()
        self._column = self._row = 0
        self._last_received = None
        self._sample_connected = False
        super().__init__(parent, init_channel)
        style_display(self)

    def channels(self):
        return (super().channels() or []) + self._monitor_channels

    def connection_changed(self, connected):
        super().connection_changed(connected)
        if connected and not self._built:
            self._built = True
            self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)
        monitor = self.channel + '.HardwareGroup.PidLockMonitor'
        if nodeFromAddress(monitor) is None:
            layout.addWidget(QLabel('PID Lock requires a server with PidLockMonitor support.'))
            return

        heading = QHBoxLayout()
        title = QLabel('PID lock monitor')
        title.setObjectName('plotHeading')
        heading.addWidget(title)
        heading.addStretch()
        self._age = QLabel('Waiting for samples')
        self._age.setObjectName('plotStatus')
        heading.addWidget(self._age)
        layout.addLayout(heading)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        layout.addLayout(controls)
        for label, variable in [('Global column', 'ColumnSelect'), ('Logical row', 'RowSelect')]:
            controls.addWidget(QLabel(label))
            spin = PyDMSpinbox(init_channel=monitor + '.' + variable)
            spin.setFixedWidth(80)
            spin.showStepExponent = False
            spin.writeOnPress = True
            controls.addWidget(spin)
        self._debug_enable = PyDMCheckbox(init_channel=monitor + '.PidDebugEnable')
        self._debug_enable.setText('Enable debug stream for column')
        controls.addWidget(self._debug_enable)
        controls.addStretch()

        options = QHBoxLayout()
        layout.addLayout(options)
        self._mode = QComboBox()
        self._mode.addItems(['DAC + flux jumps', 'Full feedback', 'Both'])
        options.addWidget(self._mode)
        options.addWidget(QLabel('History'))
        self._window = QSpinBox()
        self._window.setRange(5, 600)
        self._window.setValue(60)
        self._window.setSuffix(' s')
        options.addWidget(self._window)
        self._pause = QPushButton('Pause')
        self._pause.setCheckable(True)
        options.addWidget(self._pause)
        clear = QPushButton('Clear')
        options.addWidget(clear)
        options.addStretch()

        self._feedback = self._plot('SQ1 feedback', 'Signed DAC codes')
        self._feedback.showLegend = True
        self._flux = self._plot('Net flux wraps', 'Wrap count')
        self._error = self._plot('Mean PID error', 'ADC counts / sample')
        layout.addWidget(self._feedback, 3)
        layout.addWidget(self._flux, 1)
        layout.addWidget(self._error, 2)
        self._curves = {
            DAC: self._curve(self._feedback, 'DAC', TRACE_COLORS[0]),
            FULL: self._curve(self._feedback, 'Full feedback', TRACE_COLORS[1]),
            JUMPS: self._curve(self._flux, 'Net wraps', TRACE_COLORS[2]),
            ERROR: self._curve(self._error, 'Mean error', TRACE_COLORS[3]),
        }
        for plot, title, units in (
                (self._feedback, 'SQ1 feedback', 'Signed DAC codes'),
                (self._flux, 'Net flux wraps', 'Wrap count'),
                (self._error, 'Mean PID error', 'ADC counts / sample')):
            style_live_plot(plot, title, units)
        self._detail = QLabel()
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)
        layout.addWidget(PyDMLabel(init_channel=monitor + '.Status'))
        note = QLabel('Display samples up to 10 Hz; fast transients may be missed. '
                      'Selection is shared across GUI clients. Debug enable is per column; '
                      'changing selection leaves other columns unchanged.')
        note.setObjectName('plotNote')
        note.setWordWrap(True)
        layout.addWidget(note)

        self._mode.currentIndexChanged.connect(self._set_mode)
        self._window.valueChanged.connect(self._set_window)
        self._pause.toggled.connect(self._set_paused)
        clear.clicked.connect(self._clear)
        self._set_mode(0)
        self._select_column(0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_age)
        self._timer.start(250)

        for suffix, slot in [('ColumnSelect', self._select_column),
                             ('RowSelect', self._select_row), ('Sample', self._receive_sample)]:
            channel = PyDMChannel(address=monitor + '.' + suffix, value_slot=slot,
                                  connection_slot=self._sample_connection if suffix == 'Sample' else None)
            self._monitor_channels.append(channel)
            channel.connect()

    @staticmethod
    def _plot(title, units):
        plot = PyDMWaveformPlot()
        plot.addAxis(plot_data_item=None, name='left', orientation='left', label=units)
        plot.setAutoRangeX(False)
        # Curves receive coherent x/y histories together via setData below.
        # Initialize PyDM's redraw flag before addCurve starts its timer.
        plot.set_needs_redraw()
        plot.setTitle(title)
        plot.setLabel('bottom', 'Time relative to latest sample', units='s')
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.setMinimumHeight(120)
        return plot

    @staticmethod
    def _curve(plot, name, color):
        curve = WaveformCurveItem(name=name, color=color, lineWidth=2, antialias=True)
        plot.addCurve(curve, curve_color=color)
        return curve

    @Slot(int)
    def _select_column(self, value):
        self._column = int(value)
        self._clear()

    @Slot(int)
    def _select_row(self, value):
        self._row = int(value)
        self._clear()

    @Slot(bool)
    def _sample_connection(self, connected):
        if connected == self._sample_connected:
            return
        self._sample_connected = connected
        self._clear()

    @Slot(np.ndarray)
    def _receive_sample(self, value):
        if (self._pause.isChecked() or np.shape(value) != (SAMPLE_SIZE,)
                or value[COLUMN] != self._column or value[ROW] != self._row):
            return
        if not self._history.append(value):
            return
        self._last_received = time.monotonic()
        flags = int(value[FLAGS])
        detail = f'Net wraps: {value[JUMPS]:g}    Firmware debug drops: {value[DROPS]:g}'
        if flags & NOT_COMMITTED:
            detail += '    PID or row disabled: feedback candidate is not applied.'
        elif flags & FULL_UNAVAILABLE:
            detail += '    Full feedback unavailable: incomplete feedback/count, count limit, or invalid wrap period.'
        self._detail.setText(detail)
        self._draw()
        self._update_age()

    def _draw(self):
        values = self._history.arrays()
        for field, curve in self._curves.items():
            curve.setData(x=values[:, TIME], y=values[:, field], connect='finite')
        for plot in (self._feedback, self._flux, self._error):
            plot.setXRange(-self._history.seconds, 0, padding=0)
            plot.getAxis('left').linkedView().updateAutoRange()

    def _clear(self):
        self._history.clear()
        self._last_received = None
        self._detail.setText('')
        self._draw()
        self._update_age()

    def _set_mode(self, mode):
        self._curves[DAC].setVisible(mode != 1)
        self._curves[FULL].setVisible(mode != 0)
        self._flux.setVisible(mode != 1)
        self._draw()

    def _set_window(self, seconds):
        self._history.seconds = seconds
        self._history.trim()
        self._draw()

    def _set_paused(self, paused):
        self._pause.setText('Resume' if paused else 'Pause')
        if not paused:
            self._clear()
        self._update_age()

    def _update_age(self):
        if self._pause.isChecked():
            text = 'Paused'
        elif not self._sample_connected:
            text = 'Disconnected'
        elif self._last_received is None:
            text = 'Waiting for selected row / column'
        else:
            age = time.monotonic() - self._last_received
            text = f'No new samples for {age:.1f} s' if age > 2 else 'Live'
        self._age.setText(text)
        state = 'live' if text == 'Live' else 'stale' if text.startswith('No new') else 'idle'
        if self._age.property('state') != state:
            self._age.setProperty('state', state)
            self._age.style().unpolish(self._age)
            self._age.style().polish(self._age)
