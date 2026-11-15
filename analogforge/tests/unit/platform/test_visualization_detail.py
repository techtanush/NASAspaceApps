"""Location projections reject neighbouring, stale, corrupt and unauthorized products."""

from __future__ import annotations

import io
import json
from copy import deepcopy
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from PIL import Image
from pyproj import CRS, Transformer

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.application.visualization_detail import site_detail
from analogforge.db.store import NotFound, PersistenceError
from analogforge.ports.hashing import canonical_json_bytes, canonical_sha256


class ProjectionUow:
    """Workspace-scoped reads only; absence of write methods proves GET purity."""

    def __init__(self):
        self.workspace_id = str(uuid4())
        self.rows = {}

    def get(self, kind, identifier):
        row = self.rows.get(kind, {}).get(str(identifier))
        return deepcopy(row) if row and row.get("workspace_id") == self.workspace_id else None

    def require(self, kind, identifier):
        row = self.get(kind, identifier)
        if row is None:
            raise NotFound()
        return row

    def list(self, kind, filters=None):
        return [
            deepcopy(row)
            for row in self.rows.get(kind, {}).values()
            if row.get("workspace_id") == self.workspace_id and all(row.get(k) == v for k, v in (filters or {}).items())
        ]

    def seed(self, table, **row):
        row.setdefault("id", str(uuid4()))
        row.setdefault("workspace_id", self.workspace_id)
        self.rows.setdefault(table, {})[row["id"]] = row
        return row


@pytest.fixture
def projection(tmp_path):
    uow, blobs = ProjectionUow(), ContentAddressedStore(tmp_path / "cas")
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    mission = json.loads((root / "tests/fixtures/kit/missions/mission-mars-mobility.json").read_text())
    mission.update(id=str(uuid4()), workspace_id=uow.workspace_id)
    mission["requirements"] = mission["requirements"][:1]
    uow.seed("mission_revisions", **mission)
    uow.seed("mission_acceptances", mission_revision_id=mission["id"], accepted_at="2026-11-14T00:00:00Z")
    candidate_id = str(uuid4())
    run_id = str(uuid4())
    run = uow.seed(
        "runs",
        id=run_id,
        run_id=run_id,
        mode="synthetic",
        mission_revision_id=mission["id"],
        target_profile_id=None,
        candidate_ids=[candidate_id],
        dataset_lock_id="locked-fixture-v1",
        qualification_ids=[],
        test_ids=[],
        test_result_ids=[],
    )
    candidate = uow.seed(
        "candidates",
        id=candidate_id,
        run_id=run_id,
        mode="synthetic",
        evidence_ids=[],
        aoi={
            "body": "EARTH",
            "bbox": [-112, 35, -111, 36],
            "longitude_convention": "NEG180_180",
            "latitude_type": "GEODETIC",
            "crs_wkt": None,
            "vertical_datum": "EGM96",
        },
    )
    return uow, blobs, run, mission, candidate


def source_record(uow, run, subject):
    evidence = uow.seed(
        "evidence",
        run_id=run["id"],
        mode=run["mode"],
        body=subject.get("aoi", subject.get("target"))["body"],
        algorithm_id="analyze-candidate",
        kind="DERIVED",
        input_evidence_ids=[],
    )
    subject["evidence_ids"].append(evidence["id"])
    subject["analysis_payload"] = {"analysis_evidence": {"evidence_id": evidence["id"]}}
    uow.seed(
        "tool_receipts",
        run_id=run["id"],
        mode=run["mode"],
        status="SUCCEEDED",
        tool_name="analyze_candidate",
        evidence_ids=[evidence["id"]],
    )
    return evidence


def json_record(uow, blobs, run, document, **fields):
    blob = blobs.put_bytes(canonical_json_bytes(document), "application/json")
    uow.seed("artifacts", sha256=blob.sha256, media_type="application/json", run_id=run["id"])
    return uow.seed(
        "evidence",
        run_id=run["id"],
        mode=run["mode"],
        artifact_sha256=blob.sha256,
        artifact_media_type="application/json",
        input_evidence_ids=[],
        **fields,
    )


