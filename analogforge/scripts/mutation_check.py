#!/usr/bin/env python3
"""Run the twenty guide-09 mutants in temporary source copies with assertion-sensitive kills."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from analogforge.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "analogforge"


@dataclass(frozen=True)
class Mutant:
    id: str
    description: str
    source: str
    before: str
    after: str
    test: str


MUTANTS = (
    Mutant(
        "M1",
        "skip artifact rehash",
        "application/registrar.py",
        "hashlib.sha256(content).hexdigest() != artifact_draft.sha256",
        "False",
        "tests/unit/platform/test_registrar.py::test_rejections_do_not_publish_domain_or_evidence",
    ),
    Mutant(
        "M2",
        "ignore idempotency body hash",
        "db/store.py",
        'existing["body_hash"] != body_hash',
        "False",
        "tests/integration/platform/test_idempotency_revisions.py::test_idempotency_hash_and_original_response",
    ),
    Mutant(
        "M3",
        "remove lease token predicate",
        "db/store.py",
        "table.c.lease_token == str(token)",
        "sa.true()",
        "tests/integration/platform/test_jobs_leases.py::test_unexpired_lease_requires_exact_owner_token",
    ),
    Mutant(
        "M4",
        "accept foreign workspace evidence",
        "domain/policy.py",
        'str(record["workspace_id"]) != str(snapshot["workspace_id"])',
        "False",
        "tests/unit/platform/test_policy.py::test_fabricated_or_foreign_evidence_cannot_support_claim",
    ),
    Mutant(
        "M5",
        "permit fourth replan",
        "domain/budgets.py",
        'if self.remaining(key) < 1 or self.remaining("replans_total") < 1:\n'
        "            raise BudgetExceeded(key)\n"
        "        self.charge(key)\n"
        '        self.charge("replans_total")',
        "self.counters[key] = self.counters.get(key, 0) + 1\n"
        '        self.counters["replans_total"] = self.counters.get("replans_total", 0) + 1',
        "tests/unit/platform/test_budgets.py::test_route_and_candidate_replans_share_total_cap",
    ),
    Mutant(
        "M6",
        "treat missing science gate as satisfied",
        "application/assurance.py",
        'not proposal.evidence_ids or any(g.outcome in {"UNSATISFIED", "NOT_ASSESSED"} for g in gates.values())',
        'not proposal.evidence_ids or any(g.outcome in {"UNSATISFIED"} for g in gates.values())',
        "tests/integration/platform/test_assurance.py::test_missing_gate_is_not_assessed_not_success",
    ),
    Mutant(
        "M7",
        "include foreign bytes in manifest digest",
        "application/passports.py",
        "digest = bytes_sha256(canonical)",
        'digest = bytes_sha256(canonical + b"manifest_sha256")',
        "tests/integration/platform/test_passport_assembly.py::test_manifest_is_independently_reproducible_and_acyclic",
    ),
    Mutant(
        "M8",
        "allow live run without key",
        "application/runs.py",
        "if not getattr(settings, field, None):",
        "if False and not getattr(settings, field, None):",
        "tests/integration/platform/test_seed_and_capabilities.py::test_live_run_requires_each_model_dependency",
    ),
    Mutant(
        "M9",
        "advance SSE cursor on heartbeat",
        "api/sse.py",
        'yield ": heartbeat\\n\\n"',
        'cursor += 1\n            yield ": heartbeat\\n\\n"',
        "tests/integration/platform/test_sse.py::test_actual_stream_heartbeat_does_not_skip_next_committed_event",
    ),
    Mutant(
        "M10",
        "inject wall clock into frozen export input",
        "application/exports.py",
        "rendered = actual_renderer.render(bundle, assets, fmt)",
        'rendered = actual_renderer.render(bundle.model_copy(update={"generated_at": '
        '__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}), assets, fmt)',
        "tests/integration/platform/test_exports.py::test_platform_passes_frozen_export_time_to_renderer",
    ),
    Mutant(
        "M11",
        "accept PROVE_IT without rover",
        "application/scheduler.py",
        'if action == "PROVE_IT" and not run.get("rover_revision_id"):',
        "if False:",
        "tests/unit/platform/test_policy.py::test_prove_it_requires_rover_at_action_boundary",
    ),
    Mutant(
        "M12",
        "skip frozen contract hash on repair",
        "domain/policy.py",
        "if contract_hash != preserved_hash:",
        "if False:",
        "tests/unit/platform/test_policy.py::test_immutable_contract_and_unpermitted_repair",
    ),
    Mutant(
        "M13",
        "bind synthetic data to live slot",
        "cli.py",
        "if load_manifest(settings, dataset_id).is_synthetic:",
        "if False:",
        "tests/integration/platform/test_dataset_cli.py::test_live_slot_rejects_synthetic_lock",
    ),
    Mutant(
        "M14",
        "write DSN to application log",
        "settings.py",
        'return self.model_dump(mode="json", exclude=excluded)',
        '__import__("logging").getLogger("analogforge").warning(self.database_url)\n'
        '        return self.model_dump(mode="json", exclude=excluded)',
        "tests/unit/platform/test_secrets.py::test_secret_values_absent_from_public_surfaces",
    ),
    Mutant(
        "M15",
        "remove workspace filter from list",
        "db/store.py",
        "query = sa.select(table.c.document_json).where(table.c.workspace_id == self.workspace_id)",
        "query = sa.select(table.c.document_json).where(sa.true())",
        "tests/integration/platform/test_workspace_isolation.py::test_workspace_get_and_lists_never_leak",
    ),
    Mutant(
        "M16",
        "default unknown observable to slope policy",
        "application/scheduler.py",
        'row["observable"], "unsupported-observable"',
        'row["observable"], "slope-band-area-fraction-v1"',
        "tests/unit/platform/test_policy.py::test_unknown_observable_selects_unsupported_policy",
    ),
    Mutant(
        "M17",
        "ignore open blocking critic",
        "application/assurance.py",
        'and c.status == "OPEN"',
        "and False",
        "tests/integration/platform/test_assurance.py::test_unresolved_critic_rejects_positive_but_preserves_negative",
    ),
    Mutant(
        "M18",
        "ignore cancellation at publication",
        "db/store.py",
        'if run.get("cancel_requested_at") or run["state"] == "CANCELLED":',
        "if False:",
        "tests/integration/platform/test_jobs_leases.py::test_cancellation_marker_fences_even_when_job_lease_is_valid",
    ),
    Mutant(
        "M19",
        "accept wrong science input hash",
        "application/registrar.py",
        "request.mode,\n            canonical_sha256(request),",
        "request.mode,\n            result.input_sha256,",
        "tests/unit/platform/test_registrar.py::test_rejections_do_not_publish_domain_or_evidence",
    ),
    Mutant(
        "M20",
        "make passport assurance FK nullable",
        "db/schema.py",
        '_uuid("assurance_evidence_id", False)',
        '_uuid("assurance_evidence_id", True)',
        "tests/integration/platform/test_seed_and_capabilities.py::test_passport_metadata_requires_assurance_evidence",
    ),
)


def run_test(test: str, source_root: Path | None = None) -> str:
    environment = Settings().pg_subprocess_environment()
    if source_root is not None:
        environment["PYTHONPATH"] = str(source_root) + os.pathsep + environment.get("PYTHONPATH", "")
    try:
        result = subprocess.run(  # noqa: S603 - fixed local pytest executable and declared tests
            [sys.executable, "-m", "pytest", test, "-q", "--tb=short", "--disable-warnings", "-p", "no:randomly"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return "PASS"
    if result.returncode == 1 and re.search(r"(?:AssertionError|Failed:|E\s+assert\b)", output):
        return "ASSERTION_FAILED"
    if "ERROR " in output or "errors during collection" in output:
        return "SETUP_OR_IMPORT_ERROR"
    return "OTHER_FAILURE"


def mutated_source(mutant: Mutant, destination: Path) -> bool:
    shutil.copytree(PACKAGE, destination / "src" / "analogforge", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in (".env", "config"):
        original = ROOT / name
        if original.exists():
            (destination / name).symlink_to(original, target_is_directory=original.is_dir())
    source = destination / "src" / "analogforge" / mutant.source
    if not source.is_file():
        return False
    content = source.read_text(encoding="utf-8")
    if content.count(mutant.before) != 1:
        return False
    source.write_text(content.replace(mutant.before, mutant.after, 1), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    parser.add_argument("--only", nargs="*", help="Optional mutant IDs for a focused rerun")
    args = parser.parse_args()
    selected = [mutant for mutant in MUTANTS if not args.only or mutant.id in args.only]
    baselines: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    for mutant in selected:
        if mutant.test not in baselines:
            baselines[mutant.test] = run_test(mutant.test)
        baseline = baselines[mutant.test]
        if baseline != "PASS":
            status = "BASELINE_FAILED"
        else:
            with tempfile.TemporaryDirectory(prefix=f"af-{mutant.id.lower()}-") as directory:
                destination = Path(directory)
                if not mutated_source(mutant, destination):
                    status = "MUTATION_NOT_APPLIED"
                else:
                    outcome = run_test(mutant.test, destination / "src")
                    status = (
                        "KILLED" if outcome == "ASSERTION_FAILED" else ("SURVIVED" if outcome == "PASS" else outcome)
                    )
        rows.append(
            {
                "id": mutant.id,
                "description": mutant.description,
                "test": mutant.test,
                "baseline": baseline,
                "status": status,
            }
        )
        print(f"{mutant.id}: {status}", flush=True)
    report = {
        "status": "PASS" if len(rows) == 20 and all(row["status"] == "KILLED" for row in rows) else "FAIL",
        "mutants": rows,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"mutation_check: {report['status']} ({sum(row['status'] == 'KILLED' for row in rows)}/{len(rows)} killed)")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
