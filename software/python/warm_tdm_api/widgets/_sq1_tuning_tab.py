import warm_tdm_api.widgets as widgets


class Sq1TuningTab(widgets.TuningTab):

    def _process_widget(self):
        return widgets.TwoColumnProcess(init_channel=self._process_channel())
