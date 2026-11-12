"""Planar and spatial example curves for FourierSplineStudio3D."""

import math
from typing import Dict, List, Tuple

import numpy as np

from .presets import PRESETS as PLANAR_PRESETS


def _embed_planar(factory):
    def create():
        return [(x, y, 0.0) for x, y in factory()]
    return create


def get_helix(num_points: int = 36) -> List[Tuple[float, float, float]]:
    t = np.linspace(0.0, 4.0 * math.pi, num_points, endpoint=False)
    return [(150.0 * math.cos(v), 150.0 * math.sin(v), 30.0 * v - 180.0) for v in t]


def get_trefoil_knot(num_points: int = 48) -> List[Tuple[float, float, float]]:
    t = np.linspace(0.0, 2.0 * math.pi, num_points, endpoint=False)
    return [
        (55.0 * (math.sin(v) + 2.0 * math.sin(2.0 * v)),
         55.0 * (math.cos(v) - 2.0 * math.cos(2.0 * v)),
         -65.0 * math.sin(3.0 * v))
        for v in t
    ]


def get_lissajous_3d(num_points: int = 48) -> List[Tuple[float, float, float]]:
    t = np.linspace(0.0, 2.0 * math.pi, num_points, endpoint=False)
    return [
        (160.0 * math.sin(3.0 * v + math.pi / 2.0),
         135.0 * math.sin(4.0 * v),
         110.0 * math.sin(5.0 * v + math.pi / 3.0))
        for v in t
    ]


PRESETS: Dict[str, callable] = {
    **{name: _embed_planar(factory) for name, factory in PLANAR_PRESETS.items()},
    "3D-Helix (Offen)": get_helix,
    "Kleeblatt-Knoten (3D)": get_trefoil_knot,
    "Lissajous (3D)": get_lissajous_3d,
}
