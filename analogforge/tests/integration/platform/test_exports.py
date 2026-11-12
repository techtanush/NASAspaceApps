from __future__ import annotations

import csv
import hashlib
import io
import json
from contextlib import contextmanager

import pytest
import rfc8785

from analogforge.application.exports import load_renderer, validate_rendered
from analogforge.application.passports import assemble_bundle
from analogforge.db.store import PersistenceError
from analogforge.ports.hashing import bytes_sha256
from tests.integration.platform.test_passport_assembly import passport_case
from tests.support.factories import renderer_factory


def test_platform_passes_frozen_export_time_to_renderer():
    """Exercise the actual export handoff, independently of renderer internals."""
    from analogforge.application.exports import export_passport

    bundle = assemble_bundle(passport_case())
    evidence = {str(row.id): row.model_dump(mode="json") for row in bundle.evidence_appendix}

    class StopAfterCapture(Exception):
        """The boundary is the subject; no rendition publication is needed here."""

    class StoreView:
        @contextmanager
        def transaction(self, workspace_id):
            yield self

        def require(self, kind, identifier):
            if kind == "passports":
                return {"bundle": bundle.model_dump(mode="json")}
            return evidence[str(identifier)]

        def list(self, kind, filters):
            return [{}] if kind == "artifacts" else []

    class Blobs:
        def read(self, digest):
            return b"authorized test-only artifact"

    class CaptureRenderer:
        renderer_version = renderer_factory().renderer_version

        def render(self, received, assets, fmt):
            assert received.generated_at == bundle.generated_at
            assert received.model_dump(mode="json") == bundle.model_dump(mode="json")
            raise StopAfterCapture()

    with pytest.raises(StopAfterCapture):
        export_passport(
            StoreView(), bundle.passport.workspace_id, bundle.passport.id, Blobs(), CaptureRenderer(), formats=("json",)
        )


@pytest.mark.parametrize("fmt", ["html", "json", "csv"])
def test_renderer_seam_has_exact_deterministic_bytes_and_separate_file_digest(fmt):
    bundle = assemble_bundle(passport_case())
    renderer = renderer_factory()
    first = renderer.render(bundle, [], fmt)
    second = renderer.render(bundle, [], fmt)
    validate_rendered(bundle, first, fmt, renderer.renderer_version)
    assert first.content == second.content
    assert first.sha256 == bytes_sha256(first.content)
    assert first.sha256 != bundle.manifest_sha256
    assert bundle.manifest_sha256.encode() in first.content
    assert b"synthetic" in first.content
    if fmt == "json":
        parsed = json.loads(first.content)
        assert hashlib.sha256(rfc8785.dumps(parsed["canonical_manifest"])).hexdigest() == parsed["manifest_sha256"]
    elif fmt == "csv":
        from analogforge.ports.passport_renderer import CSV_COLUMNS

        table = csv.DictReader(io.StringIO(first.content.decode()))
        assert table.fieldnames == list(CSV_COLUMNS)
        rows = list(table)
        assert len(rows) == 1
        assert rows[0]["qualification_status"] == "FAIL"
    else:
        assert b'<script src="http' not in first.content
        assert b'<img src="http' not in first.content


@pytest.mark.parametrize(
    "change", [{"sha256": "0" * 64}, {"format": "html"}, {"renderer_version": "other"}, {"filename": "unrelated.json"}]
)
def test_platform_rejects_renderer_digest_format_identity_or_version_drift(change):
    bundle = assemble_bundle(passport_case())
    renderer = renderer_factory()
    result = renderer.render(bundle, [], "json")
    with pytest.raises(PersistenceError):
        validate_rendered(bundle, result.model_copy(update=change), "json", renderer.renderer_version)


def test_production_loader_never_falls_back_to_fake(monkeypatch):
    def missing(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("analogforge.application.exports.importlib.import_module", missing)
    with pytest.raises(PersistenceError) as error:
        load_renderer()
    assert error.value.code == "RENDERER_MISSING"


def test_explicit_real_factory_never_falls_back(monkeypatch):
    monkeypatch.setenv("AF_RENDERER_IMPL", "real")

    def missing(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("tests.support.factories.importlib.import_module", missing)
    with pytest.raises(RuntimeError, match="RENDERER_MISSING"):
        renderer_factory()
