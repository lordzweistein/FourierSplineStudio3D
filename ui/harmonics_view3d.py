"""Spectrum table for the three coordinate components of each harmonic."""

import math

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHeaderView, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)


class HarmonicsView3D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.lbl_summary = QLabel("Keine 3D-Harmonischen geladen.")
        self.lbl_summary.setStyleSheet("font-weight: bold; color: #38bdf8;")
        top.addWidget(self.lbl_summary)
        layout.addLayout(top)
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Rang", "Frequenz k", "|cₖ| (3D)", "Phase X", "Phase Y",
            "Phase Z", "Energie (%)", "Vektor (X, Y, Z)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

    def set_epicycles(self, epicycles):
        self.table.setRowCount(len(epicycles))
        total_energy = sum(ep.energy for ep in epicycles)
        for row, ep in enumerate(epicycles):
            phases = [math.degrees(value) for value in ep.phase]
            vector = ", ".join(f"{value.real:+.3f}{value.imag:+.3f}i" for value in ep.coeff)
            items = [
                f"#{row + 1}",
                f"{ep.freq:+d}" if ep.freq else "0 (DC)",
                f"{ep.radius:.4f}",
                f"{phases[0]:+.1f}°",
                f"{phases[1]:+.1f}°",
                f"{phases[2]:+.1f}°",
                f"{ep.energy:.2f}%" if total_energy else "0.00%",
                vector,
            ]
            for col, value in enumerate(items):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
        self.lbl_summary.setText(
            f"Harmonische gesamt: {len(epicycles)} | Dominante Frequenz: "
            f"k={epicycles[0].freq}, Betrag={epicycles[0].radius:.2f}"
            if epicycles else "Keine 3D-Harmonischen vorhanden."
        )
