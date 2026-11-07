"""Provider outages and hostile discovery documents never become unsafe redirects."""

import httpx
import pytest

from analogforge.adapters.identity.oidc import OIDCClient
from analogforge.db.store import PersistenceError


@pytest.mark.parametrize("kind", ["outage", "malformed", "array", "issuer", "foreign_endpoint"])
def test_discovery_failure_is_typed_and_contains_no_provider_body(kind):
    marker = "private-provider-error-body"

    def respond(request):
        if kind == "outage":
            return httpx.Response(503, text=marker)
        if kind == "malformed":
            return httpx.Response(200, text=marker)
        if kind == "array":
            return httpx.Response(200, json=[marker])
        return httpx.Response(
            200,
            json={
                "issuer": "https://other.example" if kind == "issuer" else "https://issuer.example",
                "authorization_endpoint": "https://attacker.example/auth",
                "token_endpoint": "https://issuer.example/token",
                "jwks_uri": "https://issuer.example/jwks",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        oidc = OIDCClient(
            None,
            issuer="https://issuer.example",
            client_id="test-client",
            redirect_uri="https://app.example/auth/callback",
            client=client,
        )
        with pytest.raises(PersistenceError) as caught:
            oidc.discovery()
    assert caught.value.code in {
        "IDENTITY_PROVIDER_UNAVAILABLE",
        "AUTHENTICATION_REQUIRED",
        "OIDC_CONFIGURATION_INVALID",
    }
    assert marker not in str(caught.value)
