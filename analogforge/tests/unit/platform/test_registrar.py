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
from analogforge.ports.science import LocalScienceContext, ScienceOperation, ScienceRequest, SourcePolicy
from analogforge.ports.science_payloads import CharacterizeTargetInput, SourceSelector
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
    ],
)
def test_rejections_do_not_publish_domain_or_evidence(registration, mutation):
    registrar, store, request, result, kwargs = registration
    raw = result.model_dump(mode="json")
    if mutation == "hash":
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
