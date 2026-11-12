"""Independent API/display mutation probes; infrastructure errors do not count as kills."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MUTATIONS = (
    (
        "M2",
        "format/quantity.ts",
        "if(value==null||!Number.isFinite(value))return 'Unknown';",
        "if(value==null||!Number.isFinite(value))return '0';",
        "src/format/quantity.test.ts",
    ),
    ("M3", "api/runStream.ts", "event.seq<=this.cursor", "false", "src/api/runStream.test.ts"),
    ("M4", "api/client.ts", "'Idempotency-Key': key", "'Idempotency-Key': commandKey()", "src/api/client.test.ts"),
    ("M13", "maps/affine.ts", "d+e*pixel[0]+f*pixel[1]", "d+e*pixel[0]-f*pixel[1]", "src/maps/affine.test.ts"),
    (
        "M14",
        "maps/affine.ts",
        "[[w!,n!],[e!,n!],[e!,s!],[w!,s!]]",
        "[[w!,n!],[e!,s!],[e!,n!],[w!,s!]]",
        "src/maps/affine.test.ts",
    ),
    (
        "M19",
        "api/runStream.ts",
        "this.cursor=options.cursor;",
        "this.cursor=options.cursor || 8;",
        "src/api/runStream.test.ts",
    ),
)


def run_api_mutations(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    logs = root / "out/mutations"
    logs.mkdir(parents=True, exist_ok=True)
    records = []
    for identifier, filename, before, after, suite in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix=f"analogforge-{identifier}-") as directory:
            target = Path(directory)
            web = target / "apps/web"
            shutil.copytree(
                root / "apps/web",
                web,
                ignore=shutil.ignore_patterns(
                    "node_modules", "dist", "out", "test-results", "playwright-report", "docs"
                ),
            )
            shutil.copytree(root / "contracts", target / "contracts")
            (web / "node_modules").symlink_to(root / "apps/web/node_modules", target_is_directory=True)
            (target / "node_modules").symlink_to(root / "node_modules", target_is_directory=True)
            source = web / "src" / filename
            original = source.read_text()
            if original.count(before) != 1:
                records.append(
                    dict(
                        id=identifier,
                        killed=False,
                        status="INVALID_PROBE",
                        reason="Mutation anchor missing or ambiguous",
                    )
                )
                continue
            source.write_text(original.replace(before, after, 1))
            command = ["pnpm", "exec", "vitest", "run", suite, "--reporter=json"]
            result = subprocess.run(command, cwd=web, env=dict(os.environ), capture_output=True, text=True, check=False)  # noqa: S603
            output = result.stdout + result.stderr
            log = logs / f"api-{identifier}.log"
            log.write_text(output)
            try:
                report = json.loads(result.stdout[result.stdout.index("{") :])
            except (ValueError, json.JSONDecodeError):
                report = {}
            failures = report.get("numFailedTests", 0)
            assertion_failures = sum(
                1
                for test_file in report.get("testResults", [])
                for test in test_file.get("assertionResults", [])
                if test.get("status") == "failed"
                and any("AssertionError" in message for message in test.get("failureMessages", []))
            )
            infrastructure_error = bool(
                re.search(
                    r"Failed to (?:load|resolve)|Transform failed|SyntaxError|Cannot find module|No test files found",
                    output,
                )
            )
            killed = result.returncode == 1 and failures > 0 and assertion_failures > 0 and not infrastructure_error
            records.append(
                dict(
                    id=identifier,
                    status="KILLED" if killed else "SURVIVED",
                    killed=killed,
                    exit_code=result.returncode,
                    command=command,
                    failures=failures,
                    assertion_failures=assertion_failures,
                    output_file=str(log.relative_to(root)),
                )
            )
    return records


if __name__ == "__main__":
    results = run_api_mutations(Path(__file__).resolve().parents[2])
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(row["killed"] for row in results) else 1)
