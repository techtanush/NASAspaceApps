"""Validate science drafts and publish an atomic, workspace-scoped evidence DAG."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ValidationError

from analogforge.application.assurance import ScientificClaimRejected
from analogforge.domain.ids import envelope, new_id
from analogforge.ports.domain_models import EvidenceRecord, ToolReceipt
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import ScienceComputationResult, ScienceRequest

MEDIA_TYPES = frozenset({"application/json", "image/png", "image/tiff", "application/x-npz", "text/csv"})


class RegistrationRejected(ValueError):
    def __init__(self, reason: str, code: str = "SOURCE_CONTENT_INVALID") -> None:
        super().__init__(reason)
        self.code = code


@dataclass(frozen=True)
class RegisteredResult:
    payload: dict[str, Any] | None
    evidence_ids: tuple[str, ...]
    artifact_hashes: dict[str, str]
    local_evidence_ids: dict[str, str]
    receipt: dict[str, Any]
    status: str
    issues: tuple[dict[str, Any], ...]

    @property
    def required_payload(self) -> dict[str, Any]:
        if self.payload is None:
            raise RegistrationRejected("A blocked computation has no scientific payload", "MODEL_OUTPUT_INVALID")
        return self.payload


def resolve_refs(value: Any, allocated: dict[str, str], authorized: set[str]) -> Any:
    if isinstance(value, list):
        return [resolve_refs(v, allocated, authorized) for v in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"local_key", "evidence_id"}:
        if value["local_key"] is not None:
            key = value["local_key"]
            if key not in allocated:
                raise RegistrationRejected("Dangling payload local_key", "MODEL_OUTPUT_INVALID")
            return {"local_key": None, "evidence_id": allocated[key]}
        if str(value["evidence_id"]) not in authorized:
            raise RegistrationRejected("Unauthorized payload evidence reference", "MODEL_OUTPUT_INVALID")
    return {k: resolve_refs(v, allocated, authorized) for k, v in value.items()}


class Registrar:
    def __init__(self, store: Any, blob_store: Any) -> None:
        self.store = store
        self.blob_store = blob_store

    def _quarantine(self, scratch: Path, request_id: UUID) -> None:
        if scratch.exists():
            destination = scratch.parent / "quarantine" / str(request_id)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copytree(scratch, destination, symlinks=True)

    def register(
        self,
        request: ScienceRequest,
        result: ScienceComputationResult | dict[str, Any],
        *,
        scratch_dir: Path,
        workspace_id: str,
        run_id: str,
        invocation_id: str,
        tool_name: str,
        expected_revision: int | None = None,
        job_id: str | None = None,
        lease_token: str | None = None,
        apply_payload: Callable[[Any, RegisteredResult], None] | None = None,
    ) -> RegisteredResult:
        try:
            parsed = ScienceComputationResult.model_validate(
                result.model_dump(mode="json") if isinstance(result, ScienceComputationResult) else result
            )
            return self._register(
                request,
                parsed,
                scratch_dir=scratch_dir,
                workspace_id=workspace_id,
                run_id=run_id,
                invocation_id=invocation_id,
                tool_name=tool_name,
                expected_revision=expected_revision,
                job_id=job_id,
                lease_token=lease_token,
                apply_payload=apply_payload,
            )
        except (RegistrationRejected, ValidationError, ScientificClaimRejected) as exc:
            self._quarantine(scratch_dir, request.request_id)
            code = (
                exc.code if isinstance(exc, (RegistrationRejected, ScientificClaimRejected)) else "MODEL_OUTPUT_INVALID"
            )
            receipt = ToolReceipt.model_validate(
                {
                    **envelope(workspace_id, run_id, request.mode),
                    "invocation_id": invocation_id,
                    "tool_name": tool_name,
                    "tool_version": "1.0.0",
                    "input_sha256": canonical_sha256(request),
                    "output_sha256": None,
                    "evidence_ids": [],
                    "status": "FAILED",
                    "error_code": code,
                    "elapsed_ms": 0,
                    "cache_hit": False,
                }
            ).model_dump(mode="json")
            with self.store.transaction(workspace_id) as tx:
                tx.create("tool_receipts", receipt)
                tx.append_event(
                    run_id,
                    "tool.rejected",
                    {
                        "receipt_id": receipt["id"],
                        "error_code": code,
                        "summary": "Science output rejected before domain publication",
                    },
                    request.mode,
                )
            if isinstance(exc, (RegistrationRejected, ScientificClaimRejected)):
                raise
            raise RegistrationRejected("Science result failed strict validation", code) from exc

    def _register(
        self,
        request: ScienceRequest,
        result: ScienceComputationResult,
        *,
        scratch_dir: Path,
        workspace_id: str,
        run_id: str,
        invocation_id: str,
        tool_name: str,
        expected_revision: int | None,
        job_id: str | None,
        lease_token: str | None,
        apply_payload: Callable[[Any, RegisteredResult], None] | None,
    ) -> RegisteredResult:
        if (result.request_id, result.operation, result.mode, result.input_sha256) != (
            request.request_id,
            request.operation,
            request.mode,
            canonical_sha256(request),
        ):
            raise RegistrationRejected("Science result request identity/hash mismatch", "MODEL_OUTPUT_INVALID")
        artifacts: dict[str, tuple[Any, bytes]] = {}
        scratch = scratch_dir.resolve()
        for artifact_draft in result.artifacts:
            candidate = scratch / artifact_draft.scratch_relpath
            # Check every component: resolving a symlink before this test would hide it.
            if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != scratch.parent):
                raise RegistrationRejected("Artifact symlink is forbidden")
            resolved = candidate.resolve()
            if not resolved.is_relative_to(scratch) or not resolved.is_file():
                raise RegistrationRejected("Artifact is outside scratch or missing")
            allowed = artifact_draft.media_type in MEDIA_TYPES or (
                artifact_draft.media_type == "application/octet-stream" and artifact_draft.role == "SOURCE_BYTES"
            )
            if not allowed:
                raise RegistrationRejected("Artifact media type is not permitted")
            content = resolved.read_bytes()
            if (
                len(content) != artifact_draft.size_bytes
                or hashlib.sha256(content).hexdigest() != artifact_draft.sha256
            ):
                raise RegistrationRejected("Artifact hash/size mismatch")
            artifacts[artifact_draft.local_key] = (artifact_draft, content)
        drafts = {d.local_key: d for d in result.evidence_drafts}
        ordered: list[str] = []
        remaining = set(drafts)
        while remaining:
            ready = sorted(key for key in remaining if set(drafts[key].parent_local_keys) <= set(ordered))
            if not ready:
                raise RegistrationRejected("Evidence lineage is cyclic", "MODEL_OUTPUT_INVALID")
            ordered.extend(ready)
            remaining.difference_update(ready)
        allocated = {key: new_id() for key in ordered}
        supplied = {str(e.evidence_id) for e in request.input_evidence}
        authorized = supplied | set(allocated.values())
        payload = (
            resolve_refs(result.payload.model_dump(mode="json"), allocated, authorized) if result.payload else None
        )
        transaction: AbstractContextManager[Any] = (
            self.store.publication(workspace_id, job_id, lease_token)
            if job_id is not None and lease_token is not None
            else self.store.transaction(workspace_id)
        )
        with transaction as tx:
            run = tx.get("runs", run_id)
            if run is None or run["mode"] != request.mode:
                raise RegistrationRejected("Run context mismatch", "MODEL_OUTPUT_INVALID")
            if run["state"] == "CANCELLED" or run.get("cancel_requested_at"):
                raise RegistrationRejected("Run cancelled", "MODEL_OUTPUT_INVALID")
            if expected_revision is not None and run["revision"] != expected_revision:
                raise RegistrationRejected("Run revision changed", "MODEL_OUTPUT_INVALID")
            for handle in request.input_evidence:
                parent = tx.get("evidence", str(handle.evidence_id))
                if parent is None or parent["mode"] != request.mode or str(parent["run_id"]) != run_id:
                    raise RegistrationRejected("Input evidence scope/mode/lineage mismatch", "MODEL_OUTPUT_INVALID")
                if parent.get("artifact_sha256") != handle.artifact_sha256:
                    raise RegistrationRejected("Input evidence artifact mismatch", "MODEL_OUTPUT_INVALID")
            for key in ordered:
                draft = drafts[key]
                for parent_id in draft.parent_evidence_ids:
                    if str(parent_id) not in supplied:
                        raise RegistrationRejected("Unprovided evidence parent", "MODEL_OUTPUT_INVALID")
                try:
                    uri = urlsplit(draft.source_uri) if draft.source_uri else None
                    if uri is not None:
                        _ = uri.port
                except ValueError as exc:
                    raise RegistrationRejected("Source URI is malformed") from exc
                if uri and (uri.scheme != "https" or not uri.hostname or not uri.netloc):
                    raise RegistrationRejected("Source URI requires an approved HTTPS origin")
                if uri and not any(
                    uri.hostname == domain or str(uri.hostname).endswith("." + domain)
                    for domain in ("nasa.gov", "usgs.gov", "asu.edu", "usra.edu", "caltech.edu", "arizona.edu")
                ):
                    raise RegistrationRejected("Source URI host is outside the approved source registry")
                if uri and (uri.query or uri.username or uri.password or uri.fragment):
                    raise RegistrationRejected("Source URI includes private or signed parameters")
                if request.mode == "synthetic" and draft.source_uri is not None:
                    raise RegistrationRejected("Synthetic evidence cannot use a real source URI")
                if draft.dataset_product_id:
                    if request.mode == "synthetic" and (
                        not draft.dataset_product_id.startswith("SYNTHETIC_") or draft.source_uri is not None
                    ):
                        raise RegistrationRejected("Synthetic source naming/URI mismatch")
                    if request.mode == "live" and draft.dataset_product_id.startswith("SYNTHETIC_"):
                        raise RegistrationRejected("Synthetic source in live mode")
                if draft.artifact_key is not None and draft.artifact_key not in artifacts:
                    raise RegistrationRejected("Evidence artifact missing")
            artifact_hashes: dict[str, str] = {}
            for key, (draft, content) in artifacts.items():
                blob = self.blob_store.put_bytes(content, draft.media_type)
                artifact_hashes[key] = blob.sha256
                existing = tx.list("artifacts", {"sha256": blob.sha256})
                if not existing:
                    tx.create(
                        "artifacts",
                        {
                            "id": new_id(),
                            "workspace_id": workspace_id,
                            "run_id": run_id,
                            "sha256": blob.sha256,
                            "size_bytes": len(content),
                            "bytes": len(content),
                            "media_type": draft.media_type,
                            "role": draft.role.value,
                            "relative_path": blob.relative_path,
                        },
                    )
            for key in ordered:
                draft = drafts[key]
                record = EvidenceRecord.model_validate(
                    {
                        **envelope(workspace_id, run_id, request.mode),
                        "id": allocated[key],
                        "kind": draft.kind,
                        "artifact_sha256": artifact_hashes.get(draft.artifact_key or ""),
                        "artifact_media_type": draft.artifact_media_type,
                        "source_uri": draft.source_uri,
                        "dataset_product_id": draft.dataset_product_id,
                        "dataset_version": draft.dataset_version,
                        "granule_id": draft.granule_id,
                        "license_note": draft.license_note,
                        "body": draft.body,
                        "aoi": None,
                        "input_evidence_ids": [allocated[p] for p in draft.parent_local_keys]
                        + [str(i) for i in draft.parent_evidence_ids],
                        "parameters_sha256": draft.parameters_sha256,
                        "algorithm_id": draft.algorithm_id,
                        "algorithm_version": draft.algorithm_version,
                        "native_resolution_m": draft.native_resolution_m,
                        "comparison_scale_m": draft.comparison_scale_m,
                        "metrics": [m.model_dump(mode="json") for m in draft.metrics],
                        "limitations": draft.limitations,
                    }
                ).model_dump(mode="json")
                tx.create("evidence", record)
                for parent in record["input_evidence_ids"]:
                    tx.create(
                        "evidence_edges",
                        {
                            "id": new_id(),
                            "workspace_id": workspace_id,
                            "run_id": run_id,
                            "mode": request.mode,
                            "parent_evidence_id": parent,
                            "child_evidence_id": record["id"],
                            "relation": "DERIVED_FROM",
                        },
                    )
            receipt = ToolReceipt.model_validate(
                {
                    **envelope(workspace_id, run_id, request.mode),
                    "invocation_id": invocation_id,
                    "tool_name": tool_name,
                    "tool_version": "1.0.0",
                    "input_sha256": canonical_sha256(request),
                    "output_sha256": canonical_sha256(result),
                    "evidence_ids": list(allocated.values()),
                    "status": "SUCCEEDED" if result.status in {"SUCCEEDED", "LIMITED"} else result.status.value,
                    "error_code": result.issues[0].code if result.issues else None,
                    "elapsed_ms": 0,
                    "cache_hit": False,
                }
            ).model_dump(mode="json")
            tx.create("tool_receipts", receipt)
            registered = RegisteredResult(
                payload,
                tuple(allocated.values()),
                artifact_hashes,
                allocated,
                receipt,
                result.status.value,
                tuple(i.model_dump(mode="json") for i in result.issues),
            )
            if apply_payload is not None:
                apply_payload(tx, registered)
            tx.append_event(
                run_id,
                "tool.completed",
                {
                    "receipt_id": receipt["id"],
                    "operation": request.operation.value,
                    "evidence_ids": list(allocated.values()),
                    "summary": f"{request.operation.value}: {result.status.value}",
                },
                request.mode,
            )
        return registered
