"""Reversible model-only identifiers and tables; canonical inputs retain all commit authority."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, cast

from analogforge.agents.schemas.task import AgentTask

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_UUID_RE = re.compile(_UUID)
_DECODE = re.compile(r"~~|~[A-Za-z][0-9]+")
_COLUMNS = {
    "gates": ["gate_id", "outcome", "reason_ref", "evidence_ref"],
    "receipts": ["id", "tool_name", "status", "evidence_ids"],
    "evidence": ["local_key", "evidence_id"],
    "findings": ["finding_id", "rule_code", "severity", "message", "evidence_ids", "requirement_id", "required_repair"],
    "claims": ["claim_id", "claim_type", "requirement_id", "candidate_window_ids", "evidence_ids"],
    "claim_gates": ["gates", "claim_id"],
}
WIRE_INSTRUCTIONS = (
    "\nAliases: ~eN=evidence, ~rN=receipt, ~cN=claim, ~uN=UUID; ~~=literal ~. "
    "Use supplied aliases; restore before validation. reason_ref/evidence_ref index "
    "reason_catalog/evidence_catalog (zero-based); gate_id/outcome index gate_value_catalogs. "
    "Rows pair with *_columns; retain fields/nulls/order. "
    "Omitted prepared_submission=authoritative_submission. Value refs: audit_paths/"
    "_task_audit_ref=scientific_audit; task_paths/_task_value_ref=exact task value; table_paths/"
    "_wire_table=columns/rows. _tool_result_ref=full prior call_id result, not evidence. "
    "Review all outcomes/findings/UNKNOWNs/blockers. In submit_role_result, "
    'payload={"_task_payload_ref":"authoritative_submission.payload"} reuses that reviewed exact payload. '
    "Choose disposition/summary/issues/evidence_ids/next_action; or explicit payload. "
    "Summary: one short sentence under 160 characters, no aliases/IDs; cite evidence_ids. "
    "Schema errors are not evidence gaps or new approvals."
    " Read only missing facts."
)


class UnknownWireAlias(ValueError):
    def __init__(self) -> None:
        super().__init__("UNKNOWN_WIRE_ALIAS")


def _rows(value: Any, columns: list[str]) -> bool:
    return isinstance(value, list) and all(isinstance(row, dict) and set(row) == set(columns) for row in value)


def _compact_columns(wire: dict[str, Any]) -> None:
    payload, used = wire["payload"], []
    audit = payload.get("scientific_audit")
    contract = payload.get("contract_context")
    if isinstance(contract, dict) and "requirement_columns" not in contract:
        rows = contract.get("requirements")
        columns = list(rows[0]) if isinstance(rows, list) and len(rows) > 1 and isinstance(rows[0], dict) else []
        if columns and isinstance(rows, list) and _rows(rows, columns):
            contract["requirement_columns"] = columns
            contract["requirements"] = [[row[key] for key in columns] for row in rows]
            used.append("contract_requirements")
    profile = payload.get("target_profile_context")
    if isinstance(profile, dict):
        metrics = profile.get("metrics")
        detail = profile.get("payload")
        if isinstance(metrics, list) and isinstance(detail, dict) and detail.get("metrics") == metrics:
            detail.pop("metrics")
            used.append("target_profile_metrics_copy")
        columns = list(metrics[0]) if isinstance(metrics, list) and metrics and isinstance(metrics[0], dict) else []
        if columns and isinstance(metrics, list) and "metric_columns" not in profile and _rows(metrics, columns):
            profile["metric_columns"] = columns
            profile["metrics"] = [[row[key] for key in columns] for row in metrics]
            used.append("target_profile_metrics")
    if ("authoritative_claim_columns" not in payload
            and _rows(payload.get("authoritative_claims"), _COLUMNS["claims"])):
        payload["authoritative_claim_columns"] = _COLUMNS["claims"][:]
        payload["authoritative_claims"] = [[row[key] for key in _COLUMNS["claims"]]
                                            for row in payload["authoritative_claims"]]
        used.append("claims")
    if "receipt_columns" not in payload and _rows(payload.get("receipt_summaries"), _COLUMNS["receipts"]):
        payload["receipt_columns"] = _COLUMNS["receipts"][:]
        payload["receipt_summaries"] = [[row[key] for key in _COLUMNS["receipts"]]
                                        for row in payload["receipt_summaries"]]
        used.append("receipts")
    if isinstance(audit, dict):
        claims = audit.get("claim_gates")
        if ("gate_columns" not in audit and isinstance(claims, list)
                and all(isinstance(row, dict) and _rows(row.get("gates"), _COLUMNS["gates"]) for row in claims)):
            audit["gate_columns"] = _COLUMNS["gates"][:]
            for row in claims:
                row["gates"] = [[gate[key] for key in _COLUMNS["gates"]] for gate in row["gates"]]
            used.append("gates")
            gates = [gate for row in claims for gate in row["gates"]]
            if ("gate_value_catalogs" not in audit
                    and all(isinstance(gate[index], str) for gate in gates for index in (0, 1))):
                catalogs = {}
                for index, field in enumerate(("gate_id", "outcome")):
                    values = list(dict.fromkeys(gate[index] for gate in gates))
                    catalogs[field] = values
                    for gate in gates:
                        gate[index] = values.index(gate[index])
                audit["gate_value_catalogs"] = catalogs
                used.append("gate_values")
        groups = audit.get("evidence_catalog")
        if ("evidence_columns" not in audit and isinstance(groups, list)
                and all(_rows(group, _COLUMNS["evidence"]) for group in groups)):
            audit["evidence_columns"] = _COLUMNS["evidence"][:]
            audit["evidence_catalog"] = [[[row[key] for key in _COLUMNS["evidence"]] for row in group]
                                         for group in groups]
            used.append("evidence")
        if "finding_columns" not in audit and _rows(audit.get("findings"), _COLUMNS["findings"]):
            audit["finding_columns"] = _COLUMNS["findings"][:]
            audit["findings"] = [[row[key] for key in _COLUMNS["findings"]] for row in audit["findings"]]
            used.append("findings")
        if ("claim_gate_columns" not in audit and isinstance(claims, list)
                and _rows(claims, _COLUMNS["claim_gates"])):
            audit["claim_gate_columns"] = _COLUMNS["claim_gates"][:]
            audit["claim_gates"] = [[row[key] for key in _COLUMNS["claim_gates"]] for row in claims]
            used.append("claim_gates")
    if used:
        wire.setdefault("_wire_encoding", {})["columns_v1"] = used


def expand_wire_columns(wire: dict[str, Any]) -> dict[str, Any]:
    """Pure JSON inverse, also usable by local protocol fixtures without any private ID map."""
    result = deepcopy(wire)
    payload = result["payload"]
    used = result.get("_wire_encoding", {}).pop("columns_v1", [])
    audit = payload.get("scientific_audit", {})
    if "contract_requirements" in used:
        contract = payload["contract_context"]
        columns = contract.pop("requirement_columns")
        contract["requirements"] = [dict(zip(columns, row, strict=True)) for row in contract["requirements"]]
    if "target_profile_metrics" in used:
        profile = payload["target_profile_context"]
        columns = profile.pop("metric_columns")
        profile["metrics"] = [dict(zip(columns, row, strict=True)) for row in profile["metrics"]]
    if "target_profile_metrics_copy" in used:
        profile = payload["target_profile_context"]
        profile["payload"]["metrics"] = deepcopy(profile["metrics"])
    if "claims" in used:
        columns = payload.pop("authoritative_claim_columns")
        payload["authoritative_claims"] = [dict(zip(columns, row, strict=True))
                                           for row in payload["authoritative_claims"]]
    if "claim_gates" in used:
        columns = audit.pop("claim_gate_columns")
        audit["claim_gates"] = [dict(zip(columns, row, strict=True)) for row in audit["claim_gates"]]
    if "gate_values" in used:
        catalogs = audit.pop("gate_value_catalogs")
        for row in audit["claim_gates"]:
            for gate in row["gates"]:
                for field, values in catalogs.items():
                    index = audit["gate_columns"].index(field)
                    gate[index] = values[gate[index]]
    if "receipts" in used:
        columns = payload.pop("receipt_columns")
        payload["receipt_summaries"] = [dict(zip(columns, row, strict=True)) for row in payload["receipt_summaries"]]
    if "gates" in used:
        columns = audit.pop("gate_columns")
        for claim in audit["claim_gates"]:
            claim["gates"] = [dict(zip(columns, row, strict=True)) for row in claim["gates"]]
    if "evidence" in used:
        columns = audit.pop("evidence_columns")
        audit["evidence_catalog"] = [[dict(zip(columns, row, strict=True)) for row in group]
                                     for group in audit["evidence_catalog"]]
    if "findings" in used:
        columns = audit.pop("finding_columns")
        audit["findings"] = [dict(zip(columns, row, strict=True)) for row in audit["findings"]]
    if result.get("_wire_encoding") == {}:
        result.pop("_wire_encoding")
    return result


def _prune_definitions(schema: dict[str, Any]) -> None:
    def references(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                found.add(ref[8:].replace("~1", "/").replace("~0", "~"))
            for key, item in value.items():
                if key != "$defs":
                    found.update(references(item))
        elif isinstance(value, list):
            for item in value:
                found.update(references(item))
        return found

    definitions = schema.get("$defs", {})
    reachable = references(schema)
    pending = list(reachable)
    while pending:
        for key in references(definitions[pending.pop()]) - reachable:
            reachable.add(key)
            pending.append(key)
    if definitions:
        schema["$defs"] = {key: value for key, value in definitions.items() if key in reachable}


class WireCodec:
    def __init__(self, task: AgentTask, receipt_ids: Sequence[str]) -> None:
        self.aliases: dict[str, str] = {}
        self.canonical: dict[str, str] = {}
        self.counts = dict.fromkeys("ercu", 0)
        self.audit = deepcopy(task.payload.get("scientific_audit"))
        self.task_document = task.model_dump(mode="json")
        self.task_values: dict[str, tuple[list[str], Any]] = {}
        self.results: dict[str, Any] = {}
        self.result_ids: dict[str, str] = {}
        values = [([key], value) for key, value in self.task_document.items() if key != "payload"]
        values.extend((["payload", key], value) for key, value in self.task_document["payload"].items()
                      if key != "prepared_submission" or "authoritative_submission" not in task.payload)
        for path, value in values:
            key = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            if len(key) >= 256:
                self.task_values.setdefault(key, (path, deepcopy(value)))
        for identifier in sorted(map(str, task.input_evidence_ids)):
            self._alias(identifier, "e")
        for identifier in sorted(set(receipt_ids)):
            self._alias(identifier, "r")
        for claim in sorted(task.payload.get("authoritative_claims", []), key=lambda row: row["claim_id"]):
            identifier = claim["claim_id"]
            self._alias(identifier, "u" if _UUID_RE.fullmatch(identifier) else "c")
        for identifier in sorted(set(_UUID_RE.findall(json.dumps(task.model_dump(mode="json"))))):
            self._alias(identifier, "u")
        claims = [r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])" for value in self.aliases
                  if value and not _UUID_RE.fullmatch(value)]
        self.pattern = re.compile("|".join([*sorted(claims, key=len, reverse=True), _UUID, "~"]))

    def _alias(self, identifier: str, kind: str = "u") -> str:
        if identifier not in self.aliases:
            self.counts[kind] += 1
            alias = f"~{kind}{self.counts[kind]}"
            self.aliases[identifier] = alias
            self.canonical[alias] = identifier
        return self.aliases[identifier]

    def encode(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {self.encode(key): self.encode(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(self.encode(item) for item in value)
        if isinstance(value, str):
            if value in self.aliases:
                return self.aliases[value]
            return self.pattern.sub(lambda match: "~~" if match[0] == "~" else self._alias(match[0]), value)
        return value

    def decode(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {self.decode(key): self.decode(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(self.decode(item) for item in value)
        if isinstance(value, str):
            def restore(match: re.Match[str]) -> str:
                if match[0] == "~~":
                    return "~"
                if match[0] not in self.canonical:
                    raise UnknownWireAlias()
                return self.canonical[match[0]]
            return _DECODE.sub(restore, value)
        return value

    def task(self, wire: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(wire)
        _compact_columns(result)
        return cast(dict[str, Any], self.encode(result))

    def schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(schema)
        def rewrite(value: Any) -> None:
            if isinstance(value, dict):
                for key in ("enum", "const", "description"):
                    if key in value:
                        value[key] = self.encode(value[key])
                if value.get("format") == "uuid":
                    value.pop("format")
                    if "enum" not in value:
                        value.pop("type", None)
                        value["anyOf"] = [{"type": "string", "format": "uuid"},
                                          {"type": "string", "pattern": r"^~[eru][1-9][0-9]*$"}]
                        return
                for item in value.values():
                    rewrite(item)
            elif isinstance(value, list):
                for item in value:
                    rewrite(item)
        rewrite(result)
        _prune_definitions(result)
        return result

    def submission_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Permit one exact task-bound payload reference; canonical validation remains mandatory."""
        result = deepcopy(schema)
        # Ask for concise prose before generation; never truncate a returned assessment.
        # The canonical 800-character bound still applies after alias restoration.
        summary = result.get("properties", {}).get("summary")
        if isinstance(summary, dict):
            summary["maxLength"] = min(summary.get("maxLength", 800), 160)
            summary["description"] = "One short outcome sentence. No IDs or aliases; use evidence_ids and issues."
        expected = self.task_document["payload"].get("authoritative_submission", {}).get("payload")
        if isinstance(expected, dict):
            result["properties"]["payload"] = {"anyOf": [result["properties"]["payload"], {
                "type": "object", "additionalProperties": False,
                "properties": {"_task_payload_ref": {"type": "string", "enum": ["authoritative_submission.payload"]}},
                "required": ["_task_payload_ref"],
            }]}
        return self.schema(result)

    def submission(self, value: Any) -> Any:
        result = self.decode(value)
        if isinstance(result, dict) and isinstance(result.get("payload"), dict):
            payload = result["payload"]
            if "_task_payload_ref" in payload:
                expected = self.task_document["payload"].get("authoritative_submission", {}).get("payload")
                if (payload != {"_task_payload_ref": "authoritative_submission.payload"}
                        or not isinstance(expected, dict)):
                    raise ValueError("Invalid task payload reference")
                result["payload"] = deepcopy(expected)
        return result

    def result(self, canonical_result: Any, *, call_id: str | None = None) -> dict[str, Any]:
        key = json.dumps(canonical_result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        prior = self.result_ids.get(key) if call_id is not None else None
        if call_id is not None and prior is not None and canonical_result == self.results[prior]:
            self.results[call_id] = deepcopy(canonical_result)
            return {"value": {"_tool_result_ref": prior}, "audit_paths": [], "result_ref": prior}
        paths: list[list[str | int]] = []
        task_paths: list[dict[str, Any]] = []
        table_paths: list[list[str | int]] = []

        def project(value: Any, path: list[str | int]) -> Any:
            if self.audit is not None and value == self.audit:
                paths.append(path)
                return {"_task_audit_ref": True}
            serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            reference = self.task_values.get(serialized)
            if reference is not None and value == reference[1]:
                task_paths.append({"path": path, "task_path": reference[0]})
                return {"_task_value_ref": reference[0]}
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(row, dict) for row in value):
                columns = list(value[0])
                if all(set(row) == set(columns) for row in value):
                    rows = [[row[column] for column in columns] for row in value]
                    compact = {"_wire_table": {"columns": columns, "rows": rows}}
                    if len(json.dumps(compact, separators=(",", ":"))) + 64 < len(serialized):
                        table_paths.append(path)
                        return {"_wire_table": {"columns": columns, "rows": [
                            [project(cell, [*path, index, column]) for column, cell in zip(columns, row, strict=True)]
                            for index, row in enumerate(rows)
                        ]}}
            if isinstance(value, dict):
                return {key: project(item, [*path, key]) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return type(value)(project(item, [*path, index]) for index, item in enumerate(value))
            return value
        result = {"value": self.encode(project(canonical_result, [])), "audit_paths": self.encode(paths)}
        if task_paths:
            result["task_paths"] = self.encode(task_paths)
        if table_paths:
            result["table_paths"] = self.encode(table_paths)
        if call_id is not None:
            self.results[call_id] = deepcopy(canonical_result)
            self.result_ids.setdefault(key, call_id)
        return result

    def expand_result(self, wire: dict[str, Any]) -> Any:
        if "result_ref" in wire:
            return deepcopy(self.results[wire["result_ref"]])
        paths = {tuple(path) for path in self.decode(wire["audit_paths"])}
        task_paths = {tuple(item["path"]): item["task_path"] for item in self.decode(wire.get("task_paths", []))}
        table_paths = {tuple(path) for path in self.decode(wire.get("table_paths", []))}

        def restore(value: Any, path: tuple[str | int, ...]) -> Any:
            if path in paths:
                return deepcopy(self.audit)
            if path in task_paths:
                source: Any = self.task_document
                for key in task_paths[path]:
                    source = source[key]
                return deepcopy(source)
            if path in table_paths:
                table = value["_wire_table"]
                value = [dict(zip(table["columns"], row, strict=True)) for row in table["rows"]]
            if isinstance(value, dict):
                return {key: restore(item, (*path, key)) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return type(value)(restore(item, (*path, index)) for index, item in enumerate(value))
            return value
        return restore(self.decode(deepcopy(wire["value"])), ())
