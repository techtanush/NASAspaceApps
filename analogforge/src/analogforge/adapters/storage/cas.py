"""Fsync then atomic rename; a content hash is identity, never authorization."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from analogforge.db.store import PersistenceError


@dataclass(frozen=True)
class Blob:
    sha256: str
    size_bytes: int
    media_type: str
    relative_path: str


class ContentAddressedStore:
    def __init__(self, root: str | Path, max_bytes: int = 2147483648) -> None:
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes
        for directory in (self.root / "tmp", self.root / "blobs"):
            if directory.is_symlink():
                raise PersistenceError("SOURCE_CONTENT_INVALID", "Storage directories cannot be symlinks")
            directory.mkdir(parents=True, exist_ok=True)

    def path(self, sha256: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{64}", sha256) is None:
            raise PersistenceError("SOURCE_CONTENT_INVALID", "Invalid artifact digest")
        target = self.root / "blobs" / sha256[:2] / sha256
        if target.is_symlink() or not target.resolve().is_relative_to(self.root / "blobs"):
            raise PersistenceError("SOURCE_CONTENT_INVALID", "Artifact path is unsafe")
        return target

    def put(self, content: bytes, media_type: str = "application/octet-stream") -> Blob:
        return self.put_bytes(content, media_type)

    def put_bytes(self, content: bytes, media_type: str = "application/octet-stream") -> Blob:
        if len(content) > self.max_bytes:
            raise PersistenceError("RESOURCE_LIMIT", "Artifact exceeds storage byte budget")
        digest = hashlib.sha256(content).hexdigest()
        destination = self.path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.root / "tmp", suffix=".part", delete=False) as handle:
            temp_path = Path(handle.name)
            try:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                if destination.exists():
                    self.read(digest)
                    temp_path.unlink()
                else:
                    os.replace(temp_path, destination)
                    directory = os.open(destination.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
            finally:
                temp_path.unlink(missing_ok=True)
        return Blob(digest, len(content), media_type, destination.relative_to(self.root).as_posix())

    def put_file(
        self, path: Path, media_type: str, expected_sha256: str | None = None, expected_size: int | None = None
    ) -> Blob:
        if path.is_symlink() or not path.is_file():
            raise PersistenceError("SOURCE_CONTENT_INVALID", "Artifact must be a regular file")
        if path.stat().st_size > self.max_bytes:
            raise PersistenceError("RESOURCE_LIMIT", "Artifact exceeds storage byte budget")
        digest, size = hashlib.sha256(), 0
        with tempfile.NamedTemporaryFile(dir=self.root / "tmp", suffix=".part", delete=False) as handle:
            staged = Path(handle.name)
            try:
                with path.open("rb") as source:
                    while chunk := source.read(1048576):
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise PersistenceError("RESOURCE_LIMIT", "Artifact exceeds storage byte budget")
                        digest.update(chunk)
                        handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
                sha256 = digest.hexdigest()
                if expected_size is not None and size != expected_size:
                    raise PersistenceError("SOURCE_CONTENT_INVALID", "Artifact size differs from declared size")
                if expected_sha256 is not None and sha256 != expected_sha256:
                    raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Artifact digest differs from declared digest")
                destination = self.path(sha256)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    with destination.open("rb") as existing:
                        previous = hashlib.file_digest(existing, "sha256").hexdigest()
                    if previous != sha256:
                        raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Stored artifact integrity check failed")
                    staged.unlink()
                else:
                    os.replace(staged, destination)
                directory = os.open(destination.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
                return Blob(sha256, size, media_type, destination.relative_to(self.root).as_posix())
            finally:
                staged.unlink(missing_ok=True)

    def read(self, sha256: str) -> bytes:
        target = self.path(sha256)
        try:
            content = target.read_bytes()
        except FileNotFoundError as exc:
            raise PersistenceError("SOURCE_UNAVAILABLE", "Referenced artifact bytes are unavailable") from exc
        if hashlib.sha256(content).hexdigest() != sha256:
            raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Stored artifact integrity check failed")
        return content


CAS = ContentAddressedStore
