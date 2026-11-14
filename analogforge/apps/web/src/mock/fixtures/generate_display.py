"""Reproducible authored display fixtures; never terrain measurement inputs.

PNG alpha encodes mask/nodata. Affines describe image edges in the declared
body-specific frame. Candidate extents are projected for display only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

from pyproj import CRS

ROOT = Path(__file__).resolve().parent
PALETTE = [(35, 45, 59), (74, 92, 111), (117, 138, 159), (167, 187, 205)]
COLORS = ["#232d3b", "#4a5c6f", "#758a9f", "#a7bbcd"]


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack("!I", len(payload)) + kind + payload + struct.pack("!I", zlib.crc32(kind + payload))


def image(style: str) -> dict[str, object]:
    rows = bytearray()
    masked = 0
    for y in range(64):
        rows.append(0)
        for x in range(64):
            alpha = 255
            if style == "moon" and (x < 12 or x > 51 or y < 6):
                alpha = 0
            elif style == "mars" and 27 <= x < 30:
                alpha = 0
            elif style == "earth" and 28 <= x <= 34 and 15 <= y <= 45:
                alpha = 0
            band = (x // 16) if style != "earth" else (1 if 15 <= x < 22 else 0)
            rows.extend((*PALETTE[band], alpha))
            masked += int(alpha == 0)
    content = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", 64, 64, 8, 6, 0, 0, 0))
    content += chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")
    return {
        "mediaType": "image/png",
        "sha256": hashlib.sha256(content).hexdigest(),
        "contentBase64": base64.b64encode(content).decode(),
        "width": 64,
        "height": 64,
        "mask": {
            "encoding": "ALPHA",
            "transparent_pixel_count": masked,
            "meaning": "Water, nodata or outside valid target wedge; no values inferred",
        },
    }


def mercator(lon: float, lat: float) -> tuple[float, float]:
    return 6378137 * math.radians(lon), 6378137 * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def planetary_wkt(body: str, definition: str) -> str:
    spec = CRS.from_proj4(definition).to_json_dict()
    spec["name"] = f"{body} 2000 synthetic display"
    spec["base_crs"]["name"] = f"{body} 2000 body-fixed sphere"
    spec["base_crs"]["datum"]["name"] = f"{body} synthetic reference sphere"
    spec["base_crs"]["datum"]["ellipsoid"]["name"] = f"{body} reference sphere"
    return CRS.from_json_dict(spec).to_wkt()


def main() -> None:
    seed = json.loads((ROOT / "seed.json").read_text())
    assets = {name: image(name) for name in ["earth", "mars", "moon"]}
    layers = {}
    for candidate in seed["candidates"]:
        west, south, east, north = candidate["aoi"]["bbox"]
        xmin, ymin = mercator(west, south)
        xmax, ymax = mercator(east, north)
        layers[candidate["name"]] = {
            "body": "EARTH",
            "rendering": "EARTH_WEBMERCATOR_IMAGE",
            "display_crs_wkt": CRS.from_epsg(3857).to_wkt(),
            "pixel_to_world": [xmin, (xmax - xmin) / 64, 0, ymax, 0, -(ymax - ymin) / 64],
            "earth_corners": [[west, north], [east, north], [east, south], [west, south]],
            "support_scale_m": 60,
            "asset": "earth",
        }
    radius = 3396190
    west, south, east, north = seed["missionPresets"]["MARS"]["target"]["bbox"]
    xmin, xmax = (radius * math.radians(lon - 137.5) for lon in [west, east])
    ymin, ymax = (radius * math.radians(lat) for lat in [south, north])
    layers["MARS"] = {
        "body": "MARS",
        "rendering": "PLANETARY_PLANAR_IMAGE",
        "display_crs_wkt": planetary_wkt(
            "Mars", "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=137.5 +R=3396190 +units=m +no_defs +type=crs"
        ),
        "pixel_to_world": [xmin, (xmax - xmin) / 64, 0, ymax, 0, -(ymax - ymin) / 64],
        "earth_corners": None,
        "support_scale_m": 480,
        "asset": "mars",
    }
    layers["MOON"] = {
        "body": "MOON",
        "rendering": "PLANETARY_PLANAR_IMAGE",
        "display_crs_wkt": planetary_wkt(
            "Moon", "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m +no_defs +type=crs"
        ),
        "pixel_to_world": [-13162, 411.3125, 0, 75800, 0, -947.5],
        "earth_corners": None,
        "support_scale_m": 960,
        "asset": "moon",
    }
    result = {
        "assets": assets,
        "layers": layers,
        "legend": [
            {"label": label, "lower": lo, "upper": hi, "color": color}
            for label, lo, hi, color in zip(
                ["0–5 deg", "5–12 deg", "12–18 deg", "18–25 deg"], [0, 5, 12, 18], [5, 12, 18, 25], COLORS, strict=True
            )
        ],
    }
    (ROOT / "display-assets.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
