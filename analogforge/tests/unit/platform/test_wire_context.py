"""The model wire codec preserves canonical facts and never grants ID authority."""

import json
from copy import deepcopy
from uuid import uuid4

import httpx
import jsonschema
import pytest
from openai import RateLimitError

from analogforge.agents.runtime.openai_provider import OpenAIProvider, _expand_wire_task, _task_receipt_ids, _wire_task
from analogforge.agents.runtime.provider import ProviderError
from analogforge.agents.runtime.wire_context import UnknownWireAlias, WireCodec
from analogforge.ports.hashing import canonical_sha256
from analogforge.tools.registry import ToolRegistry
from tests.integration.platform.test_live_rehearsal import task_and_context
from tests.unit.platform.test_provider_nested_reference_schema import target_task
from tests.unit.platform.test_provider_wire_context import task_with_audit


def case():
    task, context, registry, counts, _ = target_task()
    audit = task_with_audit()[0].payload["scientific_audit"]
    payload = {**deepcopy(task.payload), "scientific_audit": audit,
               "authoritative_claims": [{"claim_id": "q:" + str(uuid4())}, {"claim_id": "uncovered:req-1"}],
               "untrusted_sources": [{"prose": "Literal ~u1, ~e999, ~0 and ~ survive.",
                                      "~r1": (str(uuid4()).upper(), -3.5, None)}]}
    task = task.model_copy(update={"payload": payload})
    return task, context, registry, counts


@pytest.mark.parametrize("prose", ["approx ~5 m", "reserve ~20%", "~0.5 km", "~0", "~", "a ~~ b"])
def test_ordinary_model_approximation_text_is_not_an_alias_or_changed_quantity(prose):
    task, *_ = case()
    codec = WireCodec(task, _task_receipt_ids(task))
    assert codec.decode({"summary": prose}) == {"summary": prose.replace("~~", "~")}
    assert codec.decode(codec.encode({"summary": prose})) == {"summary": prose}


def test_complete_task_roundtrip_preserves_case_negative_findings_null_tuple_values_and_original_inputs():
    task, *_ = case()
    original = deepcopy(task.model_dump(mode="json"))
    codec = WireCodec(task, _task_receipt_ids(task))
    wire = codec.task(_wire_task(task))
    restored = _expand_wire_task(codec.decode(wire))
    assert restored == original and canonical_sha256(restored) == canonical_sha256(original)
    assert task.model_dump(mode="json") == original
    assert "columns_v1" in wire["_wire_encoding"]
    assert len(json.dumps(wire)) < len(json.dumps(original)) * 0.6
    assert restored["payload"]["scientific_audit"]["findings"][0]["severity"] == "BLOCKING"
    assert {gate["outcome"] for gate in restored["payload"]["scientific_audit"]["claim_gates"][0]["gates"]} == {
        "SATISFIED", "UNSATISFIED", "NOT_APPLICABLE", "NOT_ASSESSED"}
    codec.decode(codec.encode({"a": "UUID with suffix " + str(uuid4()) + "XYZ"}))


@pytest.mark.parametrize("heterogeneous", [False, True])
def test_registered_target_profile_roundtrips_all_primitives_and_duplicate_metrics_without_mutation(heterogeneous):
    task, *_ = case()
    metrics = [{"metric_id": "derived:p05", "value": -3.5, "unit": "m", "uncertainty": None},
               {"metric_id": "derived:p95", "value": 12.25, "unit": "m", "uncertainty": None}]
    if heterogeneous:
        metrics[1]["future"] = {"unresolved": None}
    profile = {"id": str(uuid4()), "metrics": metrics, "payload": {"metrics": deepcopy(metrics),
               "slope_histogram": {"edges": [0, 5, 10], "area_fraction": [0.75, 0.25],
                                   "support_scale_m": 500, "valid_area_m2": 1000000}},
               "unavailable_dimensions": [{"reason": "NO_COVERAGE"}]}
    task = task.model_copy(update={"payload": {**task.payload, "target_profile_context": profile}})
    original = deepcopy(task.model_dump(mode="json"))
    codec = WireCodec(task, _task_receipt_ids(task))
    wire = codec.task(_wire_task(task))
    assert "metrics" not in wire["payload"]["target_profile_context"]["payload"]
    assert _expand_wire_task(codec.decode(wire)) == original
    assert task.model_dump(mode="json") == original


