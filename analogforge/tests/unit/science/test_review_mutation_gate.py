"""Exercise the mutation runner against real subprocess test failures and setup errors."""

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("case", ["assertion", "setup_error", "baseline_error", "skipped"])
def test_only_executed_failure_after_a_passing_baseline_counts_as_killed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    path = Path(__file__).resolve().parents[3] / "scripts/science/mutation_check.py"
    spec = importlib.util.spec_from_file_location("review_mutation_runner", path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, runner)
    spec.loader.exec_module(runner)
    package = tmp_path / "src/probe_package"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n")
    test = tmp_path / "test_probe.py"
    bodies = {
        "assertion": "def test_value():\n    assert VALUE == 1\n",
        "setup_error": ("@pytest.fixture\ndef value():\n    if VALUE == 2: raise RuntimeError('fixture failed')\n"
                        "    return VALUE\ndef test_value(value):\n    assert value == 1\n"),
        "baseline_error": "def test_value():\n    assert VALUE == 99\n",
        # This child-process skip is a deliberately invalid mutation receipt;
        # the parent test executes and asserts that the runner refuses it.
        "skipped": ("def test_value():\n    if VALUE == 2: raise unittest.SkipTest('cannot execute')\n"
                    "    assert VALUE == 1\n"),
    }
    test.write_text("import pytest\nimport unittest\nfrom probe_package import VALUE\n" + bodies[case])
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "SRC", tmp_path / "src")
    mutant = runner.Mutant("probe", "probe", "probe_package/__init__.py", "VALUE = 1", "VALUE = 2", (str(test),))
    result = runner.run_mutant(mutant, timeout=60)
    assert result["killed"] == (case == "assertion"), result
