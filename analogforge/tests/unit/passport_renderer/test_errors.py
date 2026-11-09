from uuid import UUID

import pytest

from analogforge.ports.passport_renderer import RendererError
from analogforge.rendering.passport import create_passport_renderer
from passport_renderer.fixtures.builders import build_bundle


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("candidate", "UNRESOLVED_REFERENCE"),
        ("evidence", "UNRESOLVED_REFERENCE"),
        ("attempt-candidate", "UNRESOLVED_REFERENCE"),
        ("requirement", "REQUIREMENT_UNKNOWN"),
        ("digest", "MANIFEST_DIGEST_MISMATCH"),
        ("blocked", "BLOCKED_AUDIT"),
        ("attempt", "INCONSISTENT_ATTEMPT"),
    ],
)
def test_errors(kind, expected):
    bundle = build_bundle()
    if kind == "candidate":
        bundle.qualifications[0].candidate_id = UUID(int=999)
    elif kind == "evidence":
        bundle.passport.evidence_ids.append(UUID(int=999))
    elif kind == "attempt-candidate":
        bundle.attempts[0] = bundle.attempts[0].model_copy(update={"candidate_id": UUID(int=999)})
    elif kind == "requirement":
        bundle.qualifications[0].requirement_id = "NO-SUCH-REQUIREMENT"
    elif kind == "digest":
        bundle = bundle.model_copy(update={"canonical_manifest_json": "{}"})
    elif kind == "blocked":
        bundle.assurance.publication = "BLOCKED"
    elif kind == "attempt":
        bundle.attempts[0].result.failure_category = None
    with pytest.raises(RendererError) as error:
        create_passport_renderer().render(bundle, [], "html")
    assert error.value.code == expected


def test_draft_has_no_assurance_requirement():
    bundle = build_bundle("draft")
    assert b"DRAFT" in create_passport_renderer().render(bundle, [], "html").content


@pytest.mark.parametrize("manifest", [' {"hello": 1} ', "{broken", '{"value":NaN}'])
def test_manifest_must_be_valid_canonical_json(manifest):
    import hashlib

    bundle = build_bundle()
    digest = hashlib.sha256(manifest.encode()).hexdigest()
    bundle = bundle.model_copy(update={"canonical_manifest_json": manifest, "manifest_sha256": digest})
    bundle.passport.manifest_sha256 = digest
    with pytest.raises(RendererError) as error:
        create_passport_renderer().render(bundle, [], "json")
    assert error.value.code == "MANIFEST_DIGEST_MISMATCH"


def test_qualification_cannot_print_unresolved_evidence_reference():
    bundle = build_bundle()
    bundle.qualifications[0].evidence_ids = [UUID(int=999)]
    with pytest.raises(RendererError) as error:
        create_passport_renderer().render(bundle, [], "html")
    assert error.value.code == "UNRESOLVED_REFERENCE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", UUID(int=999)),
        ("workspace_id", UUID(int=999)),
        ("mode", "live"),
        ("mission_content_sha256", "f" * 64),
        ("rover_content_sha256", "f" * 64),
        ("dataset_policy_sha256", "f" * 64),
        ("acquired_manifest_sha256", "f" * 64),
        ("algorithm_lock_sha256", "f" * 64),
    ],
)
def test_stale_or_wrong_context_assurance_is_refused(field, value):
    bundle = build_bundle()
    setattr(bundle.assurance, field, value)
    with pytest.raises(RendererError) as error:
        create_passport_renderer().render(bundle, [], "html")
    assert error.value.code == "STALE_AUDIT"
