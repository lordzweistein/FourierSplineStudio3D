"""Interactive orthographic 3D spline and Fourier viewport using QPainter."""

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np
from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

from core.fourier3d import FourierSeries3D

PLANES = {
    "XY": (0, 1, 2),
    "XZ": (0, 2, 1),
    "YZ": (1, 2, 0),
}


class SplineCanvas3D(QWidget):
    points_changed = pyqtSignal()
    cursor_moved = pyqtSignal(float, float, float)
    selection_changed = pyqtSignal(int)
    view_cube_activated = pyqtSignal(int, int, bool)
    freehand_deactivate_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._last_size = (self.width(), self.height())
        self.zoom = 1.0
        self.pan_offset = QPointF()
        self.yaw = 0.65
        self.pitch = 0.58
        self.control_points: List[Tuple[float, float, float]] = []
        self.selected_point_idx: Optional[int] = None
        self.hovered_point_idx: Optional[int] = None
        self.spline_curve_points = np.zeros((0, 3))
        self.reconstructed_curve = np.zeros((0, 3))
        self.fourier_series: Optional[FourierSeries3D] = None
        self.is_closed = True
        self.num_epicycles_to_draw = 15
        self.current_t = 0.0
        self.active_plane = "XY"
        self.depth_value = 0.0
        self.freehand_mode = False
        self.is_freehand_drawing = False
        self.freehand_raw_points: List[Tuple[float, float, float]] = []
        self.is_panning = False
        self.is_orbiting = False
        self.is_cube_dragging = False
        self._cube_press_pos = QPointF()
        self._cube_drag_face = None
        self._cube_drag_moved = False
        self.last_mouse = QPointF()
        self.is_space_pressed = False
        self._cube_face_hit_regions = []
        self._pending_cube_face = None
        self._cube_click_timer = QTimer(self)
        self._cube_click_timer.setSingleShot(True)
        self._cube_click_timer.setInterval(250)
        self._cube_click_timer.timeout.connect(self._activate_pending_cube_face)

        self.show_grid = True
        self.show_axes = True
        self.show_control_polygon = True
        self.show_control_points = True
        self.show_original_spline = True
        self.show_reconstructed_curve = True
        self.show_epicycle_circles = True
        self.show_epicycle_vectors = True
        self.show_trail = True
        self.show_pen_tip = True
        self._set_default_center()

    def _set_default_center(self):
        self.pan_offset = QPointF(self.width() / 2.0 or 400.0, self.height() / 2.0 or 300.0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_size = (event.size().width(), event.size().height())
        old_width, old_height = self._last_size
        self.pan_offset += QPointF(
            (new_size[0] - old_width) / 2.0,
            (new_size[1] - old_height) / 2.0,
        )
        self._last_size = new_size

    def _camera_basis(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        right = np.array([cy, -sy, 0.0])
        up = np.array([sy * sp, cy * sp, cp])
        return right, up

    def _camera_direction(self):
        right, up = self._camera_basis()
        return np.cross(right, up)

    def _project_cube_point(self, point, center, size, right, up):
        return QPointF(
            center.x() + size * float(np.dot(point, right)),
            center.y() - size * float(np.dot(point, up)),
        )

    def _draw_view_cube(self, painter):
        self._cube_face_hit_regions = []
        center = QPointF(self.width() - 57.0, 60.0)
        card = QRectF(center.x() - 48.0, center.y() - 44.0, 96.0, 96.0)
        painter.setPen(QPen(QColor(71, 85, 105, 190), 1.0))
        painter.setBrush(QBrush(QColor(15, 23, 42, 225)))
        painter.drawRoundedRect(card, 10.0, 10.0)
        painter.setFont(QFont("Helvetica Neue", 9, QFont.DemiBold))
        painter.setPen(QColor(203, 213, 225))
        painter.drawText(QRectF(card.x(), card.y() + 3.0, card.width(), 14.0), Qt.AlignHCenter, "ANSICHT")
        painter.setFont(QFont("Helvetica Neue", 7))
        painter.setPen(QColor(148, 163, 184))
        painter.drawText(
            QRectF(card.x() + 2.0, card.bottom() - 13.0, card.width() - 4.0, 10.0),
            Qt.AlignHCenter,
            "Ziehen: drehen",
        )

        right, up = self._camera_basis()
        direction = self._camera_direction()
        axis_colors = (QColor("#fb7185"), QColor("#4ade80"), QColor("#60a5fa"))
        faces = []
        for axis in range(3):
            other_axes = [value for value in range(3) if value != axis]
            for sign in (-1, 1):
                normal = np.zeros(3)
                normal[axis] = sign
                facing = float(np.dot(normal, direction))
                if facing <= 0.015:
                    continue
                vertices = []
                for first, second in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    point = np.zeros(3)
                    point[axis] = sign
                    point[other_axes[0]] = first
                    point[other_axes[1]] = second
                    vertices.append(point)
                polygon = QPolygonF([
                    self._project_cube_point(point, center, 26.0, right, up)
                    for point in vertices
                ])
                depth = sum(float(np.dot(point, direction)) for point in vertices) / 4.0
                faces.append((depth, axis, sign, polygon, facing))

        faces.sort(key=lambda face: face[0])
        for _, axis, sign, polygon, facing in faces:
            base_color = axis_colors[axis]
            alpha = int(95 + 85 * min(1.0, facing))
            fill = QColor(base_color)
            fill.setAlpha(alpha)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor(226, 232, 240, 225), 1.3))
            painter.drawPolygon(polygon)
            center_x = sum(point.x() for point in polygon) / len(polygon)
            center_y = sum(point.y() for point in polygon) / len(polygon)
            painter.setPen(QColor("#0f172a"))
            painter.setFont(QFont("Helvetica Neue", 9, QFont.Bold))
            painter.drawText(QPointF(center_x - 8.0, center_y + 4.0), f"{'+' if sign > 0 else '-'}{'XYZ'[axis]}")
            self._cube_face_hit_regions.append((polygon, axis, sign))

    def _cube_face_at(self, position):
        for polygon, axis, sign in reversed(self._cube_face_hit_regions):
            if polygon.containsPoint(QPointF(position), Qt.OddEvenFill):
                return axis, sign
        return None

    def _activate_pending_cube_face(self):
        face = self._pending_cube_face
        self._pending_cube_face = None
        if face is not None:
            self.view_cube_activated.emit(face[0], face[1], False)

    def world_to_screen(self, point: Sequence[float]) -> QPointF:
        right, up = self._camera_basis()
        p = np.asarray(point, dtype=float)
        return QPointF(
            self.pan_offset.x() + self.zoom * float(np.dot(p, right)),
            self.pan_offset.y() - self.zoom * float(np.dot(p, up)),
        )

    def screen_to_world(self, x: float, y: float, plane: Optional[str] = None,
                        depth: Optional[float] = None) -> np.ndarray:
        plane = plane or self.active_plane
        first_axis, second_axis, normal_axis = PLANES[plane]
        depth = self.depth_value if depth is None else depth
        right, up = self._camera_basis()
        matrix = np.array([
            [right[first_axis], right[second_axis]],
            [up[first_axis], up[second_axis]],
        ])
        target = np.array([
            (x - self.pan_offset.x()) / self.zoom - right[normal_axis] * depth,
            (self.pan_offset.y() - y) / self.zoom - up[normal_axis] * depth,
        ])
        if abs(float(np.linalg.det(matrix))) < 0.02:
            coords = np.linalg.lstsq(matrix, target, rcond=0.05)[0]
        else:
            coords = np.linalg.solve(matrix, target)
        point = np.zeros(3, dtype=float)
        point[first_axis], point[second_axis], point[normal_axis] = coords[0], coords[1], depth
        return point

    def set_active_plane(self, plane: str):
        if plane not in PLANES:
            raise ValueError(f"Unknown drawing plane: {plane}")
        self.active_plane = plane
        self.update()

    def snap_to_face(self, axis: int, sign: int):
        if axis not in range(3) or sign not in (-1, 1):
            raise ValueError("A view-cube face needs an axis (0-2) and sign (-1 or 1)")
        normal = np.zeros(3)
        normal[axis] = sign
        self.yaw = math.atan2(-normal[0], -normal[1])
        self.pitch = math.asin(normal[2])
        self.update()

    def set_depth_value(self, value: float):
        self.depth_value = float(value)
        self.update()

    def set_freehand_mode(self, enabled: bool):
        self.freehand_mode = bool(enabled)
        if not self.freehand_mode:
            self.is_freehand_drawing = False
            self.freehand_raw_points.clear()
        self.update()

    def set_control_points(self, points):
        normalized = [tuple(float(c) for c in point) for point in points]
        if any(len(point) != 3 for point in normalized):
            raise ValueError("Control points must have three coordinates")
        self.control_points = normalized
        self.selected_point_idx = None
        self.selection_changed.emit(-1)
        self.points_changed.emit()
        self.update()

    def set_spline_curve(self, curve: np.ndarray):
        self.spline_curve_points = np.asarray(curve, dtype=float).reshape((-1, 3))
        self.update()

    def set_fourier_series(self, series: Optional[FourierSeries3D]):
        self.fourier_series = series
        self.update_reconstruction()
        self.update()

    def set_num_epicycles(self, count: int):
        self.num_epicycles_to_draw = int(count)
        self.update_reconstruction()
        self.update()

    def update_reconstruction(self):
        if self.fourier_series:
            self.reconstructed_curve = self.fourier_series.evaluate_reconstruction(
                self.num_epicycles_to_draw, 600
            )
        else:
            self.reconstructed_curve = np.zeros((0, 3))

    def set_time(self, t: float):
        self.current_t = t % 1.0
        self.update()

    def reset_view(self):
        if not self.control_points:
            self.zoom = 1.0
            self._set_default_center()
            self.update()
            return
        projected = [self.world_to_screen_without_pan(p) for p in self.control_points]
        coords = np.array(projected)
        min_x, min_y = np.min(coords, axis=0)
        max_x, max_y = np.max(coords, axis=0)
        width, height = max(100.0, max_x - min_x), max(100.0, max_y - min_y)
        view_width, view_height = max(200, self.width()), max(200, self.height())
        self.zoom = max(0.15, min((view_width - 100) / width, (view_height - 100) / height, 3.0))
        center = (np.min(coords, axis=0) + np.max(coords, axis=0)) / 2.0
        self.pan_offset = QPointF(
            view_width / 2.0 - self.zoom * center[0],
            view_height / 2.0 - self.zoom * center[1],
        )
        self.update()

    def world_to_screen_without_pan(self, point):
        right, up = self._camera_basis()
        p = np.asarray(point, dtype=float)
        return np.array([np.dot(p, right), -np.dot(p, up)])

    def _draw_polyline(self, painter, points, color, width=2.0, style=Qt.SolidLine, close=False):
        if len(points) < 2:
            return
        path = QPainterPath()
        path.moveTo(self.world_to_screen(points[0]))
        for point in points[1:]:
            path.lineTo(self.world_to_screen(point))
        if close:
            path.closeSubpath()
        painter.setPen(QPen(color, width, style))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#090d16"))
        if self.show_grid:
            self._draw_grid(painter)
        if self.show_axes:
            self._draw_axes(painter)
        if self.show_control_polygon:
            self._draw_polyline(painter, self.control_points, QColor(148, 163, 184, 110), 1.1)
        if self.show_original_spline:
            self._draw_polyline(painter, self.spline_curve_points, QColor(14, 165, 233, 220), 2.2, close=self.is_closed)
        if self.show_reconstructed_curve:
            self._draw_polyline(painter, self.reconstructed_curve, QColor(234, 179, 8, 145), 1.5, Qt.DashLine, self.is_closed)
        if self.fourier_series:
            self._draw_epicycles(painter)
        if self.is_freehand_drawing:
            self._draw_polyline(painter, self.freehand_raw_points, QColor(244, 63, 94, 210), 2.0, Qt.DotLine)
        if self.show_control_points:
            self._draw_control_points(painter)
        self._draw_hud(painter)
        self._draw_view_cube(painter)

    def _draw_grid(self, painter):
        first, second, normal = PLANES[self.active_plane]
        painter.setPen(QPen(QColor(100, 116, 139, 35), 1))
        extent, step = 500, 50
        for value in range(-extent, extent + 1, step):
            p1, p2 = np.zeros(3), np.zeros(3)
            p1[normal] = p2[normal] = self.depth_value
            p1[first], p1[second] = -extent, value
            p2[first], p2[second] = extent, value
            painter.drawLine(self.world_to_screen(p1), self.world_to_screen(p2))
            p1[first], p1[second] = value, -extent
            p2[first], p2[second] = value, extent
            painter.drawLine(self.world_to_screen(p1), self.world_to_screen(p2))

    def _draw_axes(self, painter):
        colors = (QColor("#fb7185"), QColor("#4ade80"), QColor("#60a5fa"))
        labels = ("X", "Y", "Z")
        for axis in range(3):
            start, end = np.zeros(3), np.zeros(3)
            end[axis] = 220.0
            painter.setPen(QPen(colors[axis], 2.0))
            p0, p1 = self.world_to_screen(start), self.world_to_screen(end)
            painter.drawLine(p0, p1)
            painter.setPen(colors[axis])
            painter.drawText(int(p1.x() + 4), int(p1.y() - 3), labels[axis])

    def _draw_epicycles(self, painter):
        centers, contributions, tip = self.fourier_series.evaluate_chain(
            self.current_t, self.num_epicycles_to_draw
        )
        epicycles = self.fourier_series.get_active_epicycles(self.num_epicycles_to_draw)
        for index, (center, vector) in enumerate(zip(centers, contributions)):
            endpoint = center + vector
            if self.show_epicycle_circles and index > 0:
                ep = epicycles[index]
                if ep.freq:
                    loop = []
                    for phase in np.linspace(0.0, 1.0, 50):
                        angle = 2.0 * math.pi * ep.freq * (self.current_t + phase)
                        loop.append(center + np.real(ep.coeff * np.exp(1j * angle)))
                    self._draw_polyline(painter, loop, QColor(168, 85, 247, 95), 1.0, Qt.DotLine, True)
            if self.show_epicycle_vectors:
                painter.setPen(QPen(QColor(192, 132, 252, 205), 1.6))
                painter.drawLine(self.world_to_screen(center), self.world_to_screen(endpoint))

        if self.show_trail and len(self.reconstructed_curve) > 2:
            trail_end = min(len(self.reconstructed_curve), int(len(self.reconstructed_curve) * self.current_t) + 1)
            trail = list(self.reconstructed_curve[:trail_end])
            if trail:
                trail.append(tip)
                self._draw_polyline(painter, trail, QColor(250, 204, 21, 230), 2.8)
        if self.show_pen_tip:
            screen_tip = self.world_to_screen(tip)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(250, 204, 21, 85)))
            painter.drawEllipse(screen_tip, 8, 8)
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(screen_tip, 3.5, 3.5)

    def _draw_control_points(self, painter):
        painter.setFont(QFont("Helvetica Neue", 9, QFont.Bold))
        for index, point in enumerate(self.control_points):
            screen = self.world_to_screen(point)
            selected = index == self.selected_point_idx
            hovered = index == self.hovered_point_idx
            fill = QColor("#fbbf24") if selected else QColor("#f43f5e") if hovered else QColor("#e11d48")
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            radius = 7 if selected or hovered else 5.5
            painter.drawEllipse(screen, radius, radius)
            painter.setPen(QColor("#f1f5f9"))
            painter.drawText(int(screen.x() + radius + 3), int(screen.y() - radius + 3), f"P{index}")
            if hovered or selected:
                painter.setPen(QColor("#38bdf8"))
                painter.drawText(int(screen.x() + radius + 3), int(screen.y() + radius + 11),
                                 "(" + ", ".join(f"{v:.1f}" for v in point) + ")")

    def _draw_hud(self, painter):
        painter.setFont(QFont("Menlo", 9))
        painter.setPen(QColor(148, 163, 184, 210))
        lines = [
            f"Ebene: {self.active_plane} | Tiefe: {self.depth_value:.1f}",
            f"Zoom: {int(self.zoom * 100)}% | Punkte: {len(self.control_points)}",
            f"Epizyklen: {self.num_epicycles_to_draw} | t = {self.current_t:.3f}",
            "Rechts ziehen: Orbit | Mausrad: Zoom | Mittelklick/Leertaste: Pan",
        ]
        y = self.height() - 15 - len(lines) * 16
        for line in lines:
            painter.drawText(15, y, line)
            y += 16

    def _find_point_near(self, pos, threshold=14.0):
        for index, point in enumerate(self.control_points):
            screen = self.world_to_screen(point)
            if math.hypot(screen.x() - pos.x(), screen.y() - pos.y()) <= threshold:
                return index
        return None

    def _set_selected(self, index):
        self.selected_point_idx = index
        self.selection_changed.emit(index if index is not None else -1)
        self.update()

    def mousePressEvent(self, event):
        pos = event.pos()
        self.last_mouse = QPointF(pos)
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self.is_space_pressed):
            self.is_panning = True
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.RightButton:
            point_index = self._find_point_near(pos)
            if point_index is not None:
                points = list(self.control_points)
                points.pop(point_index)
                self.set_control_points(points)
            else:
                self.is_orbiting = True
                self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() != Qt.LeftButton:
            return
        cube_face = self._cube_face_at(pos)
        if cube_face is not None:
            self.is_cube_dragging = True
            self._cube_press_pos = QPointF(pos)
            self._cube_drag_face = cube_face
            self._cube_drag_moved = False
            self.setCursor(Qt.ClosedHandCursor)
            return
        self._cube_click_timer.stop()
        self._pending_cube_face = None
        world = self.screen_to_world(pos.x(), pos.y())
        if self.freehand_mode:
            self.is_freehand_drawing = True
            self.freehand_raw_points = [tuple(world)]
            self.update()
            return
        index = self._find_point_near(pos)
        if index is not None:
            self._set_selected(index)
        else:
            self._set_selected(None)
            self.control_points.append(tuple(world))
            self.points_changed.emit()
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        face = self._cube_face_at(event.pos()) or self._pending_cube_face
        if face is None:
            super().mouseDoubleClickEvent(event)
            return
        self._cube_click_timer.stop()
        self._pending_cube_face = None
        self.is_cube_dragging = False
        self._cube_drag_face = None
        self._cube_drag_moved = False
        self.setCursor(Qt.ArrowCursor)
        self.view_cube_activated.emit(face[0], face[1], True)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.is_cube_dragging:
            delta = pos - self.last_mouse
            if not self._cube_drag_moved:
                distance = math.hypot(
                    pos.x() - self._cube_press_pos.x(),
                    pos.y() - self._cube_press_pos.y(),
                )
                self._cube_drag_moved = distance >= 4.0
            if self._cube_drag_moved:
                self.yaw += delta.x() * 0.012
                self.pitch = max(-1.35, min(1.35, self.pitch - delta.y() * 0.012))
        elif self.is_panning:
            delta = pos - self.last_mouse
            self.pan_offset += delta
        elif self.is_orbiting:
            delta = pos - self.last_mouse
            self.yaw += delta.x() * 0.008
            self.pitch = max(-1.35, min(1.35, self.pitch - delta.y() * 0.008))
        elif self.is_freehand_drawing:
            world = self.screen_to_world(pos.x(), pos.y())
            if not self.freehand_raw_points or np.linalg.norm(world - self.freehand_raw_points[-1]) > 2.0:
                self.freehand_raw_points.append(tuple(world))
                self.update()
        elif self.selected_point_idx is not None and event.buttons() & Qt.LeftButton:
            point = self.screen_to_world(
                pos.x(), pos.y(), depth=self.control_points[self.selected_point_idx][PLANES[self.active_plane][2]]
            )
            points = list(self.control_points)
            points[self.selected_point_idx] = tuple(point)
            self.control_points = points
            self.points_changed.emit()
        else:
            self.hovered_point_idx = self._find_point_near(pos)
            self.setCursor(
                Qt.PointingHandCursor if self._cube_face_at(pos) is not None else Qt.ArrowCursor
            )
            world = self.screen_to_world(pos.x(), pos.y())
            self.cursor_moved.emit(*map(float, world))
        self.last_mouse = QPointF(pos)
        self.update()

    def mouseReleaseEvent(self, event):
        if self.is_cube_dragging:
            self.is_cube_dragging = False
            if not self._cube_drag_moved and self._cube_drag_face is not None:
                self._pending_cube_face = self._cube_drag_face
                self._cube_click_timer.start()
            self._cube_drag_face = None
            self._cube_drag_moved = False
            self.setCursor(Qt.ArrowCursor)
        if self.is_freehand_drawing:
            self.is_freehand_drawing = False
            if len(self.freehand_raw_points) >= 2:
                self.control_points.extend(self.freehand_raw_points)
                self.points_changed.emit()
            self.freehand_raw_points = []
        self.is_panning = False
        self.is_orbiting = False
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def wheelEvent(self, event):
        old_zoom = self.zoom
        self.zoom = max(0.12, min(8.0, self.zoom * (1.12 if event.angleDelta().y() > 0 else 1.0 / 1.12)))
        factor = self.zoom / old_zoom
        cursor = event.pos()
        self.pan_offset = QPointF(
            cursor.x() - (cursor.x() - self.pan_offset.x()) * factor,
            cursor.y() - (cursor.y() - self.pan_offset.y()) * factor,
        )
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.is_space_pressed = True
            return
        if event.key() == Qt.Key_Escape and self.freehand_mode:
            self.freehand_deactivate_requested.emit()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected_point_idx is not None:
            points = list(self.control_points)
            points.pop(self.selected_point_idx)
            self.set_control_points(points)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.is_space_pressed = False
        super().keyReleaseEvent(event)
