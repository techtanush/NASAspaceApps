"""Operator dataset intake, validation, and immutable source-policy locking."""

from __future__ import annotations

import importlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import yaml

from analogforge.ports.datasets import DatasetManifest
from analogforge.ports.hashing import canonical_sha256, file_sha256
from analogforge.ports.science import (
    LocalScienceContext,
    ScienceComputationResult,
    ScienceOperation,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import IngestLocalDatasetInput, IngestLocalDatasetPayload
from analogforge.settings import Settings


class DatasetError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _entrypoint(module: str, name: str) -> Any:
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError) as exc:
        raise DatasetError(
            "SCIENCE_FACADE_MISSING", f"Required science entry point {module}:{name} is missing"
        ) from exc


def incoming_dir(settings: Settings) -> Path:
    return settings.data_root / "incoming"


def dataset_dir(settings: Settings, dataset_id: str) -> Path:
    if not dataset_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in dataset_id):
        raise DatasetError("DATASET_ID_INVALID", "Dataset id must use lowercase letters, digits, and hyphens")
    return incoming_dir(settings) / dataset_id


def load_manifest(settings: Settings, dataset_id: str) -> DatasetManifest:
    path = dataset_dir(settings, dataset_id) / "manifest.yaml"
    try:
        manifest = DatasetManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except Exception as exc:
        raise DatasetError(
            "MANIFEST_INVALID", f"Manifest for {dataset_id} is missing or invalid ({type(exc).__name__})"
        ) from exc
    if manifest.dataset_id != dataset_id:
        raise DatasetError("MANIFEST_INVALID", "Manifest dataset_id does not match its directory")
    if manifest.provider.upper().startswith("TEST_HARNESS") and not (
        settings.test_hooks and settings.allow_test_harness_provider and settings.auth_mode == "local"
    ):
        raise DatasetError("MODE_MISMATCH", "TEST_HARNESS data requires both explicit local test hooks")
    return manifest


def list_datasets(settings: Settings) -> list[dict[str, Any]]:
    root = incoming_dir(settings)
    if not root.exists():
        return []
    items = []
    for path in sorted(root.iterdir()):
        if path.is_dir() and not path.is_symlink():
            state = _validation_path(settings, path.name)
            validation = json.loads(state.read_text(encoding="utf-8")) if state.exists() else None
            items.append(
                {
                    "dataset_id": path.name,
                    "manifest_present": (path / "manifest.yaml").is_file(),
                    "validation": validation,
                }
            )
    return items


def scaffold_dataset(settings: Settings, dataset_id: str, body: str, role: str) -> dict[str, Any]:
    if body not in {"EARTH", "MOON", "MARS"}:
        raise DatasetError("BODY_INVALID", "body must be EARTH, MOON, or MARS")
    target = dataset_dir(settings, dataset_id)
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = target / "manifest.yaml"
    if manifest_path.exists():
        raise DatasetError("MANIFEST_EXISTS", f"{manifest_path} already exists")
    draft = _entrypoint("analogforge.science.datasets.inspect", "draft_manifest")(target, body, role)
    draft["dataset_id"] = dataset_id
    manifest_path.write_text(yaml.safe_dump(draft, sort_keys=False), encoding="utf-8")
    return {"dataset_id": dataset_id, "manifest_path": str(manifest_path), "status": "DRAFT"}


def _validation_path(settings: Settings, dataset_id: str) -> Path:
    return settings.data_root / "validation" / f"{dataset_id}.json"


def _safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise DatasetError("SOURCE_CONTENT_INVALID", f"Dataset file escapes directory: {relative}")
    if not path.is_file():
        raise DatasetError("SOURCE_UNAVAILABLE", f"Dataset file missing: {relative}")
    return path