def add_display(projection, kind="ELEVATION", *, target=False):
    uow, blobs, run, mission, candidate = projection
    if target:
        if not run["target_profile_id"]:
            profile = uow.seed(
                "target_profiles",
                run_id=run["id"],
                mode=run["mode"],
                target=deepcopy(mission["target"]),
                evidence_ids=[],
            )
            run["target_profile_id"] = profile["id"]
        subject = uow.rows["target_profiles"][run["target_profile_id"]]
        aoi = subject["target"]
    else:
        subject, aoi = candidate, candidate["aoi"]
    source = source_record(uow, run, subject)
    body = aoi["body"]
    crs = (
        CRS.from_epsg(3857)
        if body == "EARTH"
        else CRS.from_proj4(f"+proj=eqc +R={3396190 if body == 'MARS' else 1737400} +units=m +type=crs")
    )
    transform = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    w, s, e, n = aoi["bbox"]
    x0, y0 = transform.transform(w, n)
    x1, y1 = transform.transform(e, s)
    image = io.BytesIO()
    Image.new("RGBA", (4, 4), (0, 50, 100, 0)).save(image, format="PNG")
    blob = blobs.put_bytes(image.getvalue(), "image/png")
    uow.seed("artifacts", sha256=blob.sha256, media_type="image/png", role="DISPLAY_IMAGE", run_id=run["id"])
    draft = {
        "body": body,
        "layer_kind": kind,
        "rendering": "EARTH_WEBMERCATOR_IMAGE" if body == "EARTH" else "PLANETARY_PLANAR_IMAGE",
        "display_crs_wkt": crs.to_wkt(),
        "pixel_to_world": [x0, (x1 - x0) / 4, 0, y0, 0, (y1 - y0) / 4],
        "width_px": 4,
        "height_px": 4,
        "earth_corners": [[w, n], [e, n], [e, s], [w, s]] if body == "EARTH" else None,
        "legend": [],
        "unit": "m" if kind == "ELEVATION" else "deg",
        "support_scale_m": 480,
        "attribution": ["SYNTHETIC fixture"],
        "limitations": ["No field validation"],
    }
    display = json_record(
        uow,
        blobs,
        run,
        {
            "operation": "BUILD_DISPLAY_LAYERS",
            "layers": [
                {
                    **draft,
                    "local_key": "display",
                    "image_artifact_key": "display-png",
                    "source_evidence": [{"local_key": None, "evidence_id": source["id"]}],
                }
            ],
        },
        body=body,
        algorithm_id="build-display-layers",
        kind="DERIVED",
    )
    display["input_evidence_ids"] = [source["id"]]
    request = {
        "mode": run["mode"],
        "inputs": {
            "operation": "BUILD_DISPLAY_LAYERS",
            "subject": "TARGET" if target else "CANDIDATE",
            "evidence_ids": [source["id"]],
        },
        "source_policy": {"policy_id": run["dataset_lock_id"]},
    }
    receipt = uow.seed(
        "tool_receipts",
        run_id=run["id"],
        mode=run["mode"],
        status="SUCCEEDED",
        tool_name="characterize_target",
        evidence_ids=[display["id"]],
        input_sha256=canonical_sha256(request),
    )
    uow.seed(
        "scientific_operations",
        run_id=run["id"],
        mode=run["mode"],
        operation="BUILD_DISPLAY_LAYERS",
        request=request,
        receipt_id=receipt["id"],
        status="SUCCEEDED",
        evidence_ids=[display["id"]],
        local_evidence_ids={"display": display["id"]},
        artifact_hashes={"display-png": blob.sha256, "display-json": display["artifact_sha256"]},
        payload=json.loads(blobs.read(display["artifact_sha256"])),
    )
    return uow.seed(
        "display_layers",
        **draft,
        run_id=run["id"],
        mode=run["mode"],
        candidate_id=None if target else candidate["id"],
        target_profile_id=subject["id"] if target else None,
        image_artifact_sha256=blob.sha256,
        source_evidence_ids=[source["id"]],
        nodata_transparent=True,
    )


