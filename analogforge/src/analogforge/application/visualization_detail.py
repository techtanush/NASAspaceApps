"""Read-only regional display projection over already registered, authorized artifacts.

The caller supplies a workspace-bound UnitOfWork. This module neither acquires data
nor builds images: unavailable or invalid existing products remain unavailable.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from typing import Any

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError, ProjError

from analogforge.application.missions import accepted_contract
from analogforge.db.store import NotFound, PersistenceError
from analogforge.ports.domain_models import AreaOfInterest, DisplayLayerManifest
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import BuildDisplayLayersPayload


def scoped_record(uow: Any, kind: str, identifier: str, run: dict[str, Any]) -> dict[str, Any]:
    """Never turn a valid ID from another run, mode or workspace into a site fact."""
    row: dict[str, Any] = uow.require(kind, identifier)
    if any(row.get(key) != run.get(key) for key in ("workspace_id", "run_id", "mode")):
        raise NotFound()
    return row


def authorized_subject(
    uow: Any,
    run_id: str,
    candidate_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    run: dict[str, Any] = uow.require("runs", run_id)
    if run.get("workspace_id") != uow.workspace_id or run.get("run_id") != run_id:
        raise NotFound()
    mission = accepted_contract(uow, run["mission_revision_id"])
    if mission.get("workspace_id") != run["workspace_id"] or not mission.get("accepted_at"):
        raise NotFound()
    if candidate_id is not None:
        if candidate_id not in run.get("candidate_ids", []):
            raise NotFound()
        subject = scoped_record(uow, "candidates", candidate_id, run)
        aoi = subject["aoi"]
        if aoi.get("body") != "EARTH":
            raise PersistenceError("SOURCE_CONTENT_INVALID", "An Earth candidate has an invalid body.")
    else:
        subject = None
        aoi = mission["target"]
        if run.get("target_profile_id"):
            subject = scoped_record(uow, "target_profiles", run["target_profile_id"], run)
            if subject["target"] != aoi:
                raise PersistenceError("SOURCE_CONTENT_INVALID", "Target profile differs from the frozen target.")
    try:
        parsed = AreaOfInterest.model_validate(aoi)
        w, s, e, n = parsed.bbox
        lo, hi = (-180, 180) if parsed.longitude_convention == "NEG180_180" else (0, 360)
        if not (lo <= w < e <= hi and -90 < s < n < 90):
            raise ValueError("Unsupported empty, seam-crossing or polar bounds")
        if parsed.body == "EARTH" and parsed.latitude_type != "GEODETIC":
            raise ValueError("Earth coordinates require the declared geodetic frame")
    except (ValidationError, ValueError, TypeError) as exc:
        raise PersistenceError(
            "SOURCE_CONTENT_INVALID", "The registered site geometry is unsupported or invalid."
        ) from exc
    return run, mission, subject, parsed.model_dump(mode="json")


def registered_json(uow: Any, blobs: Any, row: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    """Read only a scoped evidence-backed JSON blob and verify content identity."""
    if any(row.get(key) != run.get(key) for key in ("workspace_id", "run_id", "mode")):
        raise NotFound()
    digest = row.get("artifact_sha256")
    if not digest or row.get("artifact_media_type") != "application/json":
        raise ValueError("No registered JSON artifact")
    metadata = uow.list("artifacts", {"sha256": digest})
    if not any(
        m.get("workspace_id") == run["workspace_id"] and m.get("media_type") == "application/json" for m in metadata
    ):
        raise ValueError("Artifact metadata is unavailable")
    _declared_size(metadata, 8 * 1024 * 1024)
    content = blobs.read_limited(digest, 8 * 1024 * 1024)
    if len(content) > 8 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Artifact integrity or size is invalid")
    document = json.loads(content)
    if not isinstance(document, dict):
        raise ValueError("Expected a JSON object")
    return document


def _declared_size(metadata: list[dict[str, Any]], max_bytes: int) -> None:
    for row in metadata:
        declared = row.get("size_bytes", row.get("bytes"))
        if declared is not None and (
            isinstance(declared, bool) or not isinstance(declared, int) or declared < 0 or declared > max_bytes
        ):
            raise ValueError("Artifact declared size is invalid or exceeds the display read budget")


def _geometry(layer: DisplayLayerManifest, aoi: dict[str, Any]) -> None:
    crs = CRS.from_wkt(layer.display_crs_wkt)
    if not crs.is_projected or any(abs(float(a.unit_conversion_factor) - 1) > 1e-9 for a in crs.axis_info):
        raise ValueError("Display frame must use projected metres")
    if layer.body == "EARTH":
        if layer.rendering != "EARTH_WEBMERCATOR_IMAGE" or not crs.equals(CRS.from_epsg(3857)):
            raise ValueError("Earth displays require Web Mercator")
        if layer.earth_corners is None or len(layer.earth_corners) != 4:
            raise ValueError("Earth display corners are missing")
    else:
        radius = {"MARS": 3396190.0, "MOON": 1737400.0}[layer.body]
        ellipsoid = crs.ellipsoid
        if (
            layer.rendering != "PLANETARY_PLANAR_IMAGE"
            or layer.earth_corners is not None
            or crs.to_epsg(min_confidence=100) is not None
            or ellipsoid is None
            or abs(float(ellipsoid.semi_major_metre) - radius) >= 1
            or abs(float(ellipsoid.semi_minor_metre) - radius) >= 1
        ):
            raise ValueError("Planetary display has an incompatible body frame")
    x0, dx, rx, y0, ry, dy = layer.pixel_to_world
    if dx <= 0 or dy >= 0 or rx != 0 or ry != 0:
        raise ValueError("Unsupported display affine")
    corners_xy = [
        (x0, y0),
        (x0 + layer.width_px * dx, y0),
        (x0 + layer.width_px * dx, y0 + layer.height_px * dy),
        (x0, y0 + layer.height_px * dy),
    ]
    inverse = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    corners = [inverse.transform(x, y, errcheck=True) for x, y in corners_xy]
    if not all(math.isfinite(v) for corner in corners for v in corner):
        raise ValueError("Display coordinates are invalid")
    if layer.earth_corners is not None:
        for expected, actual in zip(corners, layer.earth_corners, strict=True):
            if max(abs(a - b) for a, b in zip(expected, actual.root, strict=True)) > 1e-6:
                raise ValueError("Display corners disagree with its affine")
    # A neighbour's display cannot stand in for this site. Grid padding is allowed,
    # but the site's registered centre must remain inside the actual image extent.
    w, s, e, n = aoi["bbox"]
    lon = (w + e) / 2
    lon = ((lon + 180) % 360) - 180
    lat = (s + n) / 2
    forward = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    cx, cy = forward.transform(lon, lat, errcheck=True)
    if not (x0 - dx <= cx <= x0 + (layer.width_px + 1) * dx and y0 + (layer.height_px + 1) * dy <= cy <= y0 - dy):
        raise ValueError("Display does not cover the selected site")


def _usable_layer(
    uow: Any,
    blobs: Any,
    raw: dict[str, Any],
    run: dict[str, Any],
    subject: dict[str, Any],
    aoi: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> DisplayLayerManifest:
    # Store adds created_at; it is not a property of the frozen manifest.
    layer = DisplayLayerManifest.model_validate({k: raw[k] for k in DisplayLayerManifest.model_fields if k in raw})
    if layer.body != aoi["body"]:
        raise ValueError("Display body differs from site")
    if layer.width_px > 2048 or layer.height_px > 2048:
        raise ValueError("Display dimensions exceed the registered renderer limit")
    _geometry(layer, aoi)
    sources = [str(identifier) for identifier in layer.source_evidence_ids]
    if not sources or not set(sources).issubset(subject.get("evidence_ids", [])):
        raise ValueError("Display source does not belong to selected site")
    successful = [
        r
        for r in receipts
        if r.get("status") == "SUCCEEDED" and all(r.get(k) == run.get(k) for k in ("workspace_id", "run_id", "mode"))
    ]
    for source in sources:
        evidence = scoped_record(uow, "evidence", source, run)
        if evidence.get("body") != layer.body or not any(source in r.get("evidence_ids", []) for r in successful):
            raise ValueError("Display source lacks scoped registration")
    # Match the immutable manifest to the registered display operation's JSON.
    registered = False
    for receipt in successful:
        if receipt.get("tool_name") != "characterize_target":
            continue
        operations = [
            operation
            for operation in uow.list("scientific_operations", {"run_id": run["run_id"]})
            if operation.get("receipt_id") == receipt["id"]
            and operation.get("operation") == "BUILD_DISPLAY_LAYERS"
            and operation.get("status") in {"SUCCEEDED", "LIMITED"}
            and all(operation.get(k) == run.get(k) for k in ("workspace_id", "run_id", "mode"))
        ]
        for identifier in receipt.get("evidence_ids", []):
            evidence = scoped_record(uow, "evidence", identifier, run)
            if evidence.get("algorithm_id") != "build-display-layers" or evidence.get("body") != layer.body:
                continue
            if not set(sources).issubset(evidence.get("input_evidence_ids", [])):
                continue
            payload = BuildDisplayLayersPayload.model_validate(registered_json(uow, blobs, evidence, run))
            for draft in payload.layers:
                comparable = draft.model_dump(
                    mode="json", exclude={"local_key", "image_artifact_key", "source_evidence"}
                )
                actual = layer.model_dump(mode="json")
                if not (
                    all(actual[k] == v for k, v in comparable.items())
                    and sources == [str(ref.evidence_id) for ref in draft.source_evidence]
                ):
                    continue
                for operation in operations:
                    request = operation.get("request", {})
                    inputs = request.get("inputs", {})
                    policy = request.get("source_policy", {})
                    if (
                        request.get("mode") != run["mode"]
                        or canonical_sha256(request) != receipt.get("input_sha256")
                        or policy.get("policy_id") != run.get("dataset_lock_id")
                        or inputs.get("subject") != ("CANDIDATE" if layer.candidate_id else "TARGET")
                        or not set(sources).issubset(inputs.get("evidence_ids", []))
                        or identifier not in operation.get("evidence_ids", [])
                        or identifier not in operation.get("local_evidence_ids", {}).values()
                        or evidence["artifact_sha256"] not in operation.get("artifact_hashes", {}).values()
                        or operation.get("artifact_hashes", {}).get(draft.image_artifact_key)
                        != layer.image_artifact_sha256
                    ):
                        continue
                    pinned_policy = run.get("runtime", {}).get("dataset_policy_sha256")
                    if pinned_policy is not None and policy.get("policy_sha256") != pinned_policy:
                        continue
                    if BuildDisplayLayersPayload.model_validate(operation.get("payload")) != payload:
                        continue
                    registered = True
    if not registered:
        raise ValueError("No matching registered display operation")
    digest = layer.image_artifact_sha256
    metadata = uow.list("artifacts", {"sha256": digest})
    if not any(
        m.get("workspace_id") == run["workspace_id"]
        and m.get("media_type") == "image/png"
        and m.get("role") == "DISPLAY_IMAGE"
        for m in metadata
    ):
        raise ValueError("Display image has no authorized metadata")
    _declared_size(metadata, 64 * 1024 * 1024)
    content = blobs.read_limited(digest, 64 * 1024 * 1024)
    if len(content) > 64 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Display image integrity is invalid")
    with Image.open(io.BytesIO(content)) as image:
        if image.format != "PNG" or image.mode != "RGBA" or image.size != (layer.width_px, layer.height_px):
            raise ValueError("Display image differs from its registered manifest")
        image.verify()
    return layer


def site_detail(uow: Any, blob_store: Any, run_id: str, candidate_id: str | None = None) -> dict[str, Any]:
    """Exact site-detail.v1 envelope; invalid individual products are never advertised."""
    run, _mission, subject, aoi = authorized_subject(uow, run_id, candidate_id)
    valid: list[DisplayLayerManifest] = []
    invalid = False
    if subject is not None:
        receipts = uow.list("tool_receipts", {"run_id": run_id})
        for raw in uow.list("display_layers", {"run_id": run_id}):
            if raw.get("candidate_id") != candidate_id:
                continue
            if raw.get("target_profile_id") != (None if candidate_id else run.get("target_profile_id")) or any(
                raw.get(k) != run.get(k) for k in ("workspace_id", "run_id", "mode")
            ):
                invalid = True
                continue
            try:
                valid.append(_usable_layer(uow, blob_store, raw, run, subject, aoi, receipts))
            except (
                ValueError,
                KeyError,
                TypeError,
                PersistenceError,
                OSError,
                UnidentifiedImageError,
                CRSError,
                ProjError,
            ):
                invalid = True
    kinds = {layer.layer_kind for layer in valid}
    availability = (
        "AVAILABLE"
        if {"ELEVATION", "SLOPE"}.issubset(kinds) and not invalid
        else ("PARTIAL" if valid else "UNAVAILABLE")
    )
    reasons = {
        "AVAILABLE": "Registered elevation and slope displays are available; zoom adds no analysis resolution.",
        "PARTIAL": "Only part of the registered display is usable; missing or invalid layers were not substituted.",
        "UNAVAILABLE": "No usable registered displays exist for this exact site; this read does not acquire data.",
    }
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "candidate_id": candidate_id,
        "body": aoi["body"],
        "bbox": aoi["bbox"],
        "dataset_lock_id": run.get("dataset_lock_id"),
        "availability": availability,
        "reason": reasons[availability],
        "display_layer_manifest_ids": list(dict.fromkeys(str(layer.id) for layer in valid)),
    }