@pytest.mark.parametrize("defect", ["extra_gate", "missing_gate", "receipt_collision", "evidence_extra",
                                   "finding_null"])
def test_heterogeneous_or_future_fields_fall_back_without_changing_any_fact(defect):
    task, *_ = case()
    payload = deepcopy(task.payload)
    audit = payload["scientific_audit"]
    if defect == "extra_gate":
        audit["claim_gates"][0]["gates"][0]["future_field"] = {"unknown": None}
    elif defect == "missing_gate":
        audit["claim_gates"][0]["gates"][0].pop("outcome")
    elif defect == "receipt_collision":
        payload["receipt_columns"] = ["Preexisting field"]
    elif defect == "evidence_extra":
        audit["claim_gates"][0]["gates"][0]["evidence"][0]["future_field"] = False
    else:
        audit["findings"] = None
    task = task.model_copy(update={"payload": payload})
    codec = WireCodec(task, _task_receipt_ids(task))
    assert _expand_wire_task(codec.decode(codec.task(_wire_task(task)))) == task.model_dump(mode="json")


@pytest.mark.parametrize("variant", ["complete", "extra_claim", "missing_claim", "claim_columns_collision",
                                   "gate_columns_collision", "extra_gate_claim"])
def test_claim_tables_preserve_exact_scope_nulls_order_and_unknown_fields(variant):
    task, *_ = case()
    payload = deepcopy(task.payload)
    payload["authoritative_claims"] = [
        {"claim_id": "uncovered:r1", "claim_type": "discovery", "requirement_id": None,
         "candidate_window_ids": [str(uuid4())], "evidence_ids": [str(task.input_evidence_ids[0])]},
        {"claim_id": "uncovered:r2", "claim_type": "verification", "requirement_id": "r2",
         "candidate_window_ids": [], "evidence_ids": []},
    ]
    audit = payload["scientific_audit"]
    if variant == "extra_claim":
        payload["authoritative_claims"][0]["future_scope"] = {"unknown": None}
    elif variant == "missing_claim":
        payload["authoritative_claims"][0].pop("requirement_id")
    elif variant == "claim_columns_collision":
        payload["authoritative_claim_columns"] = ["Preserve original field"]
    elif variant == "gate_columns_collision":
        audit["claim_gate_columns"] = ["Preserve original field"]
    elif variant == "extra_gate_claim":
        audit["claim_gates"][0]["future_scope"] = False
    task = task.model_copy(update={"payload": payload})
    original = deepcopy(task.model_dump(mode="json"))
    codec = WireCodec(task, _task_receipt_ids(task))
    wire = codec.task(_wire_task(task))
    used = wire["_wire_encoding"]["columns_v1"]
    assert ("claims" in used) is (variant not in {"extra_claim", "missing_claim", "claim_columns_collision"})
    assert ("claim_gates" in used) is (variant not in {"gate_columns_collision", "extra_gate_claim"})
    assert _expand_wire_task(codec.decode(wire)) == original
    assert task.model_dump(mode="json") == original


