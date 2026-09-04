from warm_tdm_api.widgets._tuning_tab import TuningTab
from warm_tdm_api.widgets._two_column_process import TwoColumnProcess


class Sq1TuningTab(TuningTab):

    def _process_widget(self):
        return TwoColumnProcess(init_channel=self._process_channel())
