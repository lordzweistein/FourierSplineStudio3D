"""Main application window for FourierSplineStudio3D."""

import time

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QSplitter, QStatusBar, QTabWidget, QWidget

from core.fourier3d import FourierSeries3D
from core.presets3d import PRESETS
from core.splines import SPLINE_ALGORITHMS
from ui.canvas3d import PLANES, SplineCanvas3D
from ui.control_panel import ControlPanel
from ui.formula_view3d import FormulaView3D
from ui.harmonics_view3d import HarmonicsView3D


class MainWindow3D(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fourier & Spline Studio 3D — Spatial Epicycles")
        self.resize(1450, 900)
        self.current_spline_name = "Catmull-Rom (Interpolierend)"
        self.is_closed = True
        self.animation_speed = 1.0
        self.last_anim_time = time.time()
        self.num_epicycles = 15
        self.init_ui()
        self.setup_animation_timer()
        self.load_preset("Kleeblatt-Knoten (3D)")

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        splitter = QSplitter(Qt.Horizontal)

        self.tabs = QTabWidget()
        self.canvas = SplineCanvas3D()
        self.formula_view = FormulaView3D()
        self.harmonics_view = HarmonicsView3D()
        self.tabs.addTab(self.canvas, "3D-Zeichenfenster & Epizyklen")
        self.tabs.addTab(self.formula_view, "3D-Funktionsausgabe & Export")
        self.tabs.addTab(self.harmonics_view, "3D-Harmonischen-Spektrum")

        self.control_panel = ControlPanel()
        self.control_panel.setMinimumWidth(350)
        self.control_panel.setMaximumWidth(420)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.control_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status_coords = QLabel("X: 0.0, Y: 0.0, Z: 0.0")
        self.lbl_status_pts = QLabel("Punkte: 0")
        self.lbl_status_help = QLabel("Ansichtswuerfel ziehen: Orbit | Flaeche: Ausrichten | Doppelklick: 2D | Freihand per Button/Esc")
        self.lbl_status_help.setStyleSheet("color: #94a3b8;")
        self.status_bar.addWidget(self.lbl_status_coords, 1)
        self.status_bar.addWidget(self.lbl_status_pts, 1)
        self.status_bar.addPermanentWidget(self.lbl_status_help)
        self._connect_signals()

    def _connect_signals(self):
        self.canvas.points_changed.connect(self._recalculate_spline_and_fourier)
        self.canvas.cursor_moved.connect(self._on_cursor_moved)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.view_cube_activated.connect(self._on_view_cube_activated)
        self.canvas.freehand_deactivate_requested.connect(
            lambda: self.control_panel.btn_freehand.setChecked(False)
        )
        cp = self.control_panel
        cp.spline_type_changed.connect(self._on_spline_type_changed)
        cp.closed_changed.connect(self._on_closed_changed)
        cp.preset_selected.connect(self.load_preset)
        cp.freehand_toggled.connect(self._on_freehand_toggled)
        cp.clear_points_clicked.connect(self._clear_points)
        cp.reverse_points_clicked.connect(self._reverse_points)
        cp.reset_view_clicked.connect(self.canvas.reset_view)
        cp.plane_changed.connect(self._on_plane_changed)
        cp.depth_changed.connect(self._on_depth_changed)
        cp.epicycles_count_changed.connect(self._on_epicycles_count_changed)
        cp.play_toggled.connect(self._on_play_toggled)
        cp.speed_changed.connect(self._on_speed_changed)
        cp.scrub_t_changed.connect(self.canvas.set_time)
        cp.toggle_circles.connect(lambda visible: self._set_layer_vis("circles", visible))
        cp.toggle_vectors.connect(lambda visible: self._set_layer_vis("vectors", visible))
        cp.toggle_recon.connect(lambda visible: self._set_layer_vis("recon", visible))
        cp.toggle_original.connect(lambda visible: self._set_layer_vis("original", visible))
        cp.toggle_points.connect(lambda visible: self._set_layer_vis("points", visible))
        cp.toggle_trail.connect(lambda visible: self._set_layer_vis("trail", visible))
        cp.toggle_grid.connect(lambda visible: self._set_layer_vis("grid", visible))

    def setup_animation_timer(self):
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._on_animation_frame)

    def _on_animation_frame(self):
        now = time.time()
        delta_t = (now - self.last_anim_time) * self.animation_speed / 8.0
        self.last_anim_time = now
        new_t = (self.canvas.current_t + delta_t) % 1.0
        self.canvas.set_time(new_t)
        self.control_panel.update_t_display(new_t)

    def _on_play_toggled(self, playing):
        if playing:
            self.last_anim_time = time.time()
            self.anim_timer.start()
        else:
            self.anim_timer.stop()

    def _on_speed_changed(self, speed):
        self.animation_speed = speed

    def _on_cursor_moved(self, x, y, z):
        self.lbl_status_coords.setText(f"X: {x:.1f}, Y: {y:.1f}, Z: {z:.1f}")

    def _on_spline_type_changed(self, name):
        self.current_spline_name = name
        self._recalculate_spline_and_fourier()

    def _on_closed_changed(self, closed):
        self.is_closed = closed
        self.canvas.is_closed = closed
        self._recalculate_spline_and_fourier()

    def _on_freehand_toggled(self, enabled):
        self.canvas.set_freehand_mode(enabled)
        self.control_panel.btn_freehand.setText(
            "✏️ Freihand beenden" if enabled else "✏️ Freihand Zeichnen"
        )
        if enabled:
            self.status_bar.showMessage("Freihand-Modus aktiv: auf der ausgewaehlten 3D-Ebene zeichnen.", 4000)
        else:
            self.status_bar.showMessage("Freihand-Modus deaktiviert: Linksklick setzt einzelne Punkte.", 3000)

    def _on_plane_changed(self, plane):
        self.canvas.set_active_plane(plane)
        if self.canvas.selected_point_idx is not None:
            self._show_selected_depth(self.canvas.selected_point_idx)

    def _on_view_cube_activated(self, axis, sign, side_view):
        self.canvas.snap_to_face(axis, sign)
        if not side_view:
            self.status_bar.showMessage(f"Ansicht auf {'XYZ'[axis]}{'+' if sign > 0 else '-'} ausgerichtet.", 2500)
            return

        plane = {0: "YZ", 1: "XZ", 2: "XY"}[axis]
        self.control_panel.combo_plane.blockSignals(True)
        self.control_panel.combo_plane.setCurrentText(plane)
        self.control_panel.combo_plane.blockSignals(False)
        self.canvas.set_active_plane(plane)
        self.control_panel.spin_depth.blockSignals(True)
        self.control_panel.spin_depth.setValue(0.0)
        self.control_panel.spin_depth.blockSignals(False)
        self.canvas.set_depth_value(0.0)
        self.canvas.reset_view()
        self.status_bar.showMessage(f"2D-Seitenansicht {'XYZ'[axis]}{'+' if sign > 0 else '-'} ({plane}-Ebene).", 3500)

    def _on_selection_changed(self, index):
        if index >= 0:
            self._show_selected_depth(index)

    def _show_selected_depth(self, index):
        normal_axis = PLANES[self.canvas.active_plane][2]
        value = self.canvas.control_points[index][normal_axis]
        self.control_panel.spin_depth.blockSignals(True)
        self.control_panel.spin_depth.setValue(value)
        self.control_panel.spin_depth.blockSignals(False)
        self.canvas.set_depth_value(value)

    def _on_depth_changed(self, value):
        self.canvas.set_depth_value(value)
        index = self.canvas.selected_point_idx
        if index is None:
            return
        normal_axis = PLANES[self.canvas.active_plane][2]
        points = list(self.canvas.control_points)
        point = list(points[index])
        point[normal_axis] = value
        points[index] = tuple(point)
        self.canvas.control_points = points
        self.canvas.points_changed.emit()
        self.canvas.update()

    def _clear_points(self):
        self.canvas.set_control_points([])

    def _reverse_points(self):
        self.canvas.set_control_points(list(reversed(self.canvas.control_points)))

    def _set_layer_vis(self, layer, visible):
        attributes = {
            "circles": ("show_epicycle_circles",),
            "vectors": ("show_epicycle_vectors",),
            "recon": ("show_reconstructed_curve",),
            "original": ("show_original_spline",),
            "points": ("show_control_points", "show_control_polygon"),
            "trail": ("show_trail",),
            "grid": ("show_grid", "show_axes"),
        }
        for attribute in attributes[layer]:
            setattr(self.canvas, attribute, visible)
        self.canvas.update()

    def _on_epicycles_count_changed(self, count):
        self.num_epicycles = count
        self.canvas.set_num_epicycles(count)
        self._update_formula_and_metrics()

    def load_preset(self, preset_name):
        if preset_name not in PRESETS:
            return
        points = PRESETS[preset_name]()
        open_curve = "Welle" in preset_name or "Offen" in preset_name or "Helix" in preset_name
        self.control_panel.chk_closed.setChecked(not open_curve)
        self.canvas.set_control_points(points)
        self.canvas.reset_view()

    def _recalculate_spline_and_fourier(self):
        points = self.canvas.control_points
        self.lbl_status_pts.setText(f"Punkte: {len(points)}")
        if len(points) < 2:
            self.canvas.set_spline_curve(np.zeros((0, 3)))
            self.canvas.set_fourier_series(None)
            self.formula_view.set_epicycles([])
            self.harmonics_view.set_epicycles([])
            self.control_panel.update_metrics(0.0, 0.0, 0.0)
            return
        spline_fn = SPLINE_ALGORITHMS.get(
            self.current_spline_name, SPLINE_ALGORITHMS["Catmull-Rom (Interpolierend)"]
        )
        curve = spline_fn(points, num_samples=600, closed=self.is_closed)
        self.canvas.set_spline_curve(curve)
        fourier = FourierSeries3D(curve)
        self.canvas.set_fourier_series(fourier)
        self.canvas.set_num_epicycles(self.num_epicycles)
        self.harmonics_view.set_epicycles(fourier.sorted_epicycles)
        self._update_formula_and_metrics()

    def _update_formula_and_metrics(self):
        fourier = self.canvas.fourier_series
        if fourier is None:
            return
        active = fourier.get_active_epicycles(self.num_epicycles)
        self.formula_view.set_epicycles(active)
        mean_error, max_error = fourier.compute_approximation_error(self.num_epicycles)
        energy = sum(ep.energy for ep in active)
        self.control_panel.update_metrics(mean_error, max_error, energy)
