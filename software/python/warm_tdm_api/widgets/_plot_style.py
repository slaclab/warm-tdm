##############################################################################
## This file is part of 'warm-tdm'. It is subject to the license terms in the
## LICENSE.txt file found in the top-level directory of this distribution and
## at https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
## No part may be copied, modified, propagated, or distributed except according
## to the terms contained in the LICENSE.txt file.
##############################################################################
"""Local display styling; no process-wide Qt or plotting defaults."""
from qtpy.QtGui import QColor, QPalette
from pyrogue.pydm.widgets import Plotter

TEXT = '#243447'
MUTED = '#536579'
BORDER = '#cbd5e1'
TRACE_COLORS = ('#0072b2', '#c56500', '#8064a2', '#00816a')


def style_display(widget):
    """Give this display and its children a light, platform-independent palette."""
    palette = widget.palette()
    for role, color in (
            (QPalette.Window, '#f3f5f8'), (QPalette.WindowText, TEXT),
            (QPalette.Base, '#ffffff'), (QPalette.AlternateBase, '#eef2f6'),
            (QPalette.Text, TEXT), (QPalette.Button, '#ffffff'),
            (QPalette.ButtonText, TEXT), (QPalette.Highlight, '#0072b2'),
            (QPalette.HighlightedText, '#ffffff'),
            (QPalette.ToolTipBase, '#ffffff'), (QPalette.ToolTipText, TEXT)):
        palette.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        palette.setColor(QPalette.Disabled, role, QColor('#8793a1'))
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
    widget.setStyleSheet("""
        QTabWidget::pane { border: 1px solid #cbd5e1; }
        QTabBar::tab { padding: 9px 14px; margin-right: 2px;
                      background: #e7ecf2; color: #536579; }
        QTabBar::tab:selected { background: white; color: #243447;
                               border-bottom: 3px solid #0072b2; }
        QPushButton { padding: 5px 14px; border: 1px solid #cbd5e1;
                      border-radius: 4px; background: white; }
        QPushButton:hover { border-color: #0072b2; background: #edf5fa; }
        QPushButton:pressed, QPushButton:checked { background: #dcecf6; }
        QPushButton:focus { border: 1px solid #0072b2; }
        QComboBox, QAbstractSpinBox { min-height: 25px; }
        QLabel#plotHeading { font-size: 18px; font-weight: 600; }
        QLabel#plotNote { color: #536579; }
        QLabel#plotStatus { padding: 5px 10px; border-radius: 4px;
                            background: #e7ecf2; color: #536579; }
        QLabel#plotStatus[state="live"] { background: #e2f1ec; color: #17634d; }
        QLabel#plotStatus[state="stale"] { background: #fff0da; color: #805000; }
    """)


def style_live_plot(plot, title, units):
    """Style a PyDM plot after its curves have established their axes."""
    plot.setBackgroundColor(QColor('#ffffff'))
    plot.setTitle(title, color=TEXT, size='11pt')
    plot.setLabel('left', units, color=TEXT)
    plot.setLabel('bottom', 'Time relative to latest sample', units='s', color=MUTED)
    plot.showGrid(x=True, y=True, alpha=0.3)
    for name in ('left', 'bottom'):
        axis = plot.getAxis(name)
        axis.setPen(QColor(BORDER))
        axis.setTextPen(QColor(MUTED))
        axis.setStyle(maxTickLevel=0, tickLength=-4)
    # Equal widths keep the three time axes visually aligned.
    plot.getAxis('left').setWidth(86)
    legend = plot.plotItem.legend
    if legend is not None:
        legend.setBrush('#ffffff')
        legend.setPen(BORDER)
        legend.setLabelTextColor(TEXT)
        legend.setLabelTextSize('10pt')
        # Refresh existing labels as well as the defaults for future entries.
        for _, label in legend.items:
            label.setText(label.text, color=TEXT, size='10pt')


class LightPlotter(Plotter):
    """Consistent figure surfaces for tuning and captured-waveform views.

    Preserve the incoming figure's curve colors, markers, limits and data:
    those may encode channel identity or tuning results.
    """

    def value_changed(self, new_val):
        new_val.set_facecolor('#ffffff')
        for text in new_val.texts:
            text.set_color(TEXT)
        for ax in new_val.axes:
            ax.set_facecolor('#ffffff')
            ax.set_axisbelow(True)
            ax.tick_params(colors=MUTED)
            ax.xaxis.label.set_color(TEXT)
            ax.yaxis.label.set_color(TEXT)
            ax.title.set_color(TEXT)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
            ax.grid(True, color=BORDER, alpha=0.45, linewidth=0.6)
            legend = ax.get_legend()
            if legend is not None:
                legend.get_frame().set_facecolor('#ffffff')
                legend.get_frame().set_edgecolor(BORDER)
                for text in [*legend.get_texts(), legend.get_title()]:
                    text.set_color(TEXT)
        super().value_changed(new_val)
