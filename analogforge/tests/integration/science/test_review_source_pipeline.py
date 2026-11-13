"""Independent regressions for source-to-science paths required by architecture 35/36/39."""

import hashlib
import io
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from PIL import Image
from pydantic import BaseModel
from support.builders import load_mission, make_context, make_request, run
from support.practice import make_practice_context, mars_target_aoi

from analogforge.ports import catalog
from analogforge.ports.domain_models import AreaOfInterest
from analogforge.ports.science_payloads import (
    BuildDisplayLayersInput,
    BuildDisplayLayersPayload,
    CharacterizeTargetInput,
    CharacterizeTargetPayload,
    IngestLocalDatasetInput,
    SourceSelector,
)
from analogforge.science.facade import create_science_service
from analogforge.science.fixtures.mock_nasa_drop import generate
from analogforge.science.ops import characterize


def target_input(source: SourceSelector, target: AreaOfInterest | None = None) -> CharacterizeTargetInput:
    return CharacterizeTargetInput(
        target=target or mars_target_aoi(),
        source=source,
        measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET,
        requested_dimensions=["TERRAIN"],
    )


def test_mock_nasa_mars_reaches_characterization_after_ingestion(tmp_path: Path) -> None:
    data = tmp_path / "incoming"
    dataset = "mock-nasa-mars-dem"
    generate(data, only=[dataset])
    ctx = make_context(tmp_path / "scratch", dataset_roots={dataset: data / dataset})
    target = mars_target_aoi().model_copy(
        update={"bbox": [200.05, -4.95, 200.95, -4.05], "longitude_convention": "ZERO_360"}
    )
    result, _ = run(
        create_science_service(), target_input(SourceSelector(kind="LOCAL_DATASET", dataset_id=dataset), target),
        ctx, datasets=[dataset],
    )
    assert isinstance(result.payload, CharacterizeTargetPayload), result.issues
    assert result.payload.slope_histogram is not None
    assert result.payload.comparison_support_m is not None and result.payload.comparison_support_m >= 590
    assert next(m.value for m in result.payload.metrics if m.metric_id == "valid_fraction") > 0.8


def test_normalized_ingest_evidence_is_reusable_without_the_incoming_directory(tmp_path: Path) -> None:
    ctx = make_practice_context(tmp_path)
    dataset = "practice-mars-target-v1"
    manifest = yaml.safe_load((ctx.dataset_roots[dataset] / "manifest.yaml").read_text())
    service = create_science_service()
    ingested, registered = run(service, IngestLocalDatasetInput(manifest=manifest), ctx, datasets=[dataset])
    assert ingested.payload is not None and registered is not None
    ref = ingested.payload.normalized_evidence
    assert ref is not None and ref.local_key is not None
    handle = registered.handles[ref.local_key]
    assert handle.artifact_sha256 is not None, "Normalized evidence must carry immutable raster bytes"
    ctx.dataset_roots.clear()
    result, _ = run(
        service, target_input(SourceSelector(kind="ADAPTER_EVIDENCE", evidence_ids=[handle.evidence_id])),
        ctx, evidence=[handle],
    )
    assert isinstance(result.payload, CharacterizeTargetPayload), result.issues
    assert any(handle.evidence_id in e.parent_evidence_ids for e in result.evidence_drafts)


@pytest.mark.parametrize("corruption", ["bytes", "mode", "body", "kind"])
def test_normalized_evidence_rejects_tampering_or_incompatible_handles(tmp_path: Path, corruption: str) -> None:
    ctx = make_practice_context(tmp_path)
    dataset = "practice-mars-target-v1"
    manifest = yaml.safe_load((ctx.dataset_roots[dataset] / "manifest.yaml").read_text())
    service = create_science_service()
    _, registered = run(service, IngestLocalDatasetInput(manifest=manifest), ctx, datasets=[dataset])
    assert registered is not None
    handle = registered.handles["source-" + dataset]
    if corruption == "bytes":
        ctx.read_artifact(handle.artifact_sha256).write_bytes(b"corrupted bytes")
    else:
        handle = handle.model_copy(update={corruption: {"mode": "live", "body": "MOON", "kind": "DERIVED"}[corruption]})
    result, _ = run(service, target_input(SourceSelector(kind="ADAPTER_EVIDENCE", evidence_ids=[handle.evidence_id])),
                    ctx, evidence=[handle])
    assert result.status.value == "BLOCKED" and result.payload is None, result.issues


