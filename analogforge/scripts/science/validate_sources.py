#!/usr/bin/env python3
# ruff: noqa: S101
"""Validate config/datasets.yaml, algorithms.yaml and candidates.yaml with the strict science models.

Each file is parsed with its own strict model (unknown keys rejected), then the aggregate ``load_config`` runs the
cross-file checks.  Prints a JSON status on stdout; exit 0 only when every file is valid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from analogforge.science.config import (  # noqa: E402
    AlgorithmsConfig,
    CandidatesConfig,
    DatasetsConfig,
    default_config_dir,
    load_config,
)
from analogforge.science.errors import ConfigError  # noqa: E402

FILES: dict[str, Any] = {
    "datasets.yaml": DatasetsConfig,
    "algorithms.yaml": AlgorithmsConfig,
    "candidates.yaml": CandidatesConfig,
}


def validate(config_dir: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, model in FILES.items():
        try:
            parsed = yaml.safe_load((config_dir / name).read_bytes())
            if not isinstance(parsed, dict):
                raise ValueError("top level must be a mapping")
            model.model_validate(parsed)
            results[name] = {"ok": True}
        except (OSError, ValueError, yaml.YAMLError) as exc:  # pydantic.ValidationError is a ValueError
            results[name] = {"ok": False, "error": str(exc).splitlines()[0] if str(exc) else type(exc).__name__}
    aggregate: dict[str, Any]
    try:
        cfg = load_config(config_dir)
        aggregate = {
            "ok": True,
            "algorithm_config_sha256": cfg.algorithm_config_sha256,
            "candidates_config_sha256": cfg.candidates_config_sha256,
            "datasets_config_sha256": cfg.datasets_config_sha256,
        }
    except ConfigError as exc:
        aggregate = {"ok": False, "error": str(exc).splitlines()[0]}
    ok = all(r["ok"] for r in results.values()) and aggregate["ok"]
    return {"status": "PASS" if ok else "FAIL", "config_dir": str(config_dir), "files": results, "aggregate": aggregate}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=None)
    args = parser.parse_args()
    report = validate((args.config_dir or default_config_dir()).resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
