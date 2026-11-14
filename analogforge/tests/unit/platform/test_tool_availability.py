"""Provider-facing tool schemas advertise exactly the executable, role-authorized stage tools."""

from uuid import uuid4

import pytest

from analogforge.domain.policy import PolicyViolation
from analogforge.ports.catalog import ROLE_KEYS
from analogforge.tools.allowlist import allowed_tools
from analogforge.tools.registry import ToolContext, ToolRegistry


@pytest.mark.parametrize("role", ROLE_KEYS)
def test_every_advertised_stage_tool_has_an_authorized_executable_handler(role):
    calls = []
    arguments = {
        "get_run_snapshot": {"sections": ["contract"]},
        "inspect_contract": {"contract_revision_id": str(uuid4())},
        "get_evidence": {"evidence_ids": [], "include": []},
        "verify_route": {"test_revision_id": str(uuid4()), "route_revision_id": str(uuid4())},
    }
    registry = ToolRegistry({name: lambda args, name=name: calls.append(name) or {} for name in arguments})
    schemas = registry.schemas(role, available_only=True)
    advertised = {schema["name"] for schema in schemas}
    assert advertised == set(registry.handlers) & allowed_tools(role)
    context = ToolContext(role, "workspace", "run", "live", 1, "hash")
    for schema in schemas:
        registry.execute(schema["name"], arguments[schema["name"]], context, call_id=str(uuid4()))
    assert set(calls) == advertised


def test_full_role_catalog_stays_available_without_the_stage_filter():
    registry = ToolRegistry({})
    full = registry.schemas("planetary_target")
    assert {schema["name"] for schema in full} == allowed_tools("planetary_target") - {"submit_role_result"}
    assert registry.schemas("planetary_target", available_only=True) == []
    assert registry.schemas("planetary_target") == full


def test_unavailable_role_allowed_tool_remains_rejected_at_execution():
    registry = ToolRegistry({"get_run_snapshot": lambda args: {}})
    context = ToolContext("planetary_target", "workspace", "run", "live", 1, "hash")
    advertised = {schema["name"] for schema in registry.schemas(context.role, available_only=True)}
    assert "characterize_target" not in advertised
    with pytest.raises(PolicyViolation, match="TOOL_NOT_PERMITTED_IN_STAGE"):
        registry.execute("characterize_target", {
            "target_revision_id": str(uuid4()), "measurement_spec_id": "terrain-target-v1", "source_evidence_ids": [],
        }, context, call_id="unavailable-call")


def test_registered_handler_does_not_expand_role_authority():
    calls = []
    registry = ToolRegistry({"verify_route": lambda args: calls.append(args) or {}})
    context = ToolContext("mission_director", "workspace", "run", "live", 1, "hash")
    assert registry.schemas(context.role, available_only=True) == []
    with pytest.raises(PolicyViolation, match="FORBIDDEN_TOOL"):
        registry.execute("verify_route", {"test_revision_id": str(uuid4()), "route_revision_id": str(uuid4())},
                         context, call_id="forbidden-call")
    assert not calls


def test_available_preparation_schemas_still_use_preparation_authority():
    registry = ToolRegistry({"validate_mission_draft": lambda args: {}, "get_run_snapshot": lambda args: {}})
    schemas = registry.schemas("requirements", preparation=True, available_only=True)
    assert {schema["name"] for schema in schemas} == {"validate_mission_draft"}
