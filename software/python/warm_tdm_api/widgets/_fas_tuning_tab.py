# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

from pydm.widgets import PyDMLabel, PyDMSpinbox
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QFormLayout, QScrollArea, QSizePolicy, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

import warm_tdm_api.widgets as widgets


class FasTuningTab(widgets.TuningTab):
    """Scrollable tuning controls alongside individually tabbed plots."""

    def _process_widget(self):
        return widgets.TwoColumnProcess(init_channel=self._process_channel())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(self._process_widget())
        controls_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(controls)
        splitter.addWidget(scroll)

        plots = QTabWidget()
        for title, plot_name, selector in (
                ('Sweep', 'SweepPlot', 'PlotRow'),
                ('Tune Summary', 'TunePlot', None),
                ('Discovery', 'DiscoveryPlot', 'PlotDiscoveryRow')):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            if selector is not None:
                channel = self.channel + '.' + selector
                fields = QFormLayout()
                value = PyDMSpinbox(init_channel=channel)
                value.showStepExponent = False
                value.writeOnPress = True
                fields.addRow(PyDMLabel(init_channel=channel + '/name'), value)
                page_layout.addLayout(fields)
            plot = widgets.LightPlotter(
                init_channel=self.channel + '.' + plot_name)
            plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            page_layout.addWidget(plot, 1)
            plots.addTab(page, title)
        splitter.addWidget(plots)
        splitter.setSizes([600, 900])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
