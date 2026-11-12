"""Required production seams fail explicitly; injected doubles stay in tests."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from analogforge.api.errors import ApiError
from analogforge.application import runs
from analogforge.application.exports import load_renderer
from analogforge.db.store import PersistenceError


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("analogforge.science.facade:create_science_service", "SCIENCE_FACADE_MISSING"),
        ("analogforge.rendering.passport:create_passport_renderer", "RENDERER_MISSING"),
    ],
)
def test_missing_component_has_named_dependency(monkeypatch, path, code):
    def missing(name):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(runs.importlib, "import_module", missing)
    with pytest.raises(ApiError) as caught:
        runs.load_entry_point(path, code)
    assert caught.value.code == code
    assert caught.value.status == 503
    assert caught.value.details == {"dependency": path}


def test_broken_component_factory_is_safe_named_failure(monkeypatch):
    def broken():
        raise RuntimeError("private-provider-credential-must-not-escape")

    monkeypatch.setattr(runs.importlib, "import_module", lambda name: SimpleNamespace(create=broken))
    with pytest.raises(ApiError) as caught:
        runs.load_entry_point("missing.component:create", "SCIENCE_FACADE_MISSING")
    assert "private-provider" not in str(caught.value.envelope())
    assert caught.value.details["dependency"] == "missing.component:create"


def test_nonconforming_renderer_is_rejected(monkeypatch):
    monkeypatch.setattr(runs.importlib, "import_module", lambda name: SimpleNamespace(create_passport_renderer=object))
    with pytest.raises(PersistenceError, match="frozen port") as caught:
        load_renderer()
    assert caught.value.code == "RENDERER_NONCONFORMING"


def test_main_import_is_offline_without_collaborator_packages():
    program = """
import importlib.abc
import socket
import sys
class DenyCollaborators(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'analogforge.science.facade', 'analogforge.rendering.passport'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, DenyCollaborators())
def deny(*args, **kwargs):
    raise AssertionError('import attempted a network connection')
socket.socket.connect = deny
import analogforge.main
assert analogforge.main.app is not None
assert not any(name.startswith('tests.') for name in sys.modules)
"""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and literal test program
        [sys.executable, "-c", program], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
