"""Optional immutable operating context, outside scientific qualification and claims.

Only a fenced live worker captures network data. The projection reads a private
CAS snapshot through an authorized run pointer and never performs acquisition.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx

from analogforge.adapters.meteomatics import WeatherQuery, fetch_earth_weather
from analogforge.adapters.meteomatics.adapter import iso
from analogforge.adapters.rems import fetch_rems_weather
from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.api.errors import ApiError
from analogforge.db.store import NotFound, PersistenceError, Store
from analogforge.ports.hashing import bytes_sha256, canonical_json_bytes, canonical_sha256
from analogforge.settings import Settings

KEY = "environment_context"
ATTEMPT = "environment_context_attempt"
MAX_SITES, MAX_CALLS, MAX_SECONDS, MAX_SNAPSHOT_BYTES = 6, 8, 30.0, 1024 * 1024
LIMITATIONS = [
    "Optional operating context; qualification, benchmark results and candidate ranking are unchanged.",
    "Earth weather represents one geographic point per candidate and the declared UTC sample window.",
    "NASA REMS is historical rover-point reference context; selected planetary AOI applicability remains UNKNOWN.",
    "No weather limits are inferred from terrain or planetary surface-temperature requirements.",
]


class ContextBudgetExpired(Exception):
    pass


class ContextScopeChanged(Exception):
    pass


def eligibility(settings: Settings, mode: str) -> str | None:
    if mode != "live":
        return "NETWORK_DISABLED_FOR_MODE"
    if settings.test_hooks or settings.allow_test_harness_provider:
        return "NETWORK_DISABLED_FOR_TEST_MODE"
    if not settings.environment_context_enabled:
        return "ENVIRONMENT_CONTEXT_DISABLED"
    if not settings.meteomatics_username or not settings.meteomatics_password:
        return "WEATHER_NOT_CONFIGURED"
    return None


def representative_point(aoi: dict[str, Any]) -> tuple[float, float]:
    if (aoi.get("body") != "EARTH" or aoi.get("latitude_type") != "GEODETIC"
            or aoi.get("longitude_convention") != "NEG180_180"):
        raise ValueError("Earth geodetic longitude/latitude AOI required")
    west, south, east, north = map(float, aoi["bbox"])
    if (not all(math.isfinite(v) for v in (west, south, east, north)) or not -90 <= south < north <= 90
            or not -180 <= west <= 180 or not -180 <= east <= 180 or west == east):
        raise ValueError("Invalid Earth AOI")
    width = east - west if east > west else east + 360 - west
    return (south + north) / 2, (west + width / 2 + 180) % 360 - 180


def _scope(run: dict[str, Any], mission: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "workspace_id": run["workspace_id"], "run_id": run["id"], "mode": run["mode"],
        "mission_revision_id": mission["id"], "mission_content_sha256": mission["content_sha256"],
        "target": mission["target"],
        "candidate_aoi_sha256": {c["id"]: canonical_sha256(c["aoi"]) for c in candidates},
    }


def _candidate_rows(tx: Any, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Use the run's authoritative shortlist, never orphan rows sharing its id."""
    identifiers = run.get("candidate_ids", [])
    if (not isinstance(identifiers, list) or any(not isinstance(cid, str) for cid in identifiers)
            or len(set(identifiers)) != len(identifiers)):
        raise ValueError("Invalid candidate membership")
    candidates = [tx.require("candidates", cid) for cid in identifiers]
    if any(c.get("run_id") != run["id"] or c.get("workspace_id") != run["workspace_id"]
           or c.get("mode") != run["mode"] for c in candidates):
        raise ValueError("Candidate scope differs")
    return candidates


