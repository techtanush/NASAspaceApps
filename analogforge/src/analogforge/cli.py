"""Operator command line for local runtime, datasets, and readiness checks."""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from analogforge.application.capabilities import get_scenarios, save_scenarios
from analogforge.application.datasets import (
    DatasetError,
    create_lock,
    generate_mock_nasa_drop,
    generate_practice,
    list_datasets,
    load_manifest,
    read_lock,
    scaffold_dataset,
    validate_dataset,
)
from analogforge.application.preflight import run_preflight
from analogforge.application.seed import seed_synthetic
from analogforge.settings import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="analogforge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    sub.add_parser("worker")
    migrate = sub.add_parser("migrate")
    migrate.add_argument("--check", action="store_true")
    db = sub.add_parser("db")
    db.add_argument("action", choices=["up", "down", "status"])
    sub.add_parser("seed-synthetic")
    rehearsal = sub.add_parser("rehearsal")
    rehearsal.add_argument("action", choices=["bind-live-slot", "restore-live-slot"])
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--mode", choices=["synthetic", "replay", "live"])
    preflight.add_argument("--scenario")
    preflight.add_argument("--output", type=Path)
    datasets = sub.add_parser("datasets")
    dataset_sub = datasets.add_subparsers(dest="dataset_action", required=True)
    dataset_sub.add_parser("list")
    scaffold = dataset_sub.add_parser("scaffold")
    scaffold.add_argument("dataset_id")
    scaffold.add_argument("--body", choices=["EARTH", "MOON", "MARS"], required=True)
    scaffold.add_argument("--role", required=True)
    validate = dataset_sub.add_parser("validate")
    validate.add_argument("dataset_id")
    validate.add_argument("--write-checksums", action="store_true")
    lock = dataset_sub.add_parser("lock")
    lock.add_argument("--policy-id", required=True)
    lock.add_argument("--datasets", nargs="+", required=True)
    dataset_sub.add_parser("generate-practice")
    dataset_sub.add_parser("generate-mock-nasa-drop")
    scenario = sub.add_parser("scenario")
    scenario_sub = scenario.add_subparsers(dest="scenario_action", required=True)
    show = scenario_sub.add_parser("show")
    show.add_argument("scenario_id")
    bind = scenario_sub.add_parser("bind")
    bind.add_argument("scenario_id")
    bind.add_argument("--target-terrain")
    bind.add_argument("--earth-terrain")
    bind.add_argument("--earth-mineral")
    bind.add_argument("--lunar-thermal")
    bind.add_argument("--policy-id")
    export = sub.add_parser("export-openapi")
    export.add_argument("--out", type=Path, required=True)
    sub.add_parser("science-check")
    sub.add_parser("assurance-selftest")
    return parser


def _store(settings: Settings) -> Any:
    from analogforge.db.store import Store

    return Store(settings.database_url)


def _db(settings: Settings, action: str) -> dict[str, Any]:
    compose = Path(__file__).resolve().parents[2] / "compose.yaml"
    if not compose.exists():
        raise RuntimeError("compose.yaml is missing")
    runtime = settings.data_root.parent / ".runtime" / "db.json"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    private_cluster = runtime.parent / "pg"
    pid_file = private_cluster / "postmaster.pid"
    pid_lines = pid_file.read_text(encoding="ascii").splitlines() if pid_file.is_file() else []
    active_port = int(pid_lines[3]) if len(pid_lines) > 3 and pid_lines[3].isdecimal() else None
    native_selected = (private_cluster / "PG_VERSION").is_file() and (
        active_port == settings.db_port or (active_port is None and settings.profile == "tanush")
    )
    if native_selected and shutil.which("pg_ctl"):
        command = [settings.postgres_tool("pg_ctl"), "-D", str(private_cluster)]
        if action == "up":
            status = subprocess.run([*command, "status"], capture_output=True, check=False)  # noqa: S603
            if status.returncode:
                command += [
                    "-l",
                    str(runtime.parent / "postgres.log"),
                    "-o",
                    f"-h 127.0.0.1 -p {settings.db_port}",
                    "start",
                ]
            else:
                command += ["status"]
        elif action == "down":
            command += ["stop", "-m", "fast"]
        else:
            command += ["status"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)  # noqa: S603
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip() or "Native PostgreSQL command failed")
        state = {"backend": "native", "action": action, "cluster": str(private_cluster), "db_port": settings.db_port}
    else:
        if not shutil.which("docker"):
            raise RuntimeError("No private native cluster or Docker; use the native PostgreSQL bootstrap runbook")
        command = ["docker", "compose", "-f", str(compose)]
        command += ["up", "-d", "db"] if action == "up" else ["stop", "db"] if action == "down" else ["ps", "db"]
        result = subprocess.run(command, text=True, capture_output=True, check=False)  # noqa: S603 - fixed argv
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip() or "Docker Compose failed")
        state = {"backend": "docker", "action": action, "compose_file": str(compose), "db_port": settings.db_port}
    runtime.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state


