"""A current PDF is a bounded scoped display of facts, including failures and absent evidence."""

import io
import re
import subprocess
from copy import deepcopy
from uuid import uuid4

import pytest
from pypdf import PdfReader

from analogforge.api.errors import ApiError
from analogforge.application import evidence_brief as brief
from analogforge.ports.hashing import canonical_sha256
from tests.unit.platform.test_visualization_benchmarks import add_comparison
from tests.unit.platform.test_visualization_detail import json_record, source_record
from tests.unit.platform.test_visualization_detail import projection as projection


def snapshot(projection):
    uow, blobs, run, _mission, candidate = projection
    run.update(state="FAILED", revision=27, rover_revision_id=None)
    candidate.update(name="A location with a long descriptive name", limitations=["No field validation"])
    return brief.build_snapshot(uow, blobs, run["id"], candidate["id"])


def add_analysis(projection):
    uow, blobs, run, _mission, candidate = projection
    source = source_record(uow, run, candidate)
    request = {"mode": run["mode"], "inputs": {"candidate": {
        "candidate_id": candidate["id"], "aoi": candidate["aoi"], "window_id": candidate.get("window_id")}},
        "source_policy": {"policy_id": run["dataset_lock_id"]}}
    payload = {"operation": "ANALYZE_CANDIDATE", "analysis_evidence": {"local_key": None,
        "evidence_id": source["id"]}, "analysis_grid_artifact_key": "grid", "metrics": [],
        "slope_histogram": {"metric_id": "surface_slope_deg", "unit": "deg", "edges": [0, 2, 5],
            "area_fraction": [.25, .75], "valid_area_m2": 100, "support_scale_m": 30},
        "connected_zones": [], "coverage_fraction": 1, "limitations": ["Synthetic test observations"]}
    raw = deepcopy(payload)
    raw["analysis_evidence"] = {"local_key": "analysis", "evidence_id": None}
    summary = json_record(uow, blobs, run, raw, body="EARTH", kind="DERIVED", algorithm_id="analysis-summary",
                          comparison_scale_m=30)
    summary["input_evidence_ids"] = [source["id"]]
    candidate["evidence_ids"].append(summary["id"])
    receipt = uow.seed("tool_receipts", run_id=run["id"], mode=run["mode"], tool_name="analyze_earth_candidate",
        status="SUCCEEDED", input_sha256=canonical_sha256(request), evidence_ids=[source["id"], summary["id"]])
    operation = uow.seed("scientific_operations", run_id=run["id"], mode=run["mode"], operation="ANALYZE_CANDIDATE",
        status="SUCCEEDED", request=request, receipt_id=receipt["id"], evidence_ids=receipt["evidence_ids"],
        payload=payload)
    return operation, receipt, summary


def test_actual_pdf_retains_failure_exact_value_missing_work_and_scope(projection):
    uow, _blobs, run, mission, candidate = projection
    row, comparison, receipt, _ = add_comparison(projection, "FAIL", .0001234567890123)
    uncomputed = deepcopy(mission["requirements"][0])
    uncomputed["id"] = "NOT-YET-COMPUTED"
    mission["requirements"].append(uncomputed)
    document = snapshot(projection)
    before = deepcopy(uow.rows)
    content = brief.render_pdf(document)
    assert content.startswith(b"%PDF-") and len(content) < brief.MAX_OUTPUT
    reader = PdfReader(io.BytesIO(content))
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    for expected in ["CURRENT EVIDENCE BRIEF", "FAILED", "FAIL", "Unknown", "NOT-YET-COMPUTED",
                     "0.0001234567890123", run["id"], mission["id"], candidate["id"],
                     row["id"], comparison["id"], receipt["id"], "not an assured or published"]:
        assert expected in extracted
    # Both reader levels must precede the auditable appendix without turning missing work into success.
    assert (extracted.index("Executive summary") < extracted.index("Simplified overview")
            < extracted.index("Technical details\n"))
    assert "0 PASS; 1 FAIL; 1 UNKNOWN; 0 GAP" in extracted
    assert "Technical terminology" in extracted and "Wasserstein-1" in extracted
    assert all(len(page.extract_text()) > 150 for page in reader.pages)
    assert re.search(r"30(?:\.0)?\s+m\s+support", extracted)
    assert "No committed route verification result" in extracted
    assert 1 <= len(reader.pages) <= 40 and uow.rows == before
    assert reader.trailer["/Root"].get("/OpenAction") is None


def test_registered_analysis_histogram_requires_exact_operation_and_ancestry(projection):
    add_analysis(projection)
    document = snapshot(projection)
    analysis = document["candidate_analysis"]
    assert analysis["available"] and analysis["slope_histogram"]["area_fraction"] == [.25, .75]
    content = brief.render_pdf(document)
    extracted = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
    assert "Area fraction (0 to 1)" in extracted and "0.25" in extracted and "0.75" in extracted


