from pydm.widgets.frame import PyDMFrame
from pyrogue.pydm.data_plugins.rogue_plugin import nodeFromAddress
from pyrogue.pydm.widgets import DebugTree, Plotter
from qtpy.QtWidgets import QVBoxLayout, QHBoxLayout

DEVICE_ROOT = 'rogue://0/root'


class WaveformTab(PyDMFrame):
    """Waveform tab widget.

    The channel should point to the GroupRoot.Group node. DebugTree widgets
    use the device-root path (``rogue://0/root.Group.HardwareGroup...``)
    while the Plotter uses the GroupRoot path.
    """

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

    def _setup_ui(self):
        vb = QVBoxLayout()
        self.setLayout(vb)

        hb = QHBoxLayout()
        vb.addLayout(hb)

        tree1 = DebugTree(
            init_channel=DEVICE_ROOT + '.Group.HardwareGroup.ColumnBoard[0].DataPath.WaveformCapture')
        hb.addWidget(tree1)

        tree2 = DebugTree(
            init_channel=DEVICE_ROOT + '.Group.HardwareGroup.WaveformCaptureReceiver')
        tree2.setMinimumHeight(469)
        hb.addWidget(tree2)

        plotter = Plotter(
            init_channel=self.channel + '.HardwareGroup.WaveformCaptureReceiver.MultiPlot')
        vb.addWidget(plotter)
