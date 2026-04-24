from pydm.widgets.frame import PyDMFrame
from pydm.widgets import PyDMLabel, PyDMSpinbox, PyDMEnumComboBox, PyDMPushButton
from pyrogue.pydm.data_plugins.rogue_plugin import nodeFromAddress
from pyrogue.pydm.widgets import RootControl, PyRogueLineEdit
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QTextEdit, QSizePolicy, QSpacerItem, QWidget,
)


class ControlTab(PyDMFrame):

    def __init__(self, parent=None, init_channel=None):
        super().__init__(parent, init_channel)
        self._node = None

    def connection_changed(self, connected):
        build = (self._node is None) and (self._connected != connected and connected is True)
        super().connection_changed(connected)
        if not build:
            return
        self._node = nodeFromAddress(self.channel)
        self._setup_ui()

    def _setup_ui(self):
        vb = QVBoxLayout()
        self.setLayout(vb)

        root_ctrl = RootControl(init_channel=self.channel)
        vb.addWidget(root_ctrl)

        vb.addWidget(self._build_general_config())
        vb.addWidget(self._build_row_col_config())

    def _build_general_config(self):
        group_path = self.channel + '.Group'

        gb = QGroupBox('General Configuration')
        hb = QHBoxLayout()
        gb.setLayout(hb)

        fl_left = QFormLayout()
        fl_left.setLabelAlignment(Qt.AlignCenter)
        hb.addLayout(fl_left)

        fl_left.addRow(
            PyDMLabel(init_channel=group_path + '.RowTuneMode/name'),
            PyDMEnumComboBox(init_channel=group_path + '.RowTuneMode'))

        sp = PyDMSpinbox(init_channel=group_path + '.RowTuneIndex')
        sp.showStepExponent = False
        sp.writeOnPress = True
        fl_left.addRow(
            PyDMLabel(init_channel=group_path + '.RowTuneIndex/name'),
            sp)

        fl_left.addRow(
            PyDMLabel(init_channel=group_path + '.FllEnable/name'),
            PyDMEnumComboBox(init_channel=group_path + '.FllEnable'))

        hb.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        fl_right = QFormLayout()
        fl_right.setLabelAlignment(Qt.AlignCenter)
        fl_right.setFormAlignment(Qt.AlignRight | Qt.AlignTop | Qt.AlignTrailing)
        hb.addLayout(fl_right)

        for var in ('NumColumnBoards', 'NumColumns', 'NumRowBoards', 'NumRows'):
            le = PyRogueLineEdit(init_channel=group_path + f'.{var}/disp')
            le.setReadOnly(True)
            fl_right.addRow(
                PyDMLabel(init_channel=group_path + f'.{var}/name'),
                le)

        return gb

    def _build_row_col_config(self):
        cs_path = self.channel + '.Group.ConfigSelect'

        gb = QGroupBox('Row / Column Configuration')
        hb = QHBoxLayout()
        gb.setLayout(hb)

        left_vb = QVBoxLayout()
        hb.addLayout(left_vb)

        fl_sel = QFormLayout()
        left_vb.addLayout(fl_sel)

        sp_col = PyDMSpinbox(init_channel=cs_path + '.ColumnSelect')
        sp_col.showStepExponent = False
        sp_col.writeOnPress = True
        fl_sel.addRow(
            PyDMLabel(init_channel=cs_path + '.ColumnSelect/name'),
            sp_col)

        sp_row = PyDMSpinbox(init_channel=cs_path + '.RowSelect')
        sp_row.showStepExponent = False
        fl_sel.addRow(
            PyDMLabel(init_channel=cs_path + '.RowSelect/name'),
            sp_row)

        btn = PyDMPushButton(label='Read All', init_channel='rogue://0/root.ReadAll')
        fl_sel.addRow('', btn)

        fl_sel.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        help_text.setHtml(
            '<p><b>Each of the variables to the right is specific to the row column selected above. '
            'Some values are specific to a row, column or row/column combination:</b></p>'
            '<p></p>'
            '<p style="color:#aa5500">- TesBias = Per Column</p>'
            '<p style="color:#aa5500">- SaBias  = Per Column</p>'
            '<p style="color:#aa5500">- SaOffset = Per Column</p>'
            '<p style="color:#aa5500">- SaOut = Per Column</p>'
            '<p style="color:#aa557f">- SaFb = Per Column / Row</p>'
            '<p style="color:#aa557f">- Sq1Bias = Per Column / Row</p>'
            '<p style="color:#aa557f">- Sq1Fb = Per Column / Row</p>'
            '<p style="color:#0000ff">- FasFluxOn = Per Row</p>'
            '<p style="color:#0000ff">- FaxFluxOff = Per Row</p>'
        )
        left_vb.addWidget(help_text)

        fl_right = QFormLayout()
        hb.addLayout(fl_right)

        combo_vars = ('ColTuneEnable', 'RowTuneEnable')
        for var in combo_vars:
            ch = cs_path + f'.{var}'
            if var == 'ColTuneEnable':
                ch += '/string'
            fl_right.addRow(
                PyDMLabel(init_channel=cs_path + f'.{var}/name'),
                PyDMEnumComboBox(init_channel=ch))

        edit_vars = (
            'TesBias', 'SaBiasCurrent', 'SaOffset',
            'SaFbForceCurrent', 'Sq1BiasForceCurrent', 'Sq1FbForceCurrent',
            'FasFluxOff', 'FasFluxOn',
        )
        for var in edit_vars:
            fl_right.addRow(
                PyDMLabel(init_channel=cs_path + f'.{var}/name'),
                PyRogueLineEdit(init_channel=cs_path + f'.{var}/disp'))

        fl_right.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        fl_right.addRow(
            PyDMLabel(init_channel=cs_path + '.SaOut/name'),
            PyRogueLineEdit(init_channel=cs_path + '.SaOut/disp'))

        return gb
