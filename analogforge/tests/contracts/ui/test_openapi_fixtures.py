"""Independent Python validation of observed mock responses exported by Vitest."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]


def test_observed_mock_responses_match_bundled_openapi():
    spec = json.loads((ROOT / "contracts/openapi.bundled.json").read_text())
    fixtures = json.loads((ROOT / "apps/web/src/mock/fixtures/validated-responses.json").read_text())
    covered = set()
    for fixture in fixtures:
        method = fixture["method"].lower()
        path = fixture["path"]
        covered.add((method, path))
        response = spec["paths"][path][method]["responses"][str(fixture["status"])]
        schema = response.get("content", {}).get("application/json", {}).get("schema")
        if schema is not None and not isinstance(fixture["body"], str):
            root = {"components": spec["components"], **schema}
            Draft202012Validator(root).validate(fixture["body"])
    expected = {
        (method, path)
        for path, ops in spec["paths"].items()
        for method in ops
        if method in ("get", "post") and not path.endswith("/events")
    }
    assert covered == expected


def test_ui_readable_mock_artifacts_match_frozen_payload_models():
    from analogforge.ports.domain_models import CritiqueIssue
    from analogforge.ports.science_payloads import (
        AnalyzeCandidatePayload,
        CharacterizeTargetPayload,
        CompareRequirementPayload,
        ConstraintsArtifact,
        DesignBenchmarkPayload,
        DiagnoseResultPayload,
        RouteArtifact,
        ScreenCandidatesPayload,
        SearchRoutePayload,
        TelemetryArtifact,
        VerifyRoutePayload,
    )

    cases = json.loads((ROOT / "apps/web/src/mock/fixtures/scenario-artifacts.json").read_text())
    artifacts = {key: value for case in cases.values() for key, value in case.items()}
    models = {
        "CHARACTERIZE_TARGET": CharacterizeTargetPayload,
        "SCREEN_CANDIDATES": ScreenCandidatesPayload,
        "ANALYZE_CANDIDATE": AnalyzeCandidatePayload,
        "COMPARE_REQUIREMENT": CompareRequirementPayload,
        "VERIFY_ROUTE": VerifyRoutePayload,
        "DESIGN_BENCHMARK": DesignBenchmarkPayload,
        "SEARCH_ROUTE": SearchRoutePayload,
        "DIAGNOSE_RESULT": DiagnoseResultPayload,
    }
    observed = set()
    for payload in artifacts.values():
        if "operation" in payload:
            model = models[payload["operation"]]
            model.model_validate(payload)
            observed.add(payload["operation"])
        elif "artifact_kind" in payload:
            ConstraintsArtifact.model_validate(payload)
            observed.add("CONSTRAINTS")
        elif "route_key" in payload:
            RouteArtifact.model_validate(payload)
            observed.add("ROUTE")
        elif "samples" in payload:
            TelemetryArtifact.model_validate(payload)
            observed.add("TELEMETRY")
        elif "issue_id" in payload:
            CritiqueIssue.model_validate(payload)
            observed.add("CRITIQUE")
    assert observed == {*models, "TELEMETRY", "CRITIQUE", "CONSTRAINTS", "ROUTE"}


def test_artifact_content_hashes_are_independently_canonical_and_images_preserve_masks():
    import base64
    import hashlib
    import struct
    import zlib

    import rfc8785

    artifacts = json.loads((ROOT / "apps/web/src/mock/fixtures/runtime-artifacts.json").read_text())
    for expected, payload in artifacts.items():
        if "mockImage" in payload:
            image = payload["mockImage"]
            content = base64.b64decode(image["contentBase64"])
            assert hashlib.sha256(content).hexdigest() == expected
            assert content.startswith(b"\x89PNG\r\n\x1a\n")
            offset = 8
            compressed = b""
            while offset < len(content):
                length = struct.unpack("!I", content[offset : offset + 4])[0]
                kind = content[offset + 4 : offset + 8]
                data = content[offset + 8 : offset + 8 + length]
                if kind == b"IDAT":
                    compressed += data
                offset += length + 12
            rows = zlib.decompress(compressed)
            transparent = sum(rows[y * 257 + 1 + x * 4 + 3] == 0 for y in range(64) for x in range(64))
            assert transparent == image["mask"]["transparent_pixel_count"]
            assert transparent > 0
        else:
            assert hashlib.sha256(rfc8785.dumps(payload)).hexdigest() == expected


def test_display_frames_are_valid_body_specific_crs_and_affines_match_earth_corners():
    from pyproj import CRS, Transformer

    fixtures = json.loads((ROOT / "apps/web/src/mock/fixtures/display-assets.json").read_text())
    for fixture in fixtures["layers"].values():
        crs = CRS.from_user_input(fixture["display_crs_wkt"])
        assert crs.is_projected
        if fixture["body"] == "EARTH":
            inverse = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
            a, b, c, d, e, f = fixture["pixel_to_world"]
            for pixel, expected in zip([(0, 0), (64, 0), (64, 64), (0, 64)], fixture["earth_corners"], strict=True):
                x, y = pixel
                lon, lat = inverse.transform(a + b * x + c * y, d + e * x + f * y)
                assert abs(lon - expected[0]) < 1e-8
                assert abs(lat - expected[1]) < 1e-8
        else:
            assert fixture["body"].lower() in crs.name.lower()
            assert fixture["earth_corners"] is None
            assert crs.ellipsoid.semi_major_metre == (3396190 if fixture["body"] == "MARS" else 1737400)
