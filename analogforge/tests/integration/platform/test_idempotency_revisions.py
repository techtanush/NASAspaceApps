"""PLT-03: replayed commands and stale revisions have transactional semantics."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from analogforge.db.store import IdempotencyConflict, RevisionConflict, Store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.mark.db
def test_idempotency_hash_and_original_response(platform_store: Store) -> None:
    workspace, _ = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        assert unit.idempotency_begin("user", "POST", "/runs", "command", "a" * 64) is None
        unit.idempotency_complete("user", "POST", "/runs", "command", 202, {"id": "original"})
    with platform_store.transaction(workspace) as unit:
        assert unit.idempotency_begin("user", "POST", "/runs", "command", "a" * 64) == (202, {"id": "original"})
    with pytest.raises(IdempotencyConflict):
        with platform_store.transaction(workspace) as unit:
            unit.idempotency_begin("user", "POST", "/runs", "command", "b" * 64)


@pytest.mark.db
def test_cas_rejects_stale_revision_and_concurrent_writer(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)

    def change() -> str:
        try:
            with platform_store.transaction(workspace) as unit:
                unit.replace("runs", run["id"], {**run, "state": "CHARACTERIZING"}, expected_revision=1)
            return "updated"
        except RevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: change(), range(2))) == ["conflict", "updated"]
    with platform_store.transaction(workspace) as unit:
        assert unit.require("runs", run["id"])["revision"] == 2


@pytest.mark.db
def test_idempotency_concurrent_duplicate_mutates_once(platform_store: Store) -> None:
    workspace, _ = seed_run(platform_store)
    key = str(uuid4())

    def command() -> dict[str, str]:
        with platform_store.transaction(workspace) as unit:
            cached = unit.idempotency_begin("user", "POST", "/missions", key, "c" * 64)
            if cached:
                return cached[1]
            row = unit.create("missions", {"name": key})
            response = {"id": row["id"]}
            unit.idempotency_complete("user", "POST", "/missions", key, 201, response)
            return response

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: command(), range(2)))
    assert results[0] == results[1]
    with platform_store.transaction(workspace) as unit:
        assert len(unit.list("missions", {"name": key})) == 1
