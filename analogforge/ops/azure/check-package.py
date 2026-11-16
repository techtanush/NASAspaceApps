#!/usr/bin/env python3
"""Offline deployment safety checks; needs Docker Compose CLI, not a running daemon.

Run from any directory with: python3 ops/azure/check-package.py
Temporary credentials are never printed, committed, or sent over the network.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "ops" / "azure"


def run(command: list[str], *, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed local tools and temporary test paths, no shell
        command, cwd=ROOT, env=environment, text=True, capture_output=True, check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def main() -> None:
    for script in PACKAGE.glob("*.sh"):
        require(run(["/bin/bash", "-n", str(script)]).returncode == 0, "Shell syntax: " + script.name)
    with tempfile.TemporaryDirectory(prefix="af-package-check-") as folder:
        runtime = Path(folder) / "runtime.env"
        database = Path(folder) / "database.env"
        hostname = "af-validation.westus2.cloudapp.azure.com"
        generate = [sys.executable, str(PACKAGE / "create-env.py"), hostname, "--output", str(runtime)]
        require(run(generate).returncode == 0, "Private runtime creation")
        for private in (runtime, database):
            require(stat.S_IMODE(private.stat().st_mode) == 0o600, "Private file permissions")
        original = (runtime.read_bytes(), database.read_bytes())
        require(run(generate).returncode != 0, "Existing credentials must never be overwritten")
        require(original == (runtime.read_bytes(), database.read_bytes()), "Existing credentials changed")
        for bad in ("a..com", "-invalid.example", "a.example/path", "a.example\nAUTH_MODE=local"):
            command = [sys.executable, str(PACKAGE / "create-env.py"), bad,
                       "--output", str(Path(folder) / "invalid.env")]
            require(run(command).returncode != 0, "Hostname validation")
        environment = {**os.environ, "AF_ENV_FILE": str(runtime), "RELEASE_ID": "a" * 40}
        command = ["docker", "compose", "--profile", "bootstrap", "--env-file", str(runtime),
                   "--env-file", str(database), "-f", str(PACKAGE / "compose.yaml")]
        composed = run([*command, "config", "--format", "json"], environment=environment)
        require(composed.returncode == 0, "Compose CLI configuration validation (Docker Compose is required)")
        config = json.loads(composed.stdout)
        services = config["services"]
        require(not services["db"].get("ports"), "Database must not publish a host port")
        for name in ("api", "worker"):
            service = services[name]
            env = service["environment"]
            require(not service.get("ports"), "Runtime service must remain private")
            require(env["AUTH_MODE"] == "public", "Runtime must use isolated public sessions")
            require(json.loads(env["ALLOWED_ORIGINS"]) == ["https://" + hostname], "Exact HTTPS origin")
            require("af_admin" not in env["DATABASE_URL"], "Runtime must not use administrator connection")
            require("DATABASE_ADMIN_URL" not in env and "POSTGRES_PASSWORD" not in env,
                    "Runtime must not receive administrator credentials")
            require(service["read_only"] and "ALL" in service["cap_drop"], "Runtime container protection")
            require(any(mount["target"] == "/data" for mount in service["volumes"]), "Durable evidence mount")
        require("af_admin" in services["migrate"]["environment"]["DATABASE_URL"], "Separate migration role")
        require(services["migrate"]["profiles"] == ["bootstrap"], "Migrations must be explicit")
        require(services["proxy"]["environment"]["APP_HOSTS"] == hostname, "Canonical hostname default")
        environment["AF_OPERATOR_CONFIG_DIR"] = folder
        live = run([*command, "-f", str(PACKAGE / "compose.live.yaml"), "config", "--format", "json"],
                   environment=environment)
        require(live.returncode == 0, "Live override configuration")
        for name in ("api", "worker"):
            mounts = json.loads(live.stdout)["services"][name]["volumes"]
            require(any(mount["target"] == "/data" for mount in mounts), "Live override lost evidence volume")
            require(any(mount["target"] == "/app/config" and mount["read_only"] for mount in mounts),
                    "Live operator config must be read-only")
    print("PASS: shell syntax, credential safety/separation, private topology, anonymous HTTPS origin, "
          "container protection, persistent evidence and explicit live config override.")
    print("NOT CHECKED: Linux image build, native dependencies, database provisioning, TLS or browser journey.")


if __name__ == "__main__":
    main()
