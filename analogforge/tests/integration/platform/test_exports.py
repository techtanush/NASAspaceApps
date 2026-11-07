from __future__ import annotations

import csv
import io
import json

import pytest

from analogforge.application.exports import load_renderer, validate_rendered
from analogforge.application.passports import assemble_bundle
from analogforge.db.store import PersistenceError
from analogforge.ports.hashing import bytes_sha256, canonical_json_bytes
from tests.integration.platform.test_passport_assembly import passport_case
from tests.support.factories import renderer_factory


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
        assert bytes_sha256(canonical_json_bytes(parsed["canonical_manifest"])) == parsed["manifest_sha256"]
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
