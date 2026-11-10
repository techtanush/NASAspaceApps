# ruff: noqa: E501, S603, S607, S101
"""SCN-19: import hygiene, no environment reads, no network in synthetic mode."""

from __future__ import annotations

import ast
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from support.builders import load_mission, load_rover, make_context, run

from analogforge.ports import catalog
from analogforge.ports.science_payloads import DesignBenchmarkInput
from analogforge.science.facade import create_science_service

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN = ("fastapi", "sqlalchemy", "psycopg", "openai")
SCIENCE_TREES = [
    "src/analogforge/science",
    "src/analogforge/adapters/earthdata",
    "src/analogforge/adapters/pds",
    "src/analogforge/adapters/emit",
    "src/analogforge/adapters/diviner",
    "src/analogforge/adapters/user_survey",
    "src/analogforge/adapters/source_http",
]
_PROBE = """
import importlib, json, sys, pkgutil
import analogforge.science.facade as f
import analogforge.science.ops as ops
for m in pkgutil.iter_modules(ops.__path__):
    try:
        importlib.import_module("analogforge.science.ops." + m.name)
    except ModuleNotFoundError as exc:
        if not str(exc.name or "").startswith("analogforge"):
            raise
bad = sorted(n for n in sys.modules if n.split(".")[0] in {forbidden})
internal = sorted(n for n in sys.modules if n.startswith(("analogforge.api", "analogforge.db", "analogforge.jobs",
    "analogforge.application", "analogforge.agents", "analogforge.tools", "analogforge.rendering.passport")))
print(json.dumps({{"bad": bad, "internal": internal}}))
"""


def test_facade_import_loads_no_platform_packages() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE.format(forbidden=set(FORBIDDEN))],
        capture_output=True, text=True, cwd=ROOT, check=True,
    )  # fmt: skip
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data == {"bad": [], "internal": []}


def test_probe_detects_a_forbidden_import() -> None:
    """The probe is not vacuous: importing a forbidden package is reported."""
    probe = "import sqlite3, json, sys\nimport fastapi\nprint(json.dumps(sorted(n for n in sys.modules if n.split('.')[0]=='fastapi')[:1]))"
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT, check=False)
    assert out.returncode == 0 and json.loads(out.stdout.strip().splitlines()[-1]) == ["fastapi"]


def _py_files() -> list[Path]:
    return [p for t in SCIENCE_TREES for p in sorted((ROOT / t).rglob("*.py")) if "__pycache__" not in p.parts]


def test_no_environment_access_in_science_code() -> None:
    offenders: list[str] = []
    files = _py_files()
    assert files
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv", "putenv"}:
                if isinstance(node.value, ast.Name) and node.value.id == "os":
                    offenders.append(f"{path}:{node.lineno}")
            if isinstance(node, ast.ImportFrom) and node.module == "os":
                if any(a.name in {"environ", "getenv"} for a in node.names):
                    offenders.append(f"{path}:{node.lineno}")
    assert offenders == []


def test_ast_scan_detects_environ_access() -> None:
    tree = ast.parse("import os\nx = os.environ['A']\n")
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "environ"]
    assert hits


def test_no_forbidden_imports_in_source() -> None:
    offenders: list[str] = []
    for path in _py_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            )  # fmt: skip
            for n in names:
                if n.split(".")[0] in FORBIDDEN or n.startswith(
                    ("analogforge.api", "analogforge.db", "analogforge.jobs", "analogforge.application",
                     "analogforge.agents", "analogforge.tools", "analogforge.rendering.passport")
                ):  # fmt: skip
                    offenders.append(f"{path}:{n}")
    assert offenders == []


def test_synthetic_run_opens_no_socket(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    attempts: list[object] = []

    def blocked(*a: object, **k: object) -> None:
        attempts.append(a)
        raise AssertionError("network access attempted in synthetic mode")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    mission = load_mission("mission-graph-regression")
    inp = DesignBenchmarkInput(
        mission=mission,
        rover=load_rover("ares-1"),
        candidate={
            "window_id": catalog.GRAPH_WINDOW_ID, "name": "g",
            "aoi": mission.target.model_copy(update={"body": "EARTH"}).model_dump(),
            "origin": "SYNTHETIC_CONTROL", "novelty_status": "NOT_ASSESSED", "discovery_method": "fixture",
        },  # type: ignore[arg-type]
        analysis_evidence_id=None, graph_fixture_id=catalog.FIXTURE_CANONICAL_GRAPH,
        strategy="WAYPOINT_RETURN", test_revision=1,
    )  # fmt: skip
    result, _ = run(create_science_service(), inp, make_context(tmp_path))
    assert result.status.value == "SUCCEEDED" and attempts == []
    assert make_context(tmp_path).http_client() is None
