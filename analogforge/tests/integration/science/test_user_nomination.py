"""User AOIs are measured on source support without requiring a catalog window identifier."""

import numpy as np
import pytest
from pyproj import Transformer
from support.practice import Flow, candidate_ref, characterize_mars, local, make_practice_context, screen, service

from analogforge.ports import catalog
from analogforge.ports.science_payloads import AnalyzeCandidateInput
from analogforge.science.raster.store import decode_analysis_grid


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    flow = Flow(service(), make_practice_context(tmp_path_factory.mktemp("nominated")))
    target, _ = characterize_mars(flow)
    return flow, candidate_ref(screen(flow, target), catalog.WINDOW_B_CORRIDOR)


def measure(flow, candidate):
    return flow.call(AnalyzeCandidateInput(
        candidate=candidate, source=local("practice-earth-grid-v1"),
        measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH,
    ), datasets=["practice-earth-grid-v1"])


def test_user_nomination_inside_available_source_is_measured_and_keeps_its_id(world):
    flow, original = world
    nominated = original.model_copy(update={"window_id": "user-nominated-region", "origin": "USER_SUPPLIED"})
    result, registered = measure(flow, nominated)
    assert result.status.value == "SUCCEEDED", result.issues
    assert registered is not None
    assert 0 < result.payload.coverage_fraction <= 1
    handle = registered.handles["analysis"]
    grid = decode_analysis_grid(flow.ctx.artifact_paths[handle.artifact_sha256].read_bytes())
    assert grid.valid.any() and grid.meta.cell_size_m >= 60
    meta = grid.meta
    x, y = np.meshgrid(meta.origin_x_m + (np.arange(meta.width) + .5) * meta.cell_size_m,
                       meta.origin_y_m - (np.arange(meta.height) + .5) * meta.cell_size_m)
    lon, lat = Transformer.from_crs(meta.crs_wkt, "EPSG:4326", always_xy=True).transform(x, y)
    west, south, east, north = nominated.aoi.bbox
    inside = (lon >= west - 1e-9) & (lon <= east + 1e-9) & (lat >= south - 1e-9) & (lat <= north + 1e-9)
    assert not (grid.valid & ~inside).any() and not (grid.land & ~inside).any()
    assert result.payload.coverage_fraction <= float(grid.valid.sum()) / max(1, int(inside.sum())) + 1e-9
    assert any("User-nominated" in value for value in result.payload.limitations)


def test_unknown_catalog_window_never_gets_user_nomination_privileges(world):
    flow, original = world
    result, _ = measure(flow, original.model_copy(update={"window_id": "not-a-catalog-window", "origin": "DISCOVERED"}))
    assert result.status.value == "BLOCKED"
    assert any(issue.code == "NO_COVERAGE" for issue in result.issues)


def test_outside_source_nomination_has_no_measurements(world):
    flow, original = world
    aoi = original.aoi.model_copy(update={"bbox": [0, 0, 0.01, 0.01]})
    result, _ = measure(flow, original.model_copy(update={
        "window_id": "user-outside", "origin": "USER_SUPPLIED", "aoi": aoi,
    }))
    assert result.status.value == "BLOCKED" and result.payload is None
    assert any(issue.code in {"NO_COVERAGE", "RESOURCE_LIMIT"} for issue in result.issues)


def test_missing_part_of_nominated_aoi_lowers_the_coverage_denominator(world):
    flow, original = world
    west, south, east, north = original.aoi.bbox
    aoi = original.aoi.model_copy(update={"bbox": [west - .2 * (east - west), south, east, north]})
    result, _ = measure(flow, original.model_copy(update={
        "window_id": "user-partial-source", "origin": "USER_SUPPLIED", "aoi": aoi,
    }))
    assert result.status.value == "SUCCEEDED", result.issues
    assert .5 < result.payload.coverage_fraction < .9
