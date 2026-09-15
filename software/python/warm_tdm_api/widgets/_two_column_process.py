from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFormLayout, QHBoxLayout, QGroupBox

from ._tuning_process import TuningProcess


class TwoColumnProcess(TuningProcess):
    """Process widget with its automatically generated fields in two columns."""

    _STATUS_ROWS = 2  # Progress and Message remain full-width.

    def __init__(self, parent=None, init_channel=None):
        self._fields_arranged = False
        super().__init__(parent=parent, init_channel=init_channel)

    def connection_changed(self, connected):
        super().connection_changed(connected)

        if self._node is not None and not self._fields_arranged:
            self._arrange_fields()

    @staticmethod
    def _new_form_layout():
        layout = QFormLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        layout.setFormAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.setLabelAlignment(Qt.AlignRight)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return layout

    def _arrange_fields(self):
        """Move the fields below Progress and Message into balanced columns."""
        outer_layout = self.layout()
        if outer_layout is None or outer_layout.count() == 0:
            return

        group_box = outer_layout.itemAt(0).widget()
        if not isinstance(group_box, QGroupBox):
            return

        process_layout = group_box.layout()
        if process_layout is None or process_layout.count() < 2:
            return

        form_layout = process_layout.itemAt(1).layout()
        if not isinstance(form_layout, QFormLayout):
            return

        rows = []
        while form_layout.rowCount() > self._STATUS_ROWS:
            row = form_layout.takeRow(self._STATUS_ROWS)
            if row.labelItem is not None and row.fieldItem is not None:
                rows.append((row.labelItem.widget(), row.fieldItem.widget()))

        if not rows:
            self._fields_arranged = True
            return

        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        left = self._new_form_layout()
        right = self._new_form_layout()
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)

        split = (len(rows) + 1) // 2
        for index, (label, field) in enumerate(rows):
            target = left if index < split else right
            target.addRow(label, field)

        process_layout.addLayout(columns)
        self._fields_arranged = True
