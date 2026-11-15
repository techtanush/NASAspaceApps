"""Offline integrity and geographic-orientation checks for the delivered context catalog."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pytest
from PIL import Image

APP = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("prepare_globe_context", APP / "scripts/data/prepare_globe_context.py")
assert SPEC is not None and SPEC.loader is not None
context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context)


def _image(width: int = 32, height: int = 16) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), (30, 80, 120)).save(output, format="PNG")
    return output.getvalue()


def _asset(data: bytes) -> dict[str, Any]:
    return {
        "body": "EARTH", "surface_path": "globe/deliveries/test.v1.png", "relief_path": None,
        "placeholder": False, "attribution": "NASA test receipt", "source_uri": "https://science.nasa.gov/",
        "source_product": "Offline test", "usage_terms": "NASA acknowledged; visual context only",
        "sha256": context.digest(data), "bytes": len(data), "width": 32, "height": 16,
        "longitude_convention": "NEG180_180", "north_up": True, "purpose": "VISUAL_CONTEXT_ONLY",
        "relief_sha256": None, "relief_bytes": None,
    }


@pytest.fixture
def publication(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    data = _image()
    path = tmp_path / "globe/deliveries/test.v1.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    return tmp_path, {"schema_version": "1.0", "assets": [_asset(data)]}


def test_optional_relief_and_empty_fallback_catalog_are_valid(publication: tuple[Path, dict[str, Any]]) -> None:
    root, catalog = publication
    context.validate_catalog(root, catalog)
    context.validate_catalog(root, {"schema_version": "1.0", "assets": []})


@pytest.mark.parametrize("path", [
    "globe/deliveries/../private.png", "globe/deliveries/./test.png", "globe/deliveries//test.png",
    "https://example.com/a.jpg", "/globe/deliveries/test.png", "globe/deliveries/a%2f..%2fsecret",
    "globe/deliveries/a\\b.png", "globe/deliveries/a.jpg?token=private",
])
def test_delivery_path_rejects_traversal_and_remote_sources(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        context.safe_delivery_path(tmp_path, path)


def test_delivery_symlink_cannot_escape_public_root(tmp_path: Path) -> None:
    outside = tmp_path / "private"
    outside.mkdir()
    public = tmp_path / "public"
    (public / "globe/deliveries").mkdir(parents=True)
    (public / "globe/deliveries/redirect").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        context.safe_delivery_path(public, "globe/deliveries/redirect/source.png")


@pytest.mark.parametrize(("field", "value"), [
    ("sha256", "0" * 64), ("bytes", 1), ("width", 64), ("height", 8),
    ("attribution", ""), ("usage_terms", "   "), ("north_up", False),
    ("longitude_convention", "ZERO_360"), ("purpose", "ELEVATION"),
    ("source_uri", "https://user:password@science.nasa.gov/"),
    ("source_uri", "https://science.nasa.gov/?token=private"),
])
def test_invalid_metadata_cannot_describe_a_valid_asset(
    publication: tuple[Path, dict[str, Any]], field: str, value: Any,
) -> None:
    root, catalog = publication
    catalog["assets"][0][field] = value
    with pytest.raises((ValueError, jsonschema.ValidationError)):
        context.validate_catalog(root, catalog)


def test_missing_file_duplicate_body_and_orphan_relief_are_rejected(
    publication: tuple[Path, dict[str, Any]],
) -> None:
    root, catalog = publication
    duplicate = copy.deepcopy(catalog)
    duplicate["assets"].append(copy.deepcopy(duplicate["assets"][0]))
    with pytest.raises(jsonschema.ValidationError):
        context.validate_catalog(root, duplicate)
    orphan = copy.deepcopy(catalog)
    orphan["assets"][0]["relief_sha256"] = "a" * 64
    with pytest.raises(jsonschema.ValidationError):
        context.validate_catalog(root, orphan)
    (root / catalog["assets"][0]["surface_path"]).unlink()
    with pytest.raises(ValueError):
        context.validate_catalog(root, catalog)


def test_image_ratio_and_alpha_are_not_inferred_from_metadata() -> None:
    with pytest.raises(ValueError):
        context.inspect_image(_image(30, 20))
    output = io.BytesIO()
    Image.new("RGBA", (32, 16), (0, 0, 0, 0)).save(output, format="PNG")
    with pytest.raises(ValueError):
        context.inspect_image(output.getvalue())


def test_explicit_zero_longitude_roll_and_south_up_flip() -> None:
    original = Image.new("RGB", (8, 4))
    original.putdata([(x * 30, y * 60, 0) for y in range(4) for x in range(8)])
    oriented = context.orient_image(original, west=0, north_up=False)
    assert oriented.getpixel((0, 0)) == (120, 180, 0)
    assert oriented.getpixel((4, 0)) == (0, 180, 0)
    assert oriented.getpixel((7, 3)) == (90, 0, 0)
    assert original.getpixel((0, 0)) == (0, 0, 0)
    with pytest.raises(ValueError):
        context.orient_image(original, west=90, north_up=True)


@pytest.mark.parametrize(("longitude", "latitude", "pixel"), [
    (-180, 90, (0, 0)), (0, 0, (180, 90)), (180, -90, (359, 179)), (-90, 45, (90, 45)),
])
def test_visual_coordinate_controls_use_north_up_area_layout(
    longitude: float, latitude: float, pixel: tuple[int, int],
) -> None:
    assert context.context_pixel(360, 180, longitude, latitude) == pixel


@pytest.mark.parametrize(("longitude", "latitude"), [(float("nan"), 0), (0, float("inf")), (181, 0), (0, -91)])
def test_invalid_visual_coordinates_are_rejected(longitude: float, latitude: float) -> None:
    with pytest.raises(ValueError):
        context.context_pixel(360, 180, longitude, latitude)


def _source(data: bytes) -> dict[str, Any]:
    return {"cache_filename": "source.png", "source_bytes": len(data), "source_sha256": context.digest(data),
            "source_dimensions": [32, 16], "source_west": -180, "source_north_up": True,
            "download_uri": "https://svs.gsfc.nasa.gov/reviewed-source.png",
            "delivery_dimensions": [32, 16], "encoding": "SOURCE_BYTES"}


def test_source_hash_mismatch_stops_before_derivation(tmp_path: Path) -> None:
    data = _image()
    source = _source(data)
    (tmp_path / "source.png").write_bytes(b"corrupt source")
    with pytest.raises(ValueError, match="checksum"):
        context.read_source(source, tmp_path, download=False)


def test_network_is_opt_in_and_arbitrary_hosts_are_rejected(tmp_path: Path) -> None:
    source = _source(_image())
    with pytest.raises(FileNotFoundError):
        context.read_source(source, tmp_path, download=False)
    source["download_uri"] = "https://example.com/source.png"
    with pytest.raises(ValueError, match="allowlist"):
        context.read_source(source, tmp_path, download=True)


@pytest.mark.parametrize("response_kind", ["redirect", "too_large", "wrong_hash", "valid"])
def test_download_bounds_and_pin_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response_kind: str,
) -> None:
    data = _image()
    source = _source(data)

    def respond(request: httpx.Request) -> httpx.Response:
        if response_kind == "redirect":
            return httpx.Response(302, headers={"location": "https://example.com/secret"})
        if response_kind == "too_large":
            return httpx.Response(200, headers={"content-length": str(context.MAX_SOURCE_BYTES + 1)})
        return httpx.Response(200, content=b"wrong bytes" if response_kind == "wrong_hash" else data)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        def mock_stream(method: str, uri: str, **kwargs: Any) -> Any:
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False
            return client.stream(method, uri)

        monkeypatch.setattr(context.httpx, "stream", mock_stream)
        if response_kind == "valid":
            assert context.read_source(source, tmp_path, download=True) == data
            assert (tmp_path / "source.png").read_bytes() == data
        else:
            with pytest.raises((ValueError, httpx.HTTPStatusError)):
                context.read_source(source, tmp_path, download=True)
            assert not (tmp_path / "source.png").exists()


def test_derivation_never_upscales_or_mutates_source_bytes() -> None:
    data = _image()
    source = _source(data)
    assert context.derive(source, data) == data
    source["delivery_dimensions"] = [64, 32]
    with pytest.raises(ValueError, match="upscale"):
        context.derive(source, data)


def test_immutable_delivery_rejects_version_collision(tmp_path: Path) -> None:
    target = tmp_path / "version.v1.png"
    context.immutable_write(target, b"first")
    context.immutable_write(target, b"first")
    with pytest.raises(FileExistsError):
        context.immutable_write(target, b"replacement")
    assert target.read_bytes() == b"first"


def _preparation_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, bytes]:
    data = _image()
    source = _source(data)
    source.update({"body": "EARTH", "delivery_path": "globe/deliveries/test.v1.png",
                   "product_uri": "https://science.nasa.gov/", "source_product": "Offline fixture",
                   "attribution": "NASA fixture for offline tests", "usage_terms": "Visual context only"})
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"sources": [source]}))
    monkeypatch.setattr(context, "SOURCES_PATH", manifest)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "source.png").write_bytes(data)
    return cache, tmp_path / "public", data


def test_complete_preparation_preserves_source_and_reproduces_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache, public, original = _preparation_fixture(tmp_path, monkeypatch)
    result = context.prepare(cache, public)
    assert (cache / "source.png").read_bytes() == original
    assert (public / "globe/deliveries/test.v1.png").read_bytes() == original
    assert not (public / "source.png").exists()
    assert result == context.prepare(cache, public)
    context.validate_catalog(public, result)


def test_publication_collision_is_detected_before_any_new_asset_is_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache, public, _ = _preparation_fixture(tmp_path, monkeypatch)
    catalog = public / "globe/data/catalog.v1.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"existing different release")
    with pytest.raises(FileExistsError):
        context.prepare(cache, public)
    assert not (public / "globe/deliveries/test.v1.png").exists()
    assert catalog.read_bytes() == b"existing different release"


def test_source_cache_must_stay_outside_public_delivery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache, _, _ = _preparation_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="separate"):
        context.prepare(cache, cache / "public")
    with pytest.raises(ValueError, match="separate"):
        context.prepare(cache, tmp_path)


def test_symlink_metadata_directory_cannot_publish_private_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache, public, _ = _preparation_fixture(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (public / "globe").mkdir(parents=True)
    (public / "globe/data").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="Symlink"):
        context.prepare(cache, public)
    assert list(outside.iterdir()) == []
    assert not (public / "globe/deliveries/test.v1.png").exists()


def test_delivered_catalog_bytes_dimensions_schema_and_source_provenance() -> None:
    catalog = json.loads((context.PUBLIC_ROOT / "globe/data/catalog.v1.json").read_text())
    context.validate_catalog(context.PUBLIC_ROOT, catalog)
    assert {asset["body"] for asset in catalog["assets"]} == {"EARTH", "MARS", "MOON"}
    assert all(not asset["placeholder"] and asset["relief_path"] is None for asset in catalog["assets"])
    receipt = json.loads((context.PUBLIC_ROOT / "globe/data/preparation.v1.json").read_text())
    assert receipt["sources_manifest_sha256"] == context.digest(context.SOURCES_PATH.read_bytes())
    assert receipt["quantitative_terrain"] is False and receipt["analysis_support_m"] is None
    for source, asset in zip(receipt["sources"], catalog["assets"], strict=True):
        assert source["body"] == asset["body"]
        assert source["delivery_sha256"] == asset["sha256"]
        assert source["delivery_bytes"] == asset["bytes"]
        assert source["delivery_dimensions"] == [asset["width"], asset["height"]]
        assert source["operations"]["inpainting"] is False
        assert source["operations"]["height_transformation"] == "NONE"
        assert asset["width"] <= source["source_dimensions"][0]


def _geographic_rgb(body: str, longitude: float, latitude: float) -> tuple[int, int, int]:
    catalog = json.loads((context.PUBLIC_ROOT / "globe/data/catalog.v1.json").read_text())
    asset = next(asset for asset in catalog["assets"] if asset["body"] == body)
    with Image.open(context.PUBLIC_ROOT / asset["surface_path"]) as image:
        point = context.context_pixel(image.width, image.height, longitude, latitude)
        rgb = image.getpixel(point)
        assert isinstance(rgb, tuple) and len(rgb) == 3
        return rgb


def test_earth_geographic_landmarks_detect_wrong_hemisphere_or_vertical_flip() -> None:
    desert = _geographic_rgb("EARTH", 20, 25)
    ocean = _geographic_rgb("EARTH", -140, 0)
    forest = _geographic_rgb("EARTH", -65, -5)
    ice = _geographic_rgb("EARTH", 0, -82)
    assert desert[0] > 160 and desert[1] > 130 and desert[2] < 180
    assert ocean[2] > ocean[0] * 2 and max(ocean) < 60
    assert forest[1] > forest[0] and max(forest) < 80
    assert min(ice) > 180


def test_mars_independent_usgs_location_controls_and_native_resolution() -> None:
    # USGS Feature4453:226.20E=133.80W,18.65N; Feature2432:70.50E,42.43S.
    volcano = _geographic_rgb("MARS", -133.8, 18.65)
    basin = _geographic_rgb("MARS", 70.5, -42.43)
    syrtis = _geographic_rgb("MARS", 69, 8)
    assert volcano[0] > volcano[1] > volcano[2]
    assert sum(basin) > sum(syrtis) + 100
    with Image.open(context.PUBLIC_ROOT / "globe/deliveries/mars-viking-nasa.v1.jpg") as image:
        assert image.size == (1440, 720)


def test_moon_tycho_control_distinguishes_bright_south_from_dark_northern_maria() -> None:
    # NASA Tycho control:43.37S,348.68E=11.32W, independent of texture dimensions.
    tycho = _geographic_rgb("MOON", -11.32, -43.37)
    crisium = _geographic_rgb("MOON", 59.1, 17)
    procellarum = _geographic_rgb("MOON", -57.4, 18.4)
    assert min(tycho) > 185
    assert max(crisium) < 120 and max(procellarum) < 120
