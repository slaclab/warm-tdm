from pydm.widgets import PyDMPushButton
from pyrogue.pydm.widgets import Process
from qtpy.QtWidgets import QGroupBox


class TuningProcess(Process):
    """PyRogue Process widget with a first-class Pause button."""

    def __init__(self, parent=None, init_channel=None):
        self._pause_added = False
        super().__init__(parent=parent, init_channel=init_channel)

    def connection_changed(self, connected):
        super().connection_changed(connected)

        if self._node is not None and not self._pause_added:
            self._add_pause_button()

    def _add_pause_button(self):
        outer_layout = self.layout()
        if outer_layout is None or outer_layout.count() == 0:
            return

        group_box = outer_layout.itemAt(0).widget()
        if not isinstance(group_box, QGroupBox):
            return

        process_layout = group_box.layout()
        if process_layout is None or process_layout.count() == 0:
            return

        button_layout = process_layout.itemAt(0).layout()
        if button_layout is None:
            return

        button_layout.insertWidget(1, PyDMPushButton(
            label='Pause',
            pressValue=1,
            init_channel=self.channel + '.Pause'))
        self._pause_added = True
