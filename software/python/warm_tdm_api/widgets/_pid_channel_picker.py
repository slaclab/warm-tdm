##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Compact single-channel search and range selection for large channel catalogs."""
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, QLabel,
    QDialogButtonBox, QCompleter,
)
from warm_tdm_api.widgets import MAX_PLOT_CHANNELS, channel_pairs


class PidChannelPicker(QDialog):
    def __init__(self, topology, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add PID channels')
        self.setMinimumWidth(510)
        self._topology = topology
        self._selected = set(selected)
        self.pairs = []
        layout = QVBoxLayout(self)
        hint = QLabel('Search for a column, or enter global-column and logical-row ranges. '
                      'Every selected column is paired with every selected row.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        self.search = QComboBox()
        self.search.setEditable(True)
        self.search.setInsertPolicy(QComboBox.NoInsert)
        for c in sorted(topology):
            self.search.addItem(f'Board {c // 8} / Column {c % 8} / Global {c}', c)
        self.search.completer().setFilterMode(Qt.MatchContains)
        self.search.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.search.completer().setCaseSensitivity(Qt.CaseInsensitive)
        form.addRow('Find a column', self.search)
        self.columns = QLineEdit(str(min(topology)))
        self.columns.setPlaceholderText('0, 3, 8-11')
        self.rows = QLineEdit(str(min(topology[min(topology)])))
        self.rows.setPlaceholderText('0, 10-15')
        form.addRow('Global columns', self.columns)
        form.addRow('Logical rows', self.rows)
        self.search.activated.connect(lambda index: self.columns.setText(str(self.search.itemData(index))))
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.button(QDialogButtonBox.Ok).setText('Add channels')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.columns.textChanged.connect(self._preview)
        self.rows.textChanged.connect(self._preview)
        self._preview()

    def _preview(self):
        try:
            pairs = channel_pairs(self.columns.text(), self.rows.text(), self._topology)
            new = set(pairs) - self._selected
            total = len(new) + len(self._selected)
            if total > MAX_PLOT_CHANNELS:
                raise ValueError(f'This would select {total} channels; the detailed-view limit is {MAX_PLOT_CHANNELS}.')
            self.pairs = sorted(new)
            cols = len({c for c, _ in pairs})
            rows = len({r for _, r in pairs})
            text = f'{cols} columns × {rows} rows = {len(pairs)} channels. {len(new)} new; {total} selected in total.'
            if total > 8:
                text += '\nOverlays may be crowded. Consider separate panels or a smaller selection.'
            self.preview.setText(text)
        except ValueError as exc:
            self.pairs = []
            self.preview.setText(str(exc))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.pairs))
