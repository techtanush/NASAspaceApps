"""Artifact bytes are stable, bounded and never trusted merely because of a filename."""

import hashlib
from pathlib import Path

import pytest

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.db.store import PersistenceError


def test_content_store_rehashes_deduplicates_and_detects_tamper(tmp_path: Path) -> None:
    cas = ContentAddressedStore(tmp_path)
    first = cas.put_bytes(b"measured data", "application/json")
    second = cas.put_bytes(b"measured data", "application/json")
    assert first == second
    assert first.sha256 == hashlib.sha256(b"measured data").hexdigest()
    assert cas.read(first.sha256) == b"measured data"
    assert len(list((tmp_path / "blobs").rglob(first.sha256))) == 1
    assert not list((tmp_path / "tmp").iterdir())
    cas.path(first.sha256).write_bytes(b"different")
    with pytest.raises(PersistenceError) as error:
        cas.read(first.sha256)
    assert error.value.code == "SOURCE_CHECKSUM_MISMATCH"
    with pytest.raises(PersistenceError):
        cas.put_bytes(b"measured data")


def test_content_store_rejects_path_escape_symlink_and_size(tmp_path: Path) -> None:
    cas = ContentAddressedStore(tmp_path / "store", max_bytes=3)
    with pytest.raises(PersistenceError):
        cas.path("../../outside")
    with pytest.raises(PersistenceError) as error:
        cas.put_bytes(b"four")
    assert error.value.code == "RESOURCE_LIMIT"
    outside = tmp_path / "outside"
    outside.write_bytes(b"ok")
    link = tmp_path / "link"
    link.symlink_to(outside)
    with pytest.raises(PersistenceError):
        cas.put_file(link, "application/json")
    with pytest.raises(PersistenceError):
        cas.put_file(outside, "application/json", expected_sha256="a" * 64)
    with pytest.raises(PersistenceError):
        cas.put_file(outside, "application/json", expected_size=3)
    assert cas.put_file(outside, "application/json", expected_size=2).size_bytes == 2


def test_parent_symlink_cannot_redirect_blob_writes(tmp_path: Path) -> None:
    cas = ContentAddressedStore(tmp_path / "store")
    value = b"safe"
    digest = hashlib.sha256(value).hexdigest()
    external = tmp_path / "external"
    external.mkdir()
    (cas.root / "blobs" / digest[:2]).symlink_to(external, target_is_directory=True)
    with pytest.raises(PersistenceError):
        cas.put_bytes(value)
    assert not list(external.iterdir())
