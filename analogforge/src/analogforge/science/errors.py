"""Exception types of the science library.

Expected data problems (missing coverage, unresolved CRS, unsupported policy) are *values* returned as
``ScienceIssue``/``BLOCKED`` results by the facade.  The exceptions below are raised by the pure helpers and are
translated by the facade; each carries a canonical ``code`` (``contracts/error-codes.json``) and an optional
``detail_code`` (e.g. ``BODY_MISMATCH``) so the translation never loses information.
"""

from __future__ import annotations


class ScienceError(Exception):
    """Base class: ``code`` is a canonical error code, ``detail_code`` a finer science-specific code."""

    code: str = "INPUT_INVALID"

    def __init__(self, message: str, *, code: str | None = None, detail_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.detail_code = detail_code

    def __str__(self) -> str:
        suffix = f" [{self.detail_code}]" if self.detail_code else ""
        return f"{self.code}{suffix}: {self.message}"


class GeometryError(ScienceError):
    """Body, frame, CRS or distortion problem (detail codes BODY_MISMATCH, FRAME_UNRESOLVED, DISTORTION_EXCEEDED)."""

    code = "UNSUPPORTED_CRS"


class RasterError(ScienceError):
    """Raster content, shape, unit, container or registration problem."""

    code = "SOURCE_CONTENT_INVALID"


class ScaleError(ScienceError):
    """Support-scale incompatibility (never resolved by upsampling)."""

    code = "SCALE_INCOMPATIBLE"


class ModelError(ScienceError):
    """Invalid physical-model parameters (e.g. efficiency outside (0, 1])."""

    code = "INPUT_INVALID"


class ConfigError(ScienceError):
    """A configuration file is missing, malformed or inconsistent with the kit catalog."""

    code = "INPUT_INVALID"
