"""MRG-06: clean integration setup chooses the private cluster's server version."""

from pathlib import Path

import analogforge.settings as settings_module
from analogforge.settings import Settings


def test_inactive_private_cluster_uses_matching_tools_in_integration_profile(tmp_path, monkeypatch):
    cluster = tmp_path / '.runtime' / 'pg'
    cluster.mkdir(parents=True)
    (cluster / 'PG_VERSION').write_text('17\n')
    monkeypatch.setattr(settings_module, 'APP_ROOT', tmp_path)
    original = Path.is_file
    expected = Path('/opt/homebrew/opt/postgresql@17/bin/pg_ctl')
    monkeypatch.setattr(Path, 'is_file', lambda path: path == expected or original(path))
    settings = Settings(_env_file=None, profile='integration', db_port=5432)
    assert settings.postgres_tool('pg_ctl') == str(expected)
