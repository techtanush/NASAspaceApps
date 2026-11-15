"""Every role's nested citations use the exact independently authorized namespace."""

import json
from copy import deepcopy
from uuid import uuid4

import jsonschema
import pytest

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _task_receipt_ids, submission_schema
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.wire_context import WireCodec
from tests.integration.platform.test_live_rehearsal import task_and_context


@pytest.mark.parametrize("role,container,field,kind,shape", [
    ("requirements", "payload", "validation_receipt_id", "receipt", "scalar"),
    ("rover_systems", "payload", "validation_receipt_id", "receipt", "scalar"),
    ("rover_systems", "CapabilityMapping", "evidence_ids", "evidence", "array"),
    ("planetary_target", "payload", "coverage_receipt_ids", "receipt", "array"),
    ("planetary_target", "payload", "source_evidence_ids", "evidence", "array"),
    ("planetary_target", "payload", "measurement_evidence_ids", "evidence", "array"),
    ("planetary_target", "payload", "geometry_validation_receipt_id", "receipt", "nullable"),
    ("planetary_target", "DimensionEvidence", "evidence_ids", "evidence", "array"),
    ("earth_scout", "payload", "screening_receipt_id", "receipt", "nullable"),
    ("earth_scout", "ShortlistItem", "evidence_ids", "evidence", "array"),
    ("earth_scout", "ExcludedCandidate", "evidence_ids", "evidence", "array"),
    ("qualification", "QualificationRow", "comparison_receipt_id", "receipt", "nullable"),
    ("qualification", "QualificationRow", "evidence_ids", "evidence", "array"),
    ("qualification", "QualificationRow", "measurement_evidence_ids", "evidence", "array"),
    ("scientific_critic", "Objection", "evidence_ids", "evidence", "array"),
    ("scientific_critic", "Objection", "resolved_by_receipt_ids", "receipt", "array"),
    ("verification_replanning", "payload", "diagnosis_receipt_id", "receipt", "nullable"),
    ("evidence_passport", "ClaimAnnotation", "evidence_ids", "evidence", "array"),
])
def test_all_nested_reference_fields_reject_wrong_namespaces(role, container, field, kind, shape):
    evidence, receipt, foreign = map(str, (uuid4(), uuid4(), uuid4()))
    schema = submission_schema(role, allowed_evidence_ids=[evidence], allowed_receipt_ids=[receipt])
    jsonschema.Draft202012Validator.check_schema(schema)
    owner = schema["properties"]["payload"] if container == "payload" else schema["$defs"][container]
    reference = {"$defs": schema["$defs"], **owner["properties"][field]}
    validator = jsonschema.Draft202012Validator(reference)
    allowed, wrong = (evidence, receipt) if kind == "evidence" else (receipt, evidence)
    validator.validate([allowed] if shape == "array" else allowed)
    if shape == "array":
        validator.validate([])
    if shape == "nullable":
        validator.validate(None)
    for identifier in (wrong, foreign):
        with pytest.raises(jsonschema.ValidationError):
            validator.validate([identifier] if shape == "array" else identifier)


def target_task():
    task, context, registry, counts, _ = task_and_context()
    evidence, extra_evidence, successful_receipt, authoritative_receipt, failed_receipt = [uuid4() for _ in range(5)]
    proposal = {**task.payload["prepared_submission"], "role_key": "planetary_target",
                "task_kind": "characterize_target", "evidence_ids": [str(evidence)], "payload": {
                    "target_revision_id": str(task.contract_revision_id), "target_profile_revision_id": None,
                    "coverage_receipt_ids": [str(successful_receipt)], "source_evidence_ids": [str(evidence)],
                    "measurement_evidence_ids": [str(evidence)], "dimension_evidence": [{
                        "requirement_id": "req-1", "availability": "AVAILABLE", "evidence_ids": [str(evidence)],
                        "measurement_spec_id": None, "limitation": None,
                    }], "geometry_validation_receipt_id": str(authoritative_receipt), "comparison_ready": False,
                }}
    task = task.model_copy(update={
        "role_key": "planetary_target", "task_kind": "characterize_target",
        "input_evidence_ids": [evidence, extra_evidence], "payload": {
            "prepared_submission": proposal, "authoritative_submission": deepcopy(proposal),
            "receipt_summaries": [{"id": str(successful_receipt), "status": "SUCCEEDED"},
                                  {"id": str(failed_receipt), "status": "FAILED"}],
        },
    })
    context.role = task.role_key
    return task, context, registry, counts, str(failed_receipt)


