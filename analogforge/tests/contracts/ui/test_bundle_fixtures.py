import json
from pathlib import Path

from analogforge.ports.catalog import ALGORITHM_IDS
from analogforge.ports.passport_renderer import PassportExportBundle

ROOT = Path(__file__).resolve().parents[3]


def test_bundle_fixtures_validate():
    paths = sorted((ROOT / "tests" / "unit" / "passport_renderer" / "fixtures" / "bundles").glob("*.json"))
    assert len(paths) == 9
    for path in paths:
        bundle = PassportExportBundle.model_validate_json(path.read_bytes())
        assert bundle.passport.mode == bundle.mode
        assert bundle.is_draft or bundle.assurance is not None


def test_algorithm_catalog_is_frozen():
    document = json.loads((ROOT / "contracts" / "algorithm-ids.json").read_text())
    expected = document.get("algorithms", document.get("algorithm_ids", document))
    assert expected == ALGORITHM_IDS
