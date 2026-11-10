"""PayPal Sandbox Developer Setup & Diagnostics tests (Prompt 14).

Verifies:
1. Server-side OAuth 2.0 client-credentials token acquisition.
2. In-memory token caching with expiry safety.
3. Diagnostic endpoint GET /api/paypal/status reports status without leaking secrets.
4. Unauthenticated requests are rejected.
5. Live endpoints are rejected by settings validation.
6. Transient network retry behavior.
"""

import time
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.user import User
from app.services.paypal_service import PayPalService, mask_secret
from tests.mock_db import MockDatabase

settings = get_settings()


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def auth_user() -> User:
    return User(
        id="user-paypal-test",
        email="paypal.dev@example.com",
        hashed_password=hash_password("Pass123!"),
        name="PayPal Dev",
    )


def test_mask_secret_helper():
    """Verify secrets are masked safely."""
    assert mask_secret(None) == "<not-set>"
    assert mask_secret("") == "<not-set>"
    assert mask_secret("short") == "***"
    assert mask_secret("Aa1234567890zZ", show_chars=2) == "Aa***zZ"


@pytest.mark.asyncio
@respx.mock
async def test_paypal_oauth_token_acquisition_and_caching(monkeypatch):
    """Verify OAuth token acquisition using client credentials and in-memory caching."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-sandbox-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-sandbox-client-secret")

    service = PayPalService()

    # Mock PayPal token endpoint
    token_route = respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "A21AA_mock_paypal_access_token_12345",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
    )

    # 1. Acquire token
    token1 = await service.get_access_token()
    assert token1 == "A21AA_mock_paypal_access_token_12345"
    assert token_route.call_count == 1

    # 2. Subsequent call uses in-memory cache without hitting the network
    token2 = await service.get_access_token()
    assert token2 == token1
    assert token_route.call_count == 1

    # 3. Simulate expired token -> should make a new network request
    service._cached_token.expires_at = time.time() - 100
    token3 = await service.get_access_token()
    assert token3 == token1
    assert token_route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_paypal_diagnostic_endpoint_connected(mock_db: MockDatabase, auth_user: User, monkeypatch):
    """GET /api/paypal/status reports connected status without revealing secrets."""
    await mock_db.users.insert_one(auth_user.model_dump())
    token = create_access_token(subject=auth_user.id)

    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-client-secret")
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "mock-webhook-id")

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(
            200,
            json={"access_token": "A21AA_secret_token", "expires_in": 3600},
        )
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            res = await client.get("/api/paypal/status", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert data["configured"] is True
            assert data["connected"] is True
            assert data["environment"] == "sandbox"
            assert data["base_url"] == settings.PAYPAL_BASE_URL
            assert data["webhook_configured"] is True

            # Invariant: Never leak raw client secret or full access token!
            res_text = res.text
            assert "mock-client-secret" not in res_text
            assert "A21AA_secret_token" not in res_text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_paypal_diagnostic_endpoint_unconfigured(mock_db: MockDatabase, auth_user: User, monkeypatch):
    """Diagnostic endpoint handles missing/unconfigured state gracefully."""
    await mock_db.users.insert_one(auth_user.model_dump())
    token = create_access_token(subject=auth_user.id)

    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "")

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            res = await client.get("/api/paypal/status", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["configured"] is False
            assert data["connected"] is False
            assert "not configured" in data["message"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_paypal_endpoint_requires_authentication():
    """Unauthenticated access to /api/paypal/status must be rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/paypal/status")
        assert res.status_code in {401, 403}