def test_normalized_container_is_deterministic_and_validates_array_headers(tmp_path: Path) -> None:
    from analogforge.science.errors import RasterError
    from analogforge.science.raster.normalized import decode_source, encode_source

    ctx = make_practice_context(tmp_path)
    dataset = "practice-mars-target-v1"
    manifest = yaml.safe_load((ctx.dataset_roots[dataset] / "manifest.yaml").read_text())
    _, registered = run(create_science_service(), IngestLocalDatasetInput(manifest=manifest), ctx, datasets=[dataset])
    assert registered is not None
    handle = registered.handles["source-" + dataset]
    raw = ctx.read_artifact(handle.artifact_sha256).read_bytes()
    source = decode_source(raw)
    assert encode_source(source.raster, source.meta.manifest, source.meta.file_hashes,
                         source.meta.bbox_lonlat, source.water) == raw
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    stream = io.BytesIO()
    # A small array with a false shape must be rejected before it can be consumed.
    np.lib.format.write_array(stream, np.ones((2, 2), dtype="<f8"), allow_pickle=False)
    members["values.npy"] = stream.getvalue()
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    with pytest.raises(RasterError, match="shape, type or byte count"):
        decode_source(bad.getvalue())


@pytest.mark.parametrize("validation_error", [False, True])
def test_facade_errors_do_not_publish_untrusted_exception_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, validation_error: bool
) -> None:
    private_text = "PRIVATE_SOURCE_SENTINEL https://example.invalid/source?token=private-review-value"

    class NumericInput(BaseModel):
        count: int

    def broken(_env: object) -> None:
        if validation_error:
            NumericInput.model_validate({"count": private_text})
        raise RuntimeError(private_text)

    monkeypatch.setattr(characterize, "run_characterize", broken)
    inputs = target_input(SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id="practice-mars-target-v1"))
    result = create_science_service().execute(make_request(inputs), make_context(tmp_path))
    assert result.status.value == ("BLOCKED" if validation_error else "FAILED")
    assert result.payload is None
    assert "PRIVATE_SOURCE_SENTINEL" not in result.model_dump_json()
    assert "?token=" not in result.model_dump_json()


def test_optional_thermal_source_is_registered_in_target_lineage(tmp_path: Path) -> None:
    ctx = make_practice_context(tmp_path)
    datasets = ["practice-moon-target-v1", "practice-moon-thermal-v1"]
    inp = CharacterizeTargetInput(
        target=load_mission("mission-moon-gap").target,
        source=SourceSelector(kind="LOCAL_DATASET", dataset_id=datasets[0]),
        measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET,
        requested_dimensions=["TERRAIN", "THERMAL"],
    )
    result, _ = run(create_science_service(), inp, ctx, datasets=datasets)
    assert isinstance(result.payload, CharacterizeTargetPayload), result.issues
    assert any(m.metric_id == "min_temperature_k" for m in result.payload.metrics)
    thermal_sources = [e for e in result.evidence_drafts if e.local_key == "source-" + datasets[1]]
    assert thermal_sources, "Every consulted thermal source needs registered lineage"
    profile = next(e for e in result.evidence_drafts if e.local_key == "profile")
    assert thermal_sources[0].local_key in profile.parent_local_keys


