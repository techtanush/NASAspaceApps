"""Probe the production image from inside its private API container.

This does not call providers, publish a host port or send cookies outside the
throwaway CI stack. It deliberately tests the actual non-superuser DB role.
"""
import http.client
import json
from http.cookies import SimpleCookie
from pathlib import Path
from uuid import uuid4

import psycopg

from analogforge.settings import Settings

settings = Settings()
origin = settings.public_base_url


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def request(path: str, *, method: str = "GET", cookies: str = "", csrf: str | None = None,
            body: dict[str, object] | None = None, origin_header: str | None = None) -> tuple[int, object, list[str]]:
    headers = {"Origin": origin_header or origin}
    if cookies:
        headers["Cookie"] = cookies
    if csrf:
        headers["X-CSRF-Token"] = csrf
    if method == "POST":
        headers["Idempotency-Key"] = str(uuid4())
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=20)
    try:
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        content = response.read()
        set_cookies = [value for key, value in response.getheaders() if key.lower() == "set-cookie"]
        return response.status, json.loads(content) if content else None, set_cookies
    finally:
        connection.close()


def visitor() -> tuple[dict[str, object], str]:
    status, document, set_cookies = request("/auth/session")
    require(status == 200 and isinstance(document, dict), "Public visitor bootstrap")
    require(document["authenticated"] and document["auth_mode"] == "public", "Public anonymous workspace")
    jar: SimpleCookie[str] = SimpleCookie()
    for value in set_cookies:
        jar.load(value)
    require(set(jar) == {"af_session", "af_workspace"}, "Both session cookies required")
    for cookie in jar.values():
        require(bool(cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "lax"),
                "Production cookie protections")
    return document, "; ".join(key + "=" + cookie.value for key, cookie in jar.items())


with psycopg.connect(settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)) as database:
    flags = database.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname=current_user"
    ).fetchone()
    require(flags == (False, False, False, False, False), "Runtime DB must have no administrator attributes")
    before = database.execute("SELECT count(*) FROM workspaces").fetchone()[0]
    for _ in range(3):
        status, _, set_cookies = request("/api/v1/health/ready")
        require(status == 200 and not set_cookies, "Readiness must be anonymous and session-free")
    after = database.execute("SELECT count(*) FROM workspaces").fetchone()[0]
    require(before == after, "Readiness created visitor workspaces")

first, first_cookie = visitor()
second, second_cookie = visitor()
require(first["workspace_id"] != second["workspace_id"], "Independent visitors share a workspace")
status, _, _ = request("/auth/session", origin_header="https://not-allowed.invalid")
require(status == 403, "Cross-origin visitor creation must be rejected")
rover = json.loads(Path("/app/config/presets/rovers/ares-1.json").read_text())
rover["name"] = "CI isolated rover"
status, _, _ = request("/api/v1/rovers", method="POST", cookies=first_cookie, body=rover)
require(status == 403, "Mutation without CSRF must be rejected")
status, created, _ = request("/api/v1/rovers", method="POST", cookies=first_cookie,
                               csrf=str(first["csrf_token"]), body=rover)
require(status == 201 and isinstance(created, dict), "Rover creation with non-superuser runtime role")
rover_id = created["rover_id"]
status, _, _ = request("/api/v1/rovers/" + str(rover_id), cookies=first_cookie)
require(status == 200, "Creating visitor must read its rover")
status, _, _ = request("/api/v1/rovers/" + str(rover_id), cookies=second_cookie)
require(status in {403, 404}, "Another visitor must not read this rover")
status, document, _ = request("/api/v1/capabilities", cookies=first_cookie)
require(status == 200 and isinstance(document, dict) and document["worker_healthy"], "Worker heartbeat unavailable")
print("PASS: production DB role, session-free readiness, isolated anonymous visitors, secure cookies, "
      "CSRF/origin rejection, private rover records and live worker heartbeat.")
