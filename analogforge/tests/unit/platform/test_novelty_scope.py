"""SCI-14 platform wording and enums never establish global scientific novelty."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from analogforge.application.assurance import audit
from analogforge.application.discovery import candidate_record
from tests.integration.platform.test_assurance import audit_case
from tests.integration.platform.test_passport_assembly import passport_case


def test_discovery_claim_is_explicitly_bounded_by_search_and_reference_scope():
    snapshot, claim, receipts = audit_case("FAIL")
    claim = replace(
        claim,
        claim_type="DISCOVERY",
        requirement_id=None,
        qualification_status=None,
        scope="locked search-region test-region and reference-list test-reference",
    )
    report = audit(snapshot, [claim], receipts)
    statement = report.claims[0].permitted_statement
    assert statement == (
        "Candidate identified within the declared search and reference-list scope "
        "(locked search-region test-region and reference-list test-reference)."
    )
    assert "globally novel" not in statement.lower()


def test_reference_list_absence_is_preserved_and_global_novelty_label_is_rejected():
    candidate = passport_case().candidates[0].model_dump(mode="json")
    candidate.update(window_id="bounded-test-window", novelty_status="NOT_IN_REFERENCE_LIST")
    result = candidate_record(
        candidate, candidate["workspace_id"], candidate["run_id"], "synthetic", candidate["evidence_ids"]
    )
    assert result["novelty_status"] == "NOT_IN_REFERENCE_LIST"
    candidate["novelty_status"] = "GLOBALLY_NOVEL"
    with pytest.raises(ValidationError):
        candidate_record(
            candidate, candidate["workspace_id"], candidate["run_id"], "synthetic", candidate["evidence_ids"]
        )
