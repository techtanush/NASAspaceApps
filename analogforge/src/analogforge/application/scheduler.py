"""Durable, data-driven investigation orchestration over frozen science ports."""

from __future__ import annotations

import importlib
import json
import tempfile
import time
from contextlib import nullcontext
from contextvars import ContextVar
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import yaml

from analogforge.agents.runtime.invocation import validate_submission
from analogforge.agents.runtime.scripted_provider import ScriptedProvider, project_payload
from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.agents.schemas.task import AgentTask
from analogforge.application import compatibility, discovery, portfolios, qualification, verification
from analogforge.application.registrar import RegisteredResult, Registrar
from analogforge.domain.budgets import BudgetExceeded, BudgetLedger
from analogforge.domain.hashing_utils import content_hash
from analogforge.domain.ids import envelope, new_id, utc_now
from analogforge.domain.policy import PolicyViolation, evaluate_transition, validate_repair
from analogforge.domain.state_machine import TERMINAL, allowed_actions, validate_transition
from analogforge.domain.validators import validate_mission_content
from analogforge.jobs.context import WorkerScienceContext
from analogforge.ports import catalog
from analogforge.ports.domain_models import (
    AgentAction,
    AgentRoleResult,
    DisplayLayerManifest,
    MissionTestContract,
    PlanetaryTargetProfile,
    RoverProfile,
    ToolReceipt,
)
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import (
    EvidenceHandle,
    ScienceCancelled,
    ScienceComputationResult,
    ScienceOperation,
    ScienceOptions,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import (
    AnalyzeCandidateInput,
    AssessCompatibilityInput,
    AttemptSummary,
    AuditEvidenceInput,
    BuildDisplayLayersInput,
    CharacterizeTargetInput,
    ClaimScope,
    CompareRequirementInput,
    DesignBenchmarkInput,
    DiagnoseResultInput,
    IngestLocalDatasetInput,
    OptimizePortfolioInput,
    QualificationRowInput,
    ResolveCoverageInput,
    ScreenCandidatesInput,
    SearchRouteInput,
    VerificationSummary,
    VerifyRouteInput,
)
from analogforge.tools.registry import ToolContext, ToolRegistry
from analogforge.tools.science_tools import OPERATION_TO_TOOL


class WorkflowRolePaused(RuntimeError):
    def __init__(self, disposition: str, summary: str) -> None:
        super().__init__(summary)
        self.disposition = disposition


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _wire(model: Any, document: dict[str, Any]) -> Any:
    return model.model_validate({key: document[key] for key in model.model_fields if key in document})


class WorkflowEngine:
    def __init__(
        self, store: Any, settings: Any, science: Any = None, renderer: Any = None, blob_store: Any = None
    ) -> None:
        self.store = store
        self.settings = settings
        self.science = science
        self.renderer = renderer
        if blob_store is None:
            from analogforge.adapters.storage.cas import ContentAddressedStore

            blob_store = ContentAddressedStore(Path(settings.data_root) / "blobs")
        self.blobs = blob_store
        self.registrar = Registrar(store, blob_store)
        self._job_context: ContextVar[tuple[str | None, str | None]] = ContextVar(
            "workflow_job_context", default=(None, None)
        )

    def _provider_client(self) -> Any:
        from urllib.parse import urlsplit

        from analogforge.adapters.openai.client import ResponsesClient

        key = getattr(self.settings, "openai_api_key", None)
        if key is not None and hasattr(key, "get_secret_value"):
            key = key.get_secret_value()
        base_url = getattr(self.settings, "fake_openai_url", None)
        if base_url:
            if not (
                getattr(self.settings, "test_hooks", False)
                and getattr(self.settings, "auth_mode", None) == "local"
                and getattr(self.settings, "allow_test_harness_provider", False)
            ):
                raise WorkflowError("INPUT_INVALID", "Live fake-provider hook is not explicitly enabled")
            parsed = urlsplit(base_url)
            if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise WorkflowError("INPUT_INVALID", "Fake provider must use a local loopback origin")
        return ResponsesClient(key, getattr(self.settings, "openai_model", None), base_url=base_url)

    def _scenario(self, identifier: str) -> dict[str, Any]:
        path = Path(self.settings.config_dir) / "scenarios.yaml"
        data = yaml.safe_load(path.read_text())
        entries = data.get("scenarios", data)
        if isinstance(entries, list):
            match = next((e for e in entries if e.get("id") == identifier), None)
        else:
            match = entries.get(identifier)
        if match is None:
            raise WorkflowError("INPUT_INVALID", "Unknown scenario")
        return dict(match)

    def _load(self, run_id: str, workspace_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
        with self.store.transaction(workspace_id) as tx:
            run = tx.require("runs", run_id)
            mission = tx.require("mission_revisions", run["mission_revision_id"])
            acceptances = tx.list("mission_acceptances", {"mission_revision_id": mission["id"]})
            if acceptances:
                mission = {**mission, "accepted_at": acceptances[0].get("accepted_at", acceptances[0]["created_at"])}
            rover = tx.require("rover_revisions", run["rover_revision_id"]) if run.get("rover_revision_id") else None
        return run, mission, rover

    def _save_run(
        self,
        run_id: str,
        workspace_id: str,
        changes: dict[str, Any],
        *,
        event: str | None = None,
        job_id: str | None = None,
        lease_token: str | None = None,
        enqueue_next: bool = False,
        complete_job: bool = False,
    ) -> dict[str, Any]:
        context = (
            self.store.publication(workspace_id, job_id, lease_token)
            if job_id and lease_token
            else self.store.transaction(workspace_id)
        )
        with context as tx:
            run = tx.require("runs", run_id, lock=True)
            if run["state"] == "CANCELLED":
                raise ScienceCancelled()
            if "state" in changes:
                validate_transition(
                    run["state"], changes["state"], resume_state=run.get("runtime", {}).get("resume_state")
                )
            run.update(changes)
            tx.replace("runs", run_id, run, run["revision"])
            if event:
                tx.append_event(run_id, event, {"summary": changes.get("state", event)}, run["mode"])
            checkpoint = tx.require("runs", run_id)
            if enqueue_next:
                tx.enqueue(
                    "ADVANCE_RUN",
                    {"run_id": run_id, "state": checkpoint["state"]},
                    run_id=run_id,
                    input_hash=canonical_sha256([run_id, checkpoint["state"], checkpoint["revision"]]),
                )
            if complete_job and job_id is not None:
                job = tx.require("jobs", job_id)
                tx.replace("jobs", job_id, {**job, "state": "SUCCEEDED"})
            return cast(dict[str, Any], tx.require("runs", run_id))

    def _charge(self, run_id: str, workspace_id: str, key: str, amount: float = 1) -> None:
        with self.store.transaction(workspace_id) as tx:
            run = tx.require("runs", run_id, lock=True)
            ledger = BudgetLedger.from_document(run.get("runtime", {}).get("budget"))
            ledger.charge(key, amount)
            run.setdefault("runtime", {})["budget"] = ledger.document()
            tx.replace("runs", run_id, run, run["revision"])

    def prepare(
        self,
        mission: dict[str, Any],
        workspace_id: str,
        preparation_id: str | None = None,
        scenario_config_id: str | None = None,
        mode: str = "synthetic",
    ) -> dict[str, Any]:
        scenario_id = (
            scenario_config_id
            or mission.get("scenario_config_id")
            or (
                catalog.SCENARIO_MOON_GAP
                if mission.get("target", {}).get("body") == "MOON"
                else catalog.DEFAULT_SCENARIO
            )
        )
        scenario = self._scenario(scenario_id)
        preset_name = scenario["mission_preset"]
        preset_path = Path(self.settings.config_dir) / "presets" / "missions" / Path(preset_name).name
        if not preset_path.exists():
            raise WorkflowError("INPUT_INVALID", "Configured mission preset is missing")
        preset = json.loads(preset_path.read_text())
        if preset["target"]["body"] != mission["target"]["body"]:
            raise WorkflowError("INPUT_INVALID", "NEEDS_USER_REVIEW: target body differs from preset")
        if mode == "live":
            # Live drafting must be explicit; no scripted defaults can masquerade as live inference.

            if not getattr(self.settings, "openai_api_key", None) or not getattr(self.settings, "openai_model", None):
                raise WorkflowError("PROVIDER_AUTH_FAILED", "Live preparation requires configured provider")
            # Run preparation through strict structured output, then the same deterministic validator.
            client = self._provider_client()
            from analogforge.tools.registry import strict_schema

            schema = strict_schema(MissionTestContract.model_json_schema())
            response = client.create(
                input=json.dumps(
                    {
                        "instruction": (
                            "Propose a mission contract; preserve supplied objective and target, "
                            "mark assumptions proposed. No acceptance."
                        ),
                        "draft": mission,
                        "example_structure": preset,
                    }
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "proposed_mission_contract",
                        "strict": True,
                        "schema": schema,
                    }
                },
            )
            texts = [
                c["text"]
                for i in response.get("output", [])
                if i.get("type") == "message"
                for c in i.get("content", [])
                if c.get("type") == "output_text"
            ]
            if response.get("status") != "completed" or len(texts) != 1:
                raise WorkflowError(
                    "MODEL_OUTPUT_INVALID", "Preparation did not return one complete structured contract"
                )
            preset = _wire(MissionTestContract, json.loads(texts[0])).model_dump(mode="json")
        supplied_requirements = mission.get("requirements")
        requirements = (
            [{**row, "origin": row.get("origin", "USER")} for row in supplied_requirements]
            if supplied_requirements
            else [{**row, "origin": "PROPOSED_DEFAULT"} for row in preset["requirements"]]
        )
        result = {
            **preset,
            **{k: mission[k] for k in ("name", "objective", "target") if k in mission},
            "schema_version": "1.0",
            "id": new_id(),
            "mission_id": mission.get("mission_id", mission.get("id")),
            "workspace_id": workspace_id,
            "revision": mission.get("revision", 1),
            "created_at": utc_now(),
            "accepted_at": None,
            "requirements": requirements,
            "assumptions": mission.get("assumptions", [])
            if supplied_requirements
            else list(dict.fromkeys(preset.get("assumptions", []) + mission.get("assumptions", []))),
        }
        result["content_sha256"] = content_hash(result, "mission")
        issues = validate_mission_content(result)
        if any(i.severity == "ERROR" for i in issues):
            raise WorkflowError("INPUT_INVALID", "Proposed contract failed deterministic semantic validation")
        return cast(dict[str, Any], _wire(MissionTestContract, result).model_dump(mode="json"))

    def _source_policy(self, run: dict[str, Any], scenario: dict[str, Any]) -> SourcePolicy:
        from analogforge.application.datasets import read_lock

        lock = read_lock(self.settings, run["dataset_lock_id"])
        runtime = run.get("runtime", {})
        pinned = runtime.get("dataset_policy_sha256")
        if pinned is not None and pinned != lock["policy_sha256"]:
            raise WorkflowError("SOURCE_CHECKSUM_MISMATCH", "Run source-policy lock changed")
        if runtime.get("source_policy"):
            policy = SourcePolicy.model_validate(runtime["source_policy"])
            if policy.policy_sha256 != lock["policy_sha256"]:
                raise WorkflowError("SOURCE_CHECKSUM_MISMATCH", "Source-policy snapshot differs from lock bytes")
            return policy
        return SourcePolicy(
            policy_id=run["dataset_lock_id"],
            policy_sha256=lock["policy_sha256"],
            allowed_adapter_ids=["synthetic_practice", "local_dataset"],
            allowed_extents=[],
            local_dataset_ids=[entry["dataset_id"] for entry in lock["datasets"]],
            synthetic_fixture_ids=lock.get("synthetic_fixture_ids", []),
            allow_network=lock["allow_network"],
        )

    def _algorithm_lock(self) -> str:
        from analogforge.ports.hashing import file_sha256

        path = Path(self.settings.config_dir) / "algorithms.yaml"
        if path.exists():
            return canonical_sha256(yaml.safe_load(path.read_text()))
        if self.science is None:
            raise WorkflowError("SCIENCE_FACADE_MISSING", "Scientific algorithm configuration is unavailable")
        # Explicitly injected branch-isolation services pin their exact source bytes.
        import inspect

        source_file = inspect.getsourcefile(type(self.science))
        if source_file is None:
            raise WorkflowError("INPUT_INVALID", "Injected science service has no reproducible source")
        return canonical_sha256(
            {
                "scope": "explicit-injected-service",
                "module": type(self.science).__module__,
                "source_sha256": file_sha256(Path(source_file)),
            }
        )

    def _compute(
        self,
        inputs: Any,
        run_id: str,
        workspace_id: str,
        *,
        job_id: str | None = None,
        lease_token: str | None = None,
        publish: Any = None,
    ) -> RegisteredResult:
        run, _, _ = self._load(run_id, workspace_id)
        if run["state"] == "CANCELLED" or run.get("cancel_requested_at"):
            raise ScienceCancelled()
        scenario = self._scenario(run["scenario_config_id"])
        policy = self._source_policy(run, scenario)
        cache_key = canonical_sha256(
            {
                "operation": inputs.operation,
                "inputs": inputs.model_dump(mode="json"),
                "source_policy": policy.model_dump(mode="json"),
                "config_sha256": run["config_sha256"],
            }
        )
        self._charge(run_id, workspace_id, "tool_calls_per_run")
        with self.store.transaction(workspace_id) as tx:
            cached = tx.list("scientific_operations", {"run_id": run_id, "cache_key": cache_key})
            if cached:
                operation = cached[-1]
                receipt = tx.require("tool_receipts", operation["receipt_id"])
                for eid in operation["evidence_ids"]:
                    evidence = tx.require("evidence", eid)
                    if evidence.get("artifact_sha256"):
                        self.blobs.read(evidence["artifact_sha256"])
                return RegisteredResult(
                    operation["payload"],
                    tuple(operation["evidence_ids"]),
                    operation["artifact_hashes"],
                    operation["local_evidence_ids"],
                    {**receipt, "cache_hit": True},
                    operation["status"],
                    tuple(operation["issues"]),
                )
            if run["mode"] == "replay":
                raise WorkflowError(
                    "REPLAY_INTEGRITY_ERROR", "Replay has no checksummed recording for this computation"
                )
            evidence = [
                e for e in tx.list("evidence", {"run_id": run_id}) if e["algorithm_id"] != "scientific-assurance"
            ]
        for upstream in evidence:
            if upstream.get("artifact_sha256"):
                self.blobs.read(upstream["artifact_sha256"])
        handles = [
            EvidenceHandle.model_validate(
                {
                    "evidence_id": e["id"],
                    "kind": e["kind"],
                    "mode": e["mode"],
                    "body": e["body"],
                    "artifact_sha256": e.get("artifact_sha256"),
                    "artifact_media_type": e.get("artifact_media_type"),
                    "algorithm_id": e["algorithm_id"],
                    "algorithm_version": e["algorithm_version"],
                    "parameters_sha256": e["parameters_sha256"],
                    "native_resolution_m": e.get("native_resolution_m"),
                    "comparison_scale_m": e.get("comparison_scale_m"),
                    "metrics": e.get("metrics", []),
                    "limitations": e.get("limitations", []),
                }
            )
            for e in evidence
        ]
        limits = scenario.get("operator_limits", {})
        request = ScienceRequest(
            request_id=UUID(new_id()),
            operation=ScienceOperation(inputs.operation),
            mode=run["mode"],
            inputs=inputs,
            input_evidence=handles,
            source_policy=policy,
            options=ScienceOptions(
                max_expansions=int(limits.get("search_max_expansions", catalog.BUDGETS["search_max_expansions"])),
                max_seconds=float(limits.get("search_max_seconds", catalog.BUDGETS["search_max_seconds"])),
                max_labels_per_node=int(
                    limits.get("search_max_labels_per_node", catalog.BUDGETS["search_max_labels_per_node"])
                ),
                algorithm_config_sha256=run.get("runtime", {}).get("algorithm_lock_sha256"),
            ),
        )
        service = self.science
        if service is None:
            try:
                service = importlib.import_module("analogforge.science.facade").create_science_service()
            except (ModuleNotFoundError, AttributeError) as exc:
                raise WorkflowError("SCIENCE_FACADE_MISSING", "Scientific entry point is unavailable") from exc
        if ScienceOperation(inputs.operation) not in service.supported_operations():
            raise WorkflowError("SCIENCE_FACADE_MISSING", "Scientific service does not implement this operation")
        scratch = Path(tempfile.mkdtemp(prefix="science-", dir=self._scratch_root()))
        from analogforge.application.datasets import read_lock

        frozen_lock = read_lock(self.settings, run["dataset_lock_id"])
        context = WorkerScienceContext(
            scratch=scratch,
            workspace_id=UUID(workspace_id),
            job_id=UUID(job_id or new_id()),
            mode=run["mode"],
            run_id=UUID(run_id),
            artifact_paths={
                e["artifact_sha256"]: self.blobs.path(e["artifact_sha256"])
                for e in evidence
                if e.get("artifact_sha256")
            },
            dataset_roots={s: Path(self.settings.data_root) / "incoming" / s for s in policy.local_dataset_ids},
            deadline_monotonic=time.monotonic() + float(request.options.max_seconds or 30),
            dataset_checksums={
                entry["dataset_id"]: {file["path"]: file["sha256"] for file in entry["files"]}
                for entry in frozen_lock["datasets"]
            },
        )

        def cancelled() -> None:
            fresh, _, _ = self._load(run_id, workspace_id)
            if fresh["state"] == "CANCELLED" or fresh.get("cancel_requested_at"):
                raise ScienceCancelled()

        from analogforge.jobs.cpu import run_science

        result = run_science(
            service,
            request,
            context,
            timeout_seconds=float(request.options.max_seconds or 30),
            check_cancelled=cancelled,
        )
        result = ScienceComputationResult.model_validate(result)
        invocation_id = new_id()
        with self.store.transaction(workspace_id) as tx:
            tx.create(
                "invocations",
                {
                    "id": invocation_id,
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "preparation_id": None,
                    "mode": run["mode"],
                    "role": "scientific_worker",
                    "status": "RUNNING",
                    "task_kind": inputs.operation,
                    "input_hash": canonical_sha256(request),
                },
            )
        operation_id = new_id()

        def apply(tx: Any, registered: RegisteredResult) -> None:
            tx.create(
                "scientific_operations",
                {
                    **envelope(workspace_id, run_id, run["mode"]),
                    "id": operation_id,
                    "operation": inputs.operation,
                    "cache_key": cache_key,
                    "request": request.model_dump(mode="json"),
                    "payload": registered.payload,
                    "receipt_id": registered.receipt["id"],
                    "evidence_ids": list(registered.evidence_ids),
                    "artifact_hashes": registered.artifact_hashes,
                    "local_evidence_ids": registered.local_evidence_ids,
                    "status": registered.status,
                    "issues": list(registered.issues),
                },
            )
            sources = tx.list("evidence", {"run_id": run_id, "kind": "SOURCE"})
            current = tx.require("runs", run_id)
            current.setdefault("runtime", {})["acquired_manifest_sha256"] = canonical_sha256(
                sorted(sources, key=lambda e: e["id"])
            )
            tx.replace("runs", run_id, current, current["revision"])
            if publish is not None and registered.payload is not None:
                publish(tx, registered)

        return self.registrar.register(
            request,
            result,
            scratch_dir=scratch,
            workspace_id=workspace_id,
            run_id=run_id,
            invocation_id=invocation_id,
            tool_name=OPERATION_TO_TOOL[request.operation],
            job_id=job_id,
            lease_token=lease_token,
            apply_payload=apply,
        )

    def _scratch_root(self) -> Path:
        root = Path(self.settings.data_root) / "scratch"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _rows(self, workspace_id: str, kind: str, run_id: str) -> list[dict[str, Any]]:
        with self.store.transaction(workspace_id) as tx:
            return cast(list[dict[str, Any]], tx.list(kind, {"run_id": run_id}))

    def _latest_qualifications(self, workspace_id: str, run_id: str) -> list[dict[str, Any]]:
        rows = self._rows(workspace_id, "qualifications", run_id)
        selected: dict[tuple[str, str], dict[str, Any]] = {}
        for row in sorted(rows, key=lambda r: r.get("evaluation_version", 1)):
            selected[row["candidate_id"], row["requirement_id"]] = row
        return list(selected.values())

    def _role(
        self, role: str, task_kind: str, run_id: str, workspace_id: str, extra: dict[str, Any] | None = None
    ) -> RoleSubmission:
        from analogforge.agents.runtime.openai_provider import OpenAIProvider

        run, mission, rover = self._load(run_id, workspace_id)
        scenario = self._scenario(run["scenario_config_id"])
        with self.store.transaction(workspace_id) as tx:
            evidences = tx.list("evidence", {"run_id": run_id})
            receipts = tx.list("tool_receipts", {"run_id": run_id})
            established = {
                str(eid) for receipt in receipts if receipt["status"] == "SUCCEEDED" for eid in receipt["evidence_ids"]
            }
            evidences = [e for e in evidences if e["id"] in established]
            targets = tx.list("target_profiles", {"run_id": run_id})
            candidates = tx.list("candidates", {"run_id": run_id})
            receipt = ToolReceipt.model_validate(
                {
                    **envelope(workspace_id, run_id, run["mode"]),
                    "invocation_id": new_id(),
                    "tool_name": "inspect_contract",
                    "tool_version": "1.0.0",
                    "input_sha256": canonical_sha256(mission),
                    "output_sha256": mission["content_sha256"],
                    "evidence_ids": [],
                    "status": "SUCCEEDED",
                    "error_code": None,
                    "elapsed_ms": 0,
                    "cache_hit": False,
                }
            ).model_dump(mode="json")
            tx.create(
                "invocations",
                {
                    "id": receipt["invocation_id"],
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "preparation_id": None,
                    "mode": run["mode"],
                    "role": role,
                    "status": "SUCCEEDED",
                    "task_kind": "inspect_contract",
                    "input_hash": canonical_sha256(mission),
                },
            )
            tx.create("tool_receipts", receipt)
        receipts.append(receipt)
        facts = {
            "mission": mission,
            "rover": rover,
            "run": run,
            "scenario": scenario,
            "evidence_ids": [e["id"] for e in evidences],
            "validation_receipt_id": receipt["id"],
            "target": targets[-1] if targets else None,
            "candidates": candidates,
            **(extra or {}),
        }
        payload = project_payload(role, facts)
        proposal: dict[str, Any] = {
            "schema_version": "1.0",
            "role_key": role,
            "task_kind": task_kind,
            "disposition": "COMPLETE",
            "summary": f"{catalog.ROLE_DISPLAY_NAMES[role]} reviewed committed receipts and preserved accepted scope.",
            "evidence_ids": [e["id"] for e in evidences],
            "assumption_ids": [],
            "issues": [],
            "next_action": None,
            "payload": payload,
        }
        invocation_id = new_id()
        ledger = BudgetLedger.from_document(run.get("runtime", {}).get("budget"))
        task = AgentTask(
            workspace_id=UUID(workspace_id),
            run_id=UUID(run_id),
            invocation_id=UUID(invocation_id),
            role_key=role,
            task_kind=task_kind,
            runtime_mode=run["mode"],
            expected_run_revision=run["revision"],
            contract_revision_id=UUID(mission["id"]),
            rover_revision_id=UUID(rover["id"]) if rover else None,
            contract_hash=mission["content_sha256"],
            rover_hash=rover["content_sha256"] if rover else None,
            input_evidence_ids=[UUID(e["id"]) for e in evidences],
            accepted_assumption_ids=[],
            allowed_actions=["continue", "request_review", "stop_investigation", "record_unknown"],
            budget={
                key: ledger.remaining(key)
                for key in ("model_requests_per_run", "tool_calls_per_run", "active_run_seconds")
            },
            payload={
                "prepared_submission": proposal,
                "authoritative_submission": proposal,
                "untrusted_sources": [],
                "authoritative_rover": rover,
                "permitted_repairs": (extra or {}).get("diagnosis", {}).get("permitted_repairs", []),
                "receipt_summaries": [
                    {k: r[k] for k in ("id", "tool_name", "status", "evidence_ids")} for r in receipts
                ],
            },
        )
        seeded_defect = False
        if (
            run["mode"] == "synthetic"
            and role == "qualification"
            and scenario.get("defect_injection")
            and not run.get("runtime", {}).get("seeded_defect_staged")
        ):
            candidate = (extra or {}).get("candidate", {})
            if candidate.get("window_id") == catalog.WINDOW_A_MESA:
                analysis = next(
                    (
                        e
                        for e in evidences
                        if e["id"] in candidate["evidence_ids"] and e["algorithm_id"] == "analyze-candidate"
                    ),
                    None,
                )
                if analysis is not None:
                    from copy import deepcopy

                    proposed = deepcopy(proposal)
                    context_row = next(
                        (
                            row
                            for row in proposed["payload"]["rows"]
                            if row["requirement_id"] == "R-TARGET-SLOPE-CONTEXT"
                        ),
                        None,
                    )
                    if context_row is not None:
                        context_row["evidence_ids"] = [analysis["id"]]
                        context_row["measurement_evidence_ids"] = [analysis["id"]]
                        task = task.model_copy(update={"payload": {**task.payload, "prepared_submission": proposed}})
                        seeded_defect = True
        local_budget = BudgetLedger()

        def charge(key: str) -> None:
            if key.endswith("per_invocation"):
                local_budget.charge(key)
            else:
                self._charge(run_id, workspace_id, key)

        context = ToolContext(
            role, workspace_id, run_id, run["mode"], run["revision"], mission["content_sha256"], charge=charge
        )
        registry = ToolRegistry(
            {
                "get_run_snapshot": lambda args: {"run_revision": run["revision"], "snapshot": run},
                "inspect_contract": lambda args: {
                    "accepted": bool(mission.get("accepted_at")),
                    "hash": mission["content_sha256"],
                    "requirements": mission["requirements"],
                },
                "get_evidence": lambda args: {"evidence": [e for e in evidences if e["id"] in args["evidence_ids"]]},
            }
        )
        if run["mode"] == "live":
            provider: Any = OpenAIProvider(self._provider_client())
        elif run["mode"] == "replay":
            from analogforge.agents.runtime.provider import ReplayProvider

            task = task.model_copy(update={"payload": {**task.payload, "recording_key": role + ":" + task_kind}})
            provider = ReplayProvider(run.get("runtime", {}).get("role_recordings", {}))
        else:
            provider = ScriptedProvider()
        with self.store.transaction(workspace_id) as tx:
            tx.create(
                "invocations",
                {
                    "id": invocation_id,
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "preparation_id": None,
                    "mode": run["mode"],
                    "role": role,
                    "status": "RUNNING",
                    "task_kind": task_kind,
                    "input_hash": canonical_sha256(task),
                },
            )
        submission = RoleSubmission.model_validate(provider.run(task, registry, context))
        rejected_seed = False
        try:
            validate_submission(task, submission)
        except PolicyViolation as exc:
            if not seeded_defect or exc.detail_code != "COMPARISON_CITATION_CHANGED":
                raise
            rejected_seed = True
        evaluate_transition(
            run,
            submission.model_dump(mode="json"),
            receipts,
            evidence={e["id"]: e for e in evidences},
            allowed_actions=task.allowed_actions,
        )
        result = AgentRoleResult.model_validate(
            {
                **envelope(workspace_id, run_id, run["mode"]),
                "invocation_id": invocation_id,
                "role": role,
                "status": "BLOCKED" if rejected_seed or submission.disposition != "COMPLETE" else "SUCCEEDED",
                "proposed_next_state": None,
                "evidence_ids": [str(e) for e in submission.evidence_ids],
                "receipt_ids": [r["id"] for r in receipts],
                "summary": submission.summary,
                "payload": submission.model_dump(mode="json"),
                "error_code": "SCALE_INCOMPATIBLE" if rejected_seed else None,
            }
        ).model_dump(mode="json")
        active_job, active_token = self._job_context.get()
        publication = (
            self.store.publication(workspace_id, active_job, active_token)
            if active_job and active_token
            else self.store.transaction(workspace_id)
        )
        with publication as tx:
            authoritative = tx.require("runs", run_id, lock=True)
            if authoritative["state"] == "CANCELLED" or authoritative.get("cancel_requested_at"):
                raise ScienceCancelled()
            if any(
                authoritative.get(key) != run.get(key)
                for key in (
                    "state",
                    "mission_revision_id",
                    "rover_revision_id",
                    "selected_candidate_id",
                    "qualification_ids",
                    "test_ids",
                    "test_result_ids",
                )
            ):
                raise WorkflowError("REVISION_CONFLICT", "Role proposal used a stale scientific snapshot")
            tx.create("role_results", result)
            if rejected_seed:
                authoritative.setdefault("runtime", {})["seeded_defect_staged"] = True
                tx.replace("runs", run_id, authoritative, authoritative["revision"])
            tx.create(
                "agent_actions",
                AgentAction.model_validate(
                    {
                        **envelope(workspace_id, run_id, run["mode"]),
                        "agent_role": role,
                        "invocation_id": invocation_id,
                        "action_type": "DECISION",
                        "tool_name": None,
                        "tool_receipt_id": None,
                        "summary": submission.summary,
                        "evidence_ids": [str(e) for e in submission.evidence_ids],
                        "status": "BLOCKED" if rejected_seed or submission.disposition != "COMPLETE" else "SUCCEEDED",
                    }
                ).model_dump(mode="json"),
            )
            tx.replace(
                "invocations", invocation_id, {**tx.require("invocations", invocation_id), "status": "SUCCEEDED"}
            )
            tx.append_event(
                run_id,
                "agent.proposal_rejected" if rejected_seed else "agent.completed",
                {"role": role, "invocation_id": invocation_id, "summary": submission.summary},
                run["mode"],
            )

        if submission.disposition != "COMPLETE" or submission.next_action in {
            "request_review",
            "stop_investigation",
            "record_unknown",
        }:
            raise WorkflowRolePaused(submission.disposition, submission.summary)
        return submission

    def _qualify(
        self,
        run_id: str,
        workspace_id: str,
        candidates: list[dict[str, Any]],
        mission: dict[str, Any],
        rover: dict[str, Any] | None,
        *,
        verification_by_candidate: dict[str, VerificationSummary] | None = None,
        job_id: str | None = None,
        lease_token: str | None = None,
    ) -> None:
        target = self._rows(workspace_id, "target_profiles", run_id)[-1]
        for candidate in candidates:
            summary = (verification_by_candidate or {}).get(candidate["id"])
            for row in mission["requirements"]:
                inputs = CompareRequirementInput(
                    requirement=row,
                    candidate=discovery.reference(candidate),
                    target_evidence_ids=target["evidence_ids"],
                    candidate_evidence_ids=candidate["evidence_ids"],
                    verification=summary,
                    observable_policy_id=catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.get(
                        row["observable"], "unsupported-observable"
                    ),
                )

                def publish(
                    tx: Any,
                    r: RegisteredResult,
                    candidate: dict[str, Any] = candidate,
                    row: dict[str, Any] = row,
                ) -> None:
                    record = qualification.evaluate_candidate(
                        workspace_id,
                        run_id,
                        r.receipt["mode"],
                        candidate["id"],
                        r.required_payload,
                        list(r.evidence_ids),
                    )
                    previous = tx.list(
                        "qualifications",
                        {
                            "run_id": run_id,
                            "candidate_id": candidate["id"],
                            "requirement_id": r.required_payload["requirement_id"],
                        },
                    )
                    record["evaluation_version"] = (
                        max((p.get("evaluation_version", 1) for p in previous), default=0) + 1
                    )
                    record["receipt_id"] = r.receipt["id"]
                    from analogforge.application.assurance import audit_registered_claim

                    qualification.validate_payload_against_requirement(r.required_payload, row)
                    audit_registered_claim(
                        tx,
                        tx.require("runs", run_id),
                        mission,
                        rover,
                        record,
                        r.required_payload,
                        self.blobs,
                        config_dir=Path(self.settings.config_dir),
                    )
                    tx.create("qualifications", record)
                    current = tx.require("runs", run_id)
                    current["qualification_ids"] = [
                        q for q in current["qualification_ids"] if q not in {p["id"] for p in previous}
                    ] + [record["id"]]
                    tx.replace("runs", run_id, current, current["revision"])

                self._compute(inputs, run_id, workspace_id, job_id=job_id, lease_token=lease_token, publish=publish)
            if rover:
                self._compute(
                    AssessCompatibilityInput(
                        rover=_wire(RoverProfile, rover),
                        requirements=mission["requirements"],
                        candidate=discovery.reference(candidate),
                        candidate_evidence_ids=candidate["evidence_ids"],
                        verification=summary,
                    ),
                    run_id,
                    workspace_id,
                    job_id=job_id,
                    lease_token=lease_token,
                    publish=lambda tx, r, candidate=candidate: tx.create(
                        "compatibility",
                        compatibility.assess(
                            workspace_id,
                            run_id,
                            r.receipt["mode"],
                            candidate["id"],
                            r.required_payload,
                            list(r.evidence_ids),
                            rover_revision_id=rover["id"],
                        ),
                    ),
                )

    def _claims(self, workspace_id: str, run_id: str) -> list[ClaimScope]:
        candidates = self._rows(workspace_id, "candidates", run_id)
        windows = {c["id"]: c["window_id"] for c in candidates}
        claims = [
            ClaimScope(
                claim_id="q:" + q["id"],
                claim_type="QUALIFICATION",
                requirement_id=q["requirement_id"],
                candidate_window_ids=[windows[q["candidate_id"]]],
                evidence_ids=q["evidence_ids"],
            )
            for q in self._latest_qualifications(workspace_id, run_id)
        ]
        claims.extend(
            ClaimScope(
                claim_id="discovery:" + c["id"],
                claim_type="DISCOVERY",
                requirement_id=None,
                candidate_window_ids=[c["window_id"]],
                evidence_ids=c["evidence_ids"],
            )
            for c in candidates
        )
        tests = {t["id"]: t for t in self._rows(workspace_id, "tests", run_id)}
        claims.extend(
            ClaimScope(
                claim_id="v:" + r["test_id"],
                claim_type="VERIFICATION",
                requirement_id=None,
                candidate_window_ids=[windows[tests[r["test_id"]]["candidate_id"]]],
                evidence_ids=r["evidence_ids"],
            )
            for r in self._rows(workspace_id, "test_results", run_id)
        )
        return claims

    def _audit(self, run_id: str, workspace_id: str, job_id: str | None, lease_token: str | None) -> dict[str, Any]:
        claims = self._claims(workspace_id, run_id)
        if not claims:
            return {"operation": "AUDIT_EVIDENCE", "claim_gates": [], "findings": []}
        registered = self._compute(
            AuditEvidenceInput(
                claims=claims,
                check_set=["provenance", "units", "crs", "scale", "coverage", "uncertainty", "proxies", "independence"],
            ),
            run_id,
            workspace_id,
            job_id=job_id,
            lease_token=lease_token,
        )
        if registered.payload is None:
            raise WorkflowError("SCIENTIFIC_CLAIM_REJECTED", "Evidence audit is unavailable")
        return registered.payload

    def advance(
        self, run_id: str, workspace_id: str, job_id: str | None = None, lease_token: str | None = None
    ) -> dict[str, Any]:
        run, mission, rover = self._load(run_id, workspace_id)
        if (
            run["state"] in TERMINAL
            or run["state"] == "AWAITING_REVIEW"
            and not run.get("runtime", {}).get("pending_action")
        ):
            return run
        started = time.monotonic()
        context_token = self._job_context.set((job_id, lease_token))
        try:
            self._advance_step(run, mission, rover, workspace_id, job_id, lease_token)
        except WorkflowRolePaused as exc:
            current, _, _ = self._load(run_id, workspace_id)
            self._save_run(
                run_id,
                workspace_id,
                {
                    "state": "BLOCKED",
                    "runtime": {
                        **current.get("runtime", {}),
                        "resume_state": current["state"],
                        "role_disposition": exc.disposition,
                    },
                    "blocked_dependencies": [
                        "USER_REVIEW_REQUIRED"
                        if exc.disposition == "NEEDS_USER_REVIEW"
                        else "ROLE_INVESTIGATION_BLOCKED"
                    ],
                },
                event="run.blocked",
                complete_job=job_id is not None,
                job_id=job_id,
                lease_token=lease_token,
            )
        except BudgetExceeded:
            current, _, _ = self._load(run_id, workspace_id)
            runtime = current.setdefault("runtime", {})
            runtime["stop_reason"] = "BUDGET_EXHAUSTED"
            # Preserve unsupported evidence explicitly when the computation budget is exhausted.
            self._save_run(
                run_id,
                workspace_id,
                {
                    "state": "BLOCKED",
                    "runtime": {**runtime, "resume_state": current["state"]},
                    "blocked_dependencies": ["BUDGET_EXHAUSTED"],
                },
                event="run.blocked",
                job_id=job_id,
                lease_token=lease_token,
            )
        finally:
            elapsed = time.monotonic() - started
            if elapsed > 0:
                try:
                    self._charge(run_id, workspace_id, "active_run_seconds", elapsed)
                except BudgetExceeded:
                    # The next boundary sees the exhausted cap; no counter is reset by restart.
                    self._save_exhausted_time(run_id, workspace_id)
            self._job_context.reset(context_token)
        return self._load(run_id, workspace_id)[0]

    def _save_exhausted_time(self, run_id: str, workspace_id: str) -> None:
        with self.store.transaction(workspace_id) as tx:
            run = tx.require("runs", run_id)
            ledger = BudgetLedger.from_document(run.get("runtime", {}).get("budget"))
            ledger.counters["active_run_seconds"] = ledger.limits["active_run_seconds"]
            run.setdefault("runtime", {})["budget"] = ledger.document()
            tx.replace("runs", run_id, run, run["revision"])

    def _advance_step(
        self,
        run: dict[str, Any],
        mission: dict[str, Any],
        rover: dict[str, Any] | None,
        workspace_id: str,
        job_id: str | None,
        lease_token: str | None,
    ) -> dict[str, Any]:
        run_id = run["run_id"]
        scenario = self._scenario(run["scenario_config_id"])
        state = run["state"]
        kwargs: dict[str, Any] = {"job_id": job_id, "lease_token": lease_token}
        runtime = run.setdefault("runtime", {})

        def finish(next_state: str, **changes: Any) -> dict[str, Any]:
            current, _, _ = self._load(run_id, workspace_id)
            merged_runtime = {**current.get("runtime", {}), **changes.pop("runtime", {})}
            updated = self._save_run(
                run_id,
                workspace_id,
                {"state": next_state, "runtime": merged_runtime, **changes},
                event="run.state_changed",
                enqueue_next=next_state not in TERMINAL and next_state not in {"AWAITING_REVIEW", "BLOCKED"},
                complete_job=job_id is not None,
                **kwargs,
            )
            return updated

        if state == "DRAFT":
            return finish("VALIDATING")
        if state == "VALIDATING":
            if (
                not mission.get("accepted_at")
                or content_hash(_wire(MissionTestContract, mission).model_dump(mode="json"), "mission")
                != mission["content_sha256"]
            ):
                raise WorkflowError("INPUT_INVALID", "Accepted mission is missing or its content hash changed")
            if (
                rover
                and content_hash(_wire(RoverProfile, rover).model_dump(mode="json"), "rover") != rover["content_sha256"]
            ):
                raise WorkflowError("INPUT_INVALID", "Saved rover content hash changed")
            policy = self._source_policy(run, scenario)
            from analogforge.application.assurance import assurance_policy_digest

            for dataset_id in policy.local_dataset_ids:
                manifest_path = Path(self.settings.data_root) / "incoming" / dataset_id / "manifest.yaml"
                manifest = yaml.safe_load(manifest_path.read_text())
                self._compute(IngestLocalDatasetInput(manifest=manifest), run_id, workspace_id, **kwargs)
            return finish(
                "CHARACTERIZING",
                runtime={
                    "mission_content_sha256": mission["content_sha256"],
                    "rover_content_sha256": rover["content_sha256"] if rover else None,
                    "dataset_policy_sha256": policy.policy_sha256,
                    "assurance_policy_sha256": assurance_policy_digest(Path(self.settings.config_dir)),
                    "source_policy": policy.model_dump(mode="json"),
                    "acquired_manifest_sha256": canonical_sha256([]),
                    "algorithm_lock_sha256": runtime.get("algorithm_lock_sha256") or self._algorithm_lock(),
                },
            )
        if state == "CHARACTERIZING":
            coverage = self._compute(
                ResolveCoverageInput(
                    subject_kind="TARGET",
                    aoi=mission["target"],
                    adapter_id="local_dataset"
                    if scenario["target_source"]["kind"] == "LOCAL_DATASET"
                    else "synthetic_practice",
                    measurement_kinds=sorted({r["dimension"] for r in mission["requirements"]}),
                ),
                run_id,
                workspace_id,
                **kwargs,
            )

            def target_publish(tx: Any, r: RegisteredResult) -> None:
                target = PlanetaryTargetProfile.model_validate(
                    {
                        **envelope(workspace_id, run_id, run["mode"]),
                        "target": mission["target"],
                        "evidence_ids": list(r.evidence_ids),
                        "metrics": r.required_payload["metrics"],
                        "unavailable_dimensions": [
                            x["dimension"] for x in r.required_payload["unavailable_dimensions"]
                        ],
                    }
                ).model_dump(mode="json")
                target["payload"] = r.required_payload
                tx.create("target_profiles", target)
                current = tx.require("runs", run_id)
                current["target_profile_id"] = target["id"]
                tx.replace("runs", run_id, current, current["revision"])

            characterization = self._compute(
                CharacterizeTargetInput(
                    target=mission["target"],
                    source=scenario["target_source"],
                    measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET,
                    requested_dimensions=sorted({r["dimension"] for r in mission["requirements"]}),
                ),
                run_id,
                workspace_id,
                publish=target_publish,
                **kwargs,
            )
            if characterization.payload is None:
                return finish(
                    "BLOCKED",
                    blocked_dependencies=[i["code"] for i in characterization.issues],
                    runtime={"resume_state": state},
                )
            self._display(
                run_id, workspace_id, "TARGET", list(characterization.evidence_ids), None, job_id, lease_token
            )
            self._role("mission_director", "advance_workflow", run_id, workspace_id)
            self._role("requirements", "validate_accepted_contract", run_id, workspace_id)
            if rover:
                self._role("rover_systems", "validate_profile", run_id, workspace_id)
            self._role(
                "planetary_target",
                "characterize_target",
                run_id,
                workspace_id,
                {"coverage_receipt_ids": [coverage.receipt["id"]]},
            )
            return finish("DISCOVERING")
        if state == "DISCOVERING":
            target = self._rows(workspace_id, "target_profiles", run_id)[-1]

            def screen_publish(tx: Any, r: RegisteredResult) -> None:
                tx.create(
                    "screenings",
                    {
                        **envelope(workspace_id, run_id, run["mode"]),
                        "payload": r.required_payload,
                        "receipt_id": r.receipt["id"],
                    },
                )
                ids = []
                for window in r.required_payload["windows"]:
                    if window["window_id"] in r.required_payload["shortlist_window_ids"]:
                        candidate = discovery.candidate_record(
                            window, workspace_id, run_id, run["mode"], list(r.evidence_ids)
                        )
                        tx.create("candidates", candidate)
                        ids.append(candidate["id"])
                current = tx.require("runs", run_id)
                current["candidate_ids"] = ids
                tx.replace("runs", run_id, current, current["revision"])

            screening = self._compute(
                ScreenCandidatesInput(
                    search_region_set_id=scenario["search_region_set_id"],
                    source=scenario["earth_source"],
                    target_metrics=target["metrics"],
                    target_histogram=target["payload"]["slope_histogram"],
                    requirements=mission["requirements"],
                    max_detailed=int(scenario["operator_limits"].get("detailed_candidates", 6)),
                    reference_set_id=scenario["reference_set_id"],
                ),
                run_id,
                workspace_id,
                publish=screen_publish,
                **kwargs,
            )
            candidates = self._rows(workspace_id, "candidates", run_id)
            for candidate in candidates:

                def analysis_publish(tx: Any, r: RegisteredResult, candidate: dict[str, Any] = candidate) -> None:
                    current = tx.require("candidates", candidate["id"])
                    current.update(
                        metrics=r.required_payload["metrics"],
                        limitations=r.required_payload["limitations"],
                        analysis_payload=r.required_payload,
                        evidence_ids=list(dict.fromkeys(current["evidence_ids"] + list(r.evidence_ids))),
                    )
                    tx.replace("candidates", candidate["id"], current)

                analysis = self._compute(
                    AnalyzeCandidateInput(
                        candidate=discovery.reference(candidate),
                        source=scenario["earth_source"],
                        measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH,
                    ),
                    run_id,
                    workspace_id,
                    publish=analysis_publish,
                    **kwargs,
                )
                if analysis.payload:
                    self._display(
                        run_id,
                        workspace_id,
                        "CANDIDATE",
                        list(analysis.evidence_ids),
                        candidate["id"],
                        job_id,
                        lease_token,
                    )
            self._role(
                "earth_scout",
                "screen_candidates",
                run_id,
                workspace_id,
                {"screening": screening.payload or {}, "screening_receipt_id": screening.receipt["id"]},
            )
            return finish(
                "QUALIFYING" if candidates else "BUILDING_PASSPORT",
                selected_candidate_id=candidates[0]["id"] if candidates else None,
            )
        if state == "QUALIFYING":
            candidates = self._rows(workspace_id, "candidates", run_id)
            self._qualify(run_id, workspace_id, candidates, mission, rover, **kwargs)
            rows = self._latest_qualifications(workspace_id, run_id)
            for candidate in candidates:
                self._role(
                    "qualification",
                    "qualify_candidate",
                    run_id,
                    workspace_id,
                    {
                        "candidate": candidate,
                        "qualifications": [q for q in rows if q["candidate_id"] == candidate["id"]],
                    },
                )
            return finish("CRITIQUING")
        if state == "CRITIQUING":
            audit = self._audit(run_id, workspace_id, job_id, lease_token)
            if self._critic(run_id, workspace_id, mission, audit):
                return finish("CRITIQUING", runtime={"audit_payload": audit})
            if rover:
                review = {
                    "review_id": new_id(),
                    "kind": "EVIDENCE_READY",
                    "summary": "Evidence is ready. Select a candidate and choose PROVE IT for a modeled experiment.",
                    "evidence_ids": [],
                    "proposal_artifact_sha256": None,
                    "blocked_requirement_ids": [],
                    "allowed_actions": ["PROVE_IT", "CANCEL"],
                    "created_at": utc_now(),
                    "status": "PENDING",
                }
                return finish("AWAITING_REVIEW", pending_review=review, runtime={"audit_payload": audit})
            return finish(
                "BUILDING_PASSPORT",
                runtime={"audit_payload": audit, "not_run_reason": "No rover supplied — site qualification only"},
            )
        if state == "AWAITING_REVIEW":
            pending = runtime.get("pending_action")
            if pending:
                self._perform_pending_action(run_id, workspace_id, pending, mission, rover, job_id, lease_token)
                current, _, _ = self._load(run_id, workspace_id)
                current["runtime"]["pending_action"] = None
                return self._save_run(run_id, workspace_id, {"runtime": current["runtime"]})
            return run
        if state == "DESIGNING_TEST":
            if rover is None:
                raise WorkflowError("ROVER_REQUIRED", "A saved rover is required for PROVE IT")
            candidates = self._rows(workspace_id, "candidates", run_id)
            candidate = next(c for c in candidates if c["id"] == run["selected_candidate_id"])
            tests = self._rows(workspace_id, "tests", run_id)
            prior = self._attempt_summaries(workspace_id, run_id)
            strategy = runtime.get("strategy", "WAYPOINT_RETURN")
            analysis_id = next(
                (
                    e["id"]
                    for e in self._rows(workspace_id, "evidence", run_id)
                    if e["id"] in candidate["evidence_ids"] and e["algorithm_id"] == "analyze-candidate"
                ),
                None,
            )
            design_result = self._compute(
                DesignBenchmarkInput(
                    mission=_wire(MissionTestContract, mission),
                    rover=_wire(RoverProfile, rover),
                    candidate=discovery.reference(candidate),
                    analysis_evidence_id=analysis_id,
                    graph_fixture_id=scenario.get("graph_fixture_id"),
                    strategy=strategy,
                    test_revision=len(tests) + 1,
                    prior_attempts=prior,
                ),
                run_id,
                workspace_id,
                **kwargs,
            )
            if design_result.payload is None:
                return finish("BUILDING_PASSPORT", runtime={"stop_reason": "DATA_BLOCKED"})
            payload = design_result.payload
            if canonical_sha256(payload["constraints"]) != payload["constraints_sha256"]:
                raise WorkflowError("SOURCE_CHECKSUM_MISMATCH", "Constraints hash does not match canonical constraints")
            test = verification.design(
                workspace_id,
                run_id,
                run["mode"],
                candidate["id"],
                payload,
                parent_test_id=tests[-1]["id"] if tests else None,
                attempt_number=len(tests) + 1,
                changed_elements=runtime.get("changed_elements", []),
            )
            search = self._compute(
                SearchRouteInput(constraints=payload["constraints"], constraints_sha256=payload["constraints_sha256"]),
                run_id,
                workspace_id,
                **kwargs,
            )
            if search.payload is None:
                return finish("BUILDING_PASSPORT", runtime={"stop_reason": "DATA_BLOCKED"})
            test.update(
                search_status=search.payload["search_status"],
                search_payload=search.payload,
                route_artifact_sha256=search.payload.get("route_sha256"),
                requirement_mapping=payload["requirement_mapping"],
                unverified_requirement_ids=payload["unverified_requirement_ids"],
                search_evidence_ids=list(search.evidence_ids),
            )
            with self.store.transaction(workspace_id) as tx:
                tx.create("tests", test)
                fresh = tx.require("runs", run_id)
                fresh["test_ids"].append(test["id"])
                tx.replace("runs", run_id, fresh, fresh["revision"])
            self._role(
                "test_designer",
                "design_benchmark" if not tests else "design_replan",
                run_id,
                workspace_id,
                {"candidate": candidate, "test": test},
            )
            return finish("VERIFYING", runtime={"active_test_id": test["id"]})
        if state == "VERIFYING":
            tests = self._rows(workspace_id, "tests", run_id)
            test = next(t for t in tests if t["id"] == runtime["active_test_id"])
            search = test["search_payload"]
            if search["search_status"] != "FOUND":
                return finish("DIAGNOSING")

            def result_publish(tx: Any, r: RegisteredResult) -> None:
                result = verification.independently_verify(
                    workspace_id, run_id, run["mode"], test["id"], r.required_payload, list(r.evidence_ids)
                )
                tx.create("test_results", result)
                fresh = tx.require("runs", run_id)
                fresh["test_result_ids"].append(result["id"])
                tx.replace("runs", run_id, fresh, fresh["revision"])

            checked = self._compute(
                VerifyRouteInput(
                    constraints=test["constraints"],
                    constraints_sha256=test["constraints_sha256"],
                    route=search["route"],
                    route_sha256=search["route_sha256"],
                    search_status=search["search_status"],
                ),
                run_id,
                workspace_id,
                publish=result_publish,
                **kwargs,
            )
            if checked.payload is None:
                return finish("BUILDING_PASSPORT", runtime={"stop_reason": "DATA_BLOCKED"})
            verification_result = self._rows(workspace_id, "test_results", run_id)[-1]
            candidate = next(
                c for c in self._rows(workspace_id, "candidates", run_id) if c["id"] == test["candidate_id"]
            )
            summary = VerificationSummary(
                outcome=verification_result["outcome"],
                failure_category=verification_result["failure_category"],
                test_result_id=verification_result["id"],
                violation_codes=[v["code"] for v in verification_result["violations"]],
                metrics=verification_result["metrics"],
            )
            self._qualify(
                run_id,
                workspace_id,
                [candidate],
                mission,
                rover,
                verification_by_candidate={candidate["id"]: summary},
                **kwargs,
            )
            if verification_result["outcome"] == "PASS":
                self._role(
                    "verification_replanning",
                    "verify_proposed_route",
                    run_id,
                    workspace_id,
                    {"candidate": candidate, "test": test, "result": verification_result},
                )
            return finish("BUILDING_PASSPORT" if verification_result["outcome"] == "PASS" else "DIAGNOSING")
        if state == "DIAGNOSING":
            tests = self._rows(workspace_id, "tests", run_id)
            test = next(t for t in tests if t["id"] == runtime["active_test_id"])
            results = [r for r in self._rows(workspace_id, "test_results", run_id) if r["test_id"] == test["id"]]
            result = results[-1] if results else None
            search = test["search_payload"]
            provisional = VerificationSummary(
                outcome=result["outcome"]
                if result
                else "FAIL"
                if search["search_status"] == "EXHAUSTIVE_INFEASIBLE"
                else "INCONCLUSIVE",
                failure_category=result["failure_category"]
                if result
                else "DATA"
                if search["search_status"] == "EXHAUSTIVE_INFEASIBLE"
                else "SEARCH_LIMIT",
                test_result_id=result["id"] if result else None,
                metrics=result["metrics"] if result else [],
                violation_codes=[v["code"] for v in result["violations"]] if result else [],
            )
            ledger = BudgetLedger.from_document(runtime.get("budget"))
            diagnosed = self._compute(
                DiagnoseResultInput(
                    constraints=test["constraints"],
                    search_status=search["search_status"],
                    verification=provisional,
                    violations=(result or {}).get("payload", {}).get("violations", []),
                    attempt_history=self._attempt_summaries(workspace_id, run_id),
                    remaining_route_repairs=int(ledger.remaining("route_repairs_same_candidate")),
                    remaining_candidate_switches=int(ledger.remaining("candidate_switches")),
                ),
                run_id,
                workspace_id,
                **kwargs,
            )
            if diagnosed.payload is None:
                return finish("BUILDING_PASSPORT", runtime={"stop_reason": "DATA_BLOCKED"})
            diagnosis = diagnosed.payload
            if result is None:
                result = verification.no_route_result(
                    workspace_id, run_id, run["mode"], test["id"], search, list(diagnosed.evidence_ids), diagnosis
                )
                with self.store.transaction(workspace_id) as tx:
                    tx.create("test_results", result)
                    fresh = tx.require("runs", run_id)
                    fresh["test_result_ids"].append(result["id"])
                    tx.replace("runs", run_id, fresh, fresh["revision"])
            decision = self._role(
                "verification_replanning",
                "diagnose_failed_attempt",
                run_id,
                workspace_id,
                {
                    "test": test,
                    "result": result,
                    "diagnosis": diagnosis,
                    "diagnosis_receipt_id": diagnosed.receipt["id"],
                },
            )
            proposed_repair = decision.payload.get("repair")
            if proposed_repair is not None:
                diagnosis = {
                    **diagnosis,
                    "recommended_repair": proposed_repair["kind"],
                    "recommended_strategy": proposed_repair["strategy"],
                }
            repair = diagnosis["recommended_repair"]
            stop = repair is None or repair in {"NEW_CONTRACT_REQUIRED", "DATA_REPAIR", "COMPOSITE_PORTFOLIO"}
            return finish(
                "BUILDING_PASSPORT" if stop else "REPLANNING",
                runtime={
                    "diagnosis": diagnosis,
                    "diagnoses": {**runtime.get("diagnoses", {}), test["id"]: diagnosis},
                    "stop_reason": "DATA_BLOCKED"
                    if repair == "DATA_REPAIR"
                    else "NO_PERMITTED_REPAIR"
                    if stop
                    else None,
                },
            )
        if state == "REPLANNING":
            diagnosis = runtime["diagnosis"]
            repair = diagnosis["recommended_repair"]
            validate_repair(repair, diagnosis, mission["content_sha256"], runtime["mission_content_sha256"])
            ledger = BudgetLedger.from_document(runtime.get("budget"))
            ledger.replan(repair)
            selected = run["selected_candidate_id"]
            changes = []
            strategy = diagnosis["recommended_strategy"] or runtime.get("strategy", "EXPOSURE_COVERAGE")
            previous_strategy = runtime.get("strategy", "WAYPOINT_RETURN")
            if strategy != previous_strategy:
                changes.append(f"strategy: {previous_strategy} -> {strategy}")
            if repair == "NEW_CANDIDATE":
                candidates = self._rows(workspace_id, "candidates", run_id)
                attempted = {t["candidate_id"] for t in self._rows(workspace_id, "tests", run_id)}
                next_candidate = discovery.pick_replan_candidate(
                    candidates, self._latest_qualifications(workspace_id, run_id), attempted
                )
                if next_candidate is None:
                    return finish("BUILDING_PASSPORT", runtime={"stop_reason": "NO_PERMITTED_REPAIR"})
                old = next(c for c in candidates if c["id"] == selected)
                selected = next_candidate["id"]
                changes.append(f"candidate: {old['name']} -> {next_candidate['name']}")
            return finish(
                "DESIGNING_TEST",
                selected_candidate_id=selected,
                runtime={"budget": ledger.document(), "strategy": strategy, "changed_elements": changes},
            )
        if state == "BUILDING_PASSPORT":
            audit = self._audit(run_id, workspace_id, job_id, lease_token)
            current, _, _ = self._load(run_id, workspace_id)
            current["audit_payload"] = audit
            current["runtime"]["audit_payload"] = audit
            for key in (
                "mission_content_sha256",
                "rover_content_sha256",
                "dataset_policy_sha256",
                "acquired_manifest_sha256",
                "algorithm_lock_sha256",
            ):
                current[key] = current["runtime"].get(key)
            self._save_run(
                run_id,
                workspace_id,
                {
                    "audit_payload": audit,
                    "runtime": current["runtime"],
                    **{
                        k: current[k]
                        for k in (
                            "mission_content_sha256",
                            "rover_content_sha256",
                            "dataset_policy_sha256",
                            "acquired_manifest_sha256",
                            "algorithm_lock_sha256",
                        )
                    },
                },
                **kwargs,
            )
            from analogforge.application.passports import publish_passport

            bundle = publish_passport(
                self.store,
                workspace_id,
                run_id,
                self.blobs,
                renderer=self.renderer,
                job_id=job_id,
                lease_token=lease_token,
                config_dir=Path(self.settings.config_dir),
            )
            self._role(
                "evidence_passport",
                "assemble_passport",
                run_id,
                workspace_id,
                {
                    "passport": bundle.passport.model_dump(mode="json"),
                    "qualifications": self._latest_qualifications(workspace_id, run_id),
                },
            )
            return finish("COMPLETED", passport_id=str(bundle.passport.id), pending_review=None)
        raise WorkflowError("INVALID_TRANSITION", f"No worker step for state {state}")

    def _attempt_summaries(self, workspace_id: str, run_id: str) -> list[AttemptSummary]:
        candidates = {c["id"]: c for c in self._rows(workspace_id, "candidates", run_id)}
        tests = {t["id"]: t for t in self._rows(workspace_id, "tests", run_id)}
        return [
            AttemptSummary(
                attempt_number=tests[r["test_id"]]["attempt_number"],
                test_revision=tests[r["test_id"]]["test_revision"],
                candidate_window_id=candidates[tests[r["test_id"]]["candidate_id"]]["window_id"],
                strategy=tests[r["test_id"]]["strategy"],
                outcome=r["outcome"],
                failure_category=r["failure_category"],
                search_status=r["search_status"],
                route_sha256=r["verified_route_sha256"],
                violation_codes=[v["code"] for v in r["violations"]],
            )
            for r in self._rows(workspace_id, "test_results", run_id)
        ]

    def _display(
        self,
        run_id: str,
        workspace_id: str,
        subject: str,
        evidence_ids: list[str],
        candidate_id: str | None,
        job_id: str | None,
        lease_token: str | None,
    ) -> None:
        def publish(tx: Any, r: RegisteredResult) -> None:
            run = tx.require("runs", run_id)
            for layer in r.required_payload["layers"]:
                record = DisplayLayerManifest.model_validate(
                    {
                        "id": new_id(),
                        "workspace_id": workspace_id,
                        "run_id": run_id,
                        "mode": run["mode"],
                        "candidate_id": candidate_id,
                        "target_profile_id": run["target_profile_id"] if subject == "TARGET" else None,
                        **{
                            k: layer[k]
                            for k in (
                                "body",
                                "layer_kind",
                                "rendering",
                                "display_crs_wkt",
                                "pixel_to_world",
                                "width_px",
                                "height_px",
                                "legend",
                                "unit",
                                "support_scale_m",
                                "attribution",
                                "limitations",
                            )
                        },
                        "image_artifact_sha256": r.artifact_hashes[layer["image_artifact_key"]],
                        "earth_corners": layer["earth_corners"],
                        "source_evidence_ids": [ref["evidence_id"] for ref in layer["source_evidence"]],
                        "nodata_transparent": True,
                    }
                ).model_dump(mode="json")
                tx.create("display_layers", record)

        self._compute(
            BuildDisplayLayersInput(subject=subject, evidence_ids=evidence_ids, layer_kinds=["ELEVATION", "SLOPE"]),
            run_id,
            workspace_id,
            job_id=job_id,
            lease_token=lease_token,
            publish=publish,
        )

    def _critic(self, run_id: str, workspace_id: str, mission: dict[str, Any], audit: dict[str, Any]) -> bool:
        run, _, _ = self._load(run_id, workspace_id)
        candidates = self._rows(workspace_id, "candidates", run_id)
        rows = self._latest_qualifications(workspace_id, run_id)
        existing = self._rows(workspace_id, "critiques", run_id)
        seeded = run.get("runtime", {}).get("seeded_defect_staged")
        pending = [issue for issue in existing if issue.get("seeded_citation") and issue["status"] == "OPEN"]
        if seeded and not any(issue.get("seeded_citation") for issue in existing):
            rejected = next(
                result
                for result in self._rows(workspace_id, "role_results", run_id)
                if result["role"] == "qualification" and result.get("error_code") == "SCALE_INCOMPATIBLE"
            )
            payload = rejected["payload"]["payload"]
            proposed_row = next(row for row in payload["rows"] if row["requirement_id"] == "R-TARGET-SLOPE-CONTEXT")
            requirement = next(row for row in mission["requirements"] if row["id"] == proposed_row["requirement_id"])
            evidence = {e["id"]: e for e in self._rows(workspace_id, "evidence", run_id)}
            cited = [evidence[identifier] for identifier in proposed_row["evidence_ids"]]
            if not any(
                e.get("comparison_scale_m") is not None
                and e["comparison_scale_m"] < requirement["minimum_support_scale_m"]
                for e in cited
            ):
                raise PolicyViolation("SEEDED_DEFECT_NOT_DETECTED")
            issue_id = new_id()
            issue = {
                "id": issue_id,
                "issue_id": issue_id,
                "workspace_id": workspace_id,
                "run_id": run_id,
                "mode": run["mode"],
                "candidate_id": payload["candidate_revision_id"],
                "requirement_id": proposed_row["requirement_id"],
                "target_evidence_ids": proposed_row["evidence_ids"],
                "reason_code": "SCALE_MISMATCH",
                "severity": "BLOCKING",
                "status": "OPEN",
                "summary": "Qualification proposal cited Earth scale instead of common comparison support",
                "repair_request": "Cite the registered common-support comparison receipt",
                "resolution_evidence_ids": [],
                "seeded_citation": True,
            }
            with self.store.transaction(workspace_id) as tx:
                tx.create("critiques", issue)
                challenged = next(
                    q
                    for q in rows
                    if q["candidate_id"] == issue["candidate_id"] and q["requirement_id"] == issue["requirement_id"]
                )
                tx.replace("qualifications", challenged["id"], {**challenged, "critic_status": "CHALLENGED"})
                tx.append_event(
                    run_id,
                    "critic.issue_opened",
                    {"issue_id": issue_id, "severity": "BLOCKING", "summary": issue["summary"]},
                    run["mode"],
                )
                current = tx.require("runs", run_id)
                ledger = BudgetLedger.from_document(current.get("runtime", {}).get("budget"))
                ledger.charge("critic_repair_rounds")
                current.setdefault("runtime", {})["budget"] = ledger.document()
                tx.replace("runs", run_id, current, current["revision"])
            self._role(
                "scientific_critic",
                "review_qualification",
                run_id,
                workspace_id,
                {
                    "review_revision_id": issue_id,
                    "objections": [
                        {
                            "finding_id": issue_id,
                            "claim_id": None,
                            "requirement_id": issue["requirement_id"],
                            "evidence_ids": issue["target_evidence_ids"],
                            "rule_code": "SCALE_MISMATCH",
                            "severity": "BLOCKING",
                            "observation": issue["summary"],
                            "required_repair": {
                                "kind": "RECOMPUTE",
                                "target_ids": [issue["requirement_id"]],
                                "success_condition": "Registered common-support receipt replaces fine-scale citation",
                            },
                            "resolved_by_receipt_ids": [],
                        }
                    ],
                },
            )
            return True
        if pending:
            self._role("mission_director", "advance_workflow", run_id, workspace_id)
            for issue in pending:
                correct = next(
                    q
                    for q in rows
                    if q["candidate_id"] == issue["candidate_id"] and q["requirement_id"] == issue["requirement_id"]
                )
                candidate = next(c for c in candidates if c["id"] == issue["candidate_id"])
                self._role(
                    "qualification",
                    "revise_qualification",
                    run_id,
                    workspace_id,
                    {
                        "candidate": candidate,
                        "qualifications": [q for q in rows if q["candidate_id"] == candidate["id"]],
                    },
                )
                with self.store.transaction(workspace_id) as tx:
                    revised = {
                        **correct,
                        "id": new_id(),
                        "evaluation_version": correct.get("evaluation_version", 1) + 1,
                        "critic_status": "RESOLVED",
                        "supersedes_id": correct["id"],
                        "created_at": utc_now(),
                    }
                    tx.create("qualifications", revised)
                    tx.replace(
                        "critiques",
                        issue["id"],
                        {**issue, "status": "RESOLVED", "resolution_evidence_ids": correct["evidence_ids"]},
                    )
                    current = tx.require("runs", run_id)
                    current["qualification_ids"] = [
                        revised["id"] if q == correct["id"] else q for q in current["qualification_ids"]
                    ]
                    current.setdefault("runtime", {})["seeded_defect_completed"] = True
                    tx.replace("runs", run_id, current, current["revision"])
                    tx.append_event(
                        run_id,
                        "critic.issue_resolved",
                        {
                            "issue_id": issue["issue_id"],
                            "summary": "Revised qualification proposal cites common-support evidence",
                            "evidence_ids": correct["evidence_ids"],
                        },
                        run["mode"],
                    )
        for finding in audit.get("findings", []):
            issue_id = new_id()
            issue = {
                "issue_id": issue_id,
                "id": issue_id,
                "workspace_id": workspace_id,
                "run_id": run_id,
                "mode": run["mode"],
                "candidate_id": None,
                "requirement_id": finding["requirement_id"],
                "target_evidence_ids": finding["evidence_ids"],
                "reason_code": finding["rule_code"],
                "severity": finding["severity"],
                "status": "OPEN",
                "summary": finding["message"],
                "repair_request": finding["required_repair"],
                "resolution_evidence_ids": [],
            }
            with self.store.transaction(workspace_id) as tx:
                tx.create("critiques", issue)
        self._role(
            "scientific_critic",
            "review_qualification",
            run_id,
            workspace_id,
            {"review_revision_id": new_id(), "objections": []},
        )
        return False

    def apply_action(
        self,
        run_id: str,
        workspace_id: str,
        action: str,
        payload: dict[str, Any],
        expected_revision: int,
        *,
        uow: Any = None,
    ) -> dict[str, Any]:
        with nullcontext(uow) if uow is not None else self.store.transaction(workspace_id) as tx:
            run = tx.require("runs", run_id, lock=True)
            if run["revision"] != expected_revision:
                raise WorkflowError("REVISION_CONFLICT", "Run revision changed")
            if action == "PROVE_IT" and not run.get("rover_revision_id"):
                raise WorkflowError("ROVER_REQUIRED", "A saved rover is required for a modeled test")
            if action not in allowed_actions(run):
                raise WorkflowError("INVALID_TRANSITION", "Action is not allowed at this checkpoint")
            if action == "CANCEL":
                if run["state"] in TERMINAL:
                    return cast(dict[str, Any], run)
                run.update(state="CANCELLED", cancel_requested_at=utc_now())
                for job in tx.list("jobs", {"run_id": run_id}):
                    if job["state"] in {"QUEUED", "RUNNING"}:
                        tx.replace(
                            "jobs",
                            job["id"],
                            {**job, "state": "CANCELLED", "lease_token": None, "lease_expires_at": None},
                        )
            elif action == "SELECT_CANDIDATE":
                identifier = payload.get("candidate_id") or payload.get("candidate_revision_id")
                if identifier not in run["candidate_ids"]:
                    raise WorkflowError("INPUT_INVALID", "Candidate is not part of this run")
                candidate = tx.require("candidates", identifier)
                if not candidate.get("analysis_payload"):
                    raise WorkflowError("INVALID_TRANSITION", "Candidate has no registered analysis")
                run["selected_candidate_id"] = identifier
            elif action == "SELECT_PORTFOLIO":
                identifier = payload.get("portfolio_id") or payload.get("portfolio_revision_id")
                if identifier not in run["portfolio_ids"]:
                    raise WorkflowError("INPUT_INVALID", "Portfolio is not part of this run")
                run["selected_portfolio_id"] = identifier
            elif action == "PROVE_IT":
                candidate_id = (
                    payload.get("candidate_id")
                    or payload.get("candidate_revision_id")
                    or run.get("selected_candidate_id")
                )
                if candidate_id not in run["candidate_ids"]:
                    raise WorkflowError("INPUT_INVALID", "Candidate is not part of this run")
                candidate = tx.require("candidates", candidate_id)
                if not candidate.get("analysis_payload"):
                    raise WorkflowError("INVALID_TRANSITION", "Candidate has no registered analysis")
                run["selected_candidate_id"] = candidate_id
                run.update(state="DESIGNING_TEST", pending_review=None)
                run.setdefault("runtime", {})["strategy"] = "WAYPOINT_RETURN"
            elif action in {"APPROVE_EVIDENCE", "REJECT_EVIDENCE"}:
                review = run.get("pending_review")
                if not review or review["kind"] == "EVIDENCE_READY":
                    raise WorkflowError("INVALID_TRANSITION", "Only a material pending review can be resolved")
                run["pending_review"] = {**review, "status": "APPROVED" if action == "APPROVE_EVIDENCE" else "REJECTED"}
                run["state"] = "CRITIQUING"
            elif action == "RETRY":
                run["state"] = run["runtime"]["resume_state"]
                run["blocked_dependencies"] = []
            elif action in {"BUILD_PORTFOLIO", "NOMINATE_CANDIDATE"}:
                run.setdefault("runtime", {})["pending_action"] = {"type": action, "payload": payload}
            tx.replace("runs", run_id, run, expected_revision)
            tx.append_event(run_id, "run.action", {"action_type": action, "summary": action}, run["mode"])
            if action in {
                "PROVE_IT",
                "RETRY",
                "APPROVE_EVIDENCE",
                "REJECT_EVIDENCE",
                "BUILD_PORTFOLIO",
                "NOMINATE_CANDIDATE",
            }:
                tx.enqueue(
                    "ADVANCE_RUN",
                    {"run_id": run_id, "state": run["state"]},
                    run_id=run_id,
                    input_hash=canonical_sha256([run_id, action, expected_revision, payload]),
                )
            return cast(dict[str, Any], tx.require("runs", run_id))

    def _perform_pending_action(
        self,
        run_id: str,
        workspace_id: str,
        pending: dict[str, Any],
        mission: dict[str, Any],
        rover: dict[str, Any] | None,
        job_id: str | None,
        lease_token: str | None,
    ) -> None:
        run, _, _ = self._load(run_id, workspace_id)
        candidates = self._rows(workspace_id, "candidates", run_id)
        if pending["type"] == "BUILD_PORTFOLIO":
            rows = self._latest_qualifications(workspace_id, run_id)

            def publish(tx: Any, r: RegisteredResult) -> None:
                portfolio = portfolios.assemble(
                    workspace_id, run_id, run["mode"], r.required_payload, {c["window_id"]: c["id"] for c in candidates}
                )
                tx.create("portfolios", portfolio)
                fresh = tx.require("runs", run_id)
                fresh["portfolio_ids"].append(portfolio["id"])
                tx.replace("runs", run_id, fresh, fresh["revision"])

            self._compute(
                OptimizePortfolioInput(
                    requirements=mission["requirements"],
                    candidates=[discovery.reference(c) for c in candidates],
                    qualification_rows=[
                        QualificationRowInput(
                            candidate_window_id=next(
                                c["window_id"] for c in candidates if c["id"] == q["candidate_id"]
                            ),
                            requirement_id=q["requirement_id"],
                            status=q["status"],
                            evaluation_stage=q.get("evaluation_stage", "FINAL"),
                            critic_blocking_open=q["critic_status"] == "CHALLENGED",
                        )
                        for q in rows
                    ],
                    max_sites=int(pending["payload"].get("max_sites", 3)),
                ),
                run_id,
                workspace_id,
                job_id=job_id,
                lease_token=lease_token,
                publish=publish,
            )
        else:
            payload = pending["payload"]
            candidate = discovery.candidate_record(
                {
                    "window_id": payload.get("window_id", "user-" + new_id()),
                    "name": payload.get("name", "User nominated region"),
                    "aoi": payload["aoi"],
                    "origin": "USER_SUPPLIED",
                    "novelty_status": "NOT_ASSESSED",
                    "rank": None,
                },
                workspace_id,
                run_id,
                run["mode"],
                [],
            )
            if candidate["aoi"]["body"] != "EARTH":
                raise WorkflowError("INPUT_INVALID", "A nominated analog must be on Earth")
            with self.store.transaction(workspace_id) as tx:
                tx.create("candidates", candidate)
                fresh = tx.require("runs", run_id)
                fresh["candidate_ids"].append(candidate["id"])
                tx.replace("runs", run_id, fresh, fresh["revision"])
            scenario = self._scenario(run["scenario_config_id"])

            def publish(tx: Any, r: RegisteredResult) -> None:
                fresh = tx.require("candidates", candidate["id"])
                fresh.update(
                    analysis_payload=r.required_payload,
                    metrics=r.required_payload["metrics"],
                    evidence_ids=list(r.evidence_ids),
                    limitations=r.required_payload["limitations"],
                )
                tx.replace("candidates", candidate["id"], fresh)

            self._compute(
                AnalyzeCandidateInput(
                    candidate=discovery.reference(candidate),
                    source=scenario["earth_source"],
                    measurement_spec_id=catalog.MEASUREMENT_SPEC_EARTH,
                ),
                run_id,
                workspace_id,
                job_id=job_id,
                lease_token=lease_token,
                publish=publish,
            )
            refreshed = next(c for c in self._rows(workspace_id, "candidates", run_id) if c["id"] == candidate["id"])
            self._qualify(run_id, workspace_id, [refreshed], mission, rover, job_id=job_id, lease_token=lease_token)
