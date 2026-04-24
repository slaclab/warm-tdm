from pydm.widgets import PyDMSpinbox
from pyrogue.pydm.widgets import PyRogueLineEdit
from warm_tdm_api.widgets._tuning_tab import TuningTab


class SaTuningTab(TuningTab):

    def _plot_channels(self):
        return [self.channel + '.Plot']

    def _info_fields(self):
        path = self.channel
        return [
            (path + '.PlotColumn/name', path + '.PlotColumn', PyDMSpinbox),
            (path + '.FittedSaFb/name', path + '.FittedSaFb/disp', PyRogueLineEdit),
            (path + '.FittedSaBias/name', path + '.FittedSaBias/disp', PyRogueLineEdit),
            (path + '.FittedSaOut/name', path + '.FittedSaOut/disp', PyRogueLineEdit),
        ]
