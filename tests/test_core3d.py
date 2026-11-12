import unittest

import numpy as np

from core.export3d import python_code
from core.fourier3d import FourierSeries3D
from core.presets3d import PRESETS
from core.splines import SPLINE_ALGORITHMS


class Fourier3DTests(unittest.TestCase):
    def test_full_fourier_series_reconstructs_all_sampled_coordinates(self):
        points = np.array([
            [0.0, 0.0, 2.0],
            [1.0, 3.0, -1.0],
            [4.0, -2.0, 5.0],
            [-3.0, 1.0, 0.5],
            [2.0, 2.0, -4.0],
            [-1.0, -3.0, 1.0],
        ])
        series = FourierSeries3D(points)

        reconstruction = series.evaluate_reconstruction(len(points), len(points), endpoint=False)
        mean_error, max_error = series.compute_approximation_error(len(points))

        np.testing.assert_allclose(reconstruction, points, atol=1e-12)
        self.assertLess(mean_error, 1e-12)
        self.assertLess(max_error, 1e-12)

    def test_xy_epicycles_keep_the_original_complex_fourier_components(self):
        points = np.array([
            [np.cos(t), np.sin(t), 0.0]
            for t in np.linspace(0.0, 2.0 * np.pi, 16, endpoint=False)
        ])
        series = FourierSeries3D(points)
        xy_coefficients = np.fft.fft(points[:, 0] + 1j * points[:, 1]) / len(points)

        for epicycle in series.sorted_epicycles:
            expected = xy_coefficients[epicycle.freq % len(points)]
            self.assertAlmostEqual(epicycle.coeff[0].real, expected.real, places=12)
            self.assertAlmostEqual(epicycle.coeff[0].imag, expected.imag, places=12)
            self.assertAlmostEqual(epicycle.coeff[1].real, (-1j * expected).real, places=12)
            self.assertAlmostEqual(epicycle.coeff[1].imag, (-1j * expected).imag, places=12)

    def test_every_spline_algorithm_preserves_three_coordinates(self):
        points = [(0, 0, 0), (1, 2, 3), (3, -1, 2), (5, 1, -2)]
        for name, spline in SPLINE_ALGORITHMS.items():
            with self.subTest(spline=name):
                curve = spline(points, num_samples=80, closed=False)
                self.assertEqual(curve.shape, (80, 3))
                self.assertTrue(np.isfinite(curve).all())
                closed_curve = spline(points, num_samples=80, closed=True)
                self.assertEqual(closed_curve.shape, (80, 3))
                self.assertTrue(np.isfinite(closed_curve).all())

    def test_presets_are_three_dimensional(self):
        for name, factory in PRESETS.items():
            with self.subTest(preset=name):
                points = factory()
                self.assertGreaterEqual(len(points), 2)
                self.assertTrue(all(len(point) == 3 for point in points))

    def test_generated_python_export_compiles(self):
        points = np.array(PRESETS["Kleeblatt-Knoten (3D)"](), dtype=float)
        series = FourierSeries3D(points)
        code = python_code(series.get_active_epicycles(12))
        namespace = {}
        exec(compile(code, "<3d-fourier-export>", "exec"), namespace)
        exported_point = namespace["curve_point"](0.0)
        expected_point = series.evaluate_reconstruction(12, 1)[0]
        np.testing.assert_allclose(exported_point, expected_point, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
