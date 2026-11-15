"""Bounded, checksum-pinned preparation of public NASA globe context images.

This offline build utility never registers analysis datasets or modifies a source
lock. Network acquisition is opt-in and limited to the three reviewed URLs.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import jsonschema
from PIL import Image, ImageChops, features
from PIL import __version__ as pillow_version

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parent
PUBLIC_ROOT = APP_ROOT / "apps/web/public"
SOURCES_PATH = Path(__file__).with_name("globe_context_sources.v1.json")
SCHEMA_PATH = REPO_ROOT / "team handoffs/ui-split/schemas/imagery-catalog.v1.schema.json"
MAX_SOURCE_BYTES = 20_000_000
MAX_PUBLIC_BYTES = 8_000_000
MAX_IMAGE_PIXELS = 16_000_000
MAX_DOWNLOAD_SECONDS = 120
ALLOWED_HOSTS = frozenset({"assets.science.nasa.gov", "svs.gsfc.nasa.gov"})
RECIPE = "nasa-global-visual-context/1.0"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def safe_delivery_path(public_root: Path, value: str) -> Path:
    """Accept only local, non-symlink files in the reserved delivery directory."""
    if (not re.fullmatch(r"globe/deliveries/[A-Za-z0-9_./-]+", value)
            or any(part in {".", "..", ""} for part in value.split("/"))):
        raise ValueError("Invalid same-origin delivery path")
    root = public_root.resolve()
    target = root / value
    if not target.resolve().is_relative_to(root / "globe/deliveries"):
        raise ValueError("Delivery path escapes its reserved directory")
    if any(path.is_symlink() for path in [target, *target.parents] if path != root):
        raise ValueError("Symlink delivery paths are not accepted")
    return target


def inspect_image(data: bytes, max_bytes: int = MAX_PUBLIC_BYTES) -> tuple[int, int]:
    if not data or len(data) > max_bytes:
        raise ValueError("Image exceeds its byte budget")
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
        if width != 2 * height or width * height > MAX_IMAGE_PIXELS:
            raise ValueError("Expected a bounded 2:1 equirectangular image")
        if image.format not in {"JPEG", "PNG", "TIFF"} or image.mode != "RGB":
            raise ValueError("Expected an RGB image without a hidden alpha/nodata channel")
        if image.getexif().get(274, 1) != 1:
            raise ValueError("EXIF rotation is not permitted; orient pixels explicitly")
        image.load()
    # Some format-specific EXIF readers load/close the first handle (notably PNG).
    # Verify a fresh stream rather than depending on a still-open decoder handle.
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    return width, height


def orient_image(image: Image.Image, *, west: int, north_up: bool) -> Image.Image:
    """Pixel operation only: east-positive global 0..360 or -180..180, no reprojection."""
    if image.width != 2 * image.height or image.width % 2 or west not in {-180, 0}:
        raise ValueError("Unsupported global orientation")
    result = image.convert("RGB")
    if not north_up:
        result = result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if west == 0:
        result = ImageChops.offset(result, result.width // 2, 0)
    return result


def context_pixel(width: int, height: int, longitude: float, latitude: float) -> tuple[int, int]:
    """Geographic lookup for VISUAL orientation checks, never quantitative sampling."""
    if (not all(math.isfinite(v) for v in [longitude, latitude])
            or not -180 <= longitude <= 180 or not -90 <= latitude <= 90):
        raise ValueError("Invalid geographic control")
    return min(width - 1, int((longitude + 180) / 360 * width)), min(height - 1, int((90 - latitude) / 180 * height))


def validate_catalog(public_root: Path, catalog: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(catalog)
    used: set[str] = set()
    for asset in catalog["assets"]:
        for key in ["attribution", "source_product", "usage_terms"]:
            if not asset[key].strip():
                raise ValueError(f"Missing {key}")
        citation = urlsplit(asset["source_uri"])
        if (citation.scheme != "https" or not citation.hostname or citation.username or citation.password
                or citation.query or citation.fragment or citation.port not in {None, 443}):
            raise ValueError("Expected a public HTTPS citation without credentials or tokens")
        for prefix in ["surface", "relief"]:
            value = asset[f"{prefix}_path"]
            if value is None:
                continue
            if value in used:
                raise ValueError("Delivery paths must be unique")
            used.add(value)
            path = safe_delivery_path(public_root, value)
            if not path.is_file() or path.stat().st_size > MAX_PUBLIC_BYTES:
                raise ValueError("Missing or oversized delivery image")
            data = path.read_bytes()
            size = inspect_image(data)
            expected_hash = asset["sha256"] if prefix == "surface" else asset["relief_sha256"]
            expected_bytes = asset["bytes"] if prefix == "surface" else asset["relief_bytes"]
            if digest(data) != expected_hash or len(data) != expected_bytes:
                raise ValueError("Delivery image does not match its immutable digest/byte receipt")
            if size != (asset["width"], asset["height"]):
                raise ValueError("Delivery dimensions disagree with the catalog")


def read_source(source: dict[str, Any], cache: Path, *, download: bool) -> bytes:
    name = source["cache_filename"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]+", name):
        raise ValueError("Invalid cache filename")
    path = cache / name
    if path.is_symlink():
        raise ValueError("Source cache must not contain symlinks")
    if path.exists():
        if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("Source cache item exceeds its byte budget")
        data = path.read_bytes()
    else:
        if not download:
            raise FileNotFoundError(f"Missing pinned source {name}; use --download to acquire it")
        uri = source["download_uri"]
        parsed = urlsplit(uri)
        if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in {None, 443}
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Source URL is outside the reviewed public NASA allowlist")
        chunks: list[bytes] = []
        count = 0
        started = time.monotonic()
        # No redirects: acquisition cannot leave the pinned URL/host, including on a NASA 302.
        with httpx.stream("GET", uri, follow_redirects=False, timeout=30, trust_env=False) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Redirected source acquisition is not permitted")
            if int(response.headers.get("content-length", "0")) > MAX_SOURCE_BYTES:
                raise ValueError("Source response exceeds its byte budget")
            for chunk in response.iter_bytes(64 * 1024):
                count += len(chunk)
                if count > MAX_SOURCE_BYTES or time.monotonic() - started > MAX_DOWNLOAD_SECONDS:
                    raise ValueError("Source response exceeds its bounded acquisition budget")
                chunks.append(chunk)
        data = b"".join(chunks)
    if len(data) != source["source_bytes"] or digest(data) != source["source_sha256"]:
        raise ValueError("Original source bytes differ from the reviewed checksum")
    if inspect_image(data, MAX_SOURCE_BYTES) != tuple(source["source_dimensions"]):
        raise ValueError("Original source dimensions differ from the product receipt")
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        # Never replace another acquisition or a versioned source.
        with path.open("xb") as handle:
            handle.write(data)
    return data


def derive(source: dict[str, Any], data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as original:
        image = orient_image(original, west=source["source_west"], north_up=source["source_north_up"])
        dimensions = tuple(source["delivery_dimensions"])
        if dimensions[0] > original.width or dimensions[1] > original.height:
            raise ValueError("Do not upscale a global context image to invent source detail")
        if source["encoding"] == "SOURCE_BYTES":
            if (dimensions != original.size or source["source_west"] != -180
                    or not source["source_north_up"]):
                raise ValueError("A byte-copy delivery cannot change orientation or dimensions")
            return data
        if source["encoding"] != "JPEG_Q90_444":
            raise ValueError("Unknown derivative encoding")
        if image.size != dimensions:
            image = image.resize(dimensions, Image.Resampling.LANCZOS)
        result = io.BytesIO()
        image.save(result, format="JPEG", quality=90, subsampling=0, optimize=True, progressive=False)
        return result.getvalue()


def immutable_write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ValueError("Refusing a symlink publication target")
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"Refusing to replace immutable delivery: {path.name}; version it instead")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".context-stage-", dir=path.parent) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        os.fchmod(handle.fileno(), 0o644)
        # A hard link publishes complete bytes atomically and fails if another
        # writer created the immutable version while preparation was in flight.
        os.link(handle.name, path)


def prepare(cache: Path, public_root: Path, *, download: bool = False) -> dict[str, Any]:
    cache, public_root = cache.resolve(), public_root.resolve()
    if cache.is_relative_to(public_root) or public_root.is_relative_to(cache):
        raise ValueError("Original source cache and public delivery must be separate directories")
    specifications = json.loads(SOURCES_PATH.read_text())
    receipt: dict[str, Any] = {
        "recipe": RECIPE,
        "purpose": "VISUAL_CONTEXT_ONLY",
        "sources_manifest_sha256": digest(SOURCES_PATH.read_bytes()),
        "encoder": {"pillow": pillow_version, "libjpeg": features.version_codec("jpg")},
        "coordinate_layout": {"west": -180, "east": 180, "north": 90, "south": -90,
                              "positive_longitude_direction": "EAST", "pixel_interpretation": "AREA"},
        "quantitative_terrain": False,
        "analysis_support_m": None,
        "sources": [],
    }
    catalog: dict[str, Any] = {"schema_version": "1.0", "assets": []}
    outputs: dict[str, bytes] = {}
    for source in specifications["sources"]:
        data = read_source(source, cache, download=download)
        delivered = derive(source, data)
        width, height = inspect_image(delivered)
        path = source["delivery_path"]
        safe_delivery_path(public_root, path)
        outputs[path] = delivered
        catalog["assets"].append({
            "body": source["body"], "surface_path": path, "relief_path": None, "placeholder": False,
            "attribution": source["attribution"], "source_uri": source["product_uri"],
            "source_product": source["source_product"], "usage_terms": source["usage_terms"],
            "sha256": digest(delivered), "bytes": len(delivered), "width": width, "height": height,
            "longitude_convention": "NEG180_180", "north_up": True, "purpose": "VISUAL_CONTEXT_ONLY",
            "relief_sha256": None, "relief_bytes": None,
        })
        receipt["sources"].append({**source, "delivery_sha256": digest(delivered),
                                   "delivery_bytes": len(delivered),
                                   "operations": {"longitude_roll_pixels": 0, "vertical_flip": False,
                                                  "resample": "LANCZOS" if width != source["source_dimensions"][0]
                                                  else "NONE", "padding": False, "inpainting": False,
                                                  "height_transformation": "NONE"}})
    # Validate the complete staged publication before exposing its catalog.
    with tempfile.TemporaryDirectory(prefix="analogforge-context-") as temporary:
        staging = Path(temporary)
        for name, data in outputs.items():
            staged = staging / name
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
        validate_catalog(staging, catalog)
    publication = {**outputs, "globe/data/preparation.v1.json": json_bytes(receipt),
                   "globe/data/catalog.v1.json": json_bytes(catalog)}
    # Preflight every destination so a version collision cannot partially overwrite a release.
    for name, data in publication.items():
        target = public_root / name
        if any(path.is_symlink() for path in [target, *target.parents] if path != public_root):
            raise ValueError("Symlink publication paths are not accepted")
        if target.exists() and target.read_bytes() != data:
            raise FileExistsError(f"Existing {name} differs; publish a new version")
    for name, data in publication.items():
        immutable_write(public_root / name, data)
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--cache-dir", type=Path, required=True)
    build.add_argument("--public-root", type=Path, default=PUBLIC_ROOT)
    build.add_argument("--download", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("--public-root", type=Path, default=PUBLIC_ROOT)
    args = parser.parse_args()
    if args.command == "prepare":
        catalog = prepare(args.cache_dir, args.public_root, download=args.download)
    else:
        catalog = json.loads((args.public_root / "globe/data/catalog.v1.json").read_text())
        validate_catalog(args.public_root, catalog)
    print(json.dumps({"status": "PASS", "schema_version": catalog["schema_version"],
                      "bodies": [asset["body"] for asset in catalog["assets"]],
                      "bytes": sum(asset["bytes"] for asset in catalog["assets"])}))


if __name__ == "__main__":
    main()
