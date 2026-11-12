"""Fourier decomposition and epicycle evaluation for curves in 3D space."""

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Epicycle3D:
    freq: int
    coeff: np.ndarray
    radius: float
    energy: float
    phase: Tuple[float, float, float]


class FourierSeries3D:
    def __init__(self, curve_points: np.ndarray):
        self.raw_points = np.asarray(curve_points, dtype=float)
        if self.raw_points.ndim != 2 or self.raw_points.shape[1] != 3:
            raise ValueError("curve_points must have shape (N, 3)")

        self.num_samples = len(self.raw_points)
        self.sorted_epicycles: List[Epicycle3D] = []
        self.dc_offset = np.zeros(3, dtype=float)
        if self.num_samples >= 2:
            self._compute_dft()

    def _compute_dft(self):
        xy = self.raw_points[:, 0] + 1j * self.raw_points[:, 1]
        xy_coeffs = np.fft.fft(xy) / self.num_samples
        z_coeffs = np.fft.fft(self.raw_points[:, 2]) / self.num_samples
        freqs = np.rint(np.fft.fftfreq(self.num_samples, d=1.0 / self.num_samples)).astype(int)
        coeffs = np.column_stack((xy_coeffs, -1j * xy_coeffs, z_coeffs))
        powers = np.sum(np.abs(coeffs) ** 2, axis=1)
        total_energy = float(np.sum(powers))

        epicycles = []
        for coeff, freq, power in zip(coeffs, freqs, powers):
            epicycles.append(Epicycle3D(
                freq=int(freq),
                coeff=np.asarray(coeff, dtype=complex),
                radius=float(math.sqrt(power)),
                energy=float(power / total_energy * 100.0) if total_energy else 0.0,
                phase=tuple(float(v) for v in np.angle(coeff)),
            ))

        dc = next((ep for ep in epicycles if ep.freq == 0), None)
        if dc is not None:
            self.dc_offset = dc.coeff.real.copy()
        harmonics = [ep for ep in epicycles if ep.freq != 0]
        harmonics.sort(key=lambda ep: ep.radius, reverse=True)
        self.sorted_epicycles = ([dc] if dc is not None else []) + harmonics

    def get_active_epicycles(self, count: int) -> List[Epicycle3D]:
        if not self.sorted_epicycles:
            return []
        count = max(1, min(int(count), len(self.sorted_epicycles)))
        return self.sorted_epicycles[:count]

    @staticmethod
    def _contribution(epicycle: Epicycle3D, t: float) -> np.ndarray:
        angle = 2.0 * math.pi * epicycle.freq * t
        return np.real(epicycle.coeff * (math.cos(angle) + 1j * math.sin(angle)))

    def evaluate_chain(self, t: float, count: int):
        active = self.get_active_epicycles(count)
        centers = []
        contributions = []
        point = np.zeros(3, dtype=float)
        for ep in active:
            centers.append(point.copy())
            vector = self._contribution(ep, t)
            contributions.append(vector)
            point = point + vector
        return centers, contributions, point

    def evaluate_reconstruction(self, count: int, num_points: int = 500,
                                endpoint: bool = True) -> np.ndarray:
        active = self.get_active_epicycles(count)
        if not active:
            return np.zeros((0, 3), dtype=float)
        ts = np.linspace(0.0, 1.0, num_points, endpoint=endpoint)
        return self._evaluate_times(active, ts)

    @staticmethod
    def _evaluate_times(active: List[Epicycle3D], ts: np.ndarray) -> np.ndarray:
        result = np.zeros((len(ts), 3), dtype=float)
        for ep in active:
            angles = 2.0 * math.pi * ep.freq * ts
            result += np.real(
                np.exp(1j * angles[:, None]) * ep.coeff[None, :]
            )
        return result

    def compute_approximation_error(self, count: int) -> Tuple[float, float]:
        active = self.get_active_epicycles(count)
        sample_times = np.arange(self.num_samples, dtype=float) / self.num_samples
        reconstruction = self._evaluate_times(active, sample_times) if active else np.zeros((0, 3))
        if len(reconstruction) != self.num_samples or not self.num_samples:
            return 0.0, 0.0
        distances = np.linalg.norm(self.raw_points - reconstruction, axis=1)
        return float(np.mean(distances)), float(np.max(distances))