@pytest.mark.parametrize("variant", ["complete", "collision", "non_string", "empty", "future_outcome"])
def test_gate_value_catalogs_preserve_every_literal_and_fall_back_on_collisions_or_types(variant):
    task, *_ = case()
    payload = deepcopy(task.payload)
    audit = payload["scientific_audit"]
    if variant == "collision":
        audit["gate_value_catalogs"] = {"source_field": [None, "Retain this field"]}
    elif variant == "non_string":
        audit["claim_gates"][0]["gates"][0]["gate_id"] = None
    elif variant == "empty":
        for claim in audit["claim_gates"]:
            claim["gates"] = []
    elif variant == "future_outcome":
        audit["claim_gates"][0]["gates"][0]["outcome"] = "FUTURE_UNKNOWN_OUTCOME"
    task = task.model_copy(update={"payload": payload})
    original = deepcopy(task.model_dump(mode="json"))
    codec = WireCodec(task, _task_receipt_ids(task))
    wire = codec.task(_wire_task(task))
    assert ("gate_values" in wire["_wire_encoding"]["columns_v1"]) is (variant not in {"collision", "non_string"})
    if variant == "complete":
        projected = wire["payload"]["scientific_audit"]
        assert set(projected["gate_value_catalogs"]["outcome"]) == {
            "SATISFIED", "UNSATISFIED", "NOT_APPLICABLE", "NOT_ASSESSED"}
        gates = projected["claim_gates"][0][projected["claim_gate_columns"].index("gates")]
        assert all(isinstance(gate[0], int) and isinstance(gate[1], int) for gate in gates)
    assert _expand_wire_task(codec.decode(wire)) == original
    assert task.model_dump(mode="json") == original


@pytest.mark.parametrize("alias", ["~e999999", "~z1", "~e01", "Untrusted text ~r999999"])
def test_unknown_aliases_in_any_field_are_rejected_without_echoing_values(alias):
    task, *_ = case()
    codec = WireCodec(task, _task_receipt_ids(task))
    with pytest.raises(UnknownWireAlias) as caught:
        codec.decode({"summary": alias})
    assert str(caught.value) == "UNKNOWN_WIRE_ALIAS" and alias not in str(caught.value)
    with pytest.raises(UnknownWireAlias):
        codec.decode({alias: None})


def test_schema_preserves_namespace_enums_new_uuid_semantics_and_existing_definition_names():
    task, *_ = case()
    codec = WireCodec(task, _task_receipt_ids(task))
    evidence, receipt = str(task.input_evidence_ids[0]), _task_receipt_ids(task)[0]
    schema = {"$defs": {"ClientUuid": {"type": "string", "enum": ["preserved"]},
                        "A/B~C": {"type": "string", "format": "uuid"}, "Unused": {"type": "boolean"}},
              "type": "object", "properties": {
                  "id": {"$ref": "#/$defs/A~1B~0C"},
                  "evidence_id": {"type": "string", "format": "uuid", "enum": [evidence]},
                  "name": {"$ref": "#/$defs/ClientUuid"}}, "required": ["id", "evidence_id", "name"],
              "additionalProperties": False}
    original = deepcopy(schema)
    wire = codec.schema(schema)
    assert schema == original and set(wire["$defs"]) == {"ClientUuid", "A/B~C"}
    validator = jsonschema.Draft202012Validator(wire, format_checker=jsonschema.FormatChecker())
    for identifier in (codec.aliases[evidence], str(uuid4())):
        validator.validate({"id": identifier, "evidence_id": codec.aliases[evidence], "name": "preserved"})
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"id": str(uuid4()), "evidence_id": codec.aliases[receipt], "name": "preserved"})
    with pytest.raises(UnknownWireAlias):
        codec.decode({"id": "~u999999"})


def test_tool_result_exact_audit_refs_restore_nested_tuples_and_do_not_reinterpret_reserved_source_text():
    task, *_ = case()
    codec = WireCodec(task, _task_receipt_ids(task))
    audit = task.payload["scientific_audit"]
    changed = deepcopy(audit)
    changed["findings"][0]["message"] = "Different finding must remain on wire."
    result = {"snapshot": {"runtime": {"audit_payload": deepcopy(audit)}}, "again": (audit, -2.5, None),
              "new": changed, "_task_audit_ref": True, "~u1": "Natural ~e1 and ~u999999 are literal data.",
              "new_id": str(uuid4())}
    original = deepcopy(result)
    projected = codec.result(result)
    assert projected["value"]["snapshot"]["runtime"]["audit_payload"] == {"_task_audit_ref": True}
    assert len(projected["audit_paths"]) == 2
    assert codec.expand_result(projected) == original and result == original
    assert codec.expand_result(codec.result(audit)) == audit


