"""Classed colour maps: value classes -> colours, shared by the image and its legend so they cannot disagree."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
UInt8Array = NDArray[np.uint8]


@dataclass(frozen=True)
class ColorClass:
    """One legend class ``[lower, upper)`` (``upper`` inclusive for the last class) with its colour."""

    label: str
    lower: float | None
    upper: float | None
    color: str  # "#RRGGBB"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    if len(color) != 7 or color[0] != "#":
        raise ValueError(f"colour must be #RRGGBB, got {color!r}")
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def sample_ramp(ramp: Sequence[str], count: int) -> list[str]:
    """``count`` colours taken evenly (nearest stop) from an ordered ramp of hex colours."""
    if count < 1 or not ramp:
        raise ValueError("need at least one class and one ramp colour")
    if count == 1:
        return [ramp[len(ramp) // 2]]
    return [ramp[round(i * (len(ramp) - 1) / (count - 1))] for i in range(count)]


def equal_interval_classes(
    lo: float, hi: float, ramp: Sequence[str], unit: str, *, count: int = 6, decimals: int = 1
) -> list[ColorClass]:
    """Equal-width classes covering ``[lo, hi]``.  A constant field yields one class."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        raise ValueError("class range must be finite with lo <= hi")
    if hi - lo < 1e-12:
        return [ColorClass(f"{lo:.{decimals}f} {unit}", lo, hi, sample_ramp(ramp, 1)[0])]
    colors = sample_ramp(ramp, count)
    width = (hi - lo) / count
    out: list[ColorClass] = []
    for i in range(count):
        a = lo + i * width
        b = hi if i == count - 1 else lo + (i + 1) * width
        bracket = "]" if i == count - 1 else ")"
        out.append(ColorClass(f"[{a:.{decimals}f}, {b:.{decimals}f}{bracket} {unit}", a, b, colors[i]))
    return out


def class_index(values: FloatArray, classes: Sequence[ColorClass]) -> NDArray[np.intp]:
    """Class index of each value (last class closed above; values beyond the range clip to the end classes).

    Only meaningful where the value is valid; callers mask invalid cells themselves.
    """
    uppers = np.array([c.upper for c in classes[:-1]], dtype=np.float64)
    safe = np.where(np.isfinite(values), values, 0.0)
    return np.searchsorted(uppers, safe, side="right").astype(np.intp)


def colorize(values: FloatArray, valid: BoolArray, classes: Sequence[ColorClass]) -> UInt8Array:
    """RGBA image: class colour with alpha 255 where ``valid``; fully transparent (alpha 0) elsewhere."""
    palette = np.array([hex_to_rgb(c.color) for c in classes], dtype=np.uint8)
    index = class_index(values, classes)
    rgba = np.zeros(values.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = palette[index]
    rgba[..., 3] = 255
    rgba[~valid] = 0
    return rgba


__all__ = ["ColorClass", "class_index", "colorize", "equal_interval_classes", "hex_to_rgb", "sample_ramp"]
