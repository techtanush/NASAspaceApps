"""scripts/science/validate_sources.py: strict validation of the three config files with a JSON status."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "science" / "validate_sources.py"


def _run(*args: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False)  # noqa: S603
    return proc.returncode, json.loads(proc.stdout)


def test_real_config_passes() -> None:
    code, report = _run()
    assert code == 0 and report["status"] == "PASS"
    assert set(report["files"]) == {"datasets.yaml", "algorithms.yaml", "candidates.yaml"}
    assert len(report["aggregate"]["algorithm_config_sha256"]) == 64


def test_unknown_key_fails_nonzero(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "config", tmp_path / "c")
    with (tmp_path / "c" / "datasets.yaml").open("a") as fh:
        fh.write("\nbogus_unknown_key: 1\n")
    code, report = _run("--config-dir", str(tmp_path / "c"))
    assert code == 1 and report["status"] == "FAIL"
    assert report["files"]["datasets.yaml"]["ok"] is False
    assert report["files"]["algorithms.yaml"]["ok"] is True


def test_missing_file_fails_nonzero(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "config", tmp_path / "c")
    (tmp_path / "c" / "candidates.yaml").unlink()
    code, report = _run("--config-dir", str(tmp_path / "c"))
    assert code == 1 and report["files"]["candidates.yaml"]["ok"] is False
