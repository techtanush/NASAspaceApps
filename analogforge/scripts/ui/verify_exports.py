"""Verify downloaded exports and separately published file/manifest digests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.passport_renderer import CSV_COLUMNS


def verify(content: bytes, fmt: str, file_sha256: str, manifest_sha256: str) -> None:
    if hashlib.sha256(content).hexdigest() != file_sha256:
        raise ValueError("Export file digest mismatch")
    if file_sha256 == manifest_sha256:
        raise ValueError("Export file digest must be distinct from the manifest digest")
    text = content.decode("utf-8")
    if fmt == "json":
        data = json.loads(text)
        if (
            data["manifest_sha256"] != manifest_sha256
            or canonical_sha256(data["canonical_manifest"]) != manifest_sha256
        ):
            raise ValueError("Canonical manifest digest mismatch")
        if "canonical_manifest_json" in data["bundle"]:
            raise ValueError("JSON bundle duplicates canonical manifest bytes")
    elif fmt == "csv":
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or tuple(rows[0]) != CSV_COLUMNS:
            raise ValueError("CSV columns differ from the frozen contract")
        for row in rows[1:]:
            if len(row) != len(CSV_COLUMNS) or row[-1] != manifest_sha256:
                raise ValueError("CSV row or manifest digest mismatch")
            if any(cell.startswith(("=", "+", "-", "@", "\t", "\r")) for cell in row):
                raise ValueError("Active spreadsheet formula prefix")
    elif fmt == "html":
        if manifest_sha256 not in text:
            raise ValueError("HTML lacks the manifest digest")
        if re.search(r"<script\b|(?:src|href)\s*=\s*[\"']https?://|url\(", text, re.IGNORECASE):
            raise ValueError("HTML contains executable or external resource content")
    else:
        raise ValueError("Unsupported export format")


def self_test() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "tests" / "unit"))
    from analogforge.rendering.passport import create_passport_renderer
    from passport_renderer.fixtures.builders import FIXTURE_NAMES, build_bundle

    count = 0
    renderer = create_passport_renderer()
    for name in FIXTURE_NAMES:
        bundle = build_bundle(name)
        for fmt in ("html", "json", "csv"):
            result = renderer.render(bundle, [], fmt)
            verify(result.content, fmt, result.sha256, bundle.manifest_sha256)
            try:
                verify(result.content + b"tampered", fmt, result.sha256, bundle.manifest_sha256)
            except ValueError:
                count += 1
            else:
                raise AssertionError("Tampered bytes were accepted")
    return {"status": "PASS", "exports_verified": count, "tamper_cases_rejected": count}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--format", choices=["html", "json", "csv"])
    parser.add_argument("--file-sha256")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
    elif args.file and args.format and args.file_sha256 and args.manifest_sha256:
        verify(args.file.read_bytes(), args.format, args.file_sha256, args.manifest_sha256)
        print(json.dumps({"status": "PASS", "file": str(args.file)}))
    else:
        parser.error("Provide a file, --format, --file-sha256 and --manifest-sha256, or --self-test")


if __name__ == "__main__":
    main()
