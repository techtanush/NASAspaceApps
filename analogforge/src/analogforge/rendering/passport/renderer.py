"""The frozen passport port implementation: deterministic bytes, no external state."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from analogforge.ports.hashing import canonical_json_bytes
from analogforge.ports.passport_renderer import (
    ExportFormat,
    PassportExportBundle,
    ProvidedAsset,
    RenderedExport,
    RendererError,
)

from .csv_export import referenced_ids, render_csv
from .html import render_html
from .json_export import render_json


def validate_bundle(bundle: PassportExportBundle) -> None:
    """Reject inconsistent final records; draft missing assurance is legitimate."""
    if bundle.assurance is not None and bundle.assurance.publication == "BLOCKED":
        raise RendererError("BLOCKED_AUDIT", "A blocked assurance audit cannot be exported")
    audit = bundle.assurance
    if audit is not None and (
        audit.workspace_id != bundle.passport.workspace_id
        or audit.run_id != bundle.passport.run_id
        or audit.mode != bundle.mode
        or audit.mission_content_sha256 != bundle.mission.content_sha256
        or audit.rover_content_sha256 != (bundle.rover.content_sha256 if bundle.rover else None)
        or audit.dataset_policy_sha256 != bundle.source_locks.dataset_policy_sha256
        or audit.acquired_manifest_sha256 != bundle.source_locks.acquired_manifest_sha256
        or audit.algorithm_lock_sha256 != bundle.source_locks.algorithm_lock_sha256
    ):
        raise RendererError("STALE_AUDIT", "Assurance identity or frozen input hashes do not match this passport")
    if hashlib.sha256(bundle.canonical_manifest_json.encode("utf-8")).hexdigest() != bundle.manifest_sha256:
        raise RendererError("MANIFEST_DIGEST_MISMATCH", "Canonical manifest bytes do not match the published digest")
    try:
        canonical = canonical_json_bytes(json.loads(bundle.canonical_manifest_json))
    except (ValueError, TypeError) as error:
        raise RendererError("MANIFEST_DIGEST_MISMATCH", "Manifest must be valid RFC 8785 JSON") from error
    if canonical != bundle.canonical_manifest_json.encode("utf-8"):
        raise RendererError("MANIFEST_DIGEST_MISMATCH", "Manifest bytes must use RFC 8785 canonical form")
    candidates = {c.id for c in bundle.candidates}
    requirements = {r.id for r in bundle.mission.requirements}
    evidence = {e.id for e in bundle.evidence_appendix} | {bundle.passport.assurance_evidence_id}
    if (
        any(q.candidate_id not in candidates for q in bundle.qualifications)
        or any(a.candidate_id not in candidates for a in bundle.attempts)
        or any(eid not in evidence for eid in all_evidence_ids(bundle))
    ):
        raise RendererError("UNRESOLVED_REFERENCE", "A candidate or evidence reference cannot be resolved")
    if any(q.requirement_id not in requirements for q in bundle.qualifications):
        raise RendererError("REQUIREMENT_UNKNOWN", "A qualification names a requirement outside the accepted contract")
    for attempt in bundle.attempts:
        outcome, category = attempt.result.outcome, attempt.result.failure_category
        if (
            (outcome == "PASS" and category is not None)
            or (outcome != "PASS" and category is None)
            or (outcome == "INCONCLUSIVE" and category not in {"DATA", "REQUIREMENT", "SEARCH_LIMIT", "SYSTEM"})
        ):
            raise RendererError("INCONSISTENT_ATTEMPT", "The verification outcome and failure category disagree")
    try:
        PassportExportBundle.model_validate(bundle.model_dump(mode="python"))
    except ValidationError as error:
        raise RendererError("INVALID_BUNDLE", "The supplied bundle violates the frozen passport contract") from error


def all_evidence_ids(bundle: PassportExportBundle) -> list[UUID]:
    ids: set[UUID] = set()

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, Mapping):
            for name, item in value.items():
                visit(item, str(name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item, key)
        elif value is not None and (key.endswith("evidence_id") or key.endswith("evidence_ids")):
            ids.add(UUID(str(value)))

    visit(bundle.model_dump(mode="json"))
    ids.update(e.id for e in bundle.evidence_appendix)
    return sorted(ids, key=str)


class DeterministicPassportRenderer:
    renderer_version = "1.0.0"

    def render(self, bundle: PassportExportBundle, assets: list[ProvidedAsset], fmt: ExportFormat) -> RenderedExport:
        validate_bundle(bundle)
        if fmt == "html":
            content, media_type = render_html(bundle, assets), "text/html; charset=utf-8"
        elif fmt == "json":
            content, media_type = render_json(bundle), "application/json"
        elif fmt == "csv":
            content, media_type = render_csv(bundle), "text/csv; charset=utf-8"
        else:
            raise RendererError("UNSUPPORTED_FORMAT", "Format must be html, json or csv")
        return RenderedExport(
            format=fmt,
            content=content,
            media_type=media_type,
            filename=f"analogforge-passport-{bundle.mode}-{str(bundle.passport.id)[:8]}-{bundle.manifest_sha256[:8]}.{fmt}",
            sha256=hashlib.sha256(content).hexdigest(),
            renderer_version=self.renderer_version,
            referenced_evidence_ids=referenced_ids(bundle) if fmt == "csv" else all_evidence_ids(bundle),
        )
