"""Explicit, reversible live-slot rehearsal using conspicuously labelled fixture data."""

from __future__ import annotations

import json
import shutil
import tempfile
from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

from analogforge.application.capabilities import get_scenarios, save_scenarios
from analogforge.application.datasets import DatasetError, _entrypoint, create_lock, validate_dataset
from analogforge.settings import APP_ROOT, Settings

LABEL = "TEST HARNESS — not NASA data"
POLICY = "test-harness-policy-v1"
SCENARIO = "live-hackathon-v1"
PRODUCTS = ("practice-mars-target-v1", "practice-earth-grid-v1")


def _authorize(settings: Settings) -> Path:
    if not (settings.test_hooks and settings.allow_test_harness_provider and settings.auth_mode == "local"):
        raise DatasetError("MODE_MISMATCH", "TEST_HARNESS rehearsal requires both explicit local test hooks")
    if settings.config_dir.resolve() == (APP_ROOT / "config").resolve():
        raise DatasetError("INPUT_INVALID", "TEST_HARNESS rehearsal requires an isolated CONFIG_DIR copy")
    return settings.data_root / "rehearsal" / "live-slot.json"


def bind_live_slot(settings: Settings) -> dict[str, Any]:
    state_path = _authorize(settings)
    if state_path.is_file():
        state = json.loads(state_path.read_text())
        if get_scenarios(settings)[SCENARIO] != state["bound_scenario"]:
            raise DatasetError("REVISION_CONFLICT", "Rehearsal binding changed; restore it before rebinding")
        return dict(state["receipt"])
    original = get_scenarios(settings)[SCENARIO]
    if original["allowed_modes"]:
        raise DatasetError("REVISION_CONFLICT", "Rehearsal refuses to replace an already bound live dataset")
    identifiers = ["test-harness-mars-terrain", "test-harness-earth-terrain"]
    incoming = settings.data_root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    # The kit requires provider SYNTHETIC iff is_synthetic=true and live rejects
    # SYNTHETIC product ids. TEST_HARNESS is a separate, explicitly gated test
    # identity. It never carries NASA attribution or real-data validation claims.
    with tempfile.TemporaryDirectory(prefix="af-live-slot-") as temporary:
        generated = Path(temporary)
        _entrypoint("analogforge.science.fixtures.practice", "generate_all")(generated)
        for source_id, identifier in zip(PRODUCTS, identifiers, strict=True):
            destination = incoming / identifier
            if not destination.exists():
                shutil.copytree(generated / source_id, destination)
                path = destination / "manifest.yaml"
                manifest = yaml.safe_load(path.read_text())
                manifest.update(dataset_id=identifier, title=LABEL, provider="TEST_HARNESS", is_synthetic=False,
                                citation=LABEL, license_note="Generated local fixture; no NASA product used.")
                manifest["notes"] = [*manifest.get("notes", []), LABEL]
                manifest["product_identity"] = {"product_id": identifier.upper().replace("-", "_"), "version": "1"}
                path.write_text(yaml.safe_dump(manifest, sort_keys=False))
            report = validate_dataset(settings, identifier, write_checksums=True)
            if report["status"] != "PASS":
                raise DatasetError("SOURCE_CONTENT_INVALID", f"TEST_HARNESS validation failed: {identifier}")
    lock = create_lock(settings, POLICY, identifiers)
    # Use the actual operator binding implementation, including lock, role and
    # source checks. No direct scenario-file patch can manufacture availability.
    from analogforge.cli import _bind

    _bind(settings, Namespace(scenario_id=SCENARIO, policy_id=POLICY, target_terrain=identifiers[0],
                              earth_terrain=identifiers[1], earth_mineral=None, lunar_thermal=None))
    receipt = {"status": "PASS", "label": LABEL, "scenario_id": SCENARIO,
               "dataset_ids": identifiers, "policy_id": POLICY, "policy_sha256": lock["policy_sha256"]}
    state = {"original_scenario": original, "bound_scenario": get_scenarios(settings)[SCENARIO], "receipt": receipt}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    return receipt


def restore_live_slot(settings: Settings) -> dict[str, Any]:
    state_path = _authorize(settings)
    if not state_path.is_file():
        raise DatasetError("INPUT_INVALID", "No TEST_HARNESS binding receipt exists to restore")
    state = json.loads(state_path.read_text())
    scenarios = get_scenarios(settings)
    if scenarios[SCENARIO] != state["bound_scenario"]:
        raise DatasetError("REVISION_CONFLICT", "Rehearsal refuses to overwrite a newer operator binding")
    scenarios[SCENARIO] = state["original_scenario"]
    save_scenarios(settings, scenarios)
    state_path.unlink()
    return {"status": "PASS", "label": LABEL, "restored_scenario": SCENARIO}
