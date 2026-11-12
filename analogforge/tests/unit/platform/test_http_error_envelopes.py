"""Safe, actionable scientific and identity errors at the real HTTP boundary."""

import httpx
from fastapi.testclient import TestClient

from analogforge.adapters.identity.oidc import OIDCClient
from analogforge.api.contracts import validate
from analogforge.application.assurance import ScientificClaimRejected
from analogforge.main import create_app
from analogforge.settings import Settings


def test_scientific_rejection_retains_gate_issue_codes():
    def identity(request):
        raise ScientificClaimRejected(["SC-01:FROZEN_INPUT_CHANGED", "SC-02:EVIDENCE_MISSING"])

    application = create_app(settings=Settings(_env_file=None), store=object(), identity_provider=identity)
    with TestClient(application) as client:
        response = client.get("/api/v1/missions")
    assert response.status_code == 422
    validate(response.json(), {"$ref": "#/components/schemas/ErrorEnvelope"})
    assert response.json()["error"]["details"]["issue_codes"] == [
        "SC-01:FROZEN_INPUT_CHANGED",
        "SC-02:EVIDENCE_MISSING",
    ]


def test_malformed_discovery_endpoint_returns_safe_http_error():
    settings = Settings(
        _env_file=None,
        auth_mode="oidc",
        session_secret="x" * 32,
        oidc_issuer_url="https://issuer.example",
        oidc_client_id="test-client",
        oidc_client_secret="x" * 32,
        public_base_url="https://app.example",
    )
    application = create_app(settings=settings, store=object())
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"issuer": "https://issuer.example", "authorization_endpoint": []})
        )
    ) as issuer:
        application.state.oidc_client = OIDCClient(
            object(),
            issuer=settings.oidc_issuer_url,
            client_id=settings.oidc_client_id,
            redirect_uri="https://app.example/auth/callback",
            client=issuer,
        )
        with TestClient(application) as client:
            response = client.get("/auth/login?workspace_id=11111111-1111-4111-8111-111111111111")
    assert response.status_code == 503
    validate(response.json(), {"$ref": "#/components/schemas/ErrorEnvelope"})
    assert response.json()["error"]["code"] == "OIDC_CONFIGURATION_INVALID"
