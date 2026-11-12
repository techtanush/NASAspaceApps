"""Stand-in for the platform registrar (architecture 35 section 3.3).

It enforces the same rejection rules so the science suite catches a rejection before the merge:

1. the result matches the request (ids, operation, mode, ``input_sha256`` recomputed);
2. every artifact is re-hashed from ``scratch/<relpath>`` (no symlinks, inside scratch), size and media type checked;
3. evidence drafts are ordered topologically; ``parent_evidence_ids`` must be authorized request evidence;
4. every ``EvidenceRef(local_key=...)`` in the payload resolves to an evidence draft (dangling keys reject);
5. source naming: synthetic => ``SYNTHETIC_*`` product ids and ``source_uri`` None; live => never ``SYNTHETIC_``;
   no query strings or credentials in ``source_uri``.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import (
    ArtifactDraft,
    ArtifactRole,
    ComputationStatus,
    EvidenceDraft,
    EvidenceHandle,
    LocalScienceContext,
    ScienceComputationResult,
    ScienceRequest,
)

ALLOWED_MEDIA = frozenset(
    {"application/json", "image/png", "image/tiff", "application/x-npz", "text/csv", "application/octet-stream"}
)
NAMESPACE = uuid.UUID("5d3f1c7e-0a3b-4c55-9d52-6a3c1f0b9e11")


class RegistrarRejection(Exception):
    """The platform would reject this result and register nothing."""


@dataclass
class Registered:
    evidence_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    handles: dict[str, EvidenceHandle] = field(default_factory=dict)
    ordered_keys: list[str] = field(default_factory=list)
    artifact_paths: dict[str, Path] = field(default_factory=dict)


def _topological(drafts: list[EvidenceDraft]) -> list[EvidenceDraft]:
    by_key = {d.local_key: d for d in drafts}
    done: list[EvidenceDraft] = []
    state: dict[str, int] = {}

    def visit(key: str) -> None:
        if state.get(key) == 2:
            return
        if state.get(key) == 1:
            raise RegistrarRejection(f"evidence parent cycle at {key}")
        state[key] = 1
        for parent in by_key[key].parent_local_keys:
            if parent not in by_key:
                raise RegistrarRejection(f"evidence {key} has dangling parent_local_key {parent}")
            visit(parent)
        state[key] = 2
        done.append(by_key[key])

    for d in drafts:
        visit(d.local_key)
    return done


def _refs(node: Any, found: list[str]) -> None:
    if isinstance(node, dict):
        if set(node) == {"local_key", "evidence_id"} and node["local_key"] is not None:
            found.append(str(node["local_key"]))
        for v in node.values():
            _refs(v, found)
    elif isinstance(node, list):
        for v in node:
            _refs(v, found)


def _artifact_key_fields(node: Any, found: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith("artifact_key") and isinstance(v, str):
                found.append(v)
            _artifact_key_fields(v, found)
    elif isinstance(node, list):
        for v in node:
            _artifact_key_fields(v, found)


def _check_artifact(scratch: Path, art: ArtifactDraft) -> Path:
    if art.media_type not in ALLOWED_MEDIA:
        raise RegistrarRejection(f"artifact {art.local_key}: media type {art.media_type} not allowed")
    if art.media_type == "application/octet-stream" and art.role != ArtifactRole.SOURCE_BYTES:
        raise RegistrarRejection(f"artifact {art.local_key}: octet-stream only for SOURCE_BYTES")
    rel = Path(art.scratch_relpath)
    if rel.is_absolute() or ".." in rel.parts:
        raise RegistrarRejection(f"artifact {art.local_key}: path escapes scratch")
    root = scratch.resolve()
    cursor = scratch
    for part in rel.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise RegistrarRejection(f"artifact {art.local_key}: symlink in path")
    target = (scratch / rel).resolve()
    if root not in target.parents:
        raise RegistrarRejection(f"artifact {art.local_key}: resolved path outside scratch")
    if not target.is_file():
        raise RegistrarRejection(f"artifact {art.local_key}: file missing")
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != art.sha256:
        raise RegistrarRejection(f"artifact {art.local_key}: sha256 mismatch")
    if len(data) != art.size_bytes:
        raise RegistrarRejection(f"artifact {art.local_key}: size mismatch")
    return target


def _check_naming(request: ScienceRequest, ev: EvidenceDraft) -> None:
    pid = ev.dataset_product_id
    if request.mode == "synthetic":
        if pid is not None and not pid.startswith("SYNTHETIC_"):
            raise RegistrarRejection(f"evidence {ev.local_key}: synthetic mode needs SYNTHETIC_ product id")
        if ev.source_uri is not None:
            raise RegistrarRejection(f"evidence {ev.local_key}: synthetic mode requires source_uri None")
    if request.mode == "live" and pid is not None and pid.startswith("SYNTHETIC_"):
        raise RegistrarRejection(f"evidence {ev.local_key}: live mode may not use SYNTHETIC_ ids")
    if ev.source_uri is not None:
        parts = urlsplit(ev.source_uri)
        if parts.query or parts.username or parts.password:
            raise RegistrarRejection(f"evidence {ev.local_key}: source_uri carries query or credentials")


def register(
    request: ScienceRequest, result: ScienceComputationResult, context: LocalScienceContext
) -> Registered:
    """Validate ``result`` like the registrar; on success update ``context.artifact_paths`` and return handles."""
    result = ScienceComputationResult.model_validate(result.model_dump(mode="json"))
    if (result.request_id, result.operation, result.mode) != (request.request_id, request.operation, request.mode):
        raise RegistrarRejection("request_id/operation/mode differ from the request")
    if result.input_sha256 != canonical_sha256(request):
        raise RegistrarRejection("input_sha256 does not equal canonical_sha256(request)")
    scratch = context.scratch_dir()
    reg = Registered()
    artifact_by_key: dict[str, ArtifactDraft] = {}
    for art in result.artifacts:
        reg.artifact_paths[art.sha256] = _check_artifact(scratch, art)
        artifact_by_key[art.local_key] = art
    authorized = {h.evidence_id for h in request.input_evidence}
    for ev in _topological(list(result.evidence_drafts)):
        if ev.artifact_key is not None and ev.artifact_key not in artifact_by_key:
            raise RegistrarRejection(f"evidence {ev.local_key}: unknown artifact_key")
        for pid in ev.parent_evidence_ids:
            if pid not in authorized:
                raise RegistrarRejection(f"evidence {ev.local_key}: parent {pid} not authorized")
        _check_naming(request, ev)
        uid = uuid.uuid5(NAMESPACE, f"{request.request_id}:{ev.local_key}")
        art = artifact_by_key.get(ev.artifact_key) if ev.artifact_key else None
        reg.evidence_ids[ev.local_key] = uid
        reg.ordered_keys.append(ev.local_key)
        reg.handles[ev.local_key] = EvidenceHandle(
            evidence_id=uid,
            kind=ev.kind,
            mode=request.mode,
            body=ev.body,
            artifact_sha256=None if art is None else art.sha256,
            artifact_media_type=None if art is None else art.media_type,
            algorithm_id=ev.algorithm_id,
            algorithm_version=ev.algorithm_version,
            parameters_sha256=ev.parameters_sha256,
            native_resolution_m=ev.native_resolution_m,
            comparison_scale_m=ev.comparison_scale_m,
            metrics=list(ev.metrics),
            limitations=list(ev.limitations),
            local_key_origin=ev.local_key,
        )
    if result.payload is not None:
        dump = result.payload.model_dump(mode="json")
        refs: list[str] = []
        _refs(dump, refs)
        for key in refs:
            if key not in reg.evidence_ids:
                raise RegistrarRejection(f"payload has dangling evidence local_key {key!r}")
        akeys: list[str] = []
        _artifact_key_fields(dump, akeys)
        for key in akeys:
            if key not in artifact_by_key:
                raise RegistrarRejection(f"payload names unknown artifact key {key!r}")
    elif result.status in (ComputationStatus.SUCCEEDED, ComputationStatus.LIMITED):
        raise RegistrarRejection("SUCCEEDED/LIMITED result without payload")
    context.artifact_paths.update(reg.artifact_paths)
    return reg