def test_consulted_mineral_bytes_change_analysis_identity(tmp_path: Path) -> None:
    from support.practice import Flow, analyze, candidate_ref, characterize_mars, screen

    ctx = make_practice_context(tmp_path)
    flow = Flow(create_science_service(), ctx)
    target, _ = characterize_mars(flow)
    screened = screen(flow, target)
    candidate = candidate_ref(screened, "grid-r0c0")
    datasets = ["practice-earth-grid-v1", "practice-earth-minerals-v1"]
    before, _ = analyze(flow, candidate, datasets)
    root = ctx.dataset_roots[datasets[1]]
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    primary = root / manifest["primary_file"]
    with rasterio.open(primary, "r+") as image:
        values = image.read(1)
        values[10:20, 10:20] = 4
        image.write(values, 1)
    for item in manifest["files"]:
        if item["path"] == manifest["primary_file"]:
            item["sha256"] = hashlib.sha256(primary.read_bytes()).hexdigest()
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    after, _ = analyze(flow, candidate, datasets)
    assert before.parameters_sha256 != after.parameters_sha256
    assert any(e.local_key == "source-" + datasets[1] for e in after.evidence_drafts)


@pytest.mark.parametrize(
    "dataset,subject,kind,unit",
    [
        ("practice-moon-thermal-v1", "TARGET", "THERMAL", "K"),
        ("practice-earth-minerals-v1", "CANDIDATE", "MINERAL", "class"),
    ],
)
def test_bound_optional_normalized_sources_produce_honest_display_layers(
    tmp_path: Path, dataset: str, subject: str, kind: str, unit: str
) -> None:
    ctx = make_practice_context(tmp_path)
    manifest = yaml.safe_load((ctx.dataset_roots[dataset] / "manifest.yaml").read_text())
    service = create_science_service()
    ingested, registered = run(service, IngestLocalDatasetInput(manifest=manifest), ctx, datasets=[dataset])
    assert ingested.payload is not None and registered is not None
    ref = ingested.payload.normalized_evidence
    assert ref is not None and ref.local_key is not None
    handle = registered.handles[ref.local_key]
    inputs = BuildDisplayLayersInput(subject=subject, evidence_ids=[handle.evidence_id], layer_kinds=[kind])
    result, _ = run(service, inputs, ctx, evidence=[handle])
    assert isinstance(result.payload, BuildDisplayLayersPayload), result.issues
    assert len(result.payload.layers) == 1
    layer = result.payload.layers[0]
    assert layer.layer_kind == kind and layer.unit == unit
    image = next(a for a in result.artifacts if a.local_key == layer.image_artifact_key)
    with Image.open(ctx.scratch_dir() / image.scratch_relpath) as decoded:
        pixels = np.asarray(decoded)
        assert decoded.mode == "RGBA" and np.any(pixels[..., 3] > 0)
        if kind == "MINERAL":
            assert np.any(pixels[..., 3] == 0), "Missing retrievals stay transparent"
    assert layer.source_evidence[0].evidence_id == handle.evidence_id
    assert any("SYNTHETIC" in text for text in layer.attribution)


def test_water_mask_registration_is_checked_before_science(tmp_path: Path) -> None:
    ctx = make_practice_context(tmp_path)
    dataset = "practice-earth-grid-v1"
    root = ctx.dataset_roots[dataset]
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    mask_file = next(item for item in manifest["files"] if item["role"] == "MASK")
    with rasterio.open(root / mask_file["path"], "r+") as source:
        source.transform = source.transform @ rasterio.Affine.translation(1, 0)
    mask_file["sha256"] = None
    result, _ = run(
        create_science_service(), IngestLocalDatasetInput(manifest=manifest), ctx, datasets=[dataset]
    )
    assert result.status.value == "BLOCKED"
    assert result.payload is None
    assert any(issue.detail_code == "MASK_GRID_MISMATCH" for issue in result.issues)


