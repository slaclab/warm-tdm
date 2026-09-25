# This file is part of the WarmTDM software package. It is subject to
# the license terms in LICENSE.txt in the top-level directory and at:
# https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part may be copied, modified, propagated or distributed except under
# those license terms.
"""Render tuning plots without a Rogue tree or hardware."""
import importlib.util
import io
from pathlib import Path
import unittest

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np


class CurvePlottingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'python/warm_tdm_api/_CurveClass.py'
        spec = importlib.util.spec_from_file_location('curve_plotting_test', path)
        cls.curves = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.curves)

    def test_untuned_panels_stay_centered_with_narrow_shared_y_range(self):
        x = np.linspace(0, 300, 20)
        curve = self.curves.Curve(20)
        for y in 1e-8 * np.sin(2 * np.pi * x / 100):
            curve.addPoint(y)
        data = self.curves.CurveData(x)
        data.addCurve(curve)

        for empty in (None, {'curves': []}, {'curves': [[]]}):
            with self.subTest(empty=empty):
                fig = Figure(figsize=(20, 20), dpi=50, tight_layout=True)
                canvas = FigureCanvasAgg(fig)
                axes = fig.subplots(4, 2, sharey=True).ravel()
                for col, ax in enumerate(axes):
                    self.curves.plotCurveDataDict(
                        ax, data.asDict() if col == 0 else empty,
                        f'Channel {col}', 'SA FB', 'SA Out', 'SA Bias Curves')
                renderer = canvas.get_renderer()
                # Check bounds before PNG export, so a regression cannot try
                # to allocate a multi-billion-pixel image in the test runner.
                bounds = fig.get_tightbbox(renderer)
                self.assertLess(bounds.height, 21)
                self.assertLess(bounds.width, 21)
                for ax in axes[1:]:
                    label = ax.texts[0]
                    position = label.get_transform().transform(label.get_position())
                    np.testing.assert_allclose(position, ax.transAxes.transform((.5, .5)))
                output = io.BytesIO()
                fig.savefig(output, format='png', bbox_inches='tight')
                self.assertTrue(output.getvalue().startswith(b'\x89PNG\r\n\x1a\n'))


if __name__ == '__main__':
    unittest.main()
