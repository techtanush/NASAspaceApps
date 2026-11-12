"""Worker context cannot read unregistered or changed bytes after a run is accepted."""

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.db.store import PersistenceError
from analogforge.jobs.context import WorkerScienceContext


def test_worker_artifact_context_authorization_and_rehash(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest()
    context = WorkerScienceContext(
        scratch=tmp_path / "scratch", workspace_id=uuid4(), job_id=uuid4(), artifact_paths={digest: artifact}
    )
    assert context.read_artifact(digest) == artifact
    with pytest.raises(PersistenceError):
        context.read_artifact("f" * 64)
    artifact.write_bytes(b"changed")
    with pytest.raises(PersistenceError) as error:
        context.read_artifact(digest)
    assert error.value.code == "SOURCE_CHECKSUM_MISMATCH"


def test_worker_dataset_context_enforces_lock_and_prevents_escape(tmp_path: Path) -> None:
    dataset = tmp_path / "incoming" / "source"
    dataset.mkdir(parents=True)
    path = dataset / "tile.tif"
    path.write_bytes(b"raster")
    digest = hashlib.sha256(b"raster").hexdigest()
    context = WorkerScienceContext(
        scratch=tmp_path / "scratch",
        workspace_id=uuid4(),
        job_id=uuid4(),
        dataset_roots={"source": dataset},
        dataset_checksums={"source": {"tile.tif": digest}},
    )
    assert context.local_dataset_root("source") == dataset
    path.write_bytes(b"different raster")
    with pytest.raises(PersistenceError) as error:
        context.local_dataset_root("source")
    assert error.value.code == "SOURCE_CHECKSUM_MISMATCH"
    context.dataset_checksums["source"] = {"../escape": digest}
    with pytest.raises(PersistenceError) as error:
        context.local_dataset_root("source")
    assert error.value.code == "SOURCE_CONTENT_INVALID"
