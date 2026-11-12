import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from ui.canvas3d import PLANES
from ui.main_window3d import MainWindow3D


class ViewCubeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _face_center(self, canvas):
        self.app.processEvents()
        self.assertTrue(canvas._cube_face_hit_regions)
        polygon, axis, sign = canvas._cube_face_hit_regions[-1]
        return polygon.boundingRect().center(), axis, sign

    def test_single_click_snaps_camera_to_clicked_axis(self):
        window = MainWindow3D()
        window.show()
        self.app.processEvents()
        canvas = window.canvas
        center, axis, sign = self._face_center(canvas)
        activated = []
        canvas.view_cube_activated.connect(
            lambda selected_axis, selected_sign, side: activated.append(
                (selected_axis, selected_sign, side)
            )
        )

        QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, center.toPoint())
        QTest.qWait(300)

        expected = np.zeros(3)
        expected[axis] = sign
        np.testing.assert_allclose(canvas._camera_direction(), expected, atol=1e-10)
        self.assertEqual(activated, [(axis, sign, False)])
        window.close()

    def test_double_click_switches_to_matching_orthographic_plane(self):
        window = MainWindow3D()
        window.show()
        self.app.processEvents()
        canvas = window.canvas
        center, axis, sign = self._face_center(canvas)

        QTest.mouseDClick(canvas, Qt.LeftButton, Qt.NoModifier, center.toPoint(), 20)
        self.app.processEvents()

        plane = {0: "YZ", 1: "XZ", 2: "XY"}[axis]
        expected_direction = np.zeros(3)
        expected_direction[axis] = sign
        self.assertEqual(canvas.active_plane, plane)
        self.assertEqual(window.control_panel.combo_plane.currentText(), plane)
        self.assertEqual(canvas.depth_value, 0.0)
        np.testing.assert_allclose(canvas._camera_direction(), expected_direction, atol=1e-10)
        self.assertEqual(PLANES[plane][2], axis)
        window.close()

    def test_dragging_view_cube_orbits_without_snapping(self):
        window = MainWindow3D()
        window.show()
        self.app.processEvents()
        canvas = window.canvas
        center, _, _ = self._face_center(canvas)
        yaw, pitch = canvas.yaw, canvas.pitch
        activated = []
        canvas.view_cube_activated.connect(lambda *args: activated.append(args))
        drag_end = center.toPoint() + QPoint(-24, 18)

        QTest.mousePress(canvas, Qt.LeftButton, Qt.NoModifier, center.toPoint())
        move_event = QMouseEvent(
            QEvent.MouseMove, QPointF(drag_end), Qt.NoButton, Qt.LeftButton, Qt.NoModifier
        )
        self.app.sendEvent(canvas, move_event)
        QTest.mouseRelease(canvas, Qt.LeftButton, Qt.NoModifier, drag_end)
        QTest.qWait(300)

        self.assertNotEqual(canvas.yaw, yaw)
        self.assertNotEqual(canvas.pitch, pitch)
        self.assertEqual(activated, [])
        window.close()

    def test_freehand_can_be_toggled_off_and_escape_deactivates_it(self):
        window = MainWindow3D()
        window.show()
        self.app.processEvents()
        button = window.control_panel.btn_freehand
        canvas = window.canvas

        self.assertFalse(button.isChecked())
        self.assertFalse(canvas.freehand_mode)
        button.setChecked(True)
        self.assertTrue(canvas.freehand_mode)
        self.assertEqual(button.text(), "✏️ Freihand beenden")
        button.setChecked(False)
        self.assertFalse(canvas.freehand_mode)
        self.assertEqual(button.text(), "✏️ Freihand Zeichnen")

        canvas.set_control_points([])
        QTest.mouseClick(canvas, Qt.LeftButton, Qt.NoModifier, QPoint(240, 240))
        self.assertEqual(len(canvas.control_points), 1)

        button.setChecked(True)
        QTest.keyClick(canvas, Qt.Key_Escape)
        self.assertFalse(button.isChecked())
        self.assertFalse(canvas.freehand_mode)
        window.close()


if __name__ == "__main__":
    unittest.main()
