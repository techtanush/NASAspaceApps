"""A compact model view retains the complete canonical task and independent authority."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _expand_wire_task, _task_receipt_ids, _wire_task
from analogforge.agents.runtime.wire_context import WireCodec
from analogforge.ports.hashing import canonical_sha256
from tests.integration.platform.test_live_rehearsal import task_and_context


def task_with_audit():
    task, context, registry, counts, _ = task_and_context()
    proposal = deepcopy(task.payload["prepared_submission"])
    evidence = [{"local_key": None, "evidence_id": str(uuid4())} for _ in range(4)]
    gates = [{"gate_id": "SC-01", "outcome": "SATISFIED", "reason": "Pinned inputs match.",
              "evidence": evidence},
             {"gate_id": "SC-14", "outcome": "UNSATISFIED", "reason": "Decoded source is missing.",
              "evidence": []},
             {"gate_id": "SC-15", "outcome": "NOT_APPLICABLE", "reason": "Verification remains unknown.",
              "evidence": evidence},
             {"gate_id": "SC-12", "outcome": "NOT_ASSESSED", "reason": "Engineering input is unavailable.",
              "evidence": []}]
    audit = {"operation": "AUDIT_EVIDENCE", "findings": [{
        "finding_id": "finding-1", "rule_code": "SC-14", "severity": "BLOCKING",
        "message": "Retain UNKNOWN and require source validation.", "evidence_ids": [evidence[0]],
        "requirement_id": "req-1", "required_repair": "ACQUIRE_EVIDENCE_OR_DOWNGRADE",
    }], "claim_gates": [{"claim_id": "discovery:" + str(uuid4()), "gates": deepcopy(gates)} for _ in range(8)]}
    task = task.model_copy(update={"payload": {**task.payload, "authoritative_submission": deepcopy(proposal),
                                              "scientific_audit": audit}})
    return task, context, registry, counts


def test_audit_catalogs_roundtrip_every_fact_without_mutating_task_or_aliasing_evidence():
    task, *_ = task_with_audit()
    original = deepcopy(task.model_dump(mode="json"))
    wire = _wire_task(task)
    assert task.model_dump(mode="json") == original
    assert "prepared_submission" not in wire["payload"]
    audit = wire["payload"]["scientific_audit"]
    assert len(audit["reason_catalog"]) == 4 and len(audit["evidence_catalog"]) == 2
    assert audit["findings"] == original["payload"]["scientific_audit"]["findings"]
    assert [row["claim_id"] for row in audit["claim_gates"]] == [
        row["claim_id"] for row in original["payload"]["scientific_audit"]["claim_gates"]]
    restored = _expand_wire_task(wire)
    assert restored == original and canonical_sha256(restored) == canonical_sha256(original)
    assert len(json.dumps(wire)) < len(json.dumps(original)) * 0.7
    restored["payload"]["scientific_audit"]["claim_gates"][0]["gates"][0]["evidence"].clear()
    assert restored["payload"]["scientific_audit"]["claim_gates"][1]["gates"][0]["evidence"]
    assert task.model_dump(mode="json") == original
    assert _expand_wire_task(wire) == original


@pytest.mark.parametrize("variant", ["different", "prepared_only", "authoritative_only", "no_audit", "reserved_key"])
def test_wire_projection_preserves_distinct_submissions_and_optional_context(variant):
    task, *_ = task_with_audit()
    payload = deepcopy(task.payload)
    if variant == "different":
        payload["prepared_submission"]["summary"] = "Different prepared review context."
    elif variant == "prepared_only":
        payload.pop("authoritative_submission")
    elif variant == "authoritative_only":
        payload.pop("prepared_submission")
    elif variant == "no_audit":
        payload["scientific_audit"] = None
    else:
        payload["scientific_audit"]["reason_catalog"] = ["Preexisting field must remain unchanged."]
    task = task.model_copy(update={"payload": payload})
    original = task.model_dump(mode="json")
    wire = _wire_task(task)
    if variant == "different":
        assert wire["payload"]["prepared_submission"] == original["payload"]["prepared_submission"]
    if variant == "reserved_key":
        assert wire["payload"]["scientific_audit"] == original["payload"]["scientific_audit"]
    assert _expand_wire_task(wire) == original and task.model_dump(mode="json") == original


def test_actual_provider_uses_compact_lossless_wire_and_output_cap_on_single_correction():
    task, context, registry, counts = task_with_audit()
    original = task.model_dump(mode="json")
    codec = WireCodec(task, _task_receipt_ids(task))
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(deepcopy(kwargs))
            assert kwargs["max_output_tokens"] == 4096
            wire = json.loads(kwargs["input"][0]["content"])["task"]
            assert _expand_wire_task(codec.decode(wire)) == original
            assert "reason_catalog" in kwargs["instructions"] and "evidence_catalog" in kwargs["instructions"]
            assert kwargs["input"][0]["content"] == json.dumps(
                {"task": wire}, separators=(",", ":"), ensure_ascii=False)
            arguments = deepcopy(task.payload["authoritative_submission"])
            if len(calls) == 1:
                arguments["next_action"] = "Unlisted action"
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": f"submit-{len(calls)}", "arguments": json.dumps(arguments)}]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert result.payload == task.payload["authoritative_submission"]["payload"]
    assert task.model_dump(mode="json") == original and len(calls) == counts.count("model_requests_per_run") == 2