def _bind(settings: Settings, args: argparse.Namespace) -> dict[str, Any]:
    scenarios = get_scenarios(settings)
    if args.scenario_id not in scenarios:
        raise DatasetError("SCENARIO_UNKNOWN", f"Unknown scenario {args.scenario_id}")
    scenario = scenarios[args.scenario_id]
    if args.scenario_id not in {"live-hackathon-v1", "local-dataset-practice-v1"}:
        raise DatasetError("SCENARIO_BIND_FORBIDDEN", "Only the live and local dataset scenarios are operator-bindable")
    live = args.scenario_id == "live-hackathon-v1"
    if not (args.target_terrain or args.earth_terrain):
        raise DatasetError("DATASETS_UNBOUND", "Bind at least one target or Earth terrain product")
    policy_id = args.policy_id or scenario["default_dataset_lock_id"]
    lock = read_lock(settings, policy_id)
    entries = {entry["dataset_id"]: entry for entry in lock["datasets"]}
    requested = {
        "target_terrain": args.target_terrain,
        "earth_terrain": args.earth_terrain,
        "earth_mineral": args.earth_mineral,
        "lunar_thermal": args.lunar_thermal,
    }
    role_by_option = {
        "target_terrain": "TARGET_TERRAIN",
        "earth_terrain": "EARTH_TERRAIN",
        "earth_mineral": "EARTH_MINERAL",
        "lunar_thermal": "LUNAR_THERMAL",
    }
    for option, dataset_id in requested.items():
        if dataset_id is None:
            continue
        entry = entries.get(dataset_id)
        if entry is None:
            raise DatasetError("DATASETS_UNBOUND", f"{dataset_id} is not in lock {policy_id}")
        synthetic = load_manifest(settings, dataset_id).is_synthetic
        if synthetic and live:
            raise DatasetError("MODE_MISMATCH", f"Synthetic dataset {dataset_id} cannot bind to a live scenario")
        if not synthetic and not live:
            raise DatasetError(
                "MODE_MISMATCH", f"Non-synthetic dataset {dataset_id} cannot bind to a synthetic scenario"
            )
        if entry["role"] != role_by_option[option]:
            raise DatasetError(
                "DATASET_ROLE_MISMATCH", f"{dataset_id} has role {entry['role']}, expected {role_by_option[option]}"
            )
        if option in {"target_terrain", "earth_terrain"} and not entry["usable_for_quantitative_claims"]:
            raise DatasetError(
                "DATASET_NOT_USABLE", f"{dataset_id} is preview-only and cannot support a mandatory role"
            )
        if option == "target_terrain" and entry["body"] != scenario["body"]:
            scenario["body"] = entry["body"]
    scenario["target_source"] = (
        {"kind": "LOCAL_DATASET", "dataset_id": args.target_terrain} if args.target_terrain else None
    )
    scenario["earth_source"] = (
        {"kind": "LOCAL_DATASET", "dataset_id": args.earth_terrain} if args.earth_terrain else None
    )
    # The fixed practice recipe describes its declared fixture extent. An operator's
    # replacement terrain must be screened over that dataset's own bounded extent.
    scenario["search_region_set_id"] = (
        "practice-earth-grid-v1" if args.earth_terrain == "practice-earth-grid-v1" else "local-dataset-grid-v1"
    )
    scenario["additional_sources"] = {
        name: {"kind": "LOCAL_DATASET", "dataset_id": dataset_id}
        for name, dataset_id in requested.items()
        if name in {"earth_mineral", "lunar_thermal"} and dataset_id
    }
    scenario["default_dataset_lock_id"] = policy_id
    scenario["status"] = "AVAILABLE"
    scenario["allowed_modes"] = ["live" if live else "synthetic"]
    save_scenarios(settings, scenarios)
    return {
        "scenario_id": args.scenario_id,
        "status": scenario["status"],
        "dataset_lock_id": policy_id,
        "bindings": requested,
    }


def _migrate(settings: Settings, check: bool) -> dict[str, Any]:
    store = _store(settings)
    try:
        if check:
            from alembic.config import Config
            from alembic.migration import MigrationContext
            from alembic.script import ScriptDirectory

            config = Config()
            config.set_main_option("script_location", str(Path(__file__).resolve().parent / "db" / "migrations"))
            head = ScriptDirectory.from_config(config).get_current_head()
            with store.engine.connect() as connection:
                current = MigrationContext.configure(connection).get_current_revision()
            if current != head:
                raise RuntimeError(f"Database migration is {current}, expected {head}")
            return {"status": "PASS", "revision": current}
        store.migrate()
        return {"status": "PASS", "revision": "head"}
    finally:
        store.close()


