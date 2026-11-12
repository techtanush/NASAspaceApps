"""PLT-04: repository isolation remains effective even for the DB-owner connection."""

from uuid import uuid4

import pytest

from analogforge.db.store import NotFound, PersistenceError, Store
from tests.integration.platform.test_migrations import platform_store, seed_run

__all__ = ["platform_store"]


@pytest.mark.db
def test_workspace_get_and_lists_never_leak(platform_store: Store) -> None:
    first, run = seed_run(platform_store)
    second, other = seed_run(platform_store)
    with platform_store.transaction(second) as unit:
        assert unit.get("runs", run["id"]) is None
        assert [row["id"] for row in unit.list("runs")] == [other["id"]]
        with pytest.raises(NotFound):
            unit.create("evidence", {"run_id": run["id"], "mode": "synthetic", "kind": "DERIVED"})
        with pytest.raises(NotFound):
            unit.create("missions", {"workspace_id": first, "name": "Foreign"})


@pytest.mark.db
def test_cross_workspace_and_mode_edges_and_assurance_rejected(platform_store: Store) -> None:
    first, run = seed_run(platform_store)
    second, other = seed_run(platform_store)
    with platform_store.transaction(first) as unit:
        evidence = unit.create(
            "evidence",
            {"run_id": run["id"], "mode": "synthetic", "kind": "DERIVED", "algorithm_id": "scientific-assurance"},
        )
    with pytest.raises(NotFound):
        with platform_store.transaction(second) as unit:
            unit.create(
                "passports",
                {
                    "run_id": other["id"],
                    "mode": "synthetic",
                    "manifest_sha256": "a" * 64,
                    "assurance_evidence_id": evidence["id"],
                    "evidence_ids": [evidence["id"]],
                },
            )
    with pytest.raises(PersistenceError, match="integrity"):
        with platform_store.transaction(second) as unit:
            own = unit.create("evidence", {"run_id": other["id"], "kind": "DERIVED"})
            unit.create(
                "evidence_edges",
                {
                    "run_id": other["id"],
                    "mode": "synthetic",
                    "parent_evidence_id": evidence["id"],
                    "child_evidence_id": own["id"],
                    "relation": "DERIVED_FROM",
                },
            )
    with pytest.raises(PersistenceError, match="mode"):
        with platform_store.transaction(first) as unit:
            unit.create("evidence", {"id": str(uuid4()), "run_id": run["id"], "mode": "live", "kind": "SOURCE"})


@pytest.mark.db
def test_lineage_dag_is_enforced_in_database(platform_store: Store) -> None:
    workspace, run = seed_run(platform_store)
    with platform_store.transaction(workspace) as unit:
        parent = unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED"})
        child = unit.create("evidence", {"run_id": run["id"], "kind": "DERIVED"})
        unit.create(
            "evidence_edges",
            {
                "run_id": run["id"],
                "parent_evidence_id": parent["id"],
                "child_evidence_id": child["id"],
                "relation": "DERIVED_FROM",
            },
        )
    with pytest.raises(PersistenceError, match="integrity"):
        with platform_store.transaction(workspace) as unit:
            unit.create(
                "evidence_edges",
                {
                    "run_id": run["id"],
                    "parent_evidence_id": child["id"],
                    "child_evidence_id": parent["id"],
                    "relation": "DERIVED_FROM",
                },
            )
