"""Colour maps and legends of the display layers (architecture 18 section 4).

Every class list is used both to colour the image and to build the ``LegendItem`` list, so the legend always matches
the pixels.  Palettes: slope uses fixed degree classes aligned with the 12-18 degree band edges; continuous
quantities use equal-interval classes of a perceptually ordered ramp; categorical ids use the colour-blind-safe
Okabe-Ito set (ids are classes, never blended).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from analogforge.ports.domain_models import LegendItem
from analogforge.rendering.tiles.legend import ColorClass, equal_interval_classes
from analogforge.science.errors import RasterError

SLOPE_CLASS_EDGES_DEG: Final = (0.0, 6.0, 12.0, 18.0, 24.0, 30.0, 90.0)
_SLOPE_RAMP: Final = ("#FFF7BC", "#FEE391", "#FEC44F", "#FE9929", "#D95F0E", "#993404")
_VIRIDIS: Final = ("#440154", "#46337E", "#365C8D", "#277F8E", "#1FA187", "#4AC26D", "#9FDA3A", "#FDE725")
_THERMAL: Final = ("#000004", "#3B0F70", "#8C2981", "#DE4968", "#FE9F6D", "#FCFDBF")
_ROUGHNESS: Final = ("#F7FCF5", "#C7E9C0", "#74C476", "#238B45", "#00441B")
OKABE_ITO: Final = ("#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#999999")


def slope_classes() -> list[ColorClass]:
    edges = SLOPE_CLASS_EDGES_DEG
    last = len(edges) - 2
    out: list[ColorClass] = []
    for i, color in enumerate(_SLOPE_RAMP):
        bracket = "]" if i == last else ")"
        out.append(ColorClass(f"[{edges[i]:g}, {edges[i + 1]:g}{bracket} deg", edges[i], edges[i + 1], color))
    return out


def continuous_classes(kind: str, lo: float, hi: float, unit: str) -> list[ColorClass]:
    """Equal-interval classes for ELEVATION / ROUGHNESS / THERMAL over the valid-value range ``[lo, hi]``."""
    if kind == "ELEVATION":
        return equal_interval_classes(lo, hi, _VIRIDIS, unit, count=8, decimals=1)
    if kind == "ROUGHNESS":
        return equal_interval_classes(lo, hi, _ROUGHNESS, unit, count=5, decimals=3)
    if kind == "THERMAL":
        return equal_interval_classes(lo, hi, _THERMAL, unit, count=6, decimals=1)
    raise RasterError(f"no continuous colour map for layer kind {kind!r}")


def categorical_classes(ids: Sequence[int], labels: Mapping[int, str] | None) -> list[ColorClass]:
    """One class per category id present; the colour follows the sorted id position (stable across tiles)."""
    out: list[ColorClass] = []
    for position, class_id in enumerate(sorted(set(ids))):
        label = (labels or {}).get(class_id, f"class {class_id}")
        out.append(ColorClass(label, float(class_id), float(class_id), OKABE_ITO[position % len(OKABE_ITO)]))
    return out


def to_legend(classes: Sequence[ColorClass]) -> list[LegendItem]:
    return [LegendItem(label=c.label, lower=c.lower, upper=c.upper, color=c.color) for c in classes]


__all__ = [
    "OKABE_ITO",
    "SLOPE_CLASS_EDGES_DEG",
    "categorical_classes",
    "continuous_classes",
    "slope_classes",
    "to_legend",
]
