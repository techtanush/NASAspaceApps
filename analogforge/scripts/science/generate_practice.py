#!/usr/bin/env python3
"""Write the practice datasets (architecture 40) and/or the mock NASA drop (architecture 39 section 5).

Usage: ``python scripts/science/generate_practice.py --out data/incoming [--mock-nasa-drop] [--seed N]``.
Prints a JSON object ``{dataset_id: {file: sha256}}`` so reruns can be compared byte for byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from analogforge.science.fixtures import mock_nasa_drop, practice
from analogforge.science.fixtures.practice_earth import SEED_DEFAULT


def _digests(root: Path, dataset_ids: list[str]) -> dict[str, dict[str, str]]:
    return {
        d: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / d).iterdir()) if p.is_file()}
        for d in dataset_ids
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="directory that receives <dataset_id>/ folders")
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument("--mock-nasa-drop", action="store_true", help="write the nine mock NASA drop datasets instead")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    ids = (
        mock_nasa_drop.generate(args.out, seed=args.seed)
        if args.mock_nasa_drop
        else practice.generate_all(args.out, seed=args.seed)
    )
    json.dump(_digests(args.out, ids), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
