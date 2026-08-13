from warm_tdm_api.widgets._tuning_tab import TuningTab


class FasTuningTab(TuningTab):

    def _plot_channels(self):
        return [
            self.channel + '.SweepPlot',
            self.channel + '.TunePlot',
        ]
