"""Registrar rejects corrupted bytes/references atomically with diagnostic receipts."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from analogforge.adapters.storage.cas import ContentAddressedStore
from analogforge.application.registrar import Registrar, RegistrationRejected
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import (
    EvidenceDraft,
    LocalScienceContext,
    ScienceComputationResult,
    ScienceOperation,
    ScienceRequest,
    SourcePolicy,
)
from analogforge.ports.science_payloads import (
    CharacterizeTargetInput,
    ResolveCoverageInput,
    ResolveCoveragePayload,
    SourceSelector,
)
from tests.support.factories import science_factory


class StoreDouble:
    def __init__(self, ws, run):
        self.data = {
            "runs": {
                run: {
                    "id": run,
                    "run_id": run,
                    "workspace_id": ws,
                    "mode": "synthetic",
                    "state": "CHARACTERIZING",
                    "revision": 1,
                }
            }
        }

    @contextmanager
    def transaction(self, ws):
        before = deepcopy(self.data)
        try:
            yield self
        except BaseException:
            self.data = before
            raise

    def get(self, kind, identifier):
        return self.data.get(kind, {}).get(identifier)

    def list(self, kind, filters=None):
        return [v for v in self.data.get(kind, {}).values() if all(v.get(k) == x for k, x in (filters or {}).items())]

    def create(self, kind, value):
        self.data.setdefault(kind, {})[value["id"]] = deepcopy(value)
        return value

    def append_event(self, *args):
        return {}


@pytest.fixture
def registration(tmp_path):
    ws, run, invocation = str(uuid4()), str(uuid4()), str(uuid4())
    store = StoreDouble(ws, run)
    root = Path(__file__).resolve().parents[3]
    import json

    mission = json.loads((root / "tests/fixtures/kit/missions/mission-mars-mobility.json").read_text())
    request = ScienceRequest(
        request_id=uuid4(),
        operation=ScienceOperation.CHARACTERIZE_TARGET,
        mode="synthetic",
        inputs=CharacterizeTargetInput(
            target=mission["target"],
            source=SourceSelector(kind="SYNTHETIC_FIXTURE", fixture_id="practice-mars-target-v1"),
            measurement_spec_id="terrain-target-v1",
            requested_dimensions=["TERRAIN"],
        ),
        source_policy=SourcePolicy(policy_id="p", policy_sha256=canonical_sha256({}), allow_network=False),
    )
    context = LocalScienceContext(scratch=tmp_path / "scratch", workspace_id=uuid4(), job_id=uuid4())
    result = science_factory().execute(request, context)
    registrar = Registrar(store, ContentAddressedStore(tmp_path / "cas"))
    kwargs = dict(
        scratch_dir=context.scratch,
        workspace_id=ws,
        run_id=run,
        invocation_id=invocation,
        tool_name="characterize_target",
    )
    return registrar, store, request, result, kwargs


def test_valid_registration_resolves_all_refs_and_lineage(registration):
    registrar, store, request, result, kwargs = registration
    registered = registrar.register(request, result, **kwargs)
    assert registered.payload["profile_evidence"]["local_key"] is None
    assert registered.payload["profile_evidence"]["evidence_id"] in registered.evidence_ids
    assert len(store.list("evidence")) == len(result.evidence_drafts)
    assert registered.receipt["input_sha256"] == canonical_sha256(request)


@pytest.fixture
def live_source_registration(tmp_path):
    ws, run, invocation = str(uuid4()), str(uuid4()), str(uuid4())
    store = StoreDouble(ws, run)
    store.data["runs"][run]["mode"] = "live"
    request = ScienceRequest(
        request_id=uuid4(), operation=ScienceOperation.RESOLVE_COVERAGE, mode="live",
        inputs=ResolveCoverageInput(
            subject_kind="TARGET", adapter_id="mars_mola_megdr", measurement_kinds=["terrain"],
            aoi={"body": "MARS", "bbox": [137, -5, 138, -4], "longitude_convention": "NEG180_180",
                 "latitude_type": "PLANETOCENTRIC", "crs_wkt": None, "vertical_datum": "Unknown"},
        ),
        source_policy=SourcePolicy(policy_id="p", policy_sha256="0" * 64, allow_network=False),
    )
    result = ScienceComputationResult(
        request_id=request.request_id, operation=request.operation, mode="live", status="SUCCEEDED",
        algorithm_id="resolve-coverage", algorithm_version="1.0", parameters_sha256="0" * 64,
        input_sha256=canonical_sha256(request), payload=ResolveCoveragePayload(selections=[]),
        evidence_drafts=[EvidenceDraft(
            local_key="source", kind="SOURCE", body="MARS", license_note="Test source-origin boundary",
            algorithm_id="resolve-coverage", algorithm_version="1.0", parameters_sha256="0" * 64,
            dataset_product_id="MGS-M-MOLA-5-MEGDR-L3-V1.0",
            source_uri="https://pds-geosciences.wustl.edu/mgs/meg128/megt00n090hb.img",
        )],
    )
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    registrar = Registrar(store, ContentAddressedStore(tmp_path / "cas"))
    kwargs = dict(scratch_dir=scratch, workspace_id=ws, run_id=run, invocation_id=invocation,
                  tool_name="resolve_source_coverage")
    return registrar, store, request, result, kwargs


def test_live_source_accepts_the_registered_pds_geosciences_host(live_source_registration):
    registrar, store, request, result, kwargs = live_source_registration
    registered = registrar.register(request, result, **kwargs)
    assert registered.receipt["status"] == "SUCCEEDED"
    assert store.list("evidence")[0]["source_uri"] == result.evidence_drafts[0].source_uri


@pytest.fixture
def live_earth_source_registration(live_source_registration):
    registrar, store, request, result, kwargs = live_source_registration
    inputs = ResolveCoverageInput(
        subject_kind="CANDIDATE", adapter_id="earth_nasadem_hgt_v001", measurement_kinds=["terrain"],
        aoi={"body": "EARTH", "bbox": [-112, 35, -111, 36], "longitude_convention": "NEG180_180",
             "latitude_type": "GEODETIC", "crs_wkt": None, "vertical_datum": "EGM96"},
    )
    request = request.model_copy(update={"inputs": inputs})
    source = result.evidence_drafts[0].model_copy(update={
        "body": "EARTH", "dataset_product_id": "NASADEM_HGT", "dataset_version": "001",
        "source_uri": "https://nasademeuwest.blob.core.windows.net/nasadem-cog/v001/NASADEM_HGT_n35w112.tif",
        "license_note": "NASA LP DAAC product; Microsoft Planetary Computer hosting. Preserve source notices.",
    })
    result = result.model_copy(update={"input_sha256": canonical_sha256(request), "evidence_drafts": [source]})
    return registrar, store, request, result, kwargs


def test_live_nasadem_origin_preserves_product_and_host_attribution(live_earth_source_registration):
    registrar, store, request, result, kwargs = live_earth_source_registration
    registered = registrar.register(request, result, **kwargs)
    assert registered.receipt["status"] == "SUCCEEDED"
    source = store.list("evidence")[0]
    assert source["source_uri"] == result.evidence_drafts[0].source_uri
    assert source["dataset_product_id"] == "NASADEM_HGT"
    assert source["dataset_version"] == "001"
    assert source["license_note"] == result.evidence_drafts[0].license_note


@pytest.mark.parametrize("source_uri", [
    "https://anotheraccount.blob.core.windows.net/nasadem-cog/data.tif",
    "https://unregistered.nasademeuwest.blob.core.windows.net/nasadem-cog/data.tif",
    "https://nasademeuwest.blob.core.windows.net.evil.test/nasadem-cog/data.tif",
    "https://evil-nasademeuwest.blob.core.windows.net/nasadem-cog/data.tif",
    "https://planetarycomputer.microsoft.com/api/data",
    "https://nasademeuwest.blob.core.windows.net/nasadem-cog/data.tif?sv=2024-01-01&sig=private",
    "https://nasademeuwest.blob.core.windows.net/nasadem-cog/data.tif#private",
    "https://user:password@nasademeuwest.blob.core.windows.net/nasadem-cog/data.tif",
    "http://nasademeuwest.blob.core.windows.net/nasadem-cog/data.tif",
])
def test_live_nasadem_origin_keeps_host_and_private_url_guards(live_earth_source_registration, source_uri):
    registrar, store, request, result, kwargs = live_earth_source_registration
    source = result.evidence_drafts[0].model_copy(update={"source_uri": source_uri})
    result = result.model_copy(update={"evidence_drafts": [source]})
    with pytest.raises(RegistrationRejected):
        registrar.register(request, result, **kwargs)
    assert store.list("evidence") == []
    assert store.list("artifacts") == []
    assert store.list("tool_receipts")[-1]["status"] == "FAILED"
    assert (kwargs["scratch_dir"].parent / "quarantine" / str(request.request_id)).exists()


@pytest.mark.parametrize("source_uri", [
    "https://other.wustl.edu/mgs/data.img",
    "https://unregistered.pds-geosciences.wustl.edu/mgs/data.img",
    "https://pds-geosciences.wustl.edu.evil.test/mgs/data.img",
    "https://evil-pds-geosciences.wustl.edu/mgs/data.img",
    "https://pds-geosciences.wustl.edu/mgs/data.img?token=private",
    "https://pds-geosciences.wustl.edu/mgs/data.img#private",
    "https://user:password@pds-geosciences.wustl.edu/mgs/data.img",
    "http://pds-geosciences.wustl.edu/mgs/data.img",
])
def test_live_pds_origin_keeps_host_and_private_url_guards(live_source_registration, source_uri):
    registrar, store, request, result, kwargs = live_source_registration
    source = result.evidence_drafts[0].model_copy(update={"source_uri": source_uri})
    result = result.model_copy(update={"evidence_drafts": [source]})
    with pytest.raises(RegistrationRejected):
        registrar.register(request, result, **kwargs)
    assert store.list("evidence") == []
    assert store.list("artifacts") == []
    assert store.list("tool_receipts")[-1]["status"] == "FAILED"
    assert (kwargs["scratch_dir"].parent / "quarantine" / str(request.request_id)).exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "hash",
        "size",
        "request",
        "input",
        "dangling",
        "cycle",
        "signed_url",
        "synthetic_name",
        "mode",
        "symlink",
        "media",
        "malformed_url",
    ],
)
def test_rejections_do_not_publish_domain_or_evidence(registration, mutation):
    registrar, store, request, result, kwargs = registration
    raw = result.model_dump(mode="json")
    if mutation == "malformed_url":
        raw["evidence_drafts"][0]["source_uri"] = "https://[bad"
    elif mutation == "hash":
        raw["artifacts"][0]["sha256"] = "0" * 64
    elif mutation == "size":
        raw["artifacts"][0]["size_bytes"] += 1
    elif mutation == "request":
        raw["request_id"] = str(uuid4())
    elif mutation == "input":
        raw["input_sha256"] = "0" * 64
    elif mutation == "dangling":
        raw["payload"]["profile_evidence"]["local_key"] = "no-such-key"
    elif mutation == "cycle":
        raw["evidence_drafts"][0]["parent_local_keys"] = [raw["evidence_drafts"][0]["local_key"]]
    elif mutation == "signed_url":
        raw["evidence_drafts"][0]["source_uri"] = "https://data.test/file?token=secret"
    elif mutation == "synthetic_name":
        raw["evidence_drafts"][0]["dataset_product_id"] = "NASA_REAL"
    elif mutation == "mode":
        raw["mode"] = "live"
    elif mutation == "media":
        raw["artifacts"][0]["media_type"] = "text/html"
    elif mutation == "symlink":
        artifact = kwargs["scratch_dir"] / raw["artifacts"][0]["scratch_relpath"]
        real = artifact.with_suffix(".original")
        artifact.rename(real)
        artifact.symlink_to(real)
    with pytest.raises(RegistrationRejected):
        registrar.register(request, raw, **kwargs)
    assert store.list("evidence") == []
    assert store.list("artifacts") == []
    assert store.list("tool_receipts")[-1]["status"] == "FAILED"
    assert (kwargs["scratch_dir"].parent / "quarantine" / str(request.request_id)).exists()
