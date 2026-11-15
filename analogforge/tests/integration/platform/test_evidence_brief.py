"""A real PostgreSQL-backed failed run can download its own stored evidence, without new work."""

import io
from uuid import uuid4

from pypdf import PdfReader

from analogforge.application.evidence_brief import build_snapshot
from tests.integration.platform.test_runtime_journey import advance_until
from tests.integration.platform.test_runtime_journey import runtime as runtime
from tests.integration.platform.test_visualization_api import _client, _counts


def test_failed_run_pdf_is_scoped_real_and_readonly(runtime, tmp_path):
    engine, store, ws, make = runtime
    run = advance_until(engine, make(no_rover=True), ws, {"QUALIFYING", "BLOCKED", "FAILED"})
    assert run["state"] == "QUALIFYING" and run["candidate_ids"]
    with store.transaction(ws) as unit:
        run = unit.require("runs", run["run_id"])
        run.update(state="FAILED")
        unit.replace("runs", run["run_id"], run, run["revision"])
    before = _counts(store, ws, run["run_id"])
    candidate_id = run["candidate_ids"][0]
    with store.transaction(ws) as unit:
        document = build_snapshot(unit, engine.blobs, run["run_id"], candidate_id)
        assert document["candidate_analysis"]["available"] and document["target_analysis"]["available"]
        assert document["search_scope"]["search_extent"]
    path = f"/api/v1/runs/{run['run_id']}/candidates/{candidate_id}/evidence-brief.pdf"
    with _client(engine, store, ws) as client:
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF-") and response.headers["content-type"] == "application/pdf"
        assert "no-store" in response.headers["cache-control"]
        assert response.headers["content-disposition"].startswith("attachment;")
        (tmp_path / "evidence-brief.pdf").write_bytes(response.content)
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
        for expected in ("FAILED", "CURRENT EVIDENCE BRIEF", "Unknown", run["mission_revision_id"], candidate_id):
            assert expected in text
        assert "Area fraction (0 to 1)" in text  # actual registered terrain summary, not an invented benchmark
        missing = client.get(path.replace(candidate_id, str(uuid4())))
        assert missing.status_code == 404
        malformed = client.get(path.replace(candidate_id, "not-a-uuid"))
        assert malformed.status_code == 422
        assert client.get(path + "?candidate_id=other").status_code == 422
        other_run = make(no_rover=True)
        assert client.get(path.replace(run["run_id"], other_run["run_id"])).status_code == 404
        plan_path = path.replace("evidence-brief.pdf", "test-plan")
        plan = client.get(plan_path)
        assert plan.status_code == 200 and plan.json()["candidate_id"] == candidate_id
        assert plan.json()["route"] is None and "no-store" in plan.headers["cache-control"]
        assert client.get(plan_path + "?other=1").status_code == 422
        combined = client.get(f"/api/v1/runs/{run['run_id']}/test-brief.pdf")
        assert combined.status_code == 200, combined.text
        assert combined.content.startswith(b"%PDF-")
        reader = PdfReader(io.BytesIO(combined.content))
        assert reader.outline and all(identifier in "\n".join(p.extract_text() for p in reader.pages)
                                      for identifier in run["candidate_ids"])
    assert _counts(store, ws, run["run_id"]) == before
    foreign = str(uuid4())
    store.ensure_workspace(foreign)
    with _client(engine, store, foreign) as client:
        denied = client.get(path)
        assert denied.status_code == 404 and run["mission_revision_id"] not in denied.text
        assert client.get(path.replace("evidence-brief.pdf", "test-plan")).status_code == 404
        assert client.get(f"/api/v1/runs/{run['run_id']}/test-brief.pdf").status_code == 404
