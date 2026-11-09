import csv
import io

from analogforge.ports.passport_renderer import CSV_COLUMNS
from analogforge.rendering.passport import create_passport_renderer
from passport_renderer.fixtures.builders import build_bundle


def csv_rows(bundle):
    return list(csv.DictReader(io.StringIO(create_passport_renderer().render(bundle, [], "csv").content.decode())))


def test_csv_contract(bundle):
    rows = csv_rows(bundle)
    assert len(rows) == len(bundle.candidates) * len(bundle.mission.requirements)
    assert tuple(rows[0]) == CSV_COLUMNS
    assert all(r["manifest_sha256"] == bundle.manifest_sha256 for r in rows)
    for row in rows:
        req = next(r for r in bundle.mission.requirements if r.id == row["requirement_id"])
        candidate = next(c for c in bundle.candidates if str(c.id) == row["candidate_id"])
        q = next(q for q in bundle.qualifications if q.candidate_id == candidate.id and q.requirement_id == req.id)
        assert row["qualification_status"] == q.status
        assert row["evaluation_stage"] == ""
        if req.id == "R-SLOPE-AVAILABILITY":
            assert row["target_value"] == ("0.15" if bundle.rover is None else "0.2")
            assert float(row["earth_value"]) == (0.4, 0.1, 0.08, 0.03, 0.02, 0.0)[bundle.candidates.index(candidate)]
        if req.id in ("R-MINERAL", "R-CLEARANCE"):
            assert row["earth_value"] == ""
        attempts = [a for a in bundle.attempts if a.candidate_id == candidate.id]
        assert row["verification_outcome"] == (
            max(attempts, key=lambda a: a.attempt_number).result.outcome if attempts else ""
        )


def test_missing_rows_are_pending_and_formula_safe():
    bundle = build_bundle()
    bundle = bundle.model_copy(update={"qualifications": []})
    bundle.candidates[0].name = "=SUM(A1:A2)"
    rows = csv_rows(bundle)
    assert all(r["qualification_status"] == "PENDING" for r in rows)
    assert rows[0]["candidate_name"] == "'=SUM(A1:A2)"
    assert rows[0]["earth_value"] == ""


def test_metric_mappings_and_evidence_scoping():
    from analogforge.ports.domain_models import MeasuredMetric
    from passport_renderer.fixtures.builders import metric

    bundle = build_bundle()
    rows = csv_rows(bundle)
    b_rows = {r["requirement_id"]: r for r in rows if r["candidate_id"] == str(bundle.candidates[1].id)}
    assert b_rows["R-TARGET-SLOPE-CONTEXT"]["earth_value"] == "4.0"
    assert b_rows["R-EXPOSURE"]["earth_value"] == "150.0"
    assert b_rows["R-TASKS"]["earth_value"] == "2.0"
    assert b_rows["R-RESERVE"]["earth_value"] == "98.33333333333333"
    bundle.evidence_appendix[1].metrics = [MeasuredMetric.model_validate(metric("unique_exposure_m:R-EXPOSURE", 175))]
    b_rows = {r["requirement_id"]: r for r in csv_rows(bundle) if r["candidate_id"] == str(bundle.candidates[1].id)}
    assert b_rows["R-EXPOSURE"]["earth_value"] == "175.0"
    assert b_rows["R-TASKS"]["earth_value"] == ""
    assert b_rows["R-RESERVE"]["earth_value"] == ""
    assert b_rows["R-EXPOSURE"]["target_value"] == ""


def test_thermal_metric_mapping():
    from analogforge.ports.domain_models import MeasuredMetric
    from passport_renderer.fixtures.builders import metric

    bundle = build_bundle("limited")
    bundle.evidence_appendix[0].metrics = [MeasuredMetric.model_validate(metric("min_temperature_k", 88, "K"))]
    rows = csv_rows(bundle)
    row = next(
        r for r in rows if r["requirement_id"] == "R-THERMAL" and r["candidate_id"] == str(bundle.candidates[0].id)
    )
    assert row["earth_value"] == "88.0"
    assert row["target_value"] == ""


def test_header_matches_the_frozen_plain_column_contract():
    content = create_passport_renderer().render(build_bundle(), [], "csv").content.decode()
    assert content.splitlines()[0] == ",".join(CSV_COLUMNS)
