"""Pure-renderer boundary, immutable rendition storage and download metadata."""

from __future__ import annotations

import importlib
import io
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from PIL import Image

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.application.assurance import ScientificClaimRejected
from analogforge.application.passports import register_blob
from analogforge.db.store import PersistenceError, Store
from analogforge.ports.hashing import bytes_sha256, canonical_sha256
from analogforge.ports.passport_renderer import (
    RENDERER_ENTRY_POINT,
    ExportFormat,
    PassportExportBundle,
    PassportRenderer,
    ProvidedAsset,
    RenderedExport,
)

MEDIA_TYPES: dict[str, str] = {
    "json": "application/json",
    "html": "text/html; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}


def load_renderer() -> PassportRenderer:
    """Production never imports tests or silently replaces a missing entry point."""
    module_name, attribute = RENDERER_ENTRY_POINT.split(":", 1)
    try:
        renderer = getattr(importlib.import_module(module_name), attribute)()
    except (ImportError, AttributeError, TypeError) as exc:
        raise PersistenceError("RENDERER_MISSING", "The passport renderer entry point is unavailable") from exc
    if not isinstance(renderer, PassportRenderer) or not renderer.renderer_version:
        raise PersistenceError("RENDERER_NONCONFORMING", "The passport renderer does not implement the frozen port")
    return renderer


@dataclass(frozen=True)
class ExportDownload:
    status_code: int
    headers: dict[str, str]
    content: bytes | None = None
    job_id: str | None = None


def _assets(
    store: Store, workspace_id: str | UUID, bundle: PassportExportBundle, blob_store: ContentAddressedStore
) -> list[ProvidedAsset]:
    assets = []
    with store.transaction(workspace_id) as unit:
        for layer in unit.list("display_layers", {"run_id": str(bundle.passport.run_id)}):
            digest = layer.get("image_artifact_sha256") or layer.get("artifact_sha256")
            if not digest:
                continue
            rows = unit.list("artifacts", {"sha256": digest})
            if not rows or rows[0]["media_type"] != "image/png":
                continue
            content = blob_store.read(digest)
            if len(content) > 8 * 1024 * 1024:
                raise PersistenceError("RESOURCE_LIMIT", "Passport image exceeds the inline image budget")
            try:
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != "PNG" or image.width > 4096 or image.height > 4096:
                        raise ValueError("Invalid display image")
                    image.verify()
            except (OSError, ValueError) as exc:
                raise PersistenceError("SOURCE_CONTENT_INVALID", "Stored passport display image is invalid") from exc
            assets.append(
                ProvidedAsset(
                    asset_key=str(layer.get("asset_key", layer["id"])),
                    media_type="image/png",
                    sha256=digest,
                    content=content,
                )
            )
    return assets


def validate_rendered(
    bundle: PassportExportBundle, result: RenderedExport, fmt: ExportFormat, renderer_version: str
) -> None:
    if result.format != fmt or result.media_type != MEDIA_TYPES[fmt]:
        raise PersistenceError("MODEL_OUTPUT_INVALID", "Renderer format or media type disagrees with request")
    if result.sha256 != bytes_sha256(result.content) or result.renderer_version != renderer_version:
        raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Renderer digest or version disagrees with bytes")
    expected = f"analogforge-passport-{bundle.mode}-{str(bundle.passport.id)[:8]}-{bundle.manifest_sha256[:8]}.{fmt}"
    if result.filename != expected:
        raise PersistenceError("MODEL_OUTPUT_INVALID", "Renderer filename does not match immutable passport identity")
    known = {e.id for e in bundle.evidence_appendix}
    if any(eid not in known for eid in result.referenced_evidence_ids):
        raise ScientificClaimRejected(["SC-02:EXPORT_EVIDENCE_UNAUTHORIZED"])


def export_passport(
    store: Store,
    workspace_id: str | UUID,
    passport_id: str | UUID,
    blob_store: ContentAddressedStore,
    renderer: PassportRenderer | None = None,
    *,
    formats: tuple[ExportFormat, ...] = ("html", "json", "csv"),
    job_id: str | UUID | None = None,
    lease_token: str | UUID | None = None,
) -> list[dict[str, Any]]:
    actual_renderer = renderer if renderer is not None else load_renderer()
    with store.transaction(workspace_id) as unit:
        passport = unit.require("passports", passport_id)
        bundle = PassportExportBundle.model_validate(passport["bundle"])
        existing = unit.list("export_artifacts", {"passport_id": str(passport_id)})
        # Validate every blob through authorized evidence before handing the frozen report to the renderer.
        for evidence in bundle.evidence_appendix:
            stored = unit.require("evidence", evidence.id)
            if stored.get("artifact_sha256") != evidence.artifact_sha256:
                raise ScientificClaimRejected(["SC-02:EXPORT_EVIDENCE_CHANGED"])
            if evidence.artifact_sha256 is not None:
                if not unit.list("artifacts", {"sha256": evidence.artifact_sha256}):
                    raise ScientificClaimRejected(["SC-02:EXPORT_ARTIFACT_UNAUTHORIZED"])
                blob_store.read(evidence.artifact_sha256)
    if bytes_sha256(bundle.canonical_manifest_json.encode()) != bundle.manifest_sha256:
        raise ScientificClaimRejected(["SC-15:MANIFEST_BYTES_MISMATCH"])
    assets = _assets(store, workspace_id, bundle, blob_store)
    outputs = []
    for fmt in formats:
        cached = next(
            (
                row
                for row in existing
                if row["format"] == fmt and row["renderer_version"] == actual_renderer.renderer_version
            ),
            None,
        )
        if cached is not None:
            blob_store.read(cached["artifact_hash"])
            outputs.append(cached)
            continue
        rendered = actual_renderer.render(bundle, assets, fmt)
        validate_rendered(bundle, rendered, fmt, actual_renderer.renderer_version)
        blob = blob_store.put_bytes(rendered.content, rendered.media_type)
        if (job_id is None) != (lease_token is None):
            raise ValueError("job_id and lease_token must be supplied together")
        context = (
            store.publication(workspace_id, job_id, lease_token)
            if job_id is not None and lease_token is not None
            else store.transaction(workspace_id)
        )
        with context as unit:
            unit.require("passports", passport_id)
            # Multiple clients may enqueue distinct format requests simultaneously.
            # Serialize only the short immutable-rendition publication transaction.
            lock = int(
                canonical_sha256([str(workspace_id), str(passport_id), fmt, actual_renderer.renderer_version])[:15], 16
            )
            unit.connection.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
            rows = unit.list("export_artifacts", {"passport_id": str(passport_id)})
            cached = next(
                (
                    row
                    for row in rows
                    if row["format"] == fmt and row["renderer_version"] == actual_renderer.renderer_version
                ),
                None,
            )
            if cached is not None:
                if cached["artifact_hash"] != blob.sha256:
                    raise PersistenceError(
                        "MODEL_OUTPUT_INVALID", "Renderer produced different bytes for an immutable rendition"
                    )
                outputs.append(cached)
                continue
            register_blob(unit, blob)
            row = unit.create(
                "export_artifacts",
                {
                    "passport_id": str(passport_id),
                    "format": fmt,
                    "artifact_hash": blob.sha256,
                    "renderer_version": rendered.renderer_version,
                    "filename": rendered.filename,
                    "media_type": rendered.media_type,
                    "size_bytes": len(rendered.content),
                    "manifest_sha256": bundle.manifest_sha256,
                },
            )
            unit.append_event(
                bundle.passport.run_id,
                "passport.export_ready",
                {"passport_id": str(passport_id), "format": fmt, "artifact_sha256": blob.sha256},
                bundle.mode,
            )
            outputs.append(row)
    return outputs


def request_export(
    store: Store,
    workspace_id: str | UUID,
    passport_id: str | UUID,
    fmt: ExportFormat,
    blob_store: ContentAddressedStore,
) -> ExportDownload:
    """The API returns 202 until a durable renderer job publishes the requested bytes."""
    if fmt not in MEDIA_TYPES:
        raise PersistenceError("UNSUPPORTED_EXPORT_FORMAT", "Export format is not supported")
    with store.transaction(workspace_id) as unit:
        passport = unit.require("passports", passport_id)
        existing = unit.list("export_artifacts", {"passport_id": str(passport_id), "format": fmt})
        if not existing:
            job = unit.enqueue("EXPORT_PASSPORT", {"passport_id": str(passport_id)}, run_id=passport["run_id"])
            return ExportDownload(status_code=202, headers={"Retry-After": "2"}, job_id=job["id"])
        row = existing[-1]
        digest = row["artifact_hash"]
        # Workspace ownership is checked through both the passport and its blob row.
        if not unit.list("artifacts", {"sha256": digest}):
            raise PersistenceError("NOT_FOUND", "Export artifact is unavailable")
    content = blob_store.read(digest)
    if len(content) != row["size_bytes"]:
        raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Export byte count changed")
    return ExportDownload(
        status_code=200,
        headers={
            "Content-Type": row["media_type"],
            "Content-Disposition": f'attachment; filename="{row["filename"]}"',
            "Content-Length": str(len(content)),
            "ETag": f'"{digest}"',
            "X-Artifact-SHA256": digest,
            "X-Content-Type-Options": "nosniff",
        },
        content=content,
    )


export_run = export_passport
