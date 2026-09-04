from pydm.widgets import PyDMSpinbox

from warm_tdm_api.widgets._tuning_tab import TuningTab


class FasTuningTab(TuningTab):

    def _plot_channels(self):
        return [
            self.channel + '.SweepPlot',
            self.channel + '.TunePlot',
        ]

    def _info_fields(self):
        path = self.channel
        return [
            (path + '.PlotRow/name', path + '.PlotRow', PyDMSpinbox),
            (path + '.PlotColumn/name', path + '.PlotColumn', PyDMSpinbox),
        ]
