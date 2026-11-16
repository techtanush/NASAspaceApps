"""Live terrain support is isolated from the synthetic fixture's fixed grid."""

from pathlib import Path

import pytest
import yaml
from support.practice import Flow, analyze, candidate_ref, characterize_mars, local, make_practice_context, screen

from analogforge.ports import catalog
from analogforge.ports.common import RuntimeMode
from analogforge.ports.science_payloads import AnalyzeCandidatePayload, ScreenCandidatesInput, ScreenCandidatesPayload
from analogforge.science.facade import create_science_service


@pytest.fixture
def mixed_config(tmp_path: Path) -> Path:
    base = Path(__file__).resolve().parents[3] / "config"
    config = tmp_path / "config"
    config.mkdir()
    for name in ("algorithms.yaml", "candidates.yaml", "datasets.yaml"):
        data = yaml.safe_load((base / name).read_text())
        if name == "algorithms.yaml":
            data["live_terrain_support_m"] = 500
        elif name == "candidates.yaml":
            # Small generated windows fit this test's regional raster.
            data["search_region_sets"]["local-dataset-grid-v1"].update(cell_size_m=500, window_cells=6)
        (config / name).write_text(yaml.safe_dump(data))
    return config


@pytest.mark.parametrize("mode", ["synthetic", "live"])
def test_shared_config_characterizes_screens_and_analyzes_at_correct_support(
    tmp_path: Path, mixed_config: Path, mode: RuntimeMode,
) -> None:
    context = make_practice_context(tmp_path / "source")
    context.mode = mode
    earth_id = catalog.FIXTURE_EARTH_GRID
    if mode == "live":
        # Offline test products exercise the local dataset path without claiming NASA observations.
        for dataset_id in (catalog.FIXTURE_MARS_TARGET, earth_id):
            path = context.dataset_roots[dataset_id] / "manifest.yaml"
            manifest = yaml.safe_load(path.read_text())
            manifest.update(is_synthetic=False, provider="TEST_HARNESS", product_identity={
                "product_id": "terrain-test-tile",
                "version": "1.0",
                "source_url": "https://example.invalid/terrain-test-tile.tif",
            })
            path.write_text(yaml.safe_dump(manifest))

    flow = Flow(create_science_service(mixed_config), context)
    target, _ = characterize_mars(flow)
    assert target.slope_histogram is not None
    if mode == "live":
        assert target.comparison_support_m == target.slope_histogram.support_scale_m == 500
        screened, _ = flow.call(
            ScreenCandidatesInput(
                search_region_set_id="local-dataset-grid-v1",
                source=local(earth_id),
                target_histogram=target.slope_histogram,
                target_metrics=target.metrics,
                requirements=[],
                max_detailed=6,
                reference_set_id=catalog.REFERENCE_SET_PRACTICE,
            ),
            datasets=[earth_id],
        )
        assert isinstance(screened.payload, ScreenCandidatesPayload), screened.issues
        listing = screened.payload
        expected_support = 500
    else:
        assert target.comparison_support_m is not None and target.comparison_support_m < 500
        listing = screen(flow, target)
        assert listing.screened_count == 9
        expected_support = 60

    assert listing.shortlist_window_ids
    candidate = candidate_ref(listing, listing.shortlist_window_ids[0])
    window = next(item for item in listing.windows if item.window_id == candidate.window_id)
    assert window.feature_scores["slope_w1_deg"] is not None
    assessed, _ = analyze(flow, candidate)
    assert isinstance(assessed.payload, AnalyzeCandidatePayload), assessed.issues
    assert assessed.payload.slope_histogram is not None
    assert assessed.payload.slope_histogram.support_scale_m == expected_support