def test_exact_schema_unavailable_and_read_has_no_side_effects(projection):
    from pathlib import Path

    uow, blobs, run, _, candidate = projection
    before = deepcopy(uow.rows)
    result = site_detail(uow, blobs, run["id"], candidate["id"])
    schema = json.loads(
        (Path(__file__).resolve().parents[4] / "team handoffs/ui-split/schemas/site-detail.v1.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(result)
    assert result["availability"] == "UNAVAILABLE"
    assert result["bbox"] == candidate["aoi"]["bbox"]
    assert result["dataset_lock_id"] == run["dataset_lock_id"]
    assert uow.rows == before


def test_registered_earth_layers_preserve_exact_ids_and_partial_state(projection):
    uow, blobs, run, _, candidate = projection
    elevation = add_display(projection)
    assert site_detail(uow, blobs, run["id"], candidate["id"])["availability"] == "PARTIAL"
    slope = add_display(projection, "SLOPE")
    result = site_detail(uow, blobs, run["id"], candidate["id"])
    assert result["availability"] == "AVAILABLE"
    assert result["display_layer_manifest_ids"] == [elevation["id"], slope["id"]]


@pytest.mark.parametrize("body", ["MARS", "MOON"])
def test_planetary_target_uses_frozen_location_and_body_specific_frame(projection, body):
    uow, blobs, run, mission, _ = projection
    mission["target"]["body"] = body
    # seed() preserves this mission object, unlike an external mutable draft.
    add_display(projection, target=True)
    add_display(projection, "SLOPE", target=True)
    result = site_detail(uow, blobs, run["id"])
    assert result["availability"] == "AVAILABLE"
    assert result["body"] == body and result["candidate_id"] is None
    assert result["bbox"] == mission["target"]["bbox"]


@pytest.mark.parametrize("mutation", ["unpin", "wrong_run", "wrong_workspace", "unaccepted"])
def test_scoped_unknown_and_stale_subjects_rejected(projection, mutation):
    uow, blobs, run, _, candidate = projection
    if mutation == "unpin":
        run["candidate_ids"] = []
    elif mutation == "wrong_run":
        candidate["run_id"] = str(uuid4())
    elif mutation == "wrong_workspace":
        uow.workspace_id = str(uuid4())
    else:
        uow.rows["mission_acceptances"] = {}
    with pytest.raises(NotFound):
        site_detail(uow, blobs, run["id"], candidate["id"])


@pytest.mark.parametrize("mutation", ["body", "bbox", "nan", "seam"])
def test_malformed_site_geometry_rejected(projection, mutation):
    uow, blobs, run, _, candidate = projection
    if mutation == "body":
        candidate["aoi"]["body"] = "MARS"
    elif mutation == "bbox":
        candidate["aoi"]["bbox"] = [-112, 35, -113, 36]
    elif mutation == "nan":
        candidate["aoi"]["bbox"][0] = float("nan")
    else:
        candidate["aoi"]["bbox"] = [179, 35, -179, 36]
    with pytest.raises(PersistenceError):
        site_detail(uow, blobs, run["id"], candidate["id"])


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "tampered",
        "metadata",
        "receipt",
        "source",
        "mode",
        "body",
        "crs",
        "affine",
        "corners",
        "neighbour",
        "dimension",
        "target_id",
    ],
)
def test_invalid_manifest_or_artifact_is_never_advertised(projection, mutation):
    uow, blobs, run, _, candidate = projection
    layer = add_display(projection)
    if mutation == "missing":
        blobs.path(layer["image_artifact_sha256"]).unlink()
    elif mutation == "tampered":
        blobs.path(layer["image_artifact_sha256"]).write_bytes(b"not registered image bytes")
    elif mutation == "metadata":
        uow.rows["artifacts"] = {}
    elif mutation == "receipt":
        uow.rows["tool_receipts"] = {}
    elif mutation == "source":
        candidate["evidence_ids"] = []
    elif mutation == "mode":
        layer["mode"] = "live"
    elif mutation == "body":
        layer["body"] = "MARS"
    elif mutation == "crs":
        layer["display_crs_wkt"] = CRS.from_epsg(4326).to_wkt()
    elif mutation == "affine":
        layer["pixel_to_world"][1] = 0
    elif mutation == "corners":
        layer["earth_corners"][0][0] += 1
    elif mutation == "neighbour":
        candidate["aoi"]["bbox"] = [10, 20, 11, 21]
    elif mutation == "dimension":
        layer["width_px"] = 999
    else:
        layer["target_profile_id"] = str(uuid4())
    result = site_detail(uow, blobs, run["id"], candidate["id"])
    assert result["availability"] == "UNAVAILABLE"
    assert result["display_layer_manifest_ids"] == []


