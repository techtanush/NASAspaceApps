"""Write a deployment receipt containing public settings and image IDs, never keys."""
import http.client
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

commit, envfile = sys.argv[1:]
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("An exact source commit is required")
public = {}
for line in Path(envfile).read_text().splitlines():
    key, _, value = line.partition("=")
    if key in {"APP_HOST", "PUBLIC_BASE_URL", "AUTH_MODE", "ANALOGFORGE_MODE"}:
        public[key] = value
origin = urlsplit(public["PUBLIC_BASE_URL"])
if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password
        or origin.path not in {"", "/"} or origin.query or origin.fragment):
    raise SystemExit("A valid HTTPS public origin is required")
# Compose startup can finish before the proxy has obtained its first certificate.
deadline = time.monotonic() + 90
while True:
    connection = http.client.HTTPSConnection(origin.hostname, origin.port or 443, timeout=8)
    try:
        connection.request("GET", "/api/v1/health/ready")
        response = connection.getresponse()
        if response.getheader("Set-Cookie"):
            raise SystemExit("Public readiness must not create a session")
        if response.status == 200:
            response.read()
            break
    except (OSError, http.client.HTTPException):
        pass
    finally:
        connection.close()
    if time.monotonic() >= deadline:
        raise SystemExit("Public HTTPS readiness did not pass within 90 seconds")
    time.sleep(3)
images = {}
for name in ("runtime", "proxy"):
    # Validated immutable commit and two fixed image names; no shell or user command.
    images[name] = subprocess.check_output([  # noqa: S603
        "/usr/bin/docker", "image", "inspect", "--format={{.Id}}", "analogforge-" + name + ":" + commit
    ], text=True).strip()
receipt = {"source_commit": commit, "checked_at": datetime.now(UTC).isoformat(), "public": public,
           "image_ids": images, "public_readiness": "PASS", "browser_journey": "REQUIRED"}
folder = Path("/srv/analogforge/receipts")
folder.mkdir(parents=True, exist_ok=True, mode=0o700)
(folder / (commit + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