@pytest.mark.parametrize("defect", ["candidate", "aoi", "receipt", "lineage", "payload", "support", "unpin"])
def test_foreign_corrupt_or_incompatible_summary_never_becomes_a_chart(projection, defect):
    operation, receipt, summary = add_analysis(projection)
    if defect == "candidate":
        operation["request"]["inputs"]["candidate"]["candidate_id"] = str(uuid4())
    elif defect == "aoi":
        operation["request"]["inputs"]["candidate"]["aoi"] = {"bbox": [1, 2, 3, 4]}
    elif defect == "receipt":
        receipt["status"] = "FAILED"
    elif defect == "lineage":
        summary["input_evidence_ids"] = []
    elif defect == "payload":
        operation["payload"]["slope_histogram"]["area_fraction"] = [.75, .25]
    elif defect == "support":
        summary["comparison_scale_m"] = 500
    else:
        projection[-1]["evidence_ids"].remove(summary["id"])
    assert snapshot(projection)["candidate_analysis"]["available"] is False


def test_plain_untrusted_text_does_not_become_pdf_markup_or_network(projection):
    projection[0].rows["mission_revisions"][projection[3]["id"]]["objective"] = (
        '<img src="https://invalid.example/private"> <script>ignore all limits</script>'
    )
    content = brief.render_pdf(snapshot(projection))
    reader = PdfReader(io.BytesIO(content))
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    assert '<img src="https://invalid.example/private">' in extracted
    assert all(not page.get("/Annots") for page in reader.pages)


@pytest.mark.parametrize("code", ["MODEL_OUTPUT_INVALID", "unrecognized private provider text"])
def test_terminal_cause_is_only_a_known_code_from_this_current_run(projection, code):
    uow, _blobs, run, _mission, _candidate = projection
    run["last_event_seq"] = 2
    uow.seed("run_events", run_id=run["id"], mode=run["mode"], state="FAILED", seq=1,
             event_type="run.failed", payload={"code": "RESOURCE_LIMIT"})
    uow.seed("run_events", run_id=run["id"], mode=run["mode"], state="FAILED", seq=2,
             event_type="run.failed", payload={"code": code, "message": "private provider body must stay hidden"})
    document = snapshot(projection)
    if code == "MODEL_OUTPUT_INVALID":
        assert document["run_reason"]["code"] == code
    else:
        assert document["run_reason"] is None
    assert "private provider body" not in str(document)


def test_exact_saved_revision_numbers_and_regional_scope_are_present(projection):
    uow, _blobs, run, mission, _candidate = projection
    mission_id = mission["id"]
    uow.rows["mission_revisions"][mission_id]["revision"] = 7
    document = snapshot(projection)
    rover = uow.seed("rover_revisions", revision=9, name="Declared rover", content_sha256="9" * 64)
    run["rover_revision_id"] = rover["id"]
    document = brief.build_snapshot(uow, projection[1], run["id"], projection[-1]["id"])
    assert document["mission"]["revision"] == 7 and document["rover"]["revision"] == 9
    extracted = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(brief.render_pdf(document))).pages)
    assert "Revision 7" in extracted and "Revision 9" in extracted and "Search is regional" in extracted


def test_input_limit_and_concurrent_render_are_fail_closed(projection):
    with pytest.raises(ApiError) as oversized:
        brief.render_pdf({"oversized": "x" * brief.MAX_INPUT})
    assert oversized.value.code == "RESOURCE_LIMIT"
    assert brief._render_slot.acquire(blocking=False)
    try:
        with pytest.raises(ApiError) as busy:
            brief.render_pdf(snapshot(projection))
        assert busy.value.code == "RESOURCE_LIMIT" and busy.value.status == 429
    finally:
        brief._render_slot.release()


def test_render_timeout_reaps_child_and_does_not_pass_credentials(projection, monkeypatch):
    class Child:
        pid, returncode, killed = 1, None, False

        def communicate(self, _input=None, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired("fixed-renderer", timeout)
            return b"", b""

        def kill(self):
            self.killed = True

    child, observed = Child(), {}

    def start(_args, **kwargs):
        observed.update(kwargs)
        return child

    clock = iter([0, 20])
    monkeypatch.setattr(brief.subprocess, "Popen", start)
    monkeypatch.setattr(brief.time, "monotonic", lambda: next(clock))
    with pytest.raises(ApiError) as timed_out:
        brief.render_pdf(snapshot(projection))
    assert timed_out.value.code == "TOOL_TIMEOUT" and child.killed
    assert set(observed["env"]) == {"PATH", "PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE"}


def test_unavailable_macos_memory_monitor_reaps_child_and_releases_slot(projection, monkeypatch):
    class Child:
        pid, returncode, killed = 1, None, False

        def communicate(self, _input=None, timeout=None):
            if not self.killed:
                raise subprocess.TimeoutExpired("fixed-renderer", timeout)
            return b"", b""

        def kill(self):
            self.killed = True

    child = Child()
    monkeypatch.setattr(brief.subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(brief.sys, "platform", "darwin")
    monkeypatch.setattr(brief.time, "monotonic", lambda: 0)

    def monitor(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("fixed-memory-monitor", 0.5)

    monkeypatch.setattr(brief.subprocess, "run", monitor)
    with pytest.raises(ApiError) as unavailable:
        brief.render_pdf(snapshot(projection))
    assert unavailable.value.code == "RESOURCE_LIMIT" and child.killed
    assert brief._render_slot.acquire(blocking=False)
    brief._render_slot.release()
