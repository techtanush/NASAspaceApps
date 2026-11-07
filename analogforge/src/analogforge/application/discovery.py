"""Bounded candidate identity/projections and data-driven next-candidate picker."""

from typing import Any

from analogforge.domain.ids import envelope
from analogforge.ports.domain_models import EarthAnalogCandidate
from analogforge.ports.science_payloads import CandidateRef


def reference(candidate: dict[str, Any]) -> CandidateRef:
    return CandidateRef.model_validate(
        {
            "window_id": candidate["window_id"],
            "candidate_id": candidate["id"],
            **{k: candidate[k] for k in ("name", "aoi", "origin", "novelty_status", "discovery_method")},
        }
    )


def candidate_record(
    window: dict[str, Any], workspace_id: str, run_id: str, mode: str, evidence_ids: list[str]
) -> dict[str, Any]:
    candidate = EarthAnalogCandidate.model_validate(
        {
            **envelope(workspace_id, run_id, mode),
            **{k: window[k] for k in ("name", "aoi", "origin", "novelty_status")},
            "discovery_method": "mission-conditioned-bounded-screen",
            "evidence_ids": evidence_ids,
            "metrics": [],
            "accessibility_status": "NOT_ASSESSED",
            "limitations": [],
        }
    ).model_dump(mode="json")
    return {
        **candidate,
        "window_id": window["window_id"],
        "screening_rank": window.get("rank"),
        "analysis_payload": None,
    }


def pick_replan_candidate(
    candidates: list[dict[str, Any]], qualifications: list[dict[str, Any]], attempted_ids: set[str]
) -> dict[str, Any] | None:
    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate["id"] in attempted_ids or not candidate.get("analysis_payload"):
            continue
        rows = [
            q
            for q in qualifications
            if q["candidate_id"] == candidate["id"] and q["requirement_id"] == "R-SLOPE-AVAILABILITY"
        ]
        if rows and rows[-1]["status"] == "FAIL":
            continue
        eligible.append(candidate)

    def order(candidate: dict[str, Any]) -> tuple[float, int, str]:
        zones = candidate["analysis_payload"].get("connected_zones", [])
        band_area = sum(sum(z["band_area_m2"].values()) for z in zones if z["contains_start"])
        return (-band_area, candidate.get("screening_rank") or 10**6, candidate["window_id"])

    return min(eligible, key=order) if eligible else None