def validate_dataset(settings: Settings, dataset_id: str, write_checksums: bool = False) -> dict[str, Any]:
    manifest = load_manifest(settings, dataset_id)
    root = dataset_dir(settings, dataset_id)
    manifest_data = manifest.model_dump(mode="json", exclude_none=True)
    for index, item in enumerate(manifest.files):
        path = _safe_file(root, item.path)
        if path.stat().st_size > settings.max_download_bytes:
            raise DatasetError("SOURCE_CONTENT_INVALID", f"Dataset file exceeds MAX_DOWNLOAD_BYTES: {item.path}")
        digest = file_sha256(path)
        if item.sha256 and item.sha256 != digest:
            raise DatasetError("SOURCE_CHECKSUM_MISMATCH", f"Dataset file hash mismatch: {item.path}")
        if write_checksums:
            manifest_data["files"][index]["sha256"] = digest
    if write_checksums:
        (root / "manifest.yaml").write_text(yaml.safe_dump(manifest_data, sort_keys=False), encoding="utf-8")
        manifest = DatasetManifest.model_validate(manifest_data)
    service = _entrypoint("analogforge.science.facade", "create_science_service")()
    if ScienceOperation.INGEST_LOCAL_DATASET not in service.supported_operations():
        raise DatasetError("SCIENCE_OPERATION_MISSING", "Science facade lacks INGEST_LOCAL_DATASET")
    scratch = settings.data_root / "scratch" / f"validate-{uuid4()}"
    context = LocalScienceContext(
        scratch=scratch,
        workspace_id=uuid4(),
        job_id=uuid4(),
        mode="synthetic" if manifest.is_synthetic else "live",
        dataset_roots={dataset_id: root},
    )
    policy = SourcePolicy(
        policy_id=f"validate-{dataset_id}", policy_sha256="0" * 64, local_dataset_ids=[dataset_id], allow_network=False
    )
    request = ScienceRequest(
        request_id=uuid4(),
        operation=ScienceOperation.INGEST_LOCAL_DATASET,
        mode=context.mode,
        inputs=IngestLocalDatasetInput(manifest=manifest),
        source_policy=policy,
    )
    result = service.execute(request, context)
    if not isinstance(result, ScienceComputationResult):
        raise DatasetError("MODEL_OUTPUT_INVALID", "Science facade returned a non-conforming result")
    if (
        result.request_id != request.request_id
        or result.operation != request.operation
        or result.mode != request.mode
        or result.input_sha256 != canonical_sha256(request)
    ):
        raise DatasetError("MODEL_OUTPUT_INVALID", "Science validation result does not match the request")
    payload = result.payload
    if not isinstance(payload, IngestLocalDatasetPayload):
        raise DatasetError(
            "DATASET_VALIDATION_FAILED", f"Science returned {result.status} without an INGEST_LOCAL_DATASET payload"
        )
    if payload.dataset_id != manifest.dataset_id or payload.body != manifest.body or payload.role != manifest.role:
        raise DatasetError("MODEL_OUTPUT_INVALID", "Science validation payload disagrees with the manifest")
    checks = [check.model_dump(mode="json") for check in payload.checks]
    passed = result.status in {"SUCCEEDED", "LIMITED"} and all(c["status"] != "FAIL" for c in checks)
    report = {
        "dataset_id": dataset_id,
        "status": "PASS" if passed else "FAIL",
        "usable_for_quantitative_claims": payload.usable_for_quantitative_claims,
        "manifest_sha256": canonical_sha256(manifest),
        "checks": checks,
    }
    target = _validation_path(settings, dataset_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def lock_path(settings: Settings, policy_id: str) -> Path:
    if not policy_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in policy_id):
        raise DatasetError("POLICY_ID_INVALID", "Policy id must be lowercase letters, digits, and hyphens")
    return settings.data_root / "locks" / f"{policy_id}.json"


def read_lock(settings: Settings, policy_id: str, verify_files: bool = True) -> dict[str, Any]:
    path = lock_path(settings, policy_id)
    if not path.is_file():
        raise DatasetError("DATASET_LOCK_MISSING", f"Source-policy lock {policy_id} is missing")
    lock = json.loads(path.read_text(encoding="utf-8"))
    digest = lock.pop("policy_sha256", None)
    if digest != canonical_sha256(lock):
        raise DatasetError("SOURCE_CHECKSUM_MISMATCH", f"Source-policy lock {policy_id} was modified")
    lock["policy_sha256"] = digest
    if verify_files:
        for entry in lock["datasets"]:
            manifest = load_manifest(settings, entry["dataset_id"])
            if canonical_sha256(manifest) != entry["manifest_sha256"]:
                raise DatasetError("SOURCE_CHECKSUM_MISMATCH", f"Manifest changed: {entry['dataset_id']}")
            for file in entry["files"]:
                actual = _safe_file(dataset_dir(settings, entry["dataset_id"]), file["path"])
                if actual.stat().st_size != file["size_bytes"] or file_sha256(actual) != file["sha256"]:
                    raise DatasetError(
                        "SOURCE_CHECKSUM_MISMATCH", f"Dataset bytes changed: {entry['dataset_id']}/{file['path']}"
                    )
    return cast(dict[str, Any], lock)


