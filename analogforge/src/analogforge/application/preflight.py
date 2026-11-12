"""Truthful, stage-scoped readiness checks with no credential disclosure."""

from __future__ import annotations

import importlib
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from analogforge.application.capabilities import get_scenarios
from analogforge.application.datasets import DatasetError, read_lock
from analogforge.ports import catalog
from analogforge.ports.domain_models import AreaOfInterest
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import LocalScienceContext, ScienceOperation, ScienceRequest, SourcePolicy
from analogforge.ports.science_payloads import ResolveCoverageInput
from analogforge.settings import Settings

STAGES = ("RUNTIME", "STORAGE", "IDENTITY", "MODEL", "METADATA", "DOWNLOAD", "SCIENCE", "SCENARIO", "LOCK", "DATASETS")


def _gate(
    stage: str, code: str, severity: str, dependency: str, explanation: str, remediation: str = ""
) -> dict[str, str]:
    return {
        "stage": stage,
        "code": code,
        "severity": severity,
        "dependency": dependency,
        "checked_at": datetime.now(UTC).isoformat(),
        "explanation": explanation,
        "remediation": remediation,
    }


def _science_check(settings: Settings) -> tuple[bool, str, str]:
    try:
        module = importlib.import_module("analogforge.science.facade")
        service = module.create_science_service()
    except (ImportError, AttributeError) as exc:
        return False, "SCIENCE_FACADE_MISSING", f"Science facade entry point unavailable: {type(exc).__name__}"
    try:
        operations = set(service.supported_operations())
        missing = set(ScienceOperation) - operations
        if missing:
            return (
                False,
                "SCIENCE_OPERATION_MISSING",
                "Missing operations: " + ", ".join(sorted(str(op) for op in missing)),
            )
        aoi = AreaOfInterest(
            body="MARS",
            bbox=[137, -5, 138, -4],
            longitude_convention="NEG180_180",
            latitude_type="PLANETOCENTRIC",
            crs_wkt=None,
            vertical_datum="SYNTHETIC_MARS_REFERENCE_SPHERE_3396190M",
        )
        request = ScienceRequest(
            request_id=uuid4(),
            operation=ScienceOperation.RESOLVE_COVERAGE,
            mode="synthetic",
            inputs=ResolveCoverageInput(
                subject_kind="TARGET", aoi=aoi, adapter_id="synthetic_practice", measurement_kinds=["terrain"]
            ),
            source_policy=SourcePolicy(
                policy_id=catalog.DATASET_LOCK_SYNTHETIC,
                policy_sha256="0" * 64,
                allowed_adapter_ids=["synthetic_practice"],
                synthetic_fixture_ids=[catalog.FIXTURE_MARS_TARGET],
                allow_network=False,
            ),
        )
        with tempfile.TemporaryDirectory(prefix="af-science-probe-") as scratch:
            context = LocalScienceContext(scratch=Path(scratch), workspace_id=uuid4(), job_id=uuid4())
            result = service.execute(request, context)
        if result.status in {"FAILED", "BLOCKED"} or result.input_sha256 != canonical_sha256(request):
            return (
                False,
                "SCIENCE_PROBE_FAILED",
                f"Synthetic coverage probe returned {result.status} or an invalid request hash",
            )
        return (
            True,
            "SCIENCE_READY",
            f"All {len(operations)} science operations exposed; synthetic coverage probe succeeded",
        )
    except Exception as exc:  # noqa: BLE001 - preflight records a failed gate for any probe error
        return False, "SCIENCE_PROBE_FAILED", f"Science probe failed: {type(exc).__name__}"


def _renderer_check() -> tuple[bool, str, str]:
    try:
        module = importlib.import_module("analogforge.rendering.passport")
        renderer = module.create_passport_renderer()
        if not callable(getattr(renderer, "render", None)):
            return False, "RENDERER_MISSING", "Renderer entry point does not expose render()"
        return True, "RENDERER_READY", "Passport renderer entry point loaded"
    except (ImportError, AttributeError) as exc:
        return False, "RENDERER_MISSING", f"Passport renderer entry point unavailable: {type(exc).__name__}"


