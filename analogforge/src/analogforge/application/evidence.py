"""Authorized lineage traversal over append-only evidence records."""

from typing import Any

from analogforge.application.registrar import Registrar


class EvidenceService:
    def __init__(self, store: Any, blob_store: Any) -> None:
        self.store = store
        self.registrar = Registrar(store, blob_store)

    def trace(self, workspace_id: str, evidence_id: str) -> list[dict[str, Any]]:
        with self.store.transaction(workspace_id) as tx:
            visited: set[str] = set()
            result: list[dict[str, Any]] = []

            def visit(identifier: str) -> None:
                if identifier in visited:
                    return
                row = tx.get("evidence", identifier)
                if row is None:
                    raise KeyError(identifier)
                visited.add(identifier)
                for parent in row["input_evidence_ids"]:
                    visit(str(parent))
                result.append(row)

            visit(evidence_id)
            return result
