"""Scenario configuration and public capability reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from analogforge.ports import catalog
from analogforge.settings import Settings


def get_scenarios(settings: Settings) -> dict[str, dict[str, Any]]:
    path = settings.config_dir / "scenarios.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config/scenarios.yaml must be a mapping")
    expected = set(catalog.ALL_SCENARIOS)
    if set(raw) != expected:
        missing = sorted(expected - set(raw))
        extra = sorted(set(raw) - expected)
        raise ValueError(f"scenario ids differ from frozen catalog: missing={missing}, extra={extra}")
    for scenario_id, scenario in raw.items():
        if not isinstance(scenario, dict):
            raise ValueError(f"scenario {scenario_id} must be a mapping")
        for field in (
            "name",
            "body",
            "description",
            "allowed_modes",
            "default_dataset_lock_id",
            "status",
            "mission_preset",
            "rover_presets",
            "target_source",
            "earth_source",
            "search_region_set_id",
            "reference_set_id",
            "operator_limits",
        ):
            if field not in scenario:
                raise ValueError(f"scenario {scenario_id} lacks {field}")
        if scenario["status"] not in {"AVAILABLE", "AWAITING_DATASETS"}:
            raise ValueError(f"scenario {scenario_id} has invalid status")
        if any(mode not in {"synthetic", "replay", "live"} for mode in scenario["allowed_modes"]):
            raise ValueError(f"scenario {scenario_id} has invalid allowed_modes")
    return raw


def save_scenarios(settings: Settings, scenarios: dict[str, dict[str, Any]]) -> Path:
    path = settings.config_dir / "scenarios.yaml"
    get_scenarios(settings)
    path.write_text(yaml.safe_dump(scenarios, sort_keys=False), encoding="utf-8")
    return path


def scenario_wire(scenario_id: str, scenario: dict[str, Any]) -> dict[str, Any]:
    """Project private operator fields onto the exact OpenAPI ScenarioConfig."""
    return {
        "id": scenario_id,
        **{
            key: scenario[key]
            for key in ("name", "body", "description", "allowed_modes", "default_dataset_lock_id", "operator_limits")
        },
    }


def get_capabilities(settings: Settings, store: Any = None) -> dict[str, Any]:
    scenarios = get_scenarios(settings)
    locks_dir = settings.data_root / "locks"
    locks = sorted(path.stem for path in locks_dir.glob("*.json")) if locks_dir.is_dir() else []
    live_ready = bool(settings.openai_api_key and settings.openai_model)
    modes = ["synthetic", "replay"]
    if live_ready and any("live" in config["allowed_modes"] for config in scenarios.values()):
        modes.append("live")
    worker_healthy = False
    if store is not None:
        health = getattr(store, "worker_healthy", None)
        if callable(health):
            try:
                worker_healthy = bool(health())
            except Exception:  # noqa: BLE001 - capability reporting stays available if a worker probe fails
                worker_healthy = False
    adapters = {"local_dataset", "synthetic_practice"}
    registry_path = settings.config_dir / "datasets.yaml"
    if registry_path.is_file():
        try:
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            entries = registry.get("adapters", {}) if isinstance(registry, dict) else {}
            if isinstance(entries, dict):
                adapters.update(str(key) for key in entries)
            elif isinstance(entries, list):
                adapters.update(str(item["id"]) for item in entries if isinstance(item, dict) and "id" in item)
        except yaml.YAMLError as exc:
            raise ValueError("Invalid config/datasets.yaml adapter registry") from exc
    return {
        "modes": modes,
        "live_ai_configured": live_ready,
        "earthdata_configured": bool(settings.earthdata_token),
        "worker_healthy": worker_healthy,
        "adapters": sorted(adapters),
        "dataset_locks": locks,
        "export_formats": ["html", "json", "csv"],
        "scenario_config_ids": list(catalog.ALL_SCENARIOS),
        "default_scenario_config_id": settings.scenario_default,
    }