def test_unchanged_target_profile_pin_cannot_be_substituted(projection):
    uow, blobs, run, _, _ = projection
    add_display(projection, target=True)
    uow.rows["target_profiles"][run["target_profile_id"]]["target"]["bbox"][0] += 0.1
    with pytest.raises(PersistenceError):
        site_detail(uow, blobs, run["id"])


def test_another_valid_registered_png_cannot_replace_the_producer_artifact(projection):
    uow, blobs, run, _, candidate = projection
    layer = add_display(projection)
    image = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(image, format="PNG")
    replacement = blobs.put_bytes(image.getvalue(), "image/png")
    uow.seed("artifacts", sha256=replacement.sha256, media_type="image/png", role="DISPLAY_IMAGE", run_id=run["id"])
    layer["image_artifact_sha256"] = replacement.sha256
    assert site_detail(uow, blobs, run["id"], candidate["id"])["availability"] == "UNAVAILABLE"


def test_declared_oversized_display_is_rejected_before_opening_blob(projection, monkeypatch):
    uow, blobs, run, _, candidate = projection
    layer = add_display(projection)
    for row in uow.rows["artifacts"].values():
        if row["sha256"] == layer["image_artifact_sha256"]:
            row["size_bytes"] = 64 * 1024 * 1024 + 1
    original = blobs.read_limited

    def bounded_read(digest, max_bytes):
        assert digest != layer["image_artifact_sha256"], "Oversized image should be rejected using metadata first"
        return original(digest, max_bytes)

    monkeypatch.setattr(blobs, "read_limited", bounded_read)
    assert site_detail(uow, blobs, run["id"], candidate["id"])["availability"] == "UNAVAILABLE"


@pytest.mark.parametrize("mutation", ["mode", "target_id", "operation", "request", "lock", "mapping"])
def test_invalid_selected_product_marks_otherwise_complete_display_partial(projection, mutation):
    uow, blobs, run, _, candidate = projection
    add_display(projection)
    add_display(projection, "SLOPE")
    extra = add_display(projection, "ROUGHNESS")
    if mutation == "mode":
        extra["mode"] = "live"
    elif mutation == "target_id":
        extra["target_profile_id"] = str(uuid4())
    else:
        op = list(uow.rows["scientific_operations"].values())[-1]
        if mutation == "operation":
            op["operation"] = "ANALYZE_CANDIDATE"
        elif mutation == "request":
            op["request"]["inputs"]["subject"] = "TARGET"
        elif mutation == "lock":
            op["request"]["source_policy"]["policy_id"] = "a-different-lock"
        else:
            op["artifact_hashes"]["display-png"] = "0" * 64
    assert site_detail(uow, blobs, run["id"], candidate["id"])["availability"] == "PARTIAL"
