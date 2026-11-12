#!/usr/bin/env python3
"""Check operator docs, commands, and exact preset copies against the frozen kit."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from analogforge.application.capabilities import get_scenarios
from analogforge.settings import Settings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = Settings(config_dir=root / "config")
    scenarios = get_scenarios(settings)
    for group in ("missions", "rovers"):
        source = root / "tests" / "fixtures" / "kit" / group
        target = root / "config" / "presets" / group
        assert {file.name for file in source.glob("*.json")} == {file.name for file in target.glob("*.json")}
        for file in source.glob("*.json"):
            assert file.read_bytes() == (target / file.name).read_bytes(), f"Preset differs: {file.name}"
    for scenario_id, scenario in scenarios.items():
        mission = scenario["mission_preset"]
        if mission:
            assert (root / "config" / "presets" / "missions" / mission).is_file(), scenario_id
        for rover in scenario["rover_presets"]:
            assert (root / "config" / "presets" / "rovers" / rover).is_file(), scenario_id
    for name in ("README.md", "Makefile", "compose.yaml", "ops/runbooks/native-postgres.md"):
        assert (root / name).is_file(), name
    junit = settings.data_root / "out" / "platform-junit.xml"
    if junit.is_file() and settings.test_database_url:
        report = ElementTree.parse(junit).getroot()  # noqa: S314 - local pytest-generated JUnit only
        cases = report.findall(".//testcase")
        assert cases, "Platform JUnit has no executed tests"
        skipped = [case.attrib.get("name", "unnamed") for case in cases if case.find("skipped") is not None]
        assert not skipped, f"Platform JUnit contains skipped or xfailed tests: {skipped}"
    print("validate_docs: PASS")


if __name__ == "__main__":
    main()
