"""``RESOLVE_COVERAGE`` and ``FETCH_SOURCE`` (guide 08 sections 4.2 and 4.3)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from analogforge.adapters.source_http.errors import AdapterError
from analogforge.adapters.source_http.geo import Box, coverage_fraction, split_bbox
from analogforge.ports.common import EvidenceRef
from analogforge.ports.domain_models import AreaOfInterest
from analogforge.ports.hashing import bytes_sha256
from analogforge.ports.science import ArtifactDraft, ArtifactRole, ComputationStatus
from analogforge.ports.science_payloads import (
    CoverageSelection,
    FetchSourceInput,
    FetchSourcePayload,
    ResolveCoverageInput,
    ResolveCoveragePayload,
)
from analogforge.science.datasets.ingest import DatasetUnreadableError, ingest_local_dataset
from analogforge.science.geometry import split_bbox_at_antimeridian
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.ops.source import _fixture_root, read_manifest

NETWORK_ADAPTERS = {
    "earth_nasadem_hgt_v001": "analogforge.adapters.earthdata",
    "earth_srtmgl1_v003": "analogforge.adapters.earthdata",
    "mars_mola_megdr": "analogforge.adapters.pds",
    "moon_lola_gdr": "analogforge.adapters.pds",
    "earth_emit_l2bmin_v001": "analogforge.adapters.emit",
    "moon_diviner_derived": "analogforge.adapters.diviner",
    "earth_user_survey": "analogforge.adapters.user_survey",
}
PRACTICE_FIXTURES = (
    "practice-mars-target-v1",
    "practice-moon-target-v1",
    "practice-moon-thermal-v1",
    "practice-earth-grid-v1",
    "practice-earth-minerals-v1",
)


def _overlap_fraction(aoi: list[float], other: tuple[float, float, float, float], convention: str) -> float:
    """Planar-degree overlap of ``other`` with the AOI as a fraction of the AOI area (wrap-aware)."""
    a_pieces = split_bbox_at_antimeridian(tuple(aoi), convention)  # type: ignore[arg-type]
    b_pieces = split_bbox_at_antimeridian(other, convention)  # type: ignore[arg-type]
    total = sum((p[2] - p[0]) * (p[3] - p[1]) for p in a_pieces)
    if total <= 0.0:
        return 0.0
    inter = 0.0
    for a in a_pieces:
        for b in b_pieces:
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            if w > 0 and h > 0:
                inter += w * h
    return min(1.0, inter / total)


def _aoi_pieces(aoi: AreaOfInterest) -> list[Box]:
    """The AOI as boxes in the -180..180 domain; a malformed AOI (zero width, off-globe latitude) is BLOCKED."""
    try:
        return split_bbox(aoi.bbox, aoi.longitude_convention, "NEG180_180")
    except AdapterError as exc:
        raise OpBlocked(f"invalid AOI: {exc.message}", code="INPUT_INVALID", detail_code="AOI_INVALID") from exc


def _extent_pieces(bbox: tuple[float, float, float, float]) -> list[Box]:
    convention = "ZERO_360" if max(bbox[0], bbox[2]) > 180.0 else "NEG180_180"
    try:
        return split_bbox(bbox, convention, "NEG180_180")
    except AdapterError:
        return []  # an invalid extent authorizes nothing


def enforce_source_policy(env: OpEnv, adapter_id: str, aoi: AreaOfInterest) -> None:
    """Refuse before any request is made: mode, network permission, adapter allow-list and allowed extents.

    * ``synthetic_practice`` exists only in synthetic mode (never presented as live or replay data).
    * A network adapter needs ``allow_network`` and an explicit ``allowed_adapter_ids`` entry (outside live mode the
      caller's own mode block applies first).
    * A non-empty ``allowed_adapter_ids`` restricts local adapters as well (an empty one restricts nothing there:
      local sources are authorized by ``local_dataset_ids`` / ``synthetic_fixture_ids``).
    * A non-empty ``allowed_extents`` must contain the whole AOI (same body, planar-degree union).
    """
    policy = env.request.source_policy
    if adapter_id == "synthetic_practice" and env.request.mode != "synthetic":
        raise OpBlocked(
            "synthetic practice data is only available in synthetic mode",
            code="UNSUPPORTED_PRODUCT",
            detail_code="MODE_MISMATCH",
        )
    network = adapter_id in NETWORK_ADAPTERS
    if network and env.request.mode != "live":
        return  # the caller blocks network adapters outside live mode (NETWORK_UNAVAILABLE / FETCH_NOT_AVAILABLE)
    if network and not policy.allow_network:
        raise OpBlocked(f"the source policy does not allow network access ({adapter_id})", detail_code="POLICY_DENIED")
    if (network or policy.allowed_adapter_ids) and adapter_id not in policy.allowed_adapter_ids:
        raise OpBlocked(f"adapter {adapter_id} is not authorized by the source policy", detail_code="POLICY_DENIED")
    pieces = _aoi_pieces(aoi)
    if policy.allowed_extents:
        permitted = [b for e in policy.allowed_extents if e.body == aoi.body for b in _extent_pieces(e.bbox)]
        if coverage_fraction(pieces, permitted) < 1.0 - 1e-9:
            raise OpBlocked("the AOI is not inside the source policy's allowed extents", detail_code="POLICY_DENIED")


def _roles(inp: ResolveCoverageInput) -> tuple[str, ...]:
    kinds = {k.upper() for k in inp.measurement_kinds}
    if inp.subject_kind == "TARGET":
        return ("TARGET_TERRAIN", "LUNAR_THERMAL") if "THERMAL" in kinds else ("TARGET_TERRAIN",)
    return ("EARTH_TERRAIN", "EARTH_MINERAL") if "MINERAL" in kinds or "SCIENCE" in kinds else ("EARTH_TERRAIN",)


def run_resolve_coverage(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, ResolveCoverageInput)
    algo = "resolve-coverage"
    enforce_source_policy(env, inp.adapter_id, inp.aoi)
    if inp.adapter_id in NETWORK_ADAPTERS:
        if env.request.mode != "live" or env.context.http_client() is None:
            raise OpBlocked(
                "network adapters are unavailable in this mode",
                code="UNSUPPORTED_PRODUCT",
                detail_code="NETWORK_UNAVAILABLE",
            )
        module = importlib.import_module(NETWORK_ADAPTERS[inp.adapter_id])
        try:
            selections: list[CoverageSelection] = module.discover(inp, env.context.http_client())
        except AdapterError as exc:
            raise OpBlocked(exc.message, code=exc.code, detail_code=exc.detail_code, retryable=exc.retryable) from exc
    elif inp.adapter_id in ("local_dataset", "synthetic_practice"):
        selections = _local_selections(env, inp)
    else:
        raise OpBlocked(
            f"unknown adapter {inp.adapter_id!r}", code="UNSUPPORTED_PRODUCT", detail_code="ADAPTER_UNKNOWN"
        )
    selections = sorted(selections, key=lambda s: s.selection_key)
    available = [s for s in selections if s.access_state == "AVAILABLE"]
    gaps = [] if available else [f"no coverage for {','.join(inp.measurement_kinds) or 'terrain'}"]
    payload = ResolveCoveragePayload(selections=selections, gaps=gaps)
    params = env.params_hash(algo, env.operation_params())
    art = json_artifact(env, params_sha=params, key="coverage-json", name="coverage.json", payload=payload)
    ev = derived_evidence(
        env,
        key="coverage",
        kind="DERIVED",
        body=inp.aoi.body,
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        limitations=["coverage_fraction is planar-degree footprint overlap, not valid-pixel coverage."],
    )
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art], [ev])


def _local_selections(env: OpEnv, inp: ResolveCoverageInput) -> list[CoverageSelection]:
    roots: dict[str, Path] = {}
    if inp.adapter_id == "local_dataset":
        for dataset_id in env.request.source_policy.local_dataset_ids:
            try:
                roots[dataset_id] = env.context.local_dataset_root(dataset_id)
            except KeyError:
                continue
    else:
        allowed = env.request.source_policy.synthetic_fixture_ids or list(PRACTICE_FIXTURES)
        for fixture_id in allowed:
            if fixture_id in PRACTICE_FIXTURES:
                roots[fixture_id] = _fixture_root(env, fixture_id)
    wanted = _roles(inp)
    out: list[CoverageSelection] = []
    for dataset_id in sorted(roots):
        env.check()
        raw: dict[str, Any] = read_manifest(roots[dataset_id])
        if raw.get("body") != inp.aoi.body or raw.get("role") not in wanted:
            continue
        try:
            res = ingest_local_dataset(roots[dataset_id], raw, env.scratch, check_cancelled=env.check)
        except DatasetUnreadableError:
            continue
        if res.payload is None or res.payload.bbox_lonlat is None or not res.usable_for_quantitative_claims:
            out.append(
                CoverageSelection(
                    selection_key=f"{inp.adapter_id}:{dataset_id}",
                    adapter_id=inp.adapter_id,
                    product_id=res.product_id,
                    version=None,
                    access_state="UNSUPPORTED",
                    coverage_fraction=None,
                    notes=[f"dataset failed validation: {list(res.failed)}"],
                )
            )
            continue
        frac = _overlap_fraction(inp.aoi.bbox, res.payload.bbox_lonlat, inp.aoi.longitude_convention)
        out.append(
            CoverageSelection(
                selection_key=f"{inp.adapter_id}:{dataset_id}",
                adapter_id=inp.adapter_id,
                product_id=res.product_id,
                version=res.manifest.product_identity.version if res.manifest else None,
                access_state="AVAILABLE" if frac > 0 else "NO_COVERAGE",
                coverage_fraction=frac,
                native_resolution_m=res.payload.native_resolution_m,
                notes=[f"role={res.payload.role}", "coverage_fraction is planar-degree footprint overlap"],
            )
        )
    return out


def run_fetch_source(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, FetchSourceInput)
    algo = "fetch-source"
    sel = inp.selection
    enforce_source_policy(env, sel.adapter_id, inp.aoi)
    client = env.context.http_client()
    if env.request.mode != "live" or client is None or sel.adapter_id not in NETWORK_ADAPTERS:
        raise OpBlocked(
            "FETCH_SOURCE needs live mode, an injected HTTP client and a network adapter",
            code="UNSUPPORTED_PRODUCT",
            detail_code="FETCH_NOT_AVAILABLE",
        )
    module = importlib.import_module(NETWORK_ADAPTERS[sel.adapter_id])
    try:
        assets = module.fetch(sel, client, env.scratch)
    except AdapterError as exc:
        raise OpBlocked(exc.message, code=exc.code, detail_code=exc.detail_code, retryable=exc.retryable) from exc
    artifacts: list[ArtifactDraft] = []
    evidence = []
    refs: list[EvidenceRef] = []
    params = env.params_hash(algo, env.operation_params())
    for i, asset in enumerate(sorted(assets, key=lambda a: a.source_uri)):
        env.check()
        path = module.asset_path(env.scratch, asset)
        data = Path(path).read_bytes()
        rel = str(Path(path).resolve().relative_to(env.scratch.resolve()))
        art = ArtifactDraft(
            local_key=asset.artifact_key,
            scratch_relpath=rel,
            sha256=bytes_sha256(data),
            size_bytes=len(data),
            media_type="application/octet-stream",
            role=ArtifactRole.SOURCE_BYTES,
            body=inp.aoi.body,
        )
        artifacts.append(art)
        key = f"source-{i}"
        evidence.append(
            derived_evidence(
                env,
                key=key,
                kind="SOURCE",
                body=inp.aoi.body,
                algorithm_id=algo,
                params_sha=params,
                artifact=art,
                dataset_product_id=asset.product_id,
                dataset_version=asset.version,
                license_note="Provider terms apply; see the product citation.",
            ).model_copy(update={"source_uri": asset.source_uri, "granule_id": asset.granule_id})
        )
        refs.append(EvidenceRef(local_key=key))
    payload = FetchSourcePayload(source_evidence=refs, acquired_assets=assets)
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, artifacts, evidence)