def test_metric_units_do_not_waive_ground_distance_distortion(tmp_path: Path) -> None:
    from analogforge.ports.science_payloads import ScreenCandidatesInput
    from analogforge.science.config import load_config
    from analogforge.science.geometry import validate_projection_distortion
    from analogforge.science.ops.base import OpEnv
    from analogforge.science.ops.source import resolve_source

    ctx = make_practice_context(tmp_path)
    dataset = "practice-earth-grid-v1"
    root = ctx.dataset_roots[dataset]
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    manifest["crs"] = {"epsg": 3857}
    manifest["declared_native_resolution_m"] = 20.6
    for item in manifest["files"]:
        with rasterio.open(root / item["path"], "r+") as image:
            image.crs = "EPSG:3857"
            image.transform = rasterio.Affine(60, 0, 500000, 0, -60, 11068715)  # about 70 N
        item["sha256"] = None
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    inputs = ScreenCandidatesInput(
        search_region_set_id="local-dataset-grid-v1", source=SourceSelector(kind="LOCAL_DATASET", dataset_id=dataset),
        target_metrics=[], target_histogram=None, requirements=load_mission("mission-mars-mobility").requirements,
        max_detailed=6, reference_set_id=catalog.REFERENCE_SET_PRACTICE,
    )
    result, _ = run(create_science_service(), inputs, ctx, datasets=[dataset])
    assert result.status.value == "SUCCEEDED" and result.payload is not None, result.issues
    source = resolve_source(OpEnv(make_request(inputs, datasets=[dataset]), ctx, load_config()),
                            inputs.source, roles=("EARTH_TERRAIN",))
    assert "Pseudo-Mercator" not in source.raster.grid.crs_wkt
    # At 70 N, a 60 map-metre posting is about 20 ground metres. The
    # destination must use ground spacing, not preserve the distorted 60 m.
    assert 19 < source.raster.native_resolution_m < 22
    assert source.ingest is not None and source.ingest.payload is not None
    assert source.ingest.payload.native_resolution_m == pytest.approx(source.raster.native_resolution_m, rel=1e-9)
    validate_projection_distortion("EARTH", source.raster.grid.crs_wkt,
                                   tuple(result.payload.search_extent.bbox))


def test_whole_planet_aoi_is_bounded_before_large_allocation(tmp_path: Path) -> None:
    ctx = make_practice_context(tmp_path)
    target = mars_target_aoi().model_copy(update={"bbox": [-180, -89, 180, 89]})
    result, _ = run(
        create_science_service(),
        target_input(SourceSelector(kind="LOCAL_DATASET", dataset_id="practice-mars-target-v1"), target),
        ctx, datasets=["practice-mars-target-v1"],
    )
    assert result.status.value == "BLOCKED" and result.payload is None
    assert any(issue.code == "RESOURCE_LIMIT" for issue in result.issues)


