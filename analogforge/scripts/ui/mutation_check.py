"""Run the required behavioral and visual mutants against isolated source copies.

A broken test collector, syntax error or unavailable browser never counts as a kill.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from api_mutations import run_api_mutations
from renderer_mutations import run_renderer_mutations

ROOT = Path(__file__).resolve().parents[2]
# Source edits are intentionally faulty. The untouched acceptance tests must detect each one.
MUTATIONS = [
    (
        "M1",
        "src/app/App.tsx",
        'data-testid="app-shell"',
        'data-testid="renamed-shell"',
        "unit",
        "src/test/testids.test.ts",
    ),
    (
        "M5",
        "src/features/analogs/AnalogsView.tsx",
        "__OPTIMISM__",
        "",
        "unit",
        "src/features/runs/interaction.test.tsx",
    ),
    ("M6", "src/app/App.tsx", "MOCK PREVIEW — not a real backend", "Preview backend", "browser", "J01-golden.spec.ts"),
    (
        "M7",
        "vite.config.ts",
        "if (command === 'build' && mock)",
        "if (false && command === 'build' && mock)",
        "unit",
        "src/test/prod-build-guard.test.ts",
    ),
    (
        "M12",
        "src/features/qualification/QualificationView.tsx",
        "contract.requirements.filter(req=>!hideOptional||req.mandatory)",
        "contract.requirements.filter(req=>req.mandatory)",
        "unit",
        "src/features/runs/interaction.test.tsx",
    ),
    (
        "M16",
        "src/components/ui/index.tsx",
        "{children ?? status}",
        "{children ?? (status==='GAP'?'FAIL':status)}",
        "unit",
        "src/test/presentation.test.tsx",
    ),
    (
        "M18",
        "src/features/passport/PassportView.tsx",
        "const final=!!snapshot.passport_id;",
        (
            "const final=!!snapshot.passport_id;"
            "void crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(passport.data)));"
        ),
        "scan",
        "client-side-manifest-hash",
    ),
    (
        "M23",
        "src/features/passport/PassportView.tsx",
        "??'INCOMPLETE'",
        "??'ALLOWED'",
        "unit",
        "src/features/runs/interaction.test.tsx",
    ),
    (
        "M24",
        "src/features/analogs/AnalogsView.tsx",
        '<div className="analogs-list-pane" data-testid="candidate-list">',
        '<div className="analogs-list-pane" data-testid="candidate-list" hidden={!document.createElement("canvas").getContext("webgl")}>',
        "browser",
        "webgl-fallback.spec.ts",
    ),
    (
        "M25",
        "src/styles/base.css",
        None,
        "\n.app-header{background-image:linear-gradient(red,blue)}\n",
        "scan",
        "decorative-effect",
    ),
    (
        "M26",
        "src/styles/base.css",
        None,
        "\n.panel,.styleguide-example{border-radius:16px}\n",
        "design",
        "design-smoke.spec.ts",
    ),
    ("M27", "src/styles/base.css", None, "\n.helper{font-size:11px}\n", "design", "design-smoke.spec.ts"),
    (
        "M28",
        "src/styles/base.css",
        None,
        "\ntd[data-numeric]{text-align:left;font-variant-numeric:normal}\n",
        "design",
        "design-smoke.spec.ts",
    ),
    ("M29", "src/components/ui/index.tsx", "__GLYPH__", "", "unit", "src/test/presentation.test.tsx"),
    ("M30", "design/tokens.json", "__TOKEN__", "", "tokens", ""),
    (
        "M31",
        "src/features/workspace/Workspace.tsx",
        "Missions and runs</h1>",
        "Missions and runs \U0001f680</h1>",
        "scan",
        "emoji",
    ),
    (
        "M32",
        "src/styles/base.css",
        None,
        "\n:focus-visible{outline:none!important;box-shadow:none!important}\n",
        "design",
        "design-smoke.spec.ts",
    ),
    ("M33", "src/styles/base.css", None, "\nbody{min-width:1200px}\n", "design", "design-smoke.spec.ts"),
    ("M34", "src/styles/base.css", None, "\n.panel{color:#fff}\n", "scan", "color-outside-tokens"),
    (
        "M35",
        "src/features/workspace/Workspace.tsx",
        "New mission</Link>",
        'New mission</Link><Link className="button" data-variant="primary" to="/rovers">Choose rover</Link>',
        "design",
        "design-smoke.spec.ts",
    ),
    (
        "M36",
        "index.html",
        "<title>",
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter"/><title>',
        "external",
        "design-smoke.spec.ts",
    ),
]


def prepare(target: Path) -> None:
    for folder in [
        "apps/web/src",
        "apps/web/public",
        "apps/web/design",
        "tests/e2e",
        "tests/fixtures/kit",
        "contracts",
        "scripts/ui",
    ]:
        shutil.copytree(ROOT / folder, target / folder, ignore=shutil.ignore_patterns("__pycache__", ".cache"))
    shutil.copy2(ROOT / "scripts/build_mock_exports.py", target / "scripts/build_mock_exports.py")
    web = target / "apps/web"
    for filename in [
        "package.json",
        "index.html",
        "vite.config.ts",
        "vitest.config.ts",
        "tsconfig.json",
        "playwright.config.ts",
        "eslint.config.js",
    ]:
        shutil.copy2(ROOT / "apps/web" / filename, web / filename)
    # Dependencies are symlinked to the owning checkout, so Vite must serve their local font assets.
    config = web / "vite.config.ts"
    configuration = config.read_text()
    configuration = configuration.replace(
        "server: { strictPort:",
        "server: { fs: {allow: " + json.dumps([str(target), str(ROOT)]) + "}, strictPort:",
        1,
    )
    config.write_text(configuration)
    for filename in ["package.json", "pnpm-workspace.yaml", "pyproject.toml"]:
        shutil.copy2(ROOT / filename, target / filename)
    for source, destination in [
        (ROOT / "node_modules", target / "node_modules"),
        (ROOT / "apps/web/node_modules", web / "node_modules"),
        (ROOT / ".venv", target / ".venv"),
        (ROOT / "src", target / "src"),
    ]:
        destination.symlink_to(source, target_is_directory=True)


def run_frontend_mutations(only: set[str] | None = None) -> list[dict[str, Any]]:
    logs = ROOT / "out/mutations"
    logs.mkdir(parents=True, exist_ok=True)
    records = []
    for identifier, filename, before, after, kind, suite in MUTATIONS:
        if only and identifier not in only:
            continue
        with tempfile.TemporaryDirectory(prefix=f"{identifier}-", dir=logs) as directory:
            target = Path(directory)
            prepare(target)
            web = target / "apps/web"
            source = web / filename
            original = source.read_text()
            if before == "__OPTIMISM__":
                replacements = [
                    (
                        "const [filter,setFilter]=useState('');",
                        (
                            "const [optimistic,setOptimistic]=useState<string|null>(null);"
                            "const [filter,setFilter]=useState('');"
                        ),
                    ),
                    ("const select=async(id:string)=>{", "const select=async(id:string)=>{setOptimistic(id);"),
                    (
                        "data-selected={candidate.id===snapshot.selected_candidate_id}",
                        "data-selected={candidate.id===(optimistic||snapshot.selected_candidate_id)}",
                    ),
                ]
                modified = original
                count = 1
                for source_text, replacement_text in replacements:
                    if source_text not in modified:
                        count = 0
                    modified = modified.replace(source_text, replacement_text, 1)
            elif before == "__GLYPH__":
                passing = re.search(r"PASS:\s*'([^']+)'", original)
                modified, count = (
                    re.subn(r"UNKNOWN:\s*'[^']+'", "UNKNOWN: '" + passing[1] + "'", original, count=1)
                    if passing
                    else (original, 0)
                )
            elif before == "__TOKEN__":
                doc = json.loads(original)
                doc["themes"]["dark"]["text-secondary"] = doc["themes"]["dark"]["surface-1"]
                modified, count = json.dumps(doc), 1
            elif before is None:
                modified, count = original + after, 1
            else:
                count = original.count(before)
                modified = original.replace(before, after, 1)
            if count < 1:
                records.append(
                    dict(id=identifier, status="INVALID_PROBE", killed=False, reason="Mutation anchor missing")
                )
                continue
            source.write_text(modified)
            env = dict(os.environ, CI="true", E2E_TARGET="mock", E2E_RUN_NAME=identifier, PYTHONDONTWRITEBYTECODE="1")
            if kind == "unit":
                command = [
                    "node",
                    str(ROOT / "apps/web/node_modules/vitest/vitest.mjs"),
                    "run",
                    suite,
                    "--reporter=json",
                ]
                cwd = web
            elif kind in {"browser", "design", "external"}:
                command = ["node", str(ROOT / "node_modules/@playwright/test/cli.js"), "test", suite, "--reporter=json"]
                cwd = web
            elif kind == "tokens":
                command = [str(ROOT / ".venv/bin/python"), "scripts/ui/verify_tokens.py", "apps/web/design/tokens.json"]
                cwd = target
            else:
                command = [str(ROOT / ".venv/bin/python"), "scripts/ui/forbidden_scan.py", "--json", "out/scan.json"]
                cwd = target
            try:
                result = subprocess.run(  # noqa: S603 — fixed catalog commands on isolated source copies
                    command, cwd=cwd, env=env, capture_output=True, text=True, timeout=240, check=False
                )  # noqa: S603
                output = result.stdout + result.stderr
                log = logs / f"frontend-{identifier}.log"
                log.write_text(output)
                for context in (target / "out").rglob("error-context.md"):
                    shutil.copy2(context, logs / f"frontend-{identifier}-context.md")
                invalid = bool(
                    re.search(
                        (
                            r"Error collecting|No tests found|SyntaxError|Transform failed|"
                            r"Cannot find (?:module|package)|EADDRINUSE"
                        ),
                        output,
                    )
                )
                if kind == "scan":
                    report = (
                        json.loads((target / "out/scan.json").read_text())
                        if (target / "out/scan.json").exists()
                        else {}
                    )
                    killed = result.returncode == 1 and any(
                        item["rule"] == suite for item in report.get("findings", [])
                    )
                elif kind == "tokens":
                    killed = result.returncode == 1 and "FAIL [dark]" in output
                else:
                    killed = (
                        result.returncode == 1
                        and bool(
                            re.search(
                                r"AssertionError|TestingLibraryElementError|expect\(|toHaveAttribute|toContainText|toBeVisible|toBe\(",
                                output,
                            )
                        )
                        and not invalid
                    )
                if kind in {"browser", "design", "external"}:
                    # An unrelated startup failure is not evidence that the intended regression was caught.
                    expected_failure = {
                        "M6": "mock-banner", "M24": "candidate-list",
                        "M26": "C10", "M27": "C02", "M28": "C09",
                        "M32": "C07", "M33": "C05", "M35": "C13", "M36": "C01 external requests",
                    }[identifier]
                    killed = killed and expected_failure in output
                records.append(
                    dict(
                        id=identifier,
                        status="KILLED" if killed else "SURVIVED",
                        killed=killed,
                        exit_code=result.returncode,
                        command=command,
                        output_file=str(log.relative_to(ROOT)),
                    )
                )
            except subprocess.TimeoutExpired:
                records.append(dict(id=identifier, status="INFRASTRUCTURE_TIMEOUT", killed=False))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=ROOT / "out/mutations.json")
    parser.add_argument("--only", help="Diagnostic subset; full gate requires all 36")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None
    records = run_frontend_mutations(only)
    if not only:
        records += run_api_mutations(ROOT) + run_renderer_mutations(ROOT)
    records.sort(key=lambda row: int(row["id"][1:]))
    all_ids = {f"M{n}" for n in range(1, 37)}
    complete = {row["id"] for row in records} == all_ids
    passed = all(row["killed"] for row in records) and (complete or bool(only))
    result = dict(
        status="PASS" if passed else "FAIL",
        complete_catalog=complete,
        mutants=len(records),
        killed=sum(row["killed"] for row in records),
        records=records,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
