"""Thin, dependency-light helpers for display imagery: deterministic PNG encoding and classed colour legends.

Pure functions only (numpy + Pillow); no I/O, no clock, no environment.  ``analogforge.science.display`` builds the
georeferenced display layers on top of these helpers.
"""

from analogforge.rendering.tiles.legend import (
    ColorClass,
    class_index,
    colorize,
    equal_interval_classes,
    hex_to_rgb,
    sample_ramp,
)
from analogforge.rendering.tiles.png import decode_png_rgba, encode_png_rgba

__all__ = [
    "ColorClass",
    "class_index",
    "colorize",
    "decode_png_rgba",
    "encode_png_rgba",
    "equal_interval_classes",
    "hex_to_rgb",
    "sample_ramp",
]
