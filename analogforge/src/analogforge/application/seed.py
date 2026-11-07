"""Offline, idempotent local workspace seed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from analogforge.ports import catalog
from analogforge.ports.hashing import canonical_sha256
from analogforge.settings import Settings

SEED_WORKSPACE_ID = UUID("11111111-1111-4111-8111-111111111111")
SEED_USER_ID = UUID("22222222-2222-4222-8222-222222222222")


def _write_synthetic_lock(settings: Settings) -> Path:
    path = settings.data_root / "locks" / f"{catalog.DATASET_LOCK_SYNTHETIC}.json"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "policy_id": catalog.DATASET_LOCK_SYNTHETIC,
        "created_at": "2026-11-05T00:00:00Z",
        "allow_network": False,
        "datasets": [],
        "synthetic_fixture_ids": [
            catalog.FIXTURE_MARS_TARGET,
            catalog.FIXTURE_MOON_TARGET,
            catalog.FIXTURE_EARTH_GRID,
            catalog.FIXTURE_CANONICAL_GRAPH,
        ],
    }
    payload["policy_sha256"] = canonical_sha256(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("Synthetic policy lock exists with different contents")
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def seed_synthetic(store: Any, settings: Settings) -> dict[str, Any]:
    path = _write_synthetic_lock(settings)
    presets = {
        group: [preset.name for preset in sorted((settings.config_dir / "presets" / group).glob("*.json"))]
        for group in ("missions", "rovers")
    }
    if not presets["missions"] or not presets["rovers"]:
        raise ValueError("Frozen mission and rover presets are missing")
    seeded: list[str] = []
    if store is not None:
        store.ensure_workspace(SEED_WORKSPACE_ID, "Local AnalogForge")
        with store.transaction(SEED_WORKSPACE_ID) as uow:
            records: list[tuple[str, str, dict[str, Any]]] = [
                (
                    "users",
                    str(SEED_USER_ID),
                    {
                        "id": str(SEED_USER_ID),
                        "workspace_id": str(SEED_WORKSPACE_ID),
                        "issuer": "local",
                        "subject": "local-operator",
                        "display_name": "Local operator",
                    },
                ),
                (
                    "workspace_memberships",
                    "33333333-3333-4333-8333-333333333333",
                    {
                        "id": "33333333-3333-4333-8333-333333333333",
                        "workspace_id": str(SEED_WORKSPACE_ID),
                        "user_id": str(SEED_USER_ID),
                        "role": "OWNER",
                    },
                ),
            ]
            for kind, record_id, doc in records:
                if uow.get(kind, record_id) is None:
                    uow.create(kind, doc)
                    seeded.append(f"{kind}/{record_id}")
    return {
        "status": "PASS",
        "workspace_id": str(SEED_WORKSPACE_ID),
        "dataset_lock_id": catalog.DATASET_LOCK_SYNTHETIC,
        "lock_path": str(path),
        "presets": presets,
        "created": seeded,
    }
