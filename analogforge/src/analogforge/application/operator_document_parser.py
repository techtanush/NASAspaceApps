"""Local text extraction in a disposable, bounded process; never document execution or OCR."""

from __future__ import annotations

import io
import json
import logging
import resource
import sys
import zipfile
from importlib.metadata import version
from typing import Any

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 64000
MAX_PAGES = 40
MAX_DECOMPRESSED = 8 * 1024 * 1024


class DocumentRejected(ValueError):
    pass


def extract(content: bytes, kind: str) -> dict[str, Any]:
    if not content or len(content) > MAX_BYTES:
        raise DocumentRejected("FILE_SIZE")
    pages = None
    parser = {"name": "python-utf8", "version": "1"}
    if kind in {"txt", "md", "json"}:
        text = content.decode("utf-8-sig", errors="strict")
        if "\x00" in text:
            raise DocumentRejected("BINARY_TEXT")
        if kind == "json":
            from analogforge.api.security import json_nesting_depth

            if json_nesting_depth(content, 32) > 32:
                raise DocumentRejected("JSON_DEPTH")
            json.loads(text, parse_constant=lambda _value: (_ for _ in ()).throw(DocumentRejected("JSON_NUMBER")))
            parser = {"name": "python-json", "version": "1"}
    elif kind == "docx":
        from defusedxml.ElementTree import fromstring  # type: ignore[import-untyped]

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 128 or sum(member.file_size for member in members) > MAX_DECOMPRESSED:
                raise DocumentRejected("DECOMPRESSION_LIMIT")
            for member in members:
                parts = member.filename.replace("\\", "/").split("/")
                if (member.flag_bits & 1 or member.filename.startswith("/") or ".." in parts
                        or member.file_size > MAX_DECOMPRESSED or member.file_size > 200 * max(member.compress_size, 1)
                        or (member.external_attr >> 16) & 0o170000 == 0o120000
                        or member.filename.lower().endswith(("vbaproject.bin", ".exe"))):
                    raise DocumentRejected("UNSAFE_ARCHIVE")
            if "word/document.xml" not in archive.namelist() or "[Content_Types].xml" not in archive.namelist():
                raise DocumentRejected("NOT_DOCX")
            with archive.open("word/document.xml") as source:
                xml = source.read(MAX_DECOMPRESSED + 1)
            if len(xml) > MAX_DECOMPRESSED:
                raise DocumentRejected("DECOMPRESSION_LIMIT")
            root = fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
            text = "\n".join("".join(node.itertext()) for node in root.iter()
                             if node.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
        parser = {"name": "docx-defusedxml", "version": version("defusedxml")}
    elif kind == "pdf":
        from pypdf import PdfReader, apply_configuration

        if not content.startswith(b"%PDF-"):
            raise DocumentRejected("NOT_PDF")
        with apply_configuration(
            maximum_declared_stream_length=MAX_DECOMPRESSED, zlib_maximum_output_length=MAX_DECOMPRESSED,
            lzw_maximum_output_length=MAX_DECOMPRESSED, run_length_maximum_output_length=MAX_DECOMPRESSED,
            array_based_stream_maximum_output_length=MAX_DECOMPRESSED,
            stream_decoding_work_maximum_length=MAX_DECOMPRESSED, stream_parsing_work_maximum_count=100000,
            page_tree_maximum_entries=256, page_tree_maximum_depth=16, page_tree_maximum_page_entries=512,
            array_maximum_element_count=10000, dictionary_maximum_element_count=10000,
            xform_maximum_invocations_per_extraction=100, jbig2dec_binary=None,
        ):
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise DocumentRejected("ENCRYPTED_PDF")
            pages = len(reader.pages)
            if pages > MAX_PAGES:
                raise DocumentRejected("PAGE_LIMIT")
            parts, decoded = [], 0
            for page in reader.pages:
                stream = page.get_contents()
                decoded += len(stream.get_data()) if stream else 0
                if decoded > MAX_DECOMPRESSED:
                    raise DocumentRejected("DECOMPRESSION_LIMIT")
                parts.append(page.extract_text() or "")
                if sum(map(len, parts)) > MAX_TEXT:
                    break
            text = "\n".join(parts)
        parser = {"name": "pypdf", "version": version("pypdf")}
    else:
        raise DocumentRejected("UNSUPPORTED_TYPE")
    text = "".join(char for char in text if char in "\n\r\t" or ord(char) >= 32)
    truncated = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    return {"extracted_text": text, "text_truncated": truncated, "page_count": pages, "parser": parser,
            "extraction_status": "TRUNCATED" if truncated else "EXTRACTED" if text.strip() else "NO_TEXT"}


def main() -> None:
    # macOS does not enforce address-space limits reliably; the parent monitors this child's RSS there.
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    logging.disable(logging.CRITICAL)
    try:
        result = extract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])
    except ImportError:
        result = {"error": "PARSER_UNAVAILABLE"}
    except Exception:  # noqa: BLE001 - untrusted parser failures expose no file/provider/exception text.
        result = {"error": "DOCUMENT_REJECTED"}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
