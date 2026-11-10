"""Dataset roots and source-policy locks (architecture 36 sections 1, 3 and 7).

Everything here is read-only with respect to ``data/incoming``: the registry resolves and lists dataset
directories, loads ``manifest.yaml`` and **builds** (never writes) the lock object.  Persisting a lock under
``data/locks`` is the operator CLI's job; :func:`lock_to_bytes` returns the canonical bytes for it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import Field

from analogforge.ports.common import PortModel
from analogforge.ports.hashing import canonical_json_bytes, canonical_sha256, file_sha256
from analogforge.science.datasets.checks import TODO_MARKER
from analogforge.science.datasets.ingest import DatasetUnreadableError, IngestResult
from analogforge.science.errors import ScienceError

DATASET_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
MANIFEST_NAME: Final = "manifest.yaml"
MAX_MANIFEST_BYTES: Final = 1_048_576
LOCK_SCHEMA_VERSION: Final = "1.0"


class RegistryError(ScienceError):
    code = "INPUT_INVALID"


def validate_dataset_id(dataset_id: str) -> str:
    if DATASET_ID_PATTERN.fullmatch(dataset_id) is None:
        raise RegistryError(f"dataset_id {dataset_id!r} does not match {DATASET_ID_PATTERN.pattern}")
    return dataset_id


def resolve_dataset_dir(incoming_root: Path, dataset_id: str) -> Path:
    """``incoming_root/dataset_id`` after validating the id and refusing symlinked escapes."""
    validate_dataset_id(dataset_id)
    candidate = incoming_root / dataset_id
    if not candidate.is_dir():
        raise DatasetUnreadableError(f"dataset {dataset_id!r} is not a directory under the incoming root")
    if incoming_root.resolve() not in candidate.resolve().parents:
        raise RegistryError(f"dataset {dataset_id!r} resolves outside the incoming root")
    return candidate


def list_dataset_ids(incoming_root: Path) -> list[str]:
    """Sorted ids of valid dataset directories (invalid names are ignored, never guessed)."""
    if not incoming_root.is_dir():
        return []
    return sorted(
        p.name for p in incoming_root.iterdir() if p.is_dir() and DATASET_ID_PATTERN.fullmatch(p.name) is not None
    )


def load_manifest_file(dataset_dir: Path) -> dict[str, Any]:
    """Parse ``manifest.yaml`` with ``yaml.safe_load`` (no tags, no code); raises if unreadable or not a mapping."""
    path = dataset_dir / MANIFEST_NAME
    try:
        size = path.stat().st_size
        if size > MAX_MANIFEST_BYTES:
            raise DatasetUnreadableError(f"{MANIFEST_NAME} is {size} bytes (limit {MAX_MANIFEST_BYTES})")
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DatasetUnreadableError(f"{MANIFEST_NAME} cannot be read: {type(exc).__name__}") from exc
    if not isinstance(loaded, dict):
        raise DatasetUnreadableError(f"{MANIFEST_NAME} is not a YAML mapping")
    return {str(k): v for k, v in loaded.items()}


@dataclass(frozen=True)
class DatasetRegistry:
    """Read-only view of ``data/incoming`` (``incoming_root``) and its locks directory."""

    incoming_root: Path
    locks_root: Path

    def ids(self) -> list[str]:
        return list_dataset_ids(self.incoming_root)

    def dataset_dir(self, dataset_id: str) -> Path:
        return resolve_dataset_dir(self.incoming_root, dataset_id)

    def manifest(self, dataset_id: str) -> dict[str, Any]:
        return load_manifest_file(self.dataset_dir(dataset_id))

    def lock_path(self, policy_id: str) -> Path:
        validate_dataset_id(policy_id)
        return self.locks_root / f"{policy_id}.json"

    def is_inside_incoming(self, path: Path) -> bool:
        return self.incoming_root.resolve() in path.resolve().parents or path.resolve() == self.incoming_root.resolve()


def assert_scratch_write_allowed(target: Path, scratch_dir: Path, incoming_root: Path | None = None) -> Path:
    """Writes are allowed only below ``scratch_dir`` and never below ``incoming_root``."""
    resolved = target.resolve()
    if scratch_dir.resolve() not in resolved.parents:
        raise RegistryError("writes are only allowed under the scratch directory")
    if incoming_root is not None and (incoming_root.resolve() in resolved.parents):
        raise RegistryError("data/incoming is read-only")
    return resolved


# ----------------------------------------------------------------------------------------------- locks
class LockedFile(PortModel):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)


class LockedDataset(PortModel):
    dataset_id: str
    role: str
    body: Literal["EARTH", "MOON", "MARS"]
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    files: list[LockedFile]
    validation: Literal["PASS", "WARN"]
    usable_for_quantitative_claims: bool
    is_synthetic: bool


class SourcePolicyLock(PortModel):
    schema_version: Literal["1.0"] = "1.0"
    policy_id: str
    policy_sha256: str | None
    created_at: str
    allow_network: bool = False
    datasets: list[LockedDataset]


def lock_entry(result: IngestResult, dataset_dir: Path) -> LockedDataset:
    """Lock entry for a validated dataset; refuses any dataset with a FAIL check or without a manifest."""
    if result.manifest is None or result.manifest_sha256 is None or result.payload is None:
        raise RegistryError("cannot lock a dataset whose manifest is invalid")
    if result.failed:
        raise RegistryError("cannot lock: failed checks " + ", ".join(result.failed))
    files = [
        LockedFile(path=name, sha256=digest, size_bytes=(dataset_dir / name).stat().st_size)
        for name, digest in sorted(result.file_hashes.items())
    ]
    warned = any(c.status == "WARN" for c in result.checks)
    return LockedDataset(
        dataset_id=result.manifest.dataset_id,
        role=result.manifest.role,
        body=result.manifest.body,
        manifest_sha256=result.manifest_sha256,
        files=files,
        validation="WARN" if warned else "PASS",
        usable_for_quantitative_claims=result.usable_for_quantitative_claims,
        is_synthetic=result.manifest.is_synthetic,
    )


def build_lock(
    policy_id: str, created_at: str, entries: Sequence[LockedDataset], *, allow_network: bool = False
) -> SourcePolicyLock:
    """Lock with ``policy_sha256 = canonical_sha256`` of the object without that key; entries sorted by id."""
    validate_dataset_id(policy_id)
    ordered = sorted(entries, key=lambda e: e.dataset_id)
    unsigned = SourcePolicyLock(
        policy_id=policy_id, policy_sha256=None, created_at=created_at, allow_network=allow_network, datasets=ordered
    )
    digest = canonical_sha256(unsigned.model_dump(mode="json", exclude={"policy_sha256"}))
    return unsigned.model_copy(update={"policy_sha256": digest})


def lock_is_consistent(lock: SourcePolicyLock) -> bool:
    return lock.policy_sha256 == canonical_sha256(lock.model_dump(mode="json", exclude={"policy_sha256"}))


def lock_to_bytes(lock: SourcePolicyLock) -> bytes:
    return canonical_json_bytes(lock)


@dataclass(frozen=True)
class LockMismatch:
    dataset_id: str
    path: str
    reason: str  # SOURCE_CHECKSUM_MISMATCH | MISSING


def verify_lock_integrity(lock: SourcePolicyLock, incoming_root: Path) -> list[LockMismatch]:
    """Re-hash every locked file (architecture 36 section 7); a non-empty result means SOURCE_CHECKSUM_MISMATCH."""
    problems: list[LockMismatch] = []
    for entry in lock.datasets:
        base = incoming_root / entry.dataset_id
        for f in entry.files:
            target = base / f.path
            if not target.is_file():
                problems.append(LockMismatch(entry.dataset_id, f.path, "MISSING"))
            elif file_sha256(target) != f.sha256:
                problems.append(LockMismatch(entry.dataset_id, f.path, "SOURCE_CHECKSUM_MISMATCH"))
    return problems


def has_unfilled_fields(manifest: Mapping[str, Any]) -> list[str]:
    """Top-level manifest keys whose value still contains the draft placeholder."""
    return sorted(k for k, v in manifest.items() if isinstance(v, str) and TODO_MARKER in v)


__all__ = [
    "DATASET_ID_PATTERN",
    "DatasetRegistry",
    "LockMismatch",
    "LockedDataset",
    "LockedFile",
    "RegistryError",
    "SourcePolicyLock",
    "assert_scratch_write_allowed",
    "build_lock",
    "has_unfilled_fields",
    "list_dataset_ids",
    "load_manifest_file",
    "lock_entry",
    "lock_is_consistent",
    "lock_to_bytes",
    "resolve_dataset_dir",
    "validate_dataset_id",
    "verify_lock_integrity",
]