def run_preflight(
    settings: Settings, mode: str | None = None, scenario_id: str | None = None, store: Any = None
) -> dict[str, Any]:
    mode = mode or settings.analogforge_mode
    scenario_id = scenario_id or settings.scenario_default
    gates: list[dict[str, str]] = []

    def add(
        stage: str,
        passed: bool,
        code: str,
        dependency: str,
        explanation: str,
        remediation: str = "",
        required: bool = True,
    ) -> None:
        gates.append(
            _gate(
                stage,
                code,
                "PASS" if passed else ("FAIL" if required else "WARN"),
                dependency,
                explanation,
                remediation,
            )
        )

    try:
        import numpy  # noqa: F401
        import pyproj  # noqa: F401
        import rasterio
        import scipy  # noqa: F401

        with rasterio.Env() as env:
            drivers = env.drivers()
        missing = [driver for driver in ("GTiff", "HFA", "PDS", "netCDF", "AAIGrid") if driver not in drivers]
        add(
            "RUNTIME",
            not missing,
            "RUNTIME_READY" if not missing else "GDAL_DRIVER_MISSING",
            "GDAL",
            "Missing drivers: " + ", ".join(missing)
            if missing
            else "Scientific runtime and required GDAL drivers import",
            "Install a rasterio/GDAL build with the required drivers",
        )
    except Exception as exc:  # noqa: BLE001 - preflight records a failed gate for any probe error
        add(
            "RUNTIME",
            False,
            "RUNTIME_IMPORT_FAILED",
            "science dependencies",
            f"Scientific runtime import failed: {type(exc).__name__}",
            "Install the locked Python dependencies",
        )
    try:
        settings.data_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.data_root, delete=False) as file:
            file.write(b"atomic-test")
            temp = Path(file.name)
        target = temp.with_suffix(".renamed")
        temp.replace(target)
        target.unlink()
        free = shutil.disk_usage(settings.data_root).free
        add(
            "STORAGE",
            free >= 10 * 1024**3,
            "STORAGE_READY" if free >= 10 * 1024**3 else "STORAGE_SPACE_LOW",
            "DATA_ROOT",
            "Writable atomic storage; free bytes=" + str(free),
            "Provide at least 10 GiB free space",
            required=mode == "live",
        )
    except Exception as exc:  # noqa: BLE001 - preflight records a failed gate for any probe error
        add(
            "STORAGE",
            False,
            "STORAGE_UNAVAILABLE",
            "DATA_ROOT",
            f"Storage probe failed: {type(exc).__name__}",
            "Make DATA_ROOT writable",
        )
    if store is not None:
        healthy = False
        try:
            healthy = bool(store.health())
            add(
                "STORAGE",
                healthy,
                "DATABASE_READY" if healthy else "DATABASE_UNAVAILABLE",
                "DATABASE_URL",
                "Database readiness checked",
                "Start PostgreSQL/PostGIS and run migrations",
            )
        except Exception:  # noqa: BLE001 - unavailable storage is a failed gate
            add(
                "STORAGE",
                False,
                "DATABASE_UNAVAILABLE",
                "DATABASE_URL",
                "Database readiness failed",
                "Start PostgreSQL/PostGIS and run migrations",
            )
        if healthy and hasattr(store, "engine"):
            try:
                import sqlalchemy as sa
                from alembic.config import Config
                from alembic.migration import MigrationContext
                from alembic.script import ScriptDirectory

                config = Config()
                config.set_main_option(
                    "script_location", str(Path(__file__).resolve().parents[1] / "db" / "migrations")
                )
                head = ScriptDirectory.from_config(config).get_current_head()
                with store.engine.connect() as connection:
                    current = MigrationContext.configure(connection).get_current_revision()
                    encoding = connection.execute(sa.text("SHOW server_encoding")).scalar_one()
                add(
                    "STORAGE",
                    current == head,
                    "MIGRATION_CURRENT" if current == head else "MIGRATION_REQUIRED",
                    "DATABASE_URL",
                    f"Current schema revision={current}; expected={head}",
                    "Run analogforge migrate",
                )
                add(
                    "STORAGE",
                    encoding == "UTF8",
                    "DATABASE_ENCODING_UTF8" if encoding == "UTF8" else "DATABASE_ENCODING_UNSUPPORTED",
                    "DATABASE_URL",
                    f"Database server encoding={encoding}",
                    "Create a UTF8 database from template0",
                )
            except Exception:  # noqa: BLE001 - schema inspection failure is a failed gate
                add(
                    "STORAGE",
                    False,
                    "MIGRATION_CHECK_FAILED",
                    "DATABASE_URL",
                    "Cannot inspect schema revision",
                    "Run analogforge migrate",
                )
    add("IDENTITY", True, "IDENTITY_READY", "AUTH_MODE", f"{settings.auth_mode} binding validated by typed settings")
    if mode == "live":
        add(
            "MODEL",
            bool(settings.openai_api_key),
            "MODEL_READY" if settings.openai_api_key else "MODEL_KEY_MISSING",
            "OPENAI_API_KEY",
            "Live model key configured" if settings.openai_api_key else "Live model key missing",
            "Set OPENAI_API_KEY server-side",
        )
        add(
            "MODEL",
            bool(settings.openai_model),
            "MODEL_NAME_READY" if settings.openai_model else "MODEL_NAME_MISSING",
            "OPENAI_MODEL",
            "Live model id configured" if settings.openai_model else "Live model id missing",
            "Set an explicit OPENAI_MODEL",
        )
        if settings.openai_api_key and settings.openai_model:
            try:
                client_module = importlib.import_module("analogforge.adapters.openai.client")
                probe = importlib.import_module("analogforge.adapters.openai.probe")
                client = client_module.ResponsesClient(
                    settings.openai_api_key.get_secret_value(),
                    settings.openai_model,
                    base_url=settings.fake_openai_url if settings.test_hooks else None,
                )
                probe.probe(client)
                add(
                    "MODEL",
                    True,
                    "MODEL_CAPABILITY_READY",
                    "OpenAI Responses API",
                    "Strict tool and structured result probe passed",
                )
            except Exception as exc:  # noqa: BLE001 - model provider errors become a failed gate
                add(
                    "MODEL",
                    False,
                    "MODEL_CAPABILITY_FAILED",
                    "OpenAI Responses API",
                    f"Model capability probe failed: {type(exc).__name__}",
                    "Check model access and strict tool support",
                )
    else:
        add("MODEL", True, "MODEL_NOT_REQUIRED", "OpenAI", f"{mode} mode does not construct a model provider")
    try:
        scenarios = get_scenarios(settings)
        scenario = scenarios[scenario_id]
        add(
            "SCENARIO",
            mode in scenario["allowed_modes"] and scenario["status"] == "AVAILABLE",
            "SCENARIO_READY"
            if mode in scenario["allowed_modes"] and scenario["status"] == "AVAILABLE"
            else "SCENARIO_MODE_UNAVAILABLE",
            scenario_id,
            f"Scenario status={scenario['status']}; allowed modes={scenario['allowed_modes']}",
            "Bind required datasets or choose an available mode",
        )
    except Exception as exc:  # noqa: BLE001 - malformed scenario is a failed gate
        scenario = None
        add(
            "SCENARIO",
            False,
            "SCENARIO_CONFIG_INVALID",
            scenario_id,
            f"Scenario configuration failed: {exc}",
            "Repair config/scenarios.yaml",
        )
    required_config_keys = {
        "datasets.yaml": ("adapters",),
        "algorithms.yaml": (
            "algorithm_lock",
            "measurement_specs",
            "observable_policies",
            "grid",
            "route_search",
            "energy_defaults",
            "thresholds",
            "fixtures",
        ),
        "candidates.yaml": ("search_region_sets", "reference_sets"),
    }
    for filename, required_keys in required_config_keys.items():
        path = settings.config_dir / filename
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            missing_keys = (
                sorted(set(required_keys) - set(document)) if isinstance(document, dict) else list(required_keys)
            )
            add(
                "METADATA",
                not missing_keys,
                "CONFIG_READY" if not missing_keys else "CONFIG_KEY_MISSING",
                filename,
                "Configuration parsed with required keys"
                if not missing_keys
                else "Missing keys: " + ", ".join(missing_keys),
                "Restore the required config keys",
            )
        except Exception:  # noqa: BLE001 - missing or invalid config becomes a failed gate
            add(
                "METADATA",
                False,
                "CONFIG_MISSING",
                filename,
                "Required configuration is missing",
                f"Install config/{filename}",
            )
    add(
        "DOWNLOAD",
        True,
        "DOWNLOAD_OFFLINE" if mode != "live" else "DOWNLOAD_DEFERRED",
        "source adapters",
        "No network download is required by this preflight"
        if mode != "live"
        else "Bound local datasets are verified under DATASETS",
    )
    science_ok, science_code, science_message = _science_check(settings)
    add(
        "SCIENCE",
        science_ok,
        science_code,
        "analogforge.science.facade",
        science_message,
        "Install the science facade and its runtime dependencies",
    )
    renderer_ok, renderer_code, renderer_message = _renderer_check()
    add(
        "SCIENCE",
        renderer_ok,
        renderer_code,
        "analogforge.rendering.passport",
        renderer_message,
        "Install the passport renderer",
    )
    if scenario:
        policy_id = scenario["default_dataset_lock_id"]
        try:
            lock = read_lock(settings, policy_id)
            add("LOCK", True, "LOCK_READY", policy_id, "Policy hash and source files match")
        except DatasetError as exc:
            lock = None
            add("LOCK", False, exc.code, policy_id, str(exc), "Create or restore the source-policy lock")
        sources = [
            scenario.get("target_source"),
            scenario.get("earth_source"),
            *(scenario.get("additional_sources") or {}).values(),
        ]
        bound = [source["dataset_id"] for source in sources if source and source.get("kind") == "LOCAL_DATASET"]
        missing_slots = [
            name
            for name, key in (("target_terrain", "target_source"), ("earth_terrain", "earth_source"))
            if not scenario.get(key)
        ]
        if missing_slots and not bound:
            add(
                "DATASETS",
                False,
                "DATASETS_UNBOUND",
                ", ".join(missing_slots),
                "Required dataset slots are unbound: " + ", ".join(missing_slots),
                "Run analogforge scenario bind",
            )
        if missing_slots and bound:
            add("DATASETS", True, "PARTIAL_DATASETS", ", ".join(missing_slots),
                "Partial investigation: missing sources remain UNKNOWN / NO_COVERAGE; no substitute is used")
        if bound:
            lock_entries = {entry["dataset_id"]: entry for entry in lock["datasets"]} if lock else {}
            missing = sorted(set(bound) - set(lock_entries))
            role_errors = []
            for key, role in (("target_source", "TARGET_TERRAIN"), ("earth_source", "EARTH_TERRAIN")):
                source = scenario[key]
                if source and source.get("kind") == "LOCAL_DATASET":
                    entry = lock_entries.get(source["dataset_id"])
                    if entry and (entry["role"] != role or not entry["usable_for_quantitative_claims"]):
                        role_errors.append(source["dataset_id"])
            add(
                "DATASETS",
                not missing and not role_errors,
                "DATASETS_READY" if not missing and not role_errors else "DATASETS_UNBOUND",
                policy_id,
                "Bound datasets are locked and usable"
                if not missing and not role_errors
                else "Missing or unusable: " + ", ".join(missing + role_errors),
                "Validate and lock the bound datasets",
            )
        elif not missing_slots:
            add(
                "DATASETS",
                True,
                "SYNTHETIC_FIXTURES_READY",
                policy_id,
                "Scenario uses frozen synthetic fixture selectors",
            )
    else:
        add("LOCK", False, "SCENARIO_CONFIG_INVALID", scenario_id, "Cannot inspect lock until scenario is valid")
        add(
            "DATASETS", False, "SCENARIO_CONFIG_INVALID", scenario_id, "Cannot inspect datasets until scenario is valid"
        )
    return {
        "status": "PASS" if all(g["severity"] != "FAIL" for g in gates) else "FAIL",
        "mode": mode,
        "scenario_id": scenario_id,
        "gates": gates,
    }
