"""Validate and embed caller-provided images without external resource loads."""

from __future__ import annotations

import base64
import hashlib
import xml.etree.ElementTree as ET

from analogforge.ports.passport_renderer import ProvidedAsset, RendererError

MAX_ASSET_BYTES = 2_000_000
MAX_TOTAL_BYTES = 8_000_000


def image_data_uris(assets: list[ProvidedAsset]) -> list[dict[str, str]]:
    if sum(len(a.content) for a in assets) > MAX_TOTAL_BYTES:
        raise RendererError("UNSAFE_ASSET", "The embedded image budget was exceeded")
    images = []
    seen = set()
    for asset in assets:
        if asset.asset_key in seen:
            raise RendererError("UNSAFE_ASSET", "Duplicate image asset key")
        seen.add(asset.asset_key)
        if len(asset.content) > MAX_ASSET_BYTES or hashlib.sha256(asset.content).hexdigest() != asset.sha256:
            raise RendererError("UNSAFE_ASSET", "Invalid image size or content digest")
        if asset.media_type == "image/png":
            if not asset.content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RendererError("UNSAFE_ASSET", "PNG signature is invalid")
        else:
            try:
                source = asset.content.decode("utf-8")
                if "<!" in source or "<?" in source:
                    raise RendererError("UNSAFE_ASSET", "SVG declarations are not allowed")
                root = ET.fromstring(source)  # noqa: S314 — declarations explicitly rejected above
            except (UnicodeDecodeError, ET.ParseError) as error:
                raise RendererError("UNSAFE_ASSET", "SVG cannot be parsed") from error
            if root.tag.rsplit("}", 1)[-1] != "svg":
                raise RendererError("UNSAFE_ASSET", "SVG root is invalid")
            for node in root.iter():
                if node.tag.rsplit("}", 1)[-1] not in {
                    "svg",
                    "g",
                    "path",
                    "rect",
                    "circle",
                    "ellipse",
                    "line",
                    "polyline",
                    "polygon",
                    "text",
                    "tspan",
                    "title",
                    "desc",
                }:
                    raise RendererError("UNSAFE_ASSET", "SVG contains an unsupported element")
                for attribute, value in node.attrib.items():
                    attr = attribute.rsplit("}", 1)[-1].lower()
                    if attr.startswith("on") or attr in {"href", "src", "style"} or "url(" in value.lower():
                        raise RendererError("UNSAFE_ASSET", "SVG contains active or external content")
        images.append(
            dict(
                key=asset.asset_key,
                uri=f"data:{asset.media_type};base64,{base64.b64encode(asset.content).decode('ascii')}",
                sha256=asset.sha256,
            )
        )
    return images
