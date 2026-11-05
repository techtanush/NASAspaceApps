#!/usr/bin/env python3
"""Rebuild generated kit files from the authoritative architecture contracts.

Run ONLY when a recorded contract change (architecture 35 section 8) modifies
contracts/domain.schema.json, contracts/openapi.yaml, the assurance schema or a port model.
Branch agents never run this during a one-shot build; they run materialize.py.

Outputs (under kit/files/contracts/):
  openapi.bundled.json            OpenAPI 3.1 with every domain $ref inlined into components
  domain.schema.json, scientific-assurance.schema.json, scientific-gates.json, error-codes.json
  route-artifact.schema.json, telemetry-artifact.schema.json, constraints-artifact.schema.json,
  dataset-manifest.schema.json, passport-export-bundle.schema.json  (generated from port models)
Then rewrites kit/kit-manifest.json with the SHA-256 of every file under kit/files/.

Usage: python3 "architecture files/contracts/kit/tools/build_kit.py"   (needs pydantic, rfc8785)
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
CONTRACTS = KIT.parent
FILES = KIT / "files"
OUT = FILES / "contracts"


def rewrite_refs(node, domain_names: set[str]):
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                if value.startswith("./domain.schema.json#/$defs/"):
                    value = "#/components/schemas/" + value.rsplit("/", 1)[1]
                elif value.startswith("#/$defs/"):
                    value = "#/components/schemas/" + value.rsplit("/", 1)[1]
                if value.startswith("#/components/schemas/"):
                    name = value.rsplit("/", 1)[1]
                    if name not in domain_names and not name:
                        raise SystemExit(f"unresolvable ref {value}")
            out[key] = rewrite_refs(value, domain_names)
        return out
    if isinstance(node, list):
        return [rewrite_refs(v, domain_names) for v in node]
    return node


def bundle_openapi() -> dict:
    domain = json.loads((CONTRACTS / "domain.schema.json").read_text())
    api = json.loads((CONTRACTS / "openapi.yaml").read_text())
    names = set(domain["$defs"])
    bundled = copy.deepcopy(api)
    schemas = bundled["components"]["schemas"]
    for name, schema in domain["$defs"].items():
        existing = schemas.get(name)
        if existing is None or existing == {"$ref": f"./domain.schema.json#/$defs/{name}"}:
            schemas[name] = rewrite_refs(schema, names)
    bundled = rewrite_refs(bundled, names | set(schemas))
    text = json.dumps(bundled)
    if "domain.schema.json" in text:
        raise SystemExit("bundling left an external domain.schema.json reference")
    for ref in {seg.split('"')[0] for seg in text.split('"$ref": "')[1:]}:
        if not ref.startswith("#/components/"):
            raise SystemExit(f"unexpected ref {ref}")
        kind, name = ref.split("/")[2], ref.split("/")[3]
        if name not in bundled["components"].get(kind, {}):
            raise SystemExit(f"dangling ref {ref}")
    bundled["info"]["description"] = (
        "BUNDLED single source of truth (architecture 35). Backend serves this document and contract tests "
        "enforce conformance; the frontend generates its client from it. " + api["info"].get("description", "")
    )
    return bundled


def port_schemas() -> dict[str, dict]:
    sys.path.insert(0, str(FILES / "src"))
    from analogforge.ports.datasets import DatasetManifest
    from analogforge.ports.passport_renderer import PassportExportBundle
    from analogforge.ports.science_payloads import ConstraintsArtifact, RouteArtifact, TelemetryArtifact

    return {
        "route-artifact.schema.json": RouteArtifact.model_json_schema(),
        "telemetry-artifact.schema.json": TelemetryArtifact.model_json_schema(),
        "constraints-artifact.schema.json": ConstraintsArtifact.model_json_schema(),
        "dataset-manifest.schema.json": DatasetManifest.model_json_schema(),
        "passport-export-bundle.schema.json": PassportExportBundle.model_json_schema(mode="serialization"),
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "openapi.bundled.json", bundle_openapi())
    for name in ["domain.schema.json", "scientific-assurance.schema.json", "scientific-gates.json", "error-codes.json"]:
        shutil.copyfile(CONTRACTS / name, OUT / name)
    sys.path.insert(0, str(FILES / "src"))
    from analogforge.ports import catalog

    write_json(OUT / "algorithm-ids.json", {"schema_version": "1.0", "algorithm_ids": dict(catalog.ALGORITHM_IDS),
                                            "constraint_ids_note": "see analogforge.ports.catalog"})
    for name, schema in port_schemas().items():
        schema["$comment"] = "Generated from analogforge.ports models by kit/tools/build_kit.py. Do not edit."
        write_json(OUT / name, schema)
    manifest = {
        "kit_version": "1.0.0",
        "note": "SHA-256 of every kit file. materialize.py --verify compares analogforge/<path> against these.",
        "editable_sections": {"pyproject.toml": ["extra-tanush", "extra-ayan", "extra-aradhya"]},
        "files": {},
    }
    for path in sorted(FILES.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            rel = path.relative_to(FILES).as_posix()
            manifest["files"][rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(KIT / "kit-manifest.json", manifest)
    print(f"kit rebuilt: {len(manifest['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
