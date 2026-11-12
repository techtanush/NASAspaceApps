"""XML parsing with DTDs and entities disabled outright."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET  # noqa: S405 - parsed only after DTD/entity declarations are refused
from pathlib import Path

from analogforge.adapters.source_http.errors import AdapterError

_FORBIDDEN = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)
_DECLARED = re.compile(rb"^\s*<\?xml[^>]{0,200}?encoding\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']")
_ASCII_COMPATIBLE = frozenset({"utf-8", "utf8", "us-ascii", "ascii", "iso-8859-1", "latin-1", "latin1", "windows-1252"})
_WIDE_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)
_WIDE_PROLOGS: tuple[tuple[bytes, str], ...] = (  # "<?" / "<!" without a BOM
    (b"<\x00\x00\x00", "utf-32-le"),
    (b"\x00\x00\x00<", "utf-32-be"),
    (b"<\x00", "utf-16-le"),
    (b"\x00<", "utf-16-be"),
)
MAX_LABEL_BYTES = 8 * 1024 * 1024


def _decode(raw: bytes, name: str) -> tuple[str, bool]:
    """``(text, wide)``: ``text`` is what the DTD scan runs on; ``wide`` marks a UTF-16/32 label decoded here.

    Wide encodings are decoded *before* scanning, because a byte-level search for ``<!DOCTYPE`` cannot see a
    declaration whose characters are interleaved with NUL bytes.  Anything else must be ASCII compatible (declared
    encodings other than UTF-8/ASCII/Latin-1 are refused) so the byte-level and character-level views agree.
    """
    codec = next((c for prefix, c in (*_WIDE_BOMS, *_WIDE_PROLOGS) if raw.startswith(prefix)), None)
    if codec is not None:
        try:
            return raw.decode(codec), True
        except UnicodeDecodeError as exc:
            raise AdapterError(
                "SOURCE_CONTENT_INVALID", f"{name} is not valid {codec} text", detail_code="LABEL_PARSE_ERROR"
            ) from exc
    declared = _DECLARED.match(raw)
    if declared is not None and declared.group(1).decode("ascii").lower() not in _ASCII_COMPATIBLE:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            f"{name} declares unsupported encoding {declared.group(1).decode('ascii')!r}",
            detail_code="LABEL_PARSE_ERROR",
        )
    return raw.decode("latin-1"), False


def parse_xml_file(path: Path) -> ET.Element:
    """Parse a PDS4 label. Any DOCTYPE/ENTITY declaration is refused (in UTF-8 and, after decoding, in UTF-16/32), so
    external entities, parameter entities and entity-expansion bombs can never be processed; real PDS4 labels do not
    need them."""
    if path.stat().st_size > MAX_LABEL_BYTES:
        raise AdapterError("RESOURCE_LIMIT", f"{path.name} exceeds the label size limit", detail_code="LABEL_TOO_LARGE")
    raw = path.read_bytes()
    text, wide = _decode(raw, path.name)
    if _FORBIDDEN.search(text):
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            "XML DTD / entity declarations are not permitted in labels",
            detail_code="XML_DTD_FORBIDDEN",
        )
    try:
        # A decoded str is parsed as UTF-8 whatever its declaration says, so the parser sees the text that was scanned.
        return ET.fromstring(text if wide else raw)  # noqa: S314 - DTD/entities rejected above
    except ET.ParseError as exc:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID", f"{path.name} is not well-formed XML", detail_code="LABEL_PARSE_ERROR"
        ) from exc


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
