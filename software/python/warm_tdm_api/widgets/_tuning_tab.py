from pydm.widgets.frame import PyDMFrame
from pyrogue.pydm.data_plugins.rogue_plugin import nodeFromAddress
from pyrogue.pydm.widgets import Process, Plotter, PyRogueLineEdit
from pydm.widgets import PyDMLabel, PyDMSpinbox
from qtpy.QtWidgets import QVBoxLayout, QFormLayout, QWidget, QSizePolicy


class TuningTab(PyDMFrame):

    def __init__(self, parent=None, init_channel=None):
        super().__init__(parent, init_channel)
        self._node = None

    def connection_changed(self, connected):
        build = (self._node is None) and (self._connected != connected and connected is True)
        super().connection_changed(connected)
        if not build:
            return
        self._node = nodeFromAddress(self.channel)
        self._setup_ui()

    def _process_channel(self):
        return self.channel

    def _plot_channels(self):
        return [self.channel + '.Plot']

    def _info_fields(self):
        return []

    def _setup_ui(self):
        vb = QVBoxLayout()
        self.setLayout(vb)

        proc = Process(init_channel=self._process_channel())
        vb.addWidget(proc)

        for ch in self._plot_channels():
            p = Plotter(init_channel=ch)
            p.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            vb.addWidget(p)

        fields = self._info_fields()
        if fields:
            fl = QFormLayout()
            vb.addLayout(fl)
            for label_ch, value_ch, widget_cls in fields:
                label = PyDMLabel(init_channel=label_ch)
                if widget_cls == PyDMSpinbox:
                    value = PyDMSpinbox(init_channel=value_ch)
                    value.showStepExponent = False
                    value.writeOnPress = True
                else:
                    value = PyRogueLineEdit(init_channel=value_ch)
                fl.addRow(label, value)