@pytest.mark.parametrize("fallback", [False, True])
def test_actual_target_provider_schema_matches_authoritative_receipt_union_and_all_input_evidence(fallback):
    task, context, registry, _, failed = target_task()
    if fallback:
        task.payload.pop("authoritative_submission")
    proposal = deepcopy(task.payload["prepared_submission"])
    codec = WireCodec(task, _task_receipt_ids(task))
    checked = []

    class Client:
        def create(self, **kwargs):
            schema = next(tool["parameters"] for tool in kwargs["tools"] if tool["name"] == "submit_role_result")
            validator = jsonschema.Draft202012Validator(schema)
            validator.validate(codec.encode(proposal))
            for identifier in map(str, task.input_evidence_ids):
                amended = deepcopy(proposal)
                amended["payload"]["dimension_evidence"][0]["evidence_ids"] = [identifier]
                validator.validate(codec.encode(amended))
            for identifier in (failed, str(task.contract_revision_id), str(task.input_evidence_ids[0]), str(uuid4())):
                amended = deepcopy(proposal)
                amended["payload"]["geometry_validation_receipt_id"] = identifier
                with pytest.raises(jsonschema.ValidationError):
                    validator.validate(codec.encode(amended))
            for field in ("source_evidence_ids", "measurement_evidence_ids"):
                amended = deepcopy(proposal)
                amended["payload"][field] = proposal["payload"]["coverage_receipt_ids"]
                with pytest.raises(jsonschema.ValidationError):
                    validator.validate(codec.encode(amended))
            checked.append(True)
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": "target", "arguments": json.dumps(codec.encode(proposal))}]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert checked == [True] and result.payload == proposal["payload"]


def test_empty_nested_namespaces_preserve_empty_arrays_and_nullable_receipts_without_empty_enums():
    schema = submission_schema("earth_scout", allowed_evidence_ids=[], allowed_receipt_ids=[])
    jsonschema.Draft202012Validator.check_schema(schema)
    assert '"enum": []' not in json.dumps(schema)
    nullable = {"$defs": schema["$defs"], **schema["properties"]["payload"]["properties"]["screening_receipt_id"]}
    jsonschema.validate(None, nullable)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(str(uuid4()), nullable)
    evidence = {"$defs": schema["$defs"], **schema["$defs"]["ShortlistItem"]["properties"]["evidence_ids"]}
    jsonschema.validate([], evidence)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate([str(uuid4())], evidence)


def test_no_authorized_required_receipt_fails_before_provider_request():
    # Requirements always needs a validation receipt; an uncharacterized target
    # can legitimately report no geometry receipt and remain unready.
    task, context, registry, _, _ = task_and_context()
    task = task.model_copy(update={"role_key": "requirements", "task_kind": "validate_requirements",
                                  "payload": {"receipt_summaries": [], "prepared_submission": {"payload": {}}}})
    context.role = task.role_key

    class Client:
        def create(self, **kwargs):
            pytest.fail("An unsatisfiable required receipt must not send a provider request")

    with pytest.raises(ProviderError, match="Task lacks an authorized required reference") as caught:
        OpenAIProvider(Client()).run(task, registry, context)
    assert caught.value.code == "INPUT_INVALID"


@pytest.mark.parametrize("field", ["dimension_evidence", "geometry_validation_receipt_id"])
def test_nested_correction_reports_exact_safe_path_without_rejected_values(field, caplog):
    task, context, registry, counts, failed = target_task()
    proposal = deepcopy(task.payload["prepared_submission"])
    invalid = deepcopy(proposal)
    if field == "dimension_evidence":
        invalid["payload"][field][0]["evidence_ids"] = [failed]
        expected_path = "payload.dimension_evidence.0.evidence_ids.0"
    else:
        invalid["payload"][field] = str(task.contract_revision_id)
        expected_path = "payload.geometry_validation_receipt_id"
    invalid["summary"] = "private-model-prose-never-in-diagnostics"
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(deepcopy(kwargs))
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": f"target-{len(calls)}", "arguments": json.dumps(
                        invalid if len(calls) == 1 else proposal)}]}

    OpenAIProvider(Client()).run(task, registry, context)
    assert len(calls) == counts.count("model_requests_per_run") == 2
    feedback = next(item for item in calls[1]["input"] if item.get("type") == "function_call_output")
    details = json.loads(feedback["output"])["error"]["details"]
    assert len(details) == 1 and details[0]["field"] == expected_path
    assert details[0]["code"] == "NESTED_REFERENCE_NOT_AUTHORIZED"
    assert failed not in feedback["output"] and str(task.contract_revision_id) not in feedback["output"]
    assert invalid["summary"] not in feedback["output"] and invalid["summary"] not in caplog.text
    rejected = next(record for record in caplog.records
                    if record.getMessage() == "provider.proposal_rejected.NESTED_REFERENCE_NOT_AUTHORIZED")
    assert rejected.policy_failure_fields == [expected_path] and rejected.exc_info is None
