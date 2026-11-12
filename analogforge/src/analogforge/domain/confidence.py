"""Qualitative confidence is never a probability or physical validation."""

from analogforge.ports.common import Confidence

ORDER = {"UNASSESSED": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def bounded_confidence(proposed: Confidence, deterministic: Confidence, *, unquantified: bool = False) -> Confidence:
    allowed: Confidence = "MEDIUM" if unquantified and deterministic == "HIGH" else deterministic
    if ORDER[proposed] > ORDER[allowed]:
        raise ValueError("CONFIDENCE_INFLATION")
    return proposed
