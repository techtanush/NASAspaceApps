"""XML parsing with DTDs and entities disabled outright."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405 - parsed only after DTD/entity declarations are refused
from pathlib import Path

from analogforge.adapters.source_http.errors import AdapterError

_FORBIDDEN = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
MAX_LABEL_BYTES = 8 * 1024 * 1024


def parse_xml_file(path: Path) -> ET.Element:
    """Parse a PDS4 label. Any DOCTYPE/ENTITY declaration is refused, so external entities, parameter entities
    and entity-expansion bombs can never be processed; real PDS4 labels do not need them."""
    if path.stat().st_size > MAX_LABEL_BYTES:
        raise AdapterError("RESOURCE_LIMIT", f"{path.name} exceeds the label size limit", detail_code="LABEL_TOO_LARGE")
    data = path.read_bytes()
    if _FORBIDDEN.search(data):
        raise AdapterError("SOURCE_CONTENT_INVALID", "XML DTD / entity declarations are not permitted in labels",
                           detail_code="XML_DTD_FORBIDDEN")
    try:
        return ET.fromstring(data)  # noqa: S314 - DTD/entities rejected above
    except ET.ParseError as exc:
        raise AdapterError("SOURCE_CONTENT_INVALID", f"{path.name} is not well-formed XML",
                           detail_code="LABEL_PARSE_ERROR") from exc


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_all(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if local(el.tag) == name]


def find_one(root: ET.Element, name: str) -> ET.Element | None:
    found = find_all(root, name)
    return found[0] if found else None


def text_of(root: ET.Element, name: str) -> str | None:
    el = find_one(root, name)
    return el.text.strip() if el is not None and el.text and el.text.strip() else None
