"""Exposure semantics shared by solver and verifier: band membership and unique/total accumulation.

Architecture 12 section 4: bands are lower-inclusive/upper-exclusive; the final capped band (``upper_inclusive``)
also includes its upper endpoint.  Unique exposure counts every undirected edge subsegment once, no matter how
often or in which direction it is traversed; traversed exposure counts every traversal.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from analogforge.ports.science_payloads import ExposureSpec


def slope_in_band(slope_deg: float, band_deg: tuple[float, float], upper_inclusive: bool) -> bool:
    """``lo <= slope < hi`` (or ``<= hi`` for the final capped band)."""
    low, high = band_deg
    if slope_deg < low:
        return False
    return slope_deg <= high if upper_inclusive else slope_deg < high


def band_length_of_cells(cells: Iterable[tuple[float, float]], spec: ExposureSpec) -> float:
    """Sum of intersection lengths (m) of ``(slope_deg, length_m)`` cells whose slope lies in the spec's band."""
    total = 0.0
    for slope_deg, length_m in cells:
        if slope_in_band(slope_deg, spec.band_deg, spec.upper_inclusive):
            total += length_m
    return total


@dataclass(frozen=True)
class ExposureTotals:
    requirement_id: str
    unique_m: float
    traversed_m: float

    def counted_m(self, spec: ExposureSpec) -> float:
        """The total that counts toward the requirement under its declared counting semantics."""
        return self.unique_m if spec.counting == "UNIQUE_UNDIRECTED_EDGE_DISTANCE" else self.traversed_m


def accumulate_exposure(
    traversals: Sequence[tuple[str, Sequence[float]]], specs: Sequence[ExposureSpec]
) -> list[ExposureTotals]:
    """Accumulate exposure over a traversal list of ``(undirected_edge_id, band_length_per_spec)``.

    ``band_length_per_spec[i]`` is the in-band horizontal length of that edge for ``specs[i]``.  The second
    traversal of an edge adds to ``traversed_m`` only.
    """
    seen: set[str] = set()
    unique = [0.0] * len(specs)
    traversed = [0.0] * len(specs)
    for edge_id, lengths in traversals:
        first = edge_id not in seen
        seen.add(edge_id)
        for index in range(len(specs)):
            traversed[index] += lengths[index]
            if first:
                unique[index] += lengths[index]
    return [ExposureTotals(specs[index].requirement_id, unique[index], traversed[index]) for index in range(len(specs))]
