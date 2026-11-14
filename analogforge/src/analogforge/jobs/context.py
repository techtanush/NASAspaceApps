"""Picklable worker context checks every authorized artifact/dataset access against pinned bytes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from analogforge.db.store import PersistenceError
from analogforge.ports.science import LocalScienceContext


def _hash_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise PersistenceError("SOURCE_UNAVAILABLE", "Pinned source file is unavailable")
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


@dataclass
class WorkerScienceContext(LocalScienceContext):
    dataset_checksums: dict[str, dict[str, str]] = field(default_factory=dict)

    def read_artifact(self, sha256: str) -> Path:
        self.check_cancelled()
        if sha256 not in self.artifact_paths:
            raise PersistenceError("NOT_FOUND", "Artifact is not authorized for this operation")
        path = self.artifact_paths[sha256]
        if _hash_file(path) != sha256:
            raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Pinned artifact digest changed")
        return path

    def local_dataset_root(self, dataset_id: str) -> Path:
        self.check_cancelled()
        if dataset_id not in self.dataset_roots or dataset_id not in self.dataset_checksums:
            raise PersistenceError("NOT_FOUND", "Dataset is not authorized by the accepted source lock")
        if not self.dataset_checksums[dataset_id]:
            raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Dataset lock has no pinned file digests")
        root = self.dataset_roots[dataset_id].resolve()
        for relative, expected in self.dataset_checksums[dataset_id].items():
            candidate = root / relative
            if not candidate.resolve().is_relative_to(root) or candidate.is_symlink():
                raise PersistenceError("SOURCE_CONTENT_INVALID", "Dataset path escapes its authorized root")
            if _hash_file(candidate) != expected:
                raise PersistenceError("SOURCE_CHECKSUM_MISMATCH", "Dataset bytes changed after the source lock")
        return root