def _enable_local_practice(settings: Settings, policy_id: str, entries: list[dict[str, Any]]) -> None:
    if policy_id != "local-practice-policy-v1":
        return
    expected = {
        ("practice-mars-target-v1", "TARGET_TERRAIN", "MARS"),
        ("practice-earth-grid-v1", "EARTH_TERRAIN", "EARTH"),
        ("practice-earth-minerals-v1", "EARTH_MINERAL", "EARTH"),
    }
    actual = {(entry["dataset_id"], entry["role"], entry["body"]) for entry in entries}
    if expected <= actual and all(
        entry["usable_for_quantitative_claims"]
        for entry in entries
        if (entry["dataset_id"], entry["role"], entry["body"]) in expected
    ):
        from analogforge.application.capabilities import get_scenarios, save_scenarios

        scenarios = get_scenarios(settings)
        scenarios["local-dataset-practice-v1"]["status"] = "AVAILABLE"
        save_scenarios(settings, scenarios)


def create_lock(settings: Settings, policy_id: str, dataset_ids: list[str]) -> dict[str, Any]:
    path = lock_path(settings, policy_id)
    if path.exists():
        existing = read_lock(settings, policy_id)
        if {entry["dataset_id"] for entry in existing["datasets"]} == set(dataset_ids):
            _enable_local_practice(settings, policy_id, existing["datasets"])
            return existing
        raise DatasetError("DATASET_LOCK_EXISTS", "Policy id already names an immutable lock")
    entries = []
    for dataset_id in sorted(set(dataset_ids)):
        manifest = load_manifest(settings, dataset_id)
        state_path = _validation_path(settings, dataset_id)
        if not state_path.exists():
            raise DatasetError("DATASET_NOT_VALIDATED", f"Validate {dataset_id} before locking")
        report = json.loads(state_path.read_text(encoding="utf-8"))
        if report["status"] != "PASS" or report["manifest_sha256"] != canonical_sha256(manifest):
            raise DatasetError("DATASET_NOT_VALIDATED", f"Validation is failing or stale for {dataset_id}")
        files = []
        for item in manifest.files:
            file = _safe_file(dataset_dir(settings, dataset_id), item.path)
            digest = file_sha256(file)
            if item.sha256 and item.sha256 != digest:
                raise DatasetError("SOURCE_CHECKSUM_MISMATCH", f"Dataset file hash mismatch: {item.path}")
            files.append({"path": item.path, "sha256": digest, "size_bytes": file.stat().st_size})
        entries.append(
            {
                "dataset_id": dataset_id,
                "role": manifest.role,
                "body": manifest.body,
                "manifest_sha256": canonical_sha256(manifest),
                "files": files,
                "validation": report["status"],
                "usable_for_quantitative_claims": report["usable_for_quantitative_claims"],
            }
        )
    lock = {
        "schema_version": "1.0",
        "policy_id": policy_id,
        "created_at": datetime.now(UTC).isoformat(),
        "allow_network": False,
        "datasets": entries,
    }
    lock["policy_sha256"] = canonical_sha256(lock)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        json.dump(lock, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)
    _enable_local_practice(settings, policy_id, entries)
    return lock


def generate_practice(settings: Settings) -> list[str]:
    incoming_dir(settings).mkdir(parents=True, exist_ok=True)
    return cast(list[str], _entrypoint("analogforge.science.fixtures.practice", "generate_all")(incoming_dir(settings)))


def generate_mock_nasa_drop(settings: Settings) -> list[str]:
    incoming_dir(settings).mkdir(parents=True, exist_ok=True)
    return cast(
        list[str], _entrypoint("analogforge.science.fixtures.mock_nasa_drop", "generate")(incoming_dir(settings))
    )
