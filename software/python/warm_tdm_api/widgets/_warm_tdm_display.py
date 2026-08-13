from pydm import Display
from pydm.widgets.tab_bar import PyDMTabWidget
from pyrogue.pydm.widgets import DebugTree, SystemWindow
from qtpy.QtWidgets import QVBoxLayout

from warm_tdm_api.widgets._control_tab import ControlTab
from warm_tdm_api.widgets._tuning_tab import TuningTab
from warm_tdm_api.widgets._sa_tuning_tab import SaTuningTab
from warm_tdm_api.widgets._fas_tuning_tab import FasTuningTab
from warm_tdm_api.widgets._waveform_tab import WaveformTab

ROOT = 'rogue://0/GroupRoot'
DEVICE_ROOT = 'rogue://0/root'


class WarmTdmDisplay(Display):

    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self._setup_ui()

    def ui_filename(self):
        return None

    def _setup_ui(self):
        vb = QVBoxLayout()
        self.setLayout(vb)

        tabs = PyDMTabWidget(self)
        vb.addWidget(tabs)

        group = ROOT + '.Group'

        tab_specs = [
            ('Debug Tree', DebugTree(init_channel=DEVICE_ROOT)),
            ('Control', ControlTab(init_channel=ROOT)),
            ('System', SystemWindow(init_channel=ROOT)),
            ('SA Tuning', SaTuningTab(init_channel=group + '.SaTuneProcess')),
            ('FAS Tuning', FasTuningTab(init_channel=group + '.FasTuneProcess')),
            ('SQ1 Tuning', TuningTab(init_channel=group + '.Sq1TuneProcess')),
            ('Waveforms', WaveformTab(init_channel=group)),
            ('SA Offset', TuningTab(init_channel=group + '.SaOffsetSweepProcess')),
        ]

        for title, widget in tab_specs:
            tabs.addTab(widget, title)
