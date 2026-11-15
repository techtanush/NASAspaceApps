"""A valid hash-shaped filename cannot trigger an unbounded projection read."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.db.store import PersistenceError


def test_exact_budget_read_is_verified_and_tamper_is_rejected(tmp_path: Path) -> None:
    cas = ContentAddressedStore(tmp_path)
    blob = cas.put_bytes(b"12345678")
    assert cas.read_limited(blob.sha256, 8) == b"12345678"
    cas.path(blob.sha256).write_bytes(b"12345679")
    with pytest.raises(PersistenceError, match="integrity") as exc:
        cas.read_limited(blob.sha256, 8)
    assert exc.value.code == "SOURCE_CHECKSUM_MISMATCH"


def test_sparse_oversized_replacement_rejected_before_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cas = ContentAddressedStore(tmp_path)
    blob = cas.put_bytes(b"small")
    with cas.path(blob.sha256).open("wb") as f:
        f.truncate(2**30)
    original = os.fdopen

    class NoRead:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        def __enter__(self) -> NoRead:
            return self

        def __exit__(self, *args: Any) -> None:
            self.stream.close()

        def fileno(self) -> int:
            return int(self.stream.fileno())

        def read(self, size: int) -> bytes:
            raise AssertionError("Oversized artifact reached content read")

    monkeypatch.setattr(os, "fdopen", lambda *a, **kw: NoRead(original(*a, **kw)))
    with pytest.raises(PersistenceError) as exc:
        cas.read_limited(blob.sha256, 1024)
    assert exc.value.code == "RESOURCE_LIMIT"


def test_bounded_read_detects_growth_even_after_file_stat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cas = ContentAddressedStore(tmp_path)
    blob = cas.put_bytes(b"abc")
    original = os.fstat

    def grow(fd: int) -> os.stat_result:
        before = original(fd)
        cas.path(blob.sha256).write_bytes(b"abcdef")
        return before

    monkeypatch.setattr(os, "fstat", grow)
    with pytest.raises(PersistenceError) as exc:
        cas.read_limited(blob.sha256, 4)
    assert exc.value.code == "RESOURCE_LIMIT"


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_read_budget_must_be_explicit_positive_integer(tmp_path: Path, budget: Any) -> None:
    cas = ContentAddressedStore(tmp_path)
    with pytest.raises(ValueError):
        cas.read_limited("a" * 64, budget)


def test_symlink_and_missing_artifacts_are_safe_errors(tmp_path: Path) -> None:
    cas = ContentAddressedStore(tmp_path / "cas")
    blob = cas.put_bytes(b"safe")
    target = cas.path(blob.sha256)
    target.unlink()
    outside = tmp_path / "private"
    outside.write_bytes(b"secret")
    target.symlink_to(outside)
    with pytest.raises(PersistenceError) as exc:
        cas.read_limited(blob.sha256, 1024)
    assert exc.value.code == "SOURCE_CONTENT_INVALID"
    target.unlink()
    with pytest.raises(PersistenceError) as exc:
        cas.read_limited(blob.sha256, 1024)
    assert exc.value.code == "SOURCE_UNAVAILABLE"


@pytest.mark.timeout(3)
def test_fifo_replacement_is_rejected_without_waiting_for_writer(tmp_path: Path) -> None:
    cas = ContentAddressedStore(tmp_path)
    blob = cas.put_bytes(b"safe")
    target = cas.path(blob.sha256)
    target.unlink()
    os.mkfifo(target)
    with pytest.raises(PersistenceError) as exc:
        cas.read_limited(blob.sha256, 1024)
    assert exc.value.code == "SOURCE_CONTENT_INVALID"
