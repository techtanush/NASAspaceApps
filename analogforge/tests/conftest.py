"""Project-local test configuration; an explicit test DSN always takes precedence."""
from __future__ import annotations

import os

from analogforge.settings import Settings


def pytest_configure() -> None:
    configured = Settings()
    if "TEST_DATABASE_URL" not in os.environ and configured.test_database_url:
        os.environ["TEST_DATABASE_URL"] = configured.test_database_url
