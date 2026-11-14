"""Spreadsheet-safe qualification table, using existing measured values only."""

from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

from analogforge.ports.domain_models import MeasuredMetric, Requirement
from analogforge.ports.passport_renderer import CSV_COLUMNS, PassportExportBundle

from .escaping import spreadsheet_cell


def metric_key(req: Requirement) -> str | None:
    if req.observable == "slope_band_area_fraction" and req.parameters.slope_band_deg:
        lo, hi = req.parameters.slope_band_deg
        return f"slope_area_fraction:{lo:g}-{hi:g}"
    return {
        "slope_distribution_w1_deg": "slope_w1_deg",
        "unique_slope_exposure_m": f"unique_exposure_m:{req.id}",
        "completed_task_count": "tasks_completed",
        "final_battery_reserve_pct": "reserve_pct",
        "surface_temperature_min_k": "min_temperature_k",
    }.get(req.observable)


def metric_value(metrics: list[MeasuredMetric], key: str | None) -> float | None:
    return next((m.value for m in metrics if m.metric_id == key), None)


def render_csv(bundle: PassportExportBundle) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    evidence = {e.id: e for e in bundle.evidence_appendix}
    qualifications = {(q.candidate_id, q.requirement_id): q for q in bundle.qualifications}
    for candidate in bundle.candidates:
        attempts = [a for a in bundle.attempts if a.candidate_id == candidate.id]
        latest = max(attempts, key=lambda a: a.attempt_number) if attempts else None
        for req in bundle.mission.requirements:
            row = qualifications.get((candidate.id, req.id))
            cited_metrics = (
                [m for eid in row.evidence_ids if eid in evidence for m in evidence[eid].metrics] if row else []
            )
            claim = (
                next(
                    (
                        c
                        for c in bundle.assurance.claims
                        if c.requirement_id == req.id and candidate.id in c.candidate_ids
                    ),
                    None,
                )
                if bundle.assurance
                else None
            )
            fields: dict[str, Any] = dict(
                passport_id=bundle.passport.id,
                run_id=bundle.passport.run_id,
                mode=bundle.mode,
                mission_revision_id=bundle.mission.id,
                rover_revision_id=bundle.rover.id if bundle.rover else None,
                candidate_id=candidate.id,
                candidate_name=candidate.name,
                requirement_id=req.id,
                requirement_label=req.label,
                mandatory=str(req.mandatory).lower(),
                qualification_status=row.status if row else "PENDING",
                evaluation_stage=getattr(row, "evaluation_stage", "") if row else "",
                observable=req.observable,
                operator=req.operator,
                threshold_lower=req.lower,
                threshold_upper=req.upper,
                unit=req.unit,
                target_value=metric_value(bundle.target_profile.metrics, metric_key(req))
                if bundle.target_profile
                else None,
                earth_value=metric_value(cited_metrics, metric_key(req)),
                comparison_scale_m=row.comparison_scale_m if row else None,
                confidence=row.confidence if row else "UNASSESSED",
                critic_status=row.critic_status if row else "UNREVIEWED",
                limitations=" | ".join(dict.fromkeys([
                    *(row.limitations if row else ["Not assessed"]),
                    *(claim.limitations if claim else []),
                ])),
                evidence_ids=" | ".join(str(i) for i in row.evidence_ids) if row else "",
                verification_outcome=latest.result.outcome if latest else "",
                assurance_disposition=claim.disposition if claim else "",
                manifest_sha256=bundle.manifest_sha256,
            )
            writer.writerow({key: spreadsheet_cell(value) for key, value in fields.items()})
    return stream.getvalue().encode("utf-8")


def referenced_ids(bundle: PassportExportBundle) -> list[UUID]:
    return sorted({eid for q in bundle.qualifications for eid in q.evidence_ids}, key=str)