def test_short_opaque_claim_alias_preserves_composite_finding_relationship_without_rewriting_words():
    task, *_ = case()
    payload = deepcopy(task.payload)
    payload["authoritative_claims"] = [{"claim_id": "uncovered:r1"}, {"claim_id": "a"}]
    task = task.model_copy(update={"payload": payload})
    codec = WireCodec(task, _task_receipt_ids(task))
    encoded = codec.encode({"claim_id": "uncovered:r1", "finding_id": "uncovered:r1:SC-14",
                            "prose": "retain data and a claim"})
    assert encoded["finding_id"] == encoded["claim_id"] + ":SC-14"
    assert "data" in encoded["prose"] and codec.decode(encoded)["prose"] == "retain data and a claim"


def test_unknown_alias_in_model_summary_uses_single_safe_correction_before_canonical_validation():
    task, context, registry, counts = case()
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(deepcopy(kwargs))
            proposal = _expand_wire_task(json.loads(kwargs["input"][0]["content"])["task"])["payload"][
                "authoritative_submission"]
            if len(calls) == 1:
                proposal["summary"] = "Reference ~e999999"
            else:
                feedback = next(item for item in kwargs["input"] if item.get("type") == "function_call_output")
                detail = json.loads(feedback["output"])["error"]["details"][0]
                assert detail["code"] == "UNKNOWN_WIRE_ALIAS" and "~e999999" not in feedback["output"]
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": f"unknown-{len(calls)}", "arguments": json.dumps(proposal)}]}

    result = OpenAIProvider(Client()).run(task, registry, context)
    assert result.payload == task.payload["prepared_submission"]["payload"]
    assert len(calls) == counts.count("model_requests_per_run") == 2


def test_real_provider_serial_read_restores_canonical_tool_inputs_and_returns_canonical_submission():
    task, context, _, counts = case()
    audit = task.payload["scientific_audit"]
    canonical_result = {"snapshot": {"runtime": {"audit_payload": audit}}, "prose": "Literal ~u1"}
    original = deepcopy(canonical_result)
    registry = ToolRegistry({"get_run_snapshot": lambda args: canonical_result})
    calls = []

    class Client:
        def create(self, **kwargs):
            calls.append(deepcopy(kwargs))
            wire_task = _expand_wire_task(json.loads(kwargs["input"][0]["content"])["task"])
            if len(calls) == 1:
                name, arguments = "get_run_snapshot", {"sections": ["contract"]}
            else:
                output = next(item for item in kwargs["input"] if item.get("type") == "function_call_output")
                assert json.loads(output["output"])["value"]["snapshot"]["runtime"]["audit_payload"] == {
                    "_task_audit_ref": True}
                name, arguments = "submit_role_result", wire_task["payload"]["authoritative_submission"]
            return {"status": "completed", "output": [{"type": "function_call", "name": name,
                    "call_id": f"wire-{len(calls)}", "arguments": json.dumps(arguments)}]}

    proposal = OpenAIProvider(Client()).run(task, registry, context)
    assert proposal.payload == task.payload["authoritative_submission"]["payload"]
    assert canonical_result == original and len(calls) == counts.count("model_requests_per_run") == 2


@pytest.mark.parametrize("succeed", [False, True])
def test_provider_backoff_honors_long_header_with_same_three_attempt_and_charge_cap(succeed):
    task, context, registry, counts, _ = task_and_context()
    calls, sleeps = [], []

    class Client:
        def create(self, **kwargs):
            calls.append(True)
            if len(calls) < 3 or not succeed:
                response = httpx.Response(429, headers={"retry-after": "120"},
                                          request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
                raise RateLimitError("Private provider prose", response=response, body=None)
            return {"status": "completed", "output": [{"type": "function_call", "name": "submit_role_result",
                    "call_id": "third", "arguments": json.dumps(task.payload["prepared_submission"])}]}

    provider = OpenAIProvider(Client(), sleep=sleeps.append)
    if succeed:
        provider.run(task, registry, context)
    else:
        with pytest.raises(ProviderError) as caught:
            provider.run(task, registry, context)
        assert caught.value.code == "PROVIDER_RATE_LIMITED"
    assert len(calls) == counts.count("model_requests_per_run") == 3 and sleeps == [60, 60]
