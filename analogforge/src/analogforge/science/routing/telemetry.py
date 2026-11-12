"""Per-node route telemetry (``TelemetryArtifact``) built from independently recomputed cumulative quantities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from analogforge.ports.science_payloads import TelemetryArtifact, TelemetrySample


@dataclass
class TelemetryRow:
    """Recomputed state when the route arrives at node ``index`` (after task completion at that node)."""

    node_id: str
    cumulative_distance_m: float
    elapsed_s: float
    lon: float | None = None
    lat: float | None = None
    elevation_m: float | None = None
    segment_surface_slope_deg: float | None = None
    cumulative_energy_conservative_wh: float | None = None
    in_band_requirement_ids: list[str] = field(default_factory=list)


def reserve_pct(battery_wh: float, cumulative_conservative_wh: float | None) -> float | None:
    """``100 * (battery - E) / battery``; may be negative (never clamped); ``None`` when energy is unknown."""
    if cumulative_conservative_wh is None:
        return None
    return 100.0 * (battery_wh - cumulative_conservative_wh) / battery_wh


def build_telemetry(
    rows: Sequence[TelemetryRow], *, route_sha256: str, constraints_sha256: str, battery_wh: float
) -> TelemetryArtifact:
    samples = [
        TelemetrySample(
            index=index,
            node_id=row.node_id,
            cumulative_distance_m=row.cumulative_distance_m,
            elapsed_s=row.elapsed_s,
            lon=row.lon,
            lat=row.lat,
            elevation_m=row.elevation_m,
            segment_surface_slope_deg=row.segment_surface_slope_deg,
            cumulative_energy_conservative_wh=row.cumulative_energy_conservative_wh,
            reserve_pct=reserve_pct(battery_wh, row.cumulative_energy_conservative_wh),
            in_band_requirement_ids=list(row.in_band_requirement_ids),
        )
        for index, row in enumerate(rows)
    ]
    return TelemetryArtifact(route_sha256=route_sha256, constraints_sha256=constraints_sha256, samples=samples)
