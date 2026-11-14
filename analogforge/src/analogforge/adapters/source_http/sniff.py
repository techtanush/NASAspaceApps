"""Content sniffing shared by the transport layer and dataset validation (no I/O, no dependencies)."""

from __future__ import annotations

import re

SNIFF_BYTES = 4096  # how much of a body's head is examined (comments/prologs may precede the document)
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)
_SKIP = re.compile(r"\s+|<!--.*?-->|<\?.*?\?>", re.DOTALL)
_HTML_START = re.compile(r"<(!doctype|html|head|body)", re.IGNORECASE)


def _decode_head(head: bytes) -> str:
    for bom, codec in _BOMS:
        if head.startswith(bom):
            return head[len(bom) :].decode(codec, errors="ignore")
    if len(head) >= 4 and head[0] != 0 and head[1:4] == b"\x00\x00\x00":
        return head.decode("utf-32-le", errors="ignore")
    if len(head) >= 2 and head[0] != 0 and head[1] == 0:
        return head.decode("utf-16-le", errors="ignore")
    if len(head) >= 2 and head[0] == 0 and head[1] != 0:
        return head.decode("utf-16-be", errors="ignore")
    return head.decode("utf-8", errors="ignore")


def looks_like_html(head: bytes) -> bool:
    """True when ``head`` (the first bytes of a body) starts an HTML document.

    Tolerated before the document: a byte-order mark (UTF-8/16/32), whitespace, NULs, any number of ``<!-- -->``
    comments and ``<? ?>`` processing instructions (an XML prolog), and UTF-16/32 encoding.  Only the first
    :data:`SNIFF_BYTES` are examined; an unterminated comment inside that window is not HTML.
    """
    text = _decode_head(head[:SNIFF_BYTES]).replace("\x00", "")
    pos = 0
    while True:
        match = _SKIP.match(text, pos)
        if match is None or match.end() == pos:
            break
        pos = match.end()
    return _HTML_START.match(text, pos) is not None
