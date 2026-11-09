import re

from analogforge.rendering.passport import create_passport_renderer
from passport_renderer.fixtures.builders import build_bundle


def test_complete_and_safe(bundle):
    text = create_passport_renderer().render(bundle, [], "html").content.decode()
    for section in (
        "cover",
        "mission-contract",
        "target-and-sites",
        "qualification",
        "compatibility",
        "prove-it",
        "portfolio",
        "critic-limitations",
        "assurance",
        "next-steps",
        "provenance",
    ):
        assert f'id="{section}"' in text
    for requirement in bundle.mission.requirements:
        assert requirement.id in text
    for attempt in bundle.attempts:
        assert f'data-attempt-number="{attempt.attempt_number}"' in text
        assert str(attempt.test.id) in text
        assert attempt.result.outcome in text
    assert bundle.manifest_sha256 in text
    assert bundle.generated_at in text
    assert bundle.mode.upper() in text
    assert "Unknown" in text
    assert "GAP" in text and "UNKNOWN" in text
    assert "Modeled terrain-feasibility verification" in text
    assert not re.search(r"<script|(?:src|href)=[\"']https?://|url\(", text, re.I)
    if bundle.is_draft:
        assert "DRAFT — INCOMPLETE" in text
    if bundle.assurance:
        for claim in bundle.assurance.claims:
            assert claim.permitted_statement in text


def test_cover_headlines():
    renderer = create_passport_renderer()
    cases = [
        ("positive", "Qualified for these tests under these assumptions:"),
        ("supported-negative", "No supported recommendation under the accepted contract"),
        ("limited", "No rover supplied — site qualification only"),
        ("draft", "Not verified"),
    ]
    for name, headline in cases:
        text = renderer.render(build_bundle(name), [], "html").content.decode()
        assert headline in text
    negative = renderer.render(build_bundle("supported-negative"), [], "html").content.decode()
    assert "Qualified for these tests under these assumptions:" not in negative


def test_perturbed_content_is_preserved():
    bundle = build_bundle()
    bundle.attempts[0] = bundle.attempts[0].model_copy(update={"diagnosis_explanation": "A distinct updated diagnosis"})
    bundle.mission.requirements[0].label = "Changed requirement label"
    text = create_passport_renderer().render(bundle, [], "html").content.decode()
    assert "A distinct updated diagnosis" in text and "Changed requirement label" in text


def test_embedded_template_matches_reviewable_source():
    from pathlib import Path

    from analogforge.rendering.passport.html import CSS, TEMPLATE

    root = Path(__file__).parents[3] / "src/analogforge/rendering/passport/templates"
    assert (root / "passport.html.j2").read_text() == TEMPLATE
    assert (root / "passport.css").read_text() == CSS