def _run(args: argparse.Namespace, settings: Settings) -> dict[str, Any]:
    if args.command == "serve":
        import uvicorn

        uvicorn.run("analogforge.main:app", host=settings.api_host, port=settings.api_port, reload=False)
        return {"status": "STOPPED"}
    if args.command == "worker":
        import signal

        from analogforge.jobs.worker import Worker
        from analogforge.main import PlatformRuntime

        store = _store(settings)
        runtime = PlatformRuntime(settings, store)
        worker = Worker(
            store,
            runtime.handle_job,
            lease_seconds=settings.job_lease_seconds,
            heartbeat_seconds=settings.job_heartbeat_seconds,
        )
        signal.signal(signal.SIGTERM, lambda *_: worker.stop())
        signal.signal(signal.SIGINT, lambda *_: worker.stop())
        try:
            worker.run_forever()
        finally:
            store.close()
        return {"status": "STOPPED"}
    if args.command == "migrate":
        return _migrate(settings, args.check)
    if args.command == "db":
        return _db(settings, args.action)
    if args.command == "seed-synthetic":
        store = _store(settings)
        try:
            return seed_synthetic(store, settings)
        finally:
            store.close()
    if args.command == "preflight":
        store = _store(settings)
        try:
            report = run_preflight(settings, args.mode, args.scenario, store=store)
        finally:
            store.close()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report
    if args.command == "rehearsal":
        from analogforge.application.rehearsal import bind_live_slot, restore_live_slot

        return bind_live_slot(settings) if args.action == "bind-live-slot" else restore_live_slot(settings)
    if args.command == "datasets":
        action = args.dataset_action
        if action == "list":
            return {"datasets": list_datasets(settings)}
        if action == "scaffold":
            return scaffold_dataset(settings, args.dataset_id, args.body, args.role)
        if action == "validate":
            return validate_dataset(settings, args.dataset_id, args.write_checksums)
        if action == "lock":
            return create_lock(settings, args.policy_id, args.datasets)
        if action == "generate-practice":
            return {"dataset_ids": generate_practice(settings)}
        if action == "generate-mock-nasa-drop":
            return {"dataset_ids": generate_mock_nasa_drop(settings)}
    if args.command == "scenario":
        if args.scenario_action == "show":
            return {"id": args.scenario_id, **get_scenarios(settings)[args.scenario_id]}
        return _bind(settings, args)
    if args.command == "export-openapi":
        from analogforge.main import app

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"status": "PASS", "out": str(args.out)}
    if args.command == "science-check":
        from analogforge.application.preflight import _science_check

        passed, code, explanation = _science_check(settings)
        return {"status": "PASS" if passed else "FAIL", "code": code, "explanation": explanation}
    if args.command == "assurance-selftest":
        module = importlib.import_module("analogforge.application.assurance")
        snapshot = module.AuditSnapshot(
            workspace_id=uuid4(),
            run_id=uuid4(),
            mode="synthetic",
            mission_content_sha256="0" * 64,
            rover_content_sha256=None,
            dataset_policy_sha256="0" * 64,
            acquired_manifest_sha256="0" * 64,
            algorithm_lock_sha256="0" * 64,
            assurance_policy_sha256="0" * 64,
            snapshot_content={},
            evidence={},
        )
        unsupported = module.audit(
            snapshot,
            [
                module.ClaimInput(
                    claim_id="unsupported-positive",
                    claim_type="QUALIFICATION",
                    requirement_id="R-TEST",
                    candidate_ids=(),
                    scope="selftest",
                    evidence_ids=(),
                    qualification_status="PASS",
                )
            ],
            [],
        )
        unknown = module.audit(
            snapshot,
            [
                module.ClaimInput(
                    claim_id="visible-unknown",
                    claim_type="QUALIFICATION",
                    requirement_id="R-TEST",
                    candidate_ids=(),
                    scope="selftest",
                    evidence_ids=(),
                    qualification_status="UNKNOWN",
                )
            ],
            [],
        )
        if unsupported.publication != "BLOCKED" or unknown.publication != "LIMITED":
            raise RuntimeError("Assurance claim gate selftest failed")
        return {
            "status": "PASS",
            "unsupported_positive": unsupported.publication,
            "visible_unknown": unknown.publication,
        }
    raise RuntimeError("Unknown command")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in argv
    argv = [arg for arg in argv if arg != "--json"]
    args = _parser().parse_args(argv)
    try:
        result = _run(args, Settings())
        if json_mode or args.command not in {"serve", "worker"}:
            sys.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
        return 0 if result.get("status") not in {"FAIL", "BLOCKED"} else 1
    except Exception as exc:  # noqa: BLE001 - CLI converts all operator errors to JSON and nonzero exit
        code = exc.code if isinstance(exc, DatasetError) else type(exc).__name__.upper()
        message = str(exc) if isinstance(exc, (DatasetError, RuntimeError)) else "Operation failed; see error code"
        sys.stderr.write(json.dumps({"status": "FAIL", "code": code, "message": message}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
