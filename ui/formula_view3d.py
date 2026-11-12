"""Formula and export panel for 3D Fourier curves."""

from typing import List

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from core.export3d import (
    cartesian_formulas, complex_vector_formula, desmos_syntax, javascript_code,
    latex_formula, python_code,
)
from core.fourier3d import Epicycle3D


class FormulaView3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_epicycles: List[Epicycle3D] = []
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Ausgabe-Format:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems([
            "3D-Fourier-Vektorform",
            "Kartesische Funktionen x(t), y(t), z(t)",
            "Python Script",
            "LaTeX-Gleichungen",
            "Parametrische 3D-Kurve",
            "JavaScript-Funktion",
        ])
        self.combo_format.currentIndexChanged.connect(self._refresh_content)
        header.addWidget(self.combo_format, 1)
        self.btn_copy = QPushButton("In Zwischenablage kopieren")
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        header.addWidget(self.btn_copy)
        self.btn_save = QPushButton("Als Datei speichern...")
        self.btn_save.clicked.connect(self._save_to_file)
        header.addWidget(self.btn_save)
        layout.addLayout(header)
        self.text_editor = QTextEdit()
        self.text_editor.setReadOnly(True)
        self.text_editor.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.text_editor)
        self.lbl_tip = QLabel("Der Parameter t laeuft von 0 bis 1; jeder Punkt der Kurve hat drei Koordinaten.")
        self.lbl_tip.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.lbl_tip)
        self._refresh_content()

    def set_epicycles(self, epicycles):
        self.current_epicycles = list(epicycles)
        self._refresh_content()

    def _content(self):
        epicycles = self.current_epicycles
        index = self.combo_format.currentIndex()
        if index == 0:
            return complex_vector_formula(epicycles)
        if index == 1:
            return "\n\n".join(cartesian_formulas(epicycles))
        if index == 2:
            return python_code(epicycles)
        if index == 3:
            return latex_formula(epicycles)
        if index == 4:
            return desmos_syntax(epicycles)
        if index == 5:
            return javascript_code(epicycles)
        return ""

    def _refresh_content(self):
        if not self.current_epicycles:
            self.text_editor.setPlainText("Zeichne zuerst eine 3D-Kurve, um Formeln zu generieren.")
        else:
            self.text_editor.setPlainText(self._content())

    def _copy_to_clipboard(self):
        text = self.text_editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.btn_copy.setText("Kopiert!")
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("In Zwischenablage kopieren"))

    def _save_to_file(self):
        text = self.text_editor.toPlainText()
        if not text:
            return
        index = self.combo_format.currentIndex()
        suffix = ".py" if index == 2 else ".tex" if index == 3 else ".js" if index == 5 else ".txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "3D-Formel exportieren", f"fourier_curve_3d{suffix}",
            f"Dateien (*{suffix});;Alle Dateien (*)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as file:
                file.write(text)
