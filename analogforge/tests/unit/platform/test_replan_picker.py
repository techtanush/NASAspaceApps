"""Architecture 40 s4 replan picker, with band areas observed from the real science engine (2026-11-12 browser run).

Summing every ``band_area_m2`` key let wide low-slope bands dominate and picked the rolling window grid-r1c0; the
normative order uses the start-zone area of the availability requirement's own band, so B (grid-r0c0) is chosen.
"""

from __future__ import annotations

from analogforge.application.discovery import availability_band_key, pick_replan_candidate

MISSION = {"requirements": [{"id": "R-SLOPE-AVAILABILITY", "parameters": {"slope_band_deg": [12.0, 18.0]}}]}


def candidate(cid: str, window: str, rank: int, bands: dict[str, float]) -> dict:
    zone = {"contains_start": True, "band_area_m2": bands}
    return {"id": cid, "window_id": window, "screening_rank": rank, "analysis_payload": {"connected_zones": [zone]}}


def availability(cid: str, status: str) -> dict:
    return {"candidate_id": cid, "requirement_id": "R-SLOPE-AVAILABILITY", "status": status}


CANDIDATES = [
    candidate("a", "grid-r0c1", 1, {"0-90": 8_740_800.0, "12-18": 0.0}),
    candidate("b", "grid-r0c0", 2, {"0-90": 14_284_800.0, "0-18": 14_284_800.0, "12-18": 2_041_200.0}),
    candidate(
        "rolling1", "grid-r1c0", 4, {"0-90": 14_284_800.0, "0-18": 14_284_800.0, "2-8": 5_371_200.0, "12-18": 414_000.0}
    ),
    candidate("known", "grid-r2c2", 3, {"0-90": 11_030_400.0, "12-18": 0.0}),
    candidate("flat", "grid-r0c2", 6, {"0-90": 14_187_600.0, "12-18": 0.0}),
]
QUALIFICATIONS = [
    availability("rolling1", "PASS"),
    availability("b", "PASS"),
    availability("known", "PASS"),
    availability("flat", "FAIL"),
]


def test_band_key_matches_science_formatting():
    assert availability_band_key(MISSION) == "12-18"
    assert availability_band_key({"requirements": []}) is None


def test_picker_uses_the_requirement_band_and_chooses_b():
    chosen = pick_replan_candidate(CANDIDATES, QUALIFICATIONS, {"a"}, MISSION)
    assert chosen is not None and chosen["window_id"] == "grid-r0c0"


def test_failed_availability_is_ineligible_and_known_with_zero_band_area_is_last():
    chosen = pick_replan_candidate(CANDIDATES, QUALIFICATIONS, {"a", "b", "rolling1"}, MISSION)
    assert chosen is not None and chosen["window_id"] == "grid-r2c2"
