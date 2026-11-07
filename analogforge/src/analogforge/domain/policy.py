"""Authoritative evidence/reference checks around untrusted role proposals."""

from collections.abc import Mapping, Sequence
from typing import Any

from analogforge.domain.confidence import bounded_confidence


class PolicyViolation(ValueError):
    def __init__(self, reason: str, code: str = "MODEL_OUTPUT_INVALID") -> None:
        super().__init__(reason)
        self.code = code
        self.detail_code = reason


def evaluate_transition(
    snapshot: Mapping[str, Any],
    proposal: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    *,
    evidence: Mapping[str, Mapping[str, Any]],
    allowed_actions: Sequence[str],
    expected_revision: int | None = None,
) -> None:
    if expected_revision is not None and snapshot["revision"] != expected_revision:
        raise PolicyViolation("STALE_REVISION", "REVISION_CONFLICT")
    for key in ("mission_content_sha256", "rover_content_sha256"):
        if key in proposal and proposal[key] != snapshot.get(key):
            raise PolicyViolation("FROZEN_INPUT_CHANGED")
    if proposal.get("next_action") is not None and proposal["next_action"] not in allowed_actions:
        raise PolicyViolation("UNLISTED_ACTION")
    good = {str(x) for r in receipts if r.get("status") == "SUCCEEDED" for x in r.get("evidence_ids", [])}
    for eid in proposal.get("evidence_ids", []):
        record = evidence.get(str(eid))
        if record is None or str(eid) not in good:
            raise PolicyViolation("EVIDENCE_NOT_ESTABLISHED")
        if str(record["workspace_id"]) != str(snapshot["workspace_id"]) or str(record["run_id"]) != str(
            snapshot["run_id"]
        ):
            raise PolicyViolation("WORKSPACE_SCOPE_MISMATCH", "INPUT_INVALID")
        if record["mode"] != snapshot["mode"]:
            raise PolicyViolation("MODE_MISMATCH", "INPUT_INVALID")


def validate_comparison(proposal: Mapping[str, Any], computed: Mapping[str, Any]) -> None:
    if proposal.get("proposed_status") != computed.get("proposed_status"):
        raise PolicyViolation("STATUS_INFLATION")
    bounded_confidence(proposal["confidence"], computed["confidence"], unquantified=computed.get("unquantified", False))
    for key in ("threshold_lower", "threshold_upper", "measured_value", "measured_unit", "comparison_scale_m"):
        if key in proposal and proposal[key] != computed.get(key):
            raise PolicyViolation("COMPUTED_FIELD_CHANGED")


def validate_repair(repair: str | None, diagnosis: Mapping[str, Any], contract_hash: str, preserved_hash: str) -> None:
    if contract_hash != preserved_hash:
        raise PolicyViolation("FROZEN_INPUT_CHANGED")
    if repair is not None and repair not in diagnosis.get("permitted_repairs", []):
        raise PolicyViolation("REPAIR_NOT_PERMITTED")
