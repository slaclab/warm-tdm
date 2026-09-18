# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

from pydm.widgets import PyDMSpinbox

from warm_tdm_api.widgets._tuning_tab import TuningTab


class FasTuningTab(TuningTab):

    def _plot_channels(self):
        return [
            self.channel + '.SweepPlot',
            self.channel + '.TunePlot',
            self.channel + '.DiscoveryPlot',
        ]

    def _info_fields(self):
        path = self.channel
        return [
            (path + '.PlotRow/name', path + '.PlotRow', PyDMSpinbox),
            (path + '.PlotDiscoveryRow/name', path + '.PlotDiscoveryRow', PyDMSpinbox),
        ]