def capture(
    store: Store, blobs: ContentAddressedStore, settings: Settings, workspace_id: str, run_id: str,
    *, job_id: str | None, lease_token: str | None,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
    monotonic: Callable[[], float] = time.monotonic, now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Capture once per run; caller must be an active worker at the discovery boundary.

    A persisted reservation prevents restarted workers from repeatedly querying
    providers. An interrupted reservation is reported as unavailable, never
    treated as a successful snapshot. Lease loss/cancellation cannot publish.
    """
    if job_id is None or lease_token is None:
        return
    started = monotonic()
    deadline = started + MAX_SECONDS
    with store.publication(workspace_id, job_id, lease_token) as tx:
        job = tx.require("jobs", job_id)
        if job.get("run_id") != run_id:
            raise PersistenceError("INPUT_INVALID", "Environment worker belongs to another run")
        run = tx.require("runs", run_id)
        if (eligibility(settings, run["mode"]) is not None or KEY in run.get("runtime", {})
                or ATTEMPT in run.get("runtime", {})):
            return
        try:
            candidates = _candidate_rows(tx, run)
        except (ValueError, NotFound):
            run.setdefault("runtime", {})[ATTEMPT] = {
                "id": str(uuid4()), "started_at": iso(now()), "reason_code": "CANDIDATE_SCOPE_INVALID",
            }
            tx.replace("runs", run_id, run, run["revision"])
            return
        if not candidates:
            return
        mission = tx.require("mission_revisions", run["mission_revision_id"])
        scope = _scope(run, mission, candidates)
        attempt_id, captured = str(uuid4()), now()
        run.setdefault("runtime", {})[ATTEMPT] = {
            "id": attempt_id, "started_at": iso(captured), "reason_code": "CAPTURE_INCOMPLETE",
        }
        tx.replace("runs", run_id, run, run["revision"])
    last_probe = started
    calls = 0

    def check(*, force: bool = False) -> None:
        nonlocal last_probe
        elapsed = monotonic()
        if elapsed >= deadline:
            raise ContextBudgetExpired()
        if force or elapsed - last_probe >= 0.25:
            with store.publication(workspace_id, job_id, lease_token) as tx:
                current = tx.require("runs", run_id)
                if current.get("runtime", {}).get(ATTEMPT, {}).get("id") != attempt_id:
                    raise PersistenceError("INPUT_INVALID", "Environment reservation differs")
            last_probe = elapsed

    def before_request(request: httpx.Request) -> None:
        nonlocal calls
        check(force=True)
        if calls >= MAX_CALLS:
            raise ContextBudgetExpired()
        calls += 1
        remaining = min(3.0, deadline - monotonic())
        if remaining <= 0:
            raise ContextBudgetExpired()
        request.extensions["timeout"] = dict(connect=remaining, read=remaining, write=remaining, pool=remaining)

    earth = []
    nasa: dict[str, Any] = {"status": "UNKNOWN", "reason_code": "NOT_APPLICABLE_TO_TARGET_BODY",
                            "selected_aoi_applicability": "UNKNOWN", "qualification_supported": False}
    chosen = sorted(candidates, key=lambda c: c["id"])[:MAX_SITES]

    def record_failure(reason: str) -> None:
        with store.publication(workspace_id, job_id, lease_token) as tx:
            current = tx.require("runs", run_id)
            if current.get("runtime", {}).get(ATTEMPT, {}).get("id") == attempt_id:
                current["runtime"][ATTEMPT]["reason_code"] = reason
                tx.replace("runs", run_id, current, current["revision"])

    try:
        with client_factory(
            trust_env=False, follow_redirects=False, event_hooks={"request": [before_request]},
        ) as client:
            for candidate in chosen:
                item: dict[str, Any] = {"candidate_id": candidate["id"], "status": "UNKNOWN"}
                try:
                    check()
                    latitude, longitude = representative_point(candidate["aoi"])
                    start = captured.astimezone(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    query = WeatherQuery("EARTH", latitude, longitude, start, start + timedelta(hours=3))
                    assert settings.meteomatics_username is not None and settings.meteomatics_password is not None
                    context = fetch_earth_weather(
                        query, client=client, username=settings.meteomatics_username.get_secret_value(),
                        password=settings.meteomatics_password.get_secret_value(), mode="live", fetched_at=captured,
                        timeout_seconds=3, check_cancelled=check,
                    )
                    item.update(status=context.status, reason_code=context.reason_code,
                                representative_point={"latitude": latitude, "longitude": longitude,
                                                      "method": "GEODETIC_AOI_MIDPOINT"}, weather=context.to_dict())
                except ContextBudgetExpired:
                    item["reason_code"] = "CONTEXT_BUDGET_EXHAUSTED"
                except (ValueError, TypeError, KeyError):
                    item["reason_code"] = "CANDIDATE_GEOMETRY_UNSUPPORTED"
                earth.append(item)
            if mission["target"]["body"] == "MARS":
                try:
                    check()
                    nasa = fetch_rems_weather(client=client, mode="live", fetched_at=captured,
                                              timeout_seconds=3, check_cancelled=check)
                except ContextBudgetExpired:
                    nasa = {"status": "UNKNOWN", "reason_code": "CONTEXT_BUDGET_EXHAUSTED",
                            "selected_aoi_applicability": "UNKNOWN", "qualification_supported": False}
        check()
        snapshot = {
            "schema_version": "environment.v1", **scope, "captured_at": iso(captured),
            "status": "CAPTURED", "reason_code": "OPERATING_CONTEXT_ONLY", "earth_candidates": earth,
            "omitted_candidate_ids": sorted(set(scope["candidate_aoi_sha256"]) - {c["id"] for c in chosen}),
            "nasa_reference": nasa, "qualification_supported": False, "operating_limits": [],
            "limitations": LIMITATIONS, "budget": {"max_sites": MAX_SITES, "max_http_calls": MAX_CALLS,
                                                    "max_seconds": MAX_SECONDS, "http_calls": calls},
        }
        raw = canonical_json_bytes(snapshot)
        check()
        if len(raw) > MAX_SNAPSHOT_BYTES:
            raise ContextBudgetExpired()
        blob = blobs.put_bytes(raw, "application/json")
        check()
        with store.publication(workspace_id, job_id, lease_token) as tx:
            current = tx.require("runs", run_id)
            actual = _scope(current, tx.require("mission_revisions", current["mission_revision_id"]),
                            _candidate_rows(tx, current))
            if actual != scope or current.get("runtime", {}).get(ATTEMPT, {}).get("id") != attempt_id:
                raise ContextScopeChanged()
            if monotonic() >= deadline:
                raise ContextBudgetExpired()
            if KEY not in current.get("runtime", {}):
                current.setdefault("runtime", {})[KEY] = {"sha256": blob.sha256, "captured_at": iso(captured)}
                tx.replace("runs", run_id, current, current["revision"])
    except ContextBudgetExpired:
        record_failure("CONTEXT_BUDGET_EXHAUSTED")
    except (ContextScopeChanged, ValueError, NotFound):
        record_failure("CONTEXT_INPUTS_CHANGED")
    except OSError:
        record_failure("CONTEXT_STORAGE_UNAVAILABLE")
    except httpx.HTTPError:
        record_failure("SOURCE_UNAVAILABLE")
    except PersistenceError as exc:
        if exc.code not in {
            "SOURCE_UNAVAILABLE", "SOURCE_CHECKSUM_MISMATCH", "SOURCE_CONTENT_INVALID", "RESOURCE_LIMIT",
        }:
            raise
        record_failure(exc.code)


def project(
    store: Store, blobs: ContentAddressedStore, settings: Settings, workspace_id: str, run_id: str,
) -> dict[str, Any]:
    """Authorized stored-only projection. A private blob hash alone grants no access."""
    with store.transaction(workspace_id) as tx:
        run = tx.require("runs", run_id)
        pointer = run.get("runtime", {}).get(KEY)
        if pointer is None:
            reason = eligibility(settings, run["mode"])
            attempt = run.get("runtime", {}).get(ATTEMPT)
            return {"schema_version": "environment.v1", "run_id": run["id"], "mode": run["mode"],
                    "status": "UNKNOWN", "reason_code": reason or (attempt or {}).get("reason_code", "NOT_CAPTURED"),
                    "earth_candidates": [], "nasa_reference": None, "qualification_supported": False,
                    "operating_limits": [], "limitations": LIMITATIONS, "snapshot_sha256": None}
        mission = tx.require("mission_revisions", run["mission_revision_id"])
        try:
            candidates = _candidate_rows(tx, run)
        except (ValueError, NotFound) as exc:
            raise ApiError("SOURCE_CONTENT_INVALID", "Stored environment context could not be verified.", 409) from exc
    try:
        raw = blobs.read_limited(pointer["sha256"], MAX_SNAPSHOT_BYTES)
        snapshot = json.loads(raw)
        actual = _scope(run, mission, candidates)
        candidate_scope = snapshot["candidate_aoi_sha256"]
        if (snapshot["schema_version"] != "environment.v1" or snapshot["mode"] != "live"
                or any(snapshot[key] != actual[key] for key in actual if key != "candidate_aoi_sha256")
                or not isinstance(candidate_scope, dict) or not candidate_scope
                or any(actual["candidate_aoi_sha256"].get(cid) != digest for cid, digest in candidate_scope.items())
                or any(item["candidate_id"] not in candidate_scope for item in snapshot["earth_candidates"])
                or bytes_sha256(raw) != pointer["sha256"]):
            raise ValueError("Snapshot scope differs")
    except (ValueError, KeyError, TypeError, PersistenceError) as exc:
        raise ApiError("SOURCE_CONTENT_INVALID", "Stored environment context could not be verified.", 409) from exc
    return {**snapshot, "snapshot_sha256": pointer["sha256"]}