def test_geographic_hgt_completes_screen_analyze_and_noninteger_support_comparison(tmp_path: Path) -> None:
    from support.practice import candidate_ref

    from analogforge.ports.science_payloads import (
        AnalyzeCandidateInput,
        AnalyzeCandidatePayload,
        ScreenCandidatesInput,
        ScreenCandidatesPayload,
    )
    from analogforge.science.config import load_config
    from analogforge.science.ops.base import OpEnv
    from analogforge.science.ops.compare import histogram_and_coverage_at_support

    dataset = "mock-nasa-earth-dem"
    data = tmp_path / "incoming"
    generate(data, only=[dataset])
    ctx = make_context(tmp_path / "scratch", dataset_roots={dataset: data / dataset})
    service = create_science_service()
    inputs = ScreenCandidatesInput(
        search_region_set_id="local-dataset-grid-v1", source=SourceSelector(kind="LOCAL_DATASET", dataset_id=dataset),
        target_metrics=[], target_histogram=None, requirements=load_mission("mission-mars-mobility").requirements,
        max_detailed=6, reference_set_id=catalog.REFERENCE_SET_PRACTICE,
    )
    screened, _ = run(service, inputs, ctx, datasets=[dataset])
    assert isinstance(screened.payload, ScreenCandidatesPayload), screened.issues
    assert screened.payload.screened_count == 30
    assert all(w.origin != "KNOWN_CONTROL" for w in screened.payload.windows)
    window = next(w.window_id for w in screened.payload.windows if not w.excluded)
    analyzed_input = AnalyzeCandidateInput(candidate=candidate_ref(screened.payload, window), source=inputs.source,
                                           measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH)
    analyzed, registered = run(service, analyzed_input, ctx, datasets=[dataset])
    assert isinstance(analyzed.payload, AnalyzeCandidatePayload), analyzed.issues
    assert registered is not None
    handle = registered.handles["analysis"]
    assert handle.comparison_scale_m >= 90
    request = make_request(analyzed_input, evidence=[handle], datasets=[dataset])
    env = OpEnv(request, ctx, load_config())
    coarse = histogram_and_coverage_at_support(env, handle, 480.0)
    assert coarse is not None
    histogram, coverage = coarse
    assert histogram.support_scale_m == 480.0 and histogram.valid_area_m2 > 0
    assert 0 < coverage <= 1


@pytest.mark.parametrize("dataset,kind", [
    ("mock-nasa-lunar-radius", "ELEVATION"),
    ("mock-nasa-ascii-dem", "ELEVATION"),
    ("mock-nasa-emit", "MINERAL"),
])
def test_remaining_good_mock_formats_reach_normalized_display_and_science(
    tmp_path: Path, dataset: str, kind: str,
) -> None:
    from analogforge.science.config import load_config
    from analogforge.science.ops.base import OpEnv
    from analogforge.science.ops.source import resolve_source
    from analogforge.science.raster.normalized import decode_source

    data = tmp_path / "incoming"
    generate(data, only=[dataset])
    manifest = yaml.safe_load((data / dataset / "manifest.yaml").read_text())
    ctx = make_context(tmp_path / "scratch", dataset_roots={dataset: data / dataset})
    service = create_science_service()
    ingested, registered = run(service, IngestLocalDatasetInput(manifest=manifest), ctx, datasets=[dataset])
    assert registered is not None and ingested.payload.usable_for_quantitative_claims
    handle = registered.handles["source-" + dataset]
    inputs = BuildDisplayLayersInput(subject="TARGET" if manifest["body"] == "MOON" else "CANDIDATE",
                                    evidence_ids=[handle.evidence_id], layer_kinds=[kind])
    displayed, _ = run(service, inputs, ctx, evidence=[handle])
    assert isinstance(displayed.payload, BuildDisplayLayersPayload), displayed.issues
    assert displayed.payload.layers[0].unit == ("class" if kind == "MINERAL" else "m")
    if kind == "MINERAL":
        original = decode_source(ctx.read_artifact(handle.artifact_sha256).read_bytes())
        request = make_request(inputs, evidence=[handle])
        projected = resolve_source(OpEnv(request, ctx, load_config()),
                                   SourceSelector(kind="ADAPTER_EVIDENCE", evidence_ids=[handle.evidence_id]),
                                   roles=("EARTH_MINERAL",))
        assert set(np.unique(projected.raster.values[~projected.raster.nodata])) <= set(
            np.unique(original.raster.values[~original.raster.missing]))
    if manifest["body"] == "MOON":
        target = load_mission("mission-moon-gap").target.model_copy(
            update={"bbox": [100.05, 9.45, 100.75, 9.95], "longitude_convention": "ZERO_360"})
        result, _ = run(service, target_input(SourceSelector(kind="LOCAL_DATASET", dataset_id=dataset), target),
                        ctx, datasets=[dataset])
        assert isinstance(result.payload, CharacterizeTargetPayload), result.issues
        assert result.payload.slope_histogram is not None
