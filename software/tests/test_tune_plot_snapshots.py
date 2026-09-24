# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.

"""Concurrent tuning plot reads must not alter figures awaiting publication."""

from concurrent.futures import ThreadPoolExecutor
import importlib.util
import logging
from pathlib import Path
import pickle
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np


API = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api'


def load(name):
    spec = importlib.util.spec_from_file_location(name, API / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Variable:
    def __init__(self, value):
        self.data = value

    def value(self):
        return self.data


class LinkVariable:
    def __init__(self, **kwargs):
        self._log = logging.getLogger(__name__)


class TunePlotSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        curves = load('_CurveClass')
        api = SimpleNamespace(PausableProcess=object,
                              plotCurveDataDict=curves.plotCurveDataDict)
        with patch.dict(sys.modules, {'pyrogue': SimpleNamespace(LinkVariable=LinkVariable),
                                      'warm_tdm_api': api}):
            cls.modules = {kind: load(f'_{kind}Tune') for kind in ('Sa', 'Sq1')}
        x = np.linspace(0, 300, 20)
        data = curves.CurveData(x)
        curve = curves.Curve(20)
        for y in np.sin(2 * np.pi * x / 100):
            curve.addPoint(y)
        data.addCurve(curve)
        cls.data = data.asDict()

    def plots(self):
        for kind, module in self.modules.items():
            for name in ('SinglePlot', 'MultiPlot'):
                plot = getattr(module, name)()
                plot.parent = SimpleNamespace(
                    EnablePlots=Variable(True), PlotColumn=Variable(0), PlotRow=Variable(0),
                    SaTuneOutput=Variable([self.data] + [None] * 7),
                    Sq1TuneOutput=Variable([[self.data] + [None] * 7, [None] * 8]))
                yield kind, name, plot

    def test_previous_result_survives_selection_and_data_changes(self):
        for kind, name, plot in self.plots():
            with self.subTest(kind=kind, plot=name):
                first = plot.linkedGet()
                title = first.axes[0].get_title()
                y = first.axes[0].lines[0].get_ydata().copy()
                plot.parent.PlotRow.data = 1
                plot.parent.SaTuneOutput.data = [None] * 8
                second = plot.linkedGet()
                self.assertIsNot(first, second)
                self.assertEqual(first.axes[0].get_title(), title)
                np.testing.assert_array_equal(first.axes[0].lines[0].get_ydata(), y)
                self.assertEqual(second.axes[0].texts[0].get_text(), 'Not Tuned')
                # ZMQ pickles the figure after linkedGet has returned.
                restored = pickle.loads(pickle.dumps(first))
                np.testing.assert_array_equal(restored.axes[0].lines[0].get_ydata(), y)
                restored.set_dpi(25)
                FigureCanvasAgg(restored).draw()

    def test_overlapping_reads_use_independent_artists(self):
        for kind, name, plot in self.plots():
            with self.subTest(kind=kind, plot=name):
                barrier = threading.Barrier(2, timeout=10)
                original = plot._plot_ax
                axes = []

                def draw(ax, col, *args):
                    if col == 0:
                        axes.append(ax)
                        barrier.wait()
                        # Fail deterministically before racing Axes.clear().
                        self.assertIsNot(axes[0], axes[1])
                    original(ax, col, *args)

                with patch.object(plot, '_plot_ax', draw), ThreadPoolExecutor(2) as pool:
                    calls = [pool.submit(plot.linkedGet) for _ in range(2)]
                    figures = [call.result(timeout=15) for call in calls]
                self.assertIsNot(figures[0], figures[1])
                for figure in figures:
                    self.assertIs(figure.axes[0].figure, figure)
                    self.assertEqual(len(figure.axes), 8 if name == 'MultiPlot' else 1)
                    pickle.dumps(figure)

    def test_disabled_or_empty_keeps_last_completed_plot(self):
        for kind, name, plot in self.plots():
            with self.subTest(kind=kind, plot=name):
                first = plot.linkedGet()
                plot.parent.EnablePlots.data = False
                self.assertIs(plot.linkedGet(), first)
                plot.parent.EnablePlots.data = True
                for empty in ([], {}):
                    plot.parent.SaTuneOutput.data = empty
                    plot.parent.Sq1TuneOutput.data = empty
                    self.assertIs(plot.linkedGet(), first)


if __name__ == '__main__':
    unittest.main()
