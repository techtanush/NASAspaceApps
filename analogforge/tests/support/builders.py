# ruff: noqa: E501, S603, S607, S101
"""Test helpers: kit mission/rover presets -> frozen domain records, request/context builders, execution helper."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from analogforge.ports.domain_models import MissionTestContract, Requirement, RoverProfile
from analogforge.ports.hashing import MISSION_CONTENT_EXCLUDE, ROVER_CONTENT_EXCLUDE, model_sha256
from analogforge.ports.science import (
    EvidenceHandle,
    LocalScienceContext,
    OperationInput,
    ScienceComputationResult,
    ScienceOperation,
    ScienceOptions,
    ScienceRequest,
    ScienceService,
    SourcePolicy,
)
from support.registrar_stub import Registered, register

KIT = Path(__file__).resolve().parents[1] / "fixtures" / "kit"
WORKSPACE = uuid.UUID("00000000-0000-4000-8000-000000000001")
STAMP = datetime(2026, 11, 5, tzinfo=UTC)
_counter = {"n": 0}


def _uuid(tag: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"analogforge-test/{tag}")


def load_mission(name: str, requirement_overrides: dict[str, dict[str, Any]] | None = None) -> MissionTestContract:
    raw = json.loads((KIT / "missions" / f"{name}.json").read_text(encoding="utf-8"))
    for req in raw["requirements"]:
        if requirement_overrides and req["id"] in requirement_overrides:
            req.update(requirement_overrides[req["id"]])
    raw.update(
        schema_version="1.0",
        id=str(_uuid("mission/" + name)),
        mission_id=str(_uuid("mission-root/" + name)),
        workspace_id=str(WORKSPACE),
        revision=1,
        created_at=STAMP.isoformat(),
        accepted_at=STAMP.isoformat(),
        content_sha256="0" * 64,
    )
    draft = MissionTestContract.model_validate(raw)
    return draft.model_copy(update={"content_sha256": model_sha256(draft, MISSION_CONTENT_EXCLUDE)})


def load_rover(name: str, **overrides: Any) -> RoverProfile:
    raw = json.loads((KIT / "rovers" / f"{name}.json").read_text(encoding="utf-8"))
    raw.update(overrides)
    raw.update(
        schema_version="1.0",
        id=str(_uuid("rover/" + name)),
        rover_id=str(_uuid("rover-root/" + name)),
        workspace_id=str(WORKSPACE),
        revision=1,
        created_at=STAMP.isoformat(),
        content_sha256="0" * 64,
    )
    draft = RoverProfile.model_validate(raw)
    return draft.model_copy(update={"content_sha256": model_sha256(draft, ROVER_CONTENT_EXCLUDE)})


def requirement(mission: MissionTestContract, req_id: str) -> Requirement:
    return next(r for r in mission.requirements if r.id == req_id)


def make_context(scratch: Path, mode: str = "synthetic", **kw: Any) -> LocalScienceContext:
    return LocalScienceContext(
        scratch=scratch, workspace_id=WORKSPACE, job_id=_uuid("job"), mode=mode, **kw  # type: ignore[arg-type]
    )


def make_request(
    inputs: OperationInput,
    *,
    mode: str = "synthetic",
    evidence: list[EvidenceHandle] | None = None,
    options: ScienceOptions | None = None,
    fixtures: list[str] | None = None,
    datasets: list[str] | None = None,
) -> ScienceRequest:
    _counter["n"] += 1
    return ScienceRequest(
        request_id=_uuid(f"request/{_counter['n']}"),
        operation=ScienceOperation(inputs.operation),
        mode=mode,  # type: ignore[arg-type]
        inputs=inputs,
        input_evidence=evidence or [],
        source_policy=SourcePolicy(
            policy_id="synthetic-policy-v1",
            policy_sha256="1" * 64,
            allowed_adapter_ids=["synthetic_practice", "local_dataset"],
            local_dataset_ids=datasets or [],
            synthetic_fixture_ids=fixtures or [],
        ),
        options=options or ScienceOptions(),
    )


def run(
    service: ScienceService,
    inputs: OperationInput,
    context: LocalScienceContext,
    *,
    evidence: list[EvidenceHandle] | None = None,
    options: ScienceOptions | None = None,
    fixtures: list[str] | None = None,
    datasets: list[str] | None = None,
    check_registrar: bool = True,
) -> tuple[ScienceComputationResult, Registered | None]:
    """Execute through the facade, then push the result through the registrar stub."""
    req = make_request(
        inputs, mode=context.mode, evidence=evidence, options=options, fixtures=fixtures, datasets=datasets
    )
    result = service.execute(req, context)
    reg = register(req, result, context) if check_registrar else None
    return result, reg
