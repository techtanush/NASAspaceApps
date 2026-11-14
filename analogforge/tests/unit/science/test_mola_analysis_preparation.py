"""The offline MOLA recipe converts coordinates, preserves heights, and refuses ambiguous input."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest
import rasterio
import yaml
from pyproj import CRS, Transformer


@pytest.fixture
def recipe() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "scripts/data/prepare_mola_analysis.py"
    spec = importlib.util.spec_from_file_location("prepare_mola_analysis", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inputs(tmp_path: Path, recipe: ModuleType) -> argparse.Namespace:
    parent = tmp_path / "parent"
    parent.mkdir()
    # A tiny detached-image test tile on the same supported angular grid and figure.
    label = "\n".join(f'{key} = "{value}"' for key, value in {
        "PDS_VERSION_ID": "PDS3", "DATA_SET_ID": "MGS-M-MOLA-5-MEGDR-L3-V1.0",
        "TARGET_NAME": "MARS", "INSTRUMENT_ID": "MOLA", "SAMPLE_TYPE": "MSB_INTEGER",
        "SAMPLE_BITS": "16", "UNIT": "METER", "NAME": "MEDIAN_TOPOGRAPHY",
        "MAP_PROJECTION_TYPE": "SIMPLE CYLINDRICAL", "POSITIVE_LONGITUDE_DIRECTION": "EAST",
        "COORDINATE_SYSTEM_TYPE": "BODY-FIXED ROTATING", "COORDINATE_SYSTEM_NAME": "PLANETOCENTRIC",
        "A_AXIS_RADIUS": "3396.0 <KM>", "B_AXIS_RADIUS": "3396.0 <KM>", "C_AXIS_RADIUS": "3396.0 <KM>",
        "MAP_RESOLUTION": "128.0 <PIXEL/DEGREE>", "CENTER_LATITUDE": "0.0", "CENTER_LONGITUDE": "180.0",
        "MAP_PROJECTION_ROTATION": "0.0", "WESTERNMOST_LONGITUDE": "90", "EASTERNMOST_LONGITUDE": "91",
        "MINIMUM_LATITUDE": "-1", "MAXIMUM_LATITUDE": "0", "LINE_SAMPLES": "128", "LINES": "128",
        "PRODUCT_ID": "tile.IMG", "PRODUCT_VERSION_ID": "2.0",
    }.items()) + "\n/* IAU2000 GMM3 */\n"
    (parent / "source-pds3.lbl").write_text(label)
    (parent / "source-pds4.xml").write_text("<source/>")
    image = tmp_path / "tile.IMG"
    values = (np.arange(128 * 128).reshape(128, 128) % 1000 - 500).astype(">i2")
    values[1, 1] = -32768
    image.write_bytes(values.tobytes())
    (parent / "provenance.json").write_text(json.dumps({
        "source_sha256": recipe.sha256(image), "source_transform": [463, 0, 0, 0, -463, 0],
    }))
    manifest = {
        "dataset_id": "parent", "is_synthetic": False, "body": "MARS", "quantity": "ELEVATION", "units": "m",
        "product_identity": {"version": "2.0", "product_id": "MGS-M-MOLA-5-MEGDR-L3-V1.0",
                             "source_url": "https://pds-geosciences.wustl.edu/mgs/tile.IMG"},
        "crs": {"wkt": CRS.from_proj4("+proj=eqc +lon_0=180 +R=3396000").to_wkt()},
        "citation": "Test source", "files": [
            {"path": name, "sha256": recipe.sha256(parent / name)}
            for name in ("source-pds3.lbl", "source-pds4.xml", "provenance.json")
        ],
    }
    (parent / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    return argparse.Namespace(source_image=image, source_label=parent / "source-pds3.lbl",
                              pds4_label=parent / "source-pds4.xml", parent_dataset=parent,
                              expected_source_sha256=recipe.sha256(image), bbox=[90, -0.03125, 90.03125, 0],
                              dataset_id="prepared", output_dir=tmp_path / "prepared")


def test_coordinate_warp_preserves_angular_support_heights_and_original_bytes(
    recipe: ModuleType, inputs: argparse.Namespace,
) -> None:
    original = inputs.source_image.read_bytes()
    result = recipe.prepare(inputs)
    assert result["shape"] == [4, 4]
    with rasterio.open(inputs.output_dir / "terrain.tif") as dataset:
        assert CRS.from_wkt(dataset.crs.to_wkt()).ellipsoid.semi_major_metre == 3396190
        expected = np.frombuffer(original, dtype=">i2").reshape(128, 128)[:4, :4]
        np.testing.assert_allclose(dataset.read(1), expected, rtol=0, atol=1e-6)
        lon, lat = Transformer.from_crs(dataset.crs, CRS.from_wkt(dataset.crs.to_wkt()).geodetic_crs,
                                        always_xy=True).transform(*(dataset.transform @ (0.5, 0.5)))
        assert lon == pytest.approx(90 + 0.5 / 128)
        assert lat == pytest.approx(-0.5 / 128)
    assert inputs.source_image.read_bytes() == original
    with pytest.raises(FileExistsError):
        recipe.prepare(inputs)


def test_source_checksum_and_reference_units_are_required(recipe: ModuleType, inputs: argparse.Namespace) -> None:
    inputs.expected_source_sha256 = "0" * 64
    with pytest.raises(ValueError, match="checksum"):
        recipe.prepare(inputs)
    text = inputs.source_label.read_text().replace("3396.0 <KM>", "3396.0 <M>")
    with pytest.raises(ValueError, match="A_AXIS_RADIUS"):
        recipe.inspect_label(text)
    assert not inputs.output_dir.exists()
