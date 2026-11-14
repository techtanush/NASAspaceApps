"""Valid synthetic presentation fixtures; none are executed science receipts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from analogforge.ports.common import RuntimeMode
from analogforge.ports.hashing import canonical_json_bytes, canonical_sha256
from analogforge.ports.passport_renderer import PassportExportBundle

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_NAMES = (
    "positive",
    "supported-negative",
    "limited",
    "failed-with-replan",
    "inconclusive",
    "composite",
    "hostile-strings",
    "replay",
    "draft",
)
TIME = "2026-11-08T12:00:00Z"
HASH = "1" * 64


def uid(number: int) -> str:
    return str(UUID(int=number + 0x70000000000040008000000000000000))


def read_kit(name: str) -> Any:
    return json.loads((ROOT / "fixtures" / "kit" / name).read_text())


def metric(name: str, value: float | None, unit: str = "m", support: float = 60) -> dict[str, Any]:
    return dict(
        metric_id=name,
        value=value,
        unit=unit,
        support_scale_m=support,
        quantity_kind="DERIVED",
        method_id="synthetic-presentation-fixture-v1",
        valid_fraction=1.0,
        uncertainty_note="Synthetic fixture; not a field measurement.",
    )


def build_bundle(name: str = "failed-with-replan", *, mode_override: RuntimeMode | None = None) -> PassportExportBundle:
    """Author presentation data from S-RASTER-1, with explicit unknowns and gaps."""
    if name not in FIXTURE_NAMES:
        raise ValueError(f"Unknown fixture {name}")
    mode = mode_override or ("replay" if name == "replay" else "synthetic")
    common: dict[str, Any] = dict(schema_version="1.0", workspace_id=uid(1), run_id=uid(2), mode=mode, created_at=TIME)
    preset = read_kit("missions/mission-mars-mobility.json")
    mission = dict(
        schema_version="1.0",
        id=uid(3),
        mission_id=uid(4),
        workspace_id=uid(1),
        revision=1,
        created_at=TIME,
        accepted_at=TIME,
        content_sha256=HASH,
        **preset,
    )
    if name == "limited":
        moon = read_kit("missions/mission-moon-gap.json")
        mission.update(moon)
    if name == "hostile-strings":
        mission["name"] = "<script>alert(\"x\")</script> =cmd|' /C calc'!A0 \u202e" + "x" * 10000
        mission["requirements"][0]["label"] = "=cmd|' /C calc'!A0, \"quoted\"\nsecond line"
        mission["objective"] = '</script><img src=x onerror="alert(1)"> javascript:alert(1)'
    mission["content_sha256"] = canonical_sha256({k: mission[k] for k in preset})
    rover = read_kit("blueprint-rover-profile.json")
    rover.update(id=uid(5), rover_id=uid(6), workspace_id=uid(1), created_at=TIME)
    if name == "limited":
        rover = None
    candidates = []
    evidence = []
    qualifications = []
    statuses = {
        "R-GRAVITY": "GAP",
        "R-ATMOSPHERE": "GAP",
        "R-VACUUM": "GAP",
        "R-CLEARANCE": "UNKNOWN",
        "R-MINERAL": "UNKNOWN",
        "R-THERMAL": "UNKNOWN",
    }
    for ci, window in enumerate(("grid-r0c1", "grid-r0c0", "grid-r2c2", "grid-r1c0", "grid-r2c0", "grid-r0c2")):
        cid, eid = uid(10 + ci), uid(20 + ci)
        a_attempted = ci == 0 and name not in ("positive", "limited", "inconclusive", "draft")
        b_passed = ci == 1 and name not in ("supported-negative", "limited", "inconclusive", "draft")
        route_evaluated = a_attempted or b_passed
        metrics = [
            metric("slope_area_fraction:12-18", (0.4, 0.1, 0.08, 0.03, 0.02, 0.0)[ci], "fraction"),
            metric("slope_w1_deg", 4.0, "deg", 480),
            metric("unique_exposure_m:R-EXPOSURE", 0 if a_attempted else 150 if b_passed else None),
            metric("tasks_completed", 2 if route_evaluated else None, "count"),
            metric("reserve_pct", 98.33333333333333 if route_evaluated else None, "percent"),
        ]
        aoi = dict(
            body="EARTH",
            bbox=[-116.0 + ci, 35.0, -115.9 + ci, 35.1],
            longitude_convention="NEG180_180",
            latitude_type="GEODETIC",
            crs_wkt=None,
            vertical_datum="SYNTHETIC_EARTH_REFERENCE",
        )
        candidates.append(
            dict(
                **common,
                id=cid,
                name=f"Practice {window}",
                aoi=aoi,
                origin="KNOWN_CONTROL" if ci == 2 else "SYNTHETIC_CONTROL" if ci == 5 else "DISCOVERED",
                discovery_method="Synthetic practice screening",
                novelty_status="KNOWN_ANALOG" if ci == 2 else "NOT_IN_REFERENCE_LIST",
                evidence_ids=[eid],
                metrics=metrics,
                accessibility_status="NOT_ASSESSED",
                limitations=["Synthetic practice data; field access is not assessed."],
            )
        )
        evidence.append(
            dict(
                **common,
                id=eid,
                kind="DERIVED",
                artifact_sha256=HASH,
                artifact_media_type="application/json",
                source_uri=None,
                dataset_product_id="practice-earth-grid-v1",
                dataset_version="1",
                granule_id=None,
                license_note="Synthetic fixture only",
                body="EARTH",
                aoi=aoi,
                input_evidence_ids=[],
                parameters_sha256=HASH,
                algorithm_id="analyze-candidate-v1",
                algorithm_version="1.0",
                native_resolution_m=60,
                comparison_scale_m=60,
                metrics=metrics,
                limitations=["Not physical rover execution."],
            )
        )
        for ri, req in enumerate(mission["requirements"]):
            status = statuses.get(req["id"], "PASS")
            if ci >= 3 and req["id"] == "R-SLOPE-AVAILABILITY":
                status = "FAIL"
            if req["id"] in ("R-EXPOSURE", "R-TASKS", "R-RESERVE"):
                status = "PASS" if route_evaluated else "UNKNOWN"
                if a_attempted and req["id"] == "R-EXPOSURE":
                    status = "FAIL"
            qualifications.append(
                dict(
                    **common,
                    id=uid(1000 + ci * 20 + ri),
                    candidate_id=cid,
                    requirement_id=req["id"],
                    status=status,
                    evidence_ids=[eid],
                    rule_id=req["parameters"]["comparison_rule_id"] or "route-verification-v1",
                    rule_version="1.0",
                    confidence="MEDIUM",
                    comparison_scale_m=(960 if name == "limited" else 480)
                    if req["id"] == "R-TARGET-SLOPE-CONTEXT"
                    else 60,
                    explanation=f"Synthetic presentation receipt: {status}.",
                    limitations=["No physical validation; accepted constraints unchanged."],
                    critic_status="RESOLVED",
                    critique_evidence_ids=[],
                )
            )
    target_metrics = [
        metric(
            "slope_area_fraction:12-18",
            0.15 if name == "limited" else 0.2,
            "fraction",
            960 if name == "limited" else 480,
        )
    ]
    target = dict(
        **common,
        id=uid(30),
        target=mission["target"],
        evidence_ids=[],
        metrics=target_metrics,
        unavailable_dimensions=["MINERAL", "PHYSICAL_CLEARANCE"],
    )
    attempts = []
    if name not in ("limited", "draft"):
        outcomes = [
            ("FAIL", "ROUTE", 0, "WAYPOINT_RETURN"),
            ("FAIL", "ANALOG", 0, "EXPOSURE_COVERAGE"),
            ("PASS", None, 1, "EXPOSURE_COVERAGE"),
        ]
        if name == "supported-negative":
            outcomes = outcomes[:2]
        elif name == "inconclusive":
            outcomes = [("INCONCLUSIVE", "SEARCH_LIMIT", 1, "EXPOSURE_COVERAGE")]
        elif name == "positive":
            outcomes = outcomes[2:]
        for i, (outcome, category, ci, strategy) in enumerate(outcomes, 1):
            tid, rid = uid(200 + i), uid(300 + i)
            test = dict(
                **common,
                id=tid,
                candidate_id=candidates[ci]["id"],
                mission_revision_id=mission["id"],
                rover_revision_id=uid(5),
                test_revision=i,
                requirement_ids=[r["id"] for r in mission["requirements"]],
                route_artifact_sha256=HASH if category != "ANALOG" else None,
                waypoints_artifact_sha256=HASH,
                constraints_sha256=HASH,
                required_exposures=[
                    dict(
                        requirement_id="R-EXPOSURE",
                        metric_id="surface_slope_deg",
                        lower=12,
                        upper=18,
                        minimum_distance_m=100,
                    )
                ],
                solver_config=dict(
                    max_expansions=1 if category == "SEARCH_LIMIT" else 10000,
                    max_seconds=60,
                    max_labels_per_node=100,
                    seed=1,
                ),
                assumptions=["Synthetic presentation receipt; limits unchanged."],
            )
            observed = 150 if outcome == "PASS" else None if outcome == "INCONCLUSIVE" else 0
            result = dict(
                **common,
                id=rid,
                test_id=tid,
                outcome=outcome,
                failure_category=category,
                search_status="BUDGET_EXHAUSTED"
                if category == "SEARCH_LIMIT"
                else "EXHAUSTIVE_INFEASIBLE"
                if category == "ANALOG"
                else "FOUND",
                verified_route_sha256=HASH if outcome == "PASS" else None,
                metrics=[metric("unique_exposure_m:R-EXPOSURE", observed)],
                violations=[],
                evidence_ids=[candidates[ci]["evidence_ids"][0]],
                verifier_version="presentation-fixture-v1",
                limitations=["Bounded search; not proof that no route exists."] if category == "SEARCH_LIMIT" else [],
            )
            attempts.append(
                dict(
                    attempt_number=i,
                    parent_attempt_number=i - 1 if i > 1 else None,
                    candidate_id=candidates[ci]["id"],
                    candidate_name=candidates[ci]["name"],
                    strategy=strategy,
                    test=test,
                    result=result,
                    benchmark_rows=[
                        dict(
                            constraint_id="C-EXPOSURE-R-EXPOSURE",
                            requirement_id="R-EXPOSURE",
                            rule=">=100 m unique exposure",
                            measured=observed,
                            threshold=100,
                            unit="m",
                            margin=50 if outcome == "PASS" else None,
                            status=outcome,
                        )
                    ],
                    violations=[],
                    diagnosis_category=category,
                    diagnosis_explanation="Modeled terrain-feasibility result only.",
                    changed_elements=["strategy: WAYPOINT_RETURN → EXPOSURE_COVERAGE"]
                    if i == 2
                    else ["candidate: Practice grid-r0c1 → Practice grid-r0c0"]
                    if i == 3
                    else [],
                )
            )
    assurance = read_kit("blueprint-assurance-limited-unknown.json")
    assurance.update(
        audit_id=uid(40),
        workspace_id=uid(1),
        run_id=uid(2),
        mode=mode,
        created_at=TIME,
        mission_content_sha256=mission["content_sha256"],
        rover_content_sha256=rover["content_sha256"] if rover else None,
    )
    assurance["publication"] = "ALLOWED" if name in ("positive", "supported-negative") else "LIMITED"
    for claim in assurance["claims"]:
        claim.update(
            requirement_id="R-THERMAL" if name == "limited" else "R-CLEARANCE",
            candidate_ids=[c["id"] for c in candidates],
            evidence_ids=[uid(20)],
            permitted_statement="Earth thermal evidence is UNKNOWN; no thermal qualification is supported."
            if name == "limited"
            else "Physical obstacle clearance is UNKNOWN at 60 m support.",
        )
        for gate in claim["gates"]:
            gate["evidence_ids"] = [uid(20)]
    manifest = dict(
        schema_version="1.0",
        mode=mode,
        mission_sha256=mission["content_sha256"],
        scenario="S-RASTER-1" if name != "limited" else "S-MOON-SITE-ONLY",
        limitations=["Synthetic presentation fixtures, not executed science."],
        candidates=candidates,
        qualifications=qualifications,
        attempts=attempts,
    )
    manifest_json = canonical_json_bytes(manifest).decode()
    manifest_sha = canonical_sha256(manifest)
    passport = dict(
        **common,
        id=uid(50),
        mission_revision_id=mission["id"],
        rover_revision_id=rover["id"] if rover else None,
        candidate_ids=[c["id"] for c in candidates],
        portfolio_id=uid(60) if name == "composite" else None,
        qualification_ids=[q["id"] for q in qualifications],
        test_result_ids=[a["result"]["id"] for a in attempts],
        qualified_uses=["Modeled terrain feasibility under the accepted assumptions."]
        if any(a["result"]["outcome"] == "PASS" for a in attempts)
        else [],
        partial_uses=[],
        unsupported_uses=["Lunar gravity and vacuum" if name == "limited" else "Planetary gravity and atmosphere"],
        unknowns=["Earth thermal evidence"] if name == "limited" else ["Physical clearance", "Mineral identity"],
        evidence_ids=[*(c["evidence_ids"][0] for c in candidates), uid(41)],
        manifest_sha256=manifest_sha,
        limitations=["Not NASA data; not physical rover execution."],
        next_steps=["Acquire field evidence at the required physical clearance support."],
        assurance_evidence_id=uid(41),
    )
    portfolio = None
    if name == "composite":
        portfolio = dict(
            **common,
            id=uid(60),
            candidate_ids=[c["id"] for c in candidates],
            requirement_assignments=[
                dict(requirement_id=r["id"], candidate_ids=[uid(11)], coverage="UNKNOWN")
                for r in mission["requirements"]
            ],
            objective_value=0,
            algorithm_id="exhaustive-subset-v1",
            residual_requirement_ids=["R-CLEARANCE"],
            limitations=["Separate campaigns do not establish co-located conditions; logistics unmodeled."],
        )
    compatibility = []
    if rover:
        for candidate in candidates:
            passed = any(a["candidate_id"] == candidate["id"] and a["result"]["outcome"] == "PASS" for a in attempts)
            compatibility.append(
                dict(
                    candidate_id=candidate["id"],
                    rover_revision_id=rover["id"],
                    preliminary=not passed,
                    dimensions=[
                        dict(
                            metric_id="max_surface_slope_deg",
                            status="PASS",
                            rover_value=18,
                            required_value=18,
                            unit="deg",
                            explanation="Declared capability; not observed traversal.",
                            evidence=[],
                        ),
                        dict(
                            metric_id="ground_clearance_m",
                            status="UNKNOWN",
                            rover_value=0.2,
                            required_value=None,
                            unit="m",
                            explanation="60 m support cannot resolve physical clearance.",
                            evidence=[],
                        ),
                        dict(
                            metric_id="energy_reserve_pct",
                            status="PASS" if passed else "UNKNOWN",
                            rover_value=20,
                            required_value=98.33333333333333 if passed else None,
                            unit="percent",
                            explanation="Persisted modeled verifier receipt" if passed else "No verified route",
                            evidence=[],
                        ),
                        dict(
                            metric_id="obstacle_height",
                            status="UNKNOWN",
                            rover_value=None,
                            required_value=None,
                            unit="m",
                            explanation="No physical obstacle evidence.",
                            evidence=[],
                        ),
                    ],
                )
            )
    critiques = []
    if name not in ("limited", "draft"):
        critiques.append(
            dict(
                issue_id=uid(80),
                run_id=uid(2),
                candidate_id=uid(10),
                requirement_id="R-TARGET-SLOPE-CONTEXT",
                target_evidence_ids=[uid(20)],
                reason_code="SCALE_MISMATCH",
                severity="BLOCKING",
                status="RESOLVED",
                summary="60 m evidence replaced with 480 m common-support evidence.",
                repair_request="Cite common-support comparison receipt",
                resolution_evidence_ids=[uid(20)],
            )
        )
    return PassportExportBundle.model_validate(
        dict(
            is_draft=name == "draft",
            generated_at=TIME,
            mode=mode,
            replay_source_run_id=uid(70) if name == "replay" else None,
            passport=passport,
            manifest_sha256=manifest_sha,
            canonical_manifest_json=manifest_json,
            mission=mission,
            rover=rover,
            target_profile=target,
            compatibility=compatibility,
            critiques=critiques,
            candidates=candidates,
            qualifications=qualifications,
            attempts=attempts,
            portfolio=portfolio,
            evidence_appendix=evidence,
            assurance=None if name == "draft" else assurance,
            source_locks=dict(
                dataset_policy_sha256=assurance["dataset_policy_sha256"],
                acquired_manifest_sha256=assurance["acquired_manifest_sha256"],
                config_sha256=HASH,
                algorithm_lock_sha256=assurance["algorithm_lock_sha256"],
            ),
            search_limitations=["Bounded search; not proof that no route exists."] if name == "inconclusive" else [],
            not_run_reason="No rover supplied — site qualification only" if name == "limited" else None,
        )
    )
